//
//  BugReportCollector.swift
//  DopetracksApp
//
//  Collects recent logs into a zip for bug reports.
//

import Foundation

struct BugReportResult: Identifiable {
    let id = UUID()
    let zipURL: URL
}

@MainActor
final class BugReportCollector: ObservableObject {
    @Published var isCollecting = false
    @Published var status: String?
    @Published var errorMessage: String?
    @Published var zipURL: URL?
    
    func collect() async {
        guard !isCollecting else { return }
        isCollecting = true
        status = "Collecting last 10 minutes of logs…"
        errorMessage = nil
        zipURL = nil
        
        do {
            let url = try await Task.detached(priority: .userInitiated) {
                try BugReportCollector.collectReport()
            }.value
            zipURL = url
            status = "Bug report saved."
        } catch {
            errorMessage = error.localizedDescription
            status = nil
        }
        isCollecting = false
    }
    
    // MARK: - Private helpers (run off the main thread)
    nonisolated private static func collectReport() throws -> URL {
        let fm = FileManager.default
        let baseDir = fm.homeDirectoryForCurrentUser
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("Dopetracks")
            .appendingPathComponent("BugReports")
        
        let timestamp = BugReportCollector.timestamp()
        let reportDir = baseDir.appendingPathComponent("BugReport_\(timestamp)")
        try fm.createDirectory(at: reportDir, withIntermediateDirectories: true)
        
        let oslogURL = reportDir.appendingPathComponent("oslog.json")
        let backendTailURL = reportDir.appendingPathComponent("backend.log.tail.txt")
        let metaURL = reportDir.appendingPathComponent("meta.txt")
        
        try dumpOSLog(to: oslogURL)
        try dumpBackendTail(to: backendTailURL)
        try writeMeta(to: metaURL)
        
        let zipURL = try zipReport(at: reportDir)
        return zipURL
    }
    
    nonisolated private static func dumpOSLog(to url: URL) throws {
        let fm = FileManager.default
        fm.createFile(atPath: url.path, contents: nil)
        let outHandle = try FileHandle(forWritingTo: url)
        let errPipe = Pipe()
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/log")
        process.arguments = [
            "show",
            "--style", "json",
            "--last", "10m",
            "--predicate", #"subsystem == "com.dopetracks.app""#
        ]
        process.standardOutput = outHandle
        process.standardError = errPipe
        
        try process.run()
        process.waitUntilExit()
        try outHandle.close()
        
        if process.terminationStatus != 0 {
            let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
            let errMsg = String(data: errData, encoding: .utf8) ?? "Unknown error"
            throw NSError(domain: "BugReportCollector", code: Int(process.terminationStatus), userInfo: [
                NSLocalizedDescriptionKey: "Failed to read system logs: \(errMsg)"
            ])
        }
    }
    
    nonisolated private static func dumpBackendTail(to url: URL) throws {
        let backendLog = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library")
            .appendingPathComponent("Logs")
            .appendingPathComponent("Dopetracks")
            .appendingPathComponent("backend.log")
        
        guard FileManager.default.fileExists(atPath: backendLog.path) else {
            try "backend.log not found\n".write(to: url, atomically: true, encoding: .utf8)
            return
        }
        
        let contents = try String(contentsOf: backendLog, encoding: .utf8)
        let lines = contents.split(separator: "\n", omittingEmptySubsequences: false)
        let tail = lines.suffix(400).joined(separator: "\n")
        try tail.write(to: url, atomically: true, encoding: .utf8)
    }
    
    nonisolated private static func writeMeta(to url: URL) throws {
        let os = ProcessInfo.processInfo.operatingSystemVersionString
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let now = formatter.string(from: Date())
        let body = """
        Created: \(now)
        OS: \(os)
        App: DopetracksApp (version unknown)
        Logs: last 10 minutes (OSLog subsystem com.dopetracks.app)
        """
        try body.write(to: url, atomically: true, encoding: .utf8)
    }
    
    nonisolated private static func zipReport(at dir: URL) throws -> URL {
        let zipURL = dir.appendingPathExtension("zip")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/zip")
        process.currentDirectoryURL = dir.deletingLastPathComponent()
        process.arguments = ["-r", zipURL.path, dir.lastPathComponent]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        
        try process.run()
        process.waitUntilExit()
        
        if process.terminationStatus != 0 {
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let message = String(data: data, encoding: .utf8) ?? "Unknown zip error"
            throw NSError(domain: "BugReportCollector", code: Int(process.terminationStatus), userInfo: [
                NSLocalizedDescriptionKey: "Failed to zip bug report: \(message)"
            ])
        }
        
        return zipURL
    }
    
    nonisolated private static func timestamp() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        return formatter.string(from: Date())
    }
}

