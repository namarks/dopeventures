//
//  BackendManager.swift
//  DopetracksApp
//
//  Manages the Python FastAPI backend process
//

import Foundation
import Combine

class BackendManager: ObservableObject {
    @Published var isBackendRunning = false
    @Published var isStarting = false
    @Published var error: Error?
    
    private var backendProcess: Process?
    private var healthCheckTask: Task<Void, Never>?
    
    // Path to bundled Python backend executable
    private var backendExecutablePath: URL? {
        // In production, this will be in the app bundle
        // For development, we can use a path to the Python script
        if let bundlePath = Bundle.main.resourcePath {
            let executable = URL(fileURLWithPath: bundlePath)
                .appendingPathComponent("Backend")
                .appendingPathComponent("Dopetracks")
            
            if FileManager.default.fileExists(atPath: executable.path) {
                return executable
            }
        }
        
        // Fallback: development mode - use system Python
        // This allows testing without bundling
        return nil
    }
    
    func startBackend() async {
        guard !isBackendRunning else { return }
        
        await MainActor.run {
            isStarting = true
            error = nil
        }
        
        // Check if backend is already running (for development mode)
        print("Checking if backend is already running...")
        if await checkBackendHealth() {
            print("✅ Backend is already running, connecting to it")
            await MainActor.run {
                isBackendRunning = true
                isStarting = false
            }
            startHealthCheck()
            return
        }
        print("Backend not detected, attempting to start...")
        
        // Start backend process
        let process = Process()
        
        if let executablePath = backendExecutablePath {
            // Use bundled executable
            process.executableURL = executablePath
        } else {
            // Development mode: use system Python or venv Python
            // Get path to launch script
            // File structure: dopeventures/DopetracksApp/DopetracksApp/DopetracksApp/Services/BackendManager.swift
            // Need to go up 4 levels to reach project root (dopeventures/)
            let currentFile = URL(fileURLWithPath: #file) // BackendManager.swift
            let servicesDir = currentFile.deletingLastPathComponent() // Services/
            let appDir = servicesDir.deletingLastPathComponent() // DopetracksApp/
            let dopetracksAppDir = appDir.deletingLastPathComponent() // DopetracksApp/
            let outerDopetracksAppDir = dopetracksAppDir.deletingLastPathComponent() // DopetracksApp/
            let projectRoot = outerDopetracksAppDir.deletingLastPathComponent() // dopeventures/
            
            // First, try to find and use venv Python
            let venvPython = projectRoot
                .appendingPathComponent("venv")
                .appendingPathComponent("bin")
                .appendingPathComponent("python3")
            
            let pythonExecutable: URL
            if FileManager.default.fileExists(atPath: venvPython.path) {
                pythonExecutable = venvPython
                print("Using virtual environment Python: \(venvPython.path)")
            } else {
                pythonExecutable = URL(fileURLWithPath: "/usr/bin/python3")
                print("Using system Python: \(pythonExecutable.path)")
            }
            
            process.executableURL = pythonExecutable
            
            // Prefer dev_server.py for Swift app (simple, no browser opening)
            // Use app_launcher.py only if dev_server.py doesn't exist
            let devServerScript = projectRoot.appendingPathComponent("dev_server.py")
            let appLauncherScript = projectRoot
                .appendingPathComponent("scripts")
                .appendingPathComponent("launch")
                .appendingPathComponent("app_launcher.py")
            
            // Use dev_server.py if it exists (preferred for Swift app), otherwise try app_launcher.py
            let finalScript: URL
            if FileManager.default.fileExists(atPath: devServerScript.path) {
                finalScript = devServerScript
            } else {
                // Fallback: search for app_launcher.py
                var searchPath = currentFile.deletingLastPathComponent() // Start from Services/
                var foundScript: URL?
                
                // Search up to 6 levels for the scripts directory
                for _ in 0..<6 {
                    let testScript = searchPath
                        .appendingPathComponent("scripts")
                        .appendingPathComponent("launch")
                        .appendingPathComponent("app_launcher.py")
                    
                    if FileManager.default.fileExists(atPath: testScript.path) {
                        foundScript = testScript
                        break
                    }
                    searchPath = searchPath.deletingLastPathComponent()
                }
                
                finalScript = foundScript ?? appLauncherScript
            }
            
            print("Attempting to start backend with script: \(finalScript.path)")
            
            // Check if script exists
            if !FileManager.default.fileExists(atPath: finalScript.path) {
                await MainActor.run {
                    self.error = BackendError.processExited("Launch script not found at: \(finalScript.path). Searched from: \(currentFile.path)")
                    self.isStarting = false
                }
                return
            }
            
            process.arguments = [finalScript.path]
        }
        
        // Set up environment
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        environment["SWIFT_APP_MODE"] = "1" // Signal to launcher to skip browser opening
        process.environment = environment
        
        // Set up output pipes (optional, for debugging)
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        
        // Set file handles to non-blocking mode for real-time logging
        // Filter out only macOS system network framework messages, keep all backend logs
        outputPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty {
                if let text = String(data: data, encoding: .utf8) {
                    let lines = text.components(separatedBy: .newlines)
                    for line in lines {
                        let trimmed = line.trimmingCharacters(in: .whitespaces)
                        // Only filter out macOS system network framework internal messages
                        // Keep all actual backend application logs
                        if !trimmed.isEmpty {
                            let isSystemMessage = trimmed.contains("nw_connection_copy_") ||
                                                  trimmed.contains("nw_connection_copy_connected_") ||
                                                  trimmed.contains("nw_endpoint_copy_") ||
                                                  trimmed.contains("nw_protocol_metadata_") ||
                                                  trimmed.contains("nw_socket_") ||
                                                  trimmed.contains("nw_resolver_") ||
                                                  (trimmed.hasPrefix("Task <") && trimmed.contains("finished with error"))
                            
                            if !isSystemMessage {
                                print("Backend output: \(line)")
                            }
                        }
                    }
                }
            }
        }
        
        errorPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty {
                if let text = String(data: data, encoding: .utf8) {
                    let lines = text.components(separatedBy: .newlines)
                    for line in lines {
                        let trimmed = line.trimmingCharacters(in: .whitespaces)
                        // Only filter out macOS system network framework internal messages
                        // Keep all actual backend application logs (INFO, WARNING, ERROR from Python)
                        if !trimmed.isEmpty {
                            let isSystemMessage = trimmed.contains("nw_connection_copy_") ||
                                                  trimmed.contains("nw_connection_copy_connected_") ||
                                                  trimmed.contains("nw_endpoint_copy_") ||
                                                  trimmed.contains("nw_protocol_metadata_") ||
                                                  trimmed.contains("nw_socket_") ||
                                                  trimmed.contains("nw_resolver_") ||
                                                  (trimmed.hasPrefix("Task <") && trimmed.contains("finished with error"))
                            
                            // Keep backend logs (they usually have timestamps or log levels)
                            let isBackendLog = trimmed.contains(" - ") || // Timestamp format
                                               trimmed.contains("INFO") ||
                                               trimmed.contains("WARNING") ||
                                               trimmed.contains("ERROR") ||
                                               trimmed.contains("DEBUG") ||
                                               trimmed.contains("dopetracks") ||
                                               trimmed.contains("uvicorn") ||
                                               trimmed.contains("INFO:") ||
                                               trimmed.contains("ERROR:") ||
                                               trimmed.contains("WARNING:")
                            
                            if !isSystemMessage || isBackendLog {
                                print("Backend error: \(line)")
                            }
                        }
                    }
                }
            }
        }
        
        do {
            try process.run()
            backendProcess = process
            
            // Wait for backend to start (poll health endpoint)
            var attempts = 0
            let maxAttempts = 30 // 30 seconds
            
            while attempts < maxAttempts {
                try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
                
                if await checkBackendHealth() {
                    await MainActor.run {
                        isBackendRunning = true
                        isStarting = false
                    }
                    startHealthCheck()
                    return
                }
                
                // Check if process is still running
                if !process.isRunning {
                    // Try to read error output (non-blocking)
                    var errorString = "Process exited"
                    if let errorData = try? errorPipe.fileHandleForReading.readToEnd(), 
                       let errorText = String(data: errorData, encoding: .utf8), 
                       !errorText.isEmpty {
                        errorString = errorText
                    }
                    // Also try to read standard output for debugging
                    if let outputData = try? outputPipe.fileHandleForReading.readToEnd(),
                       let outputText = String(data: outputData, encoding: .utf8),
                       !outputText.isEmpty {
                        errorString += "\nOutput: \(outputText)"
                    }
                    throw BackendError.processExited(errorString)
                }
                
                attempts += 1
            }
            
            throw BackendError.timeout
        } catch {
            await MainActor.run {
                self.error = error
                self.isStarting = false
            }
            backendProcess?.terminate()
            backendProcess = nil
        }
    }
    
    func stopBackend() {
        backendProcess?.terminate()
        backendProcess = nil
        healthCheckTask?.cancel()
        healthCheckTask = nil
        isBackendRunning = false
    }
    
    private func checkBackendHealth() async -> Bool {
        do {
            let url = URL(string: "http://127.0.0.1:8888/health")!
            var request = URLRequest(url: url)
            request.timeoutInterval = 2.0 // Short timeout for quick checks
            
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                return httpResponse.statusCode == 200
            }
        } catch {
            // Backend not ready yet - log for debugging
            print("Backend health check failed: \(error.localizedDescription)")
        }
        return false
    }
    
    private func startHealthCheck() {
        healthCheckTask?.cancel()
        
        healthCheckTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
                
                // Check if process is still running
                if let process = backendProcess, !process.isRunning {
                    await MainActor.run {
                        isBackendRunning = false
                        error = BackendError.processExited("Backend process exited unexpectedly")
                        backendProcess = nil
                    }
                    return
                }
                
                let isHealthy = await checkBackendHealth()
                
                await MainActor.run {
                    if !isHealthy && isBackendRunning {
                        isBackendRunning = false
                        error = BackendError.connectionLost
                    }
                }
            }
        }
    }
}

enum BackendError: LocalizedError {
    case processExited(String)
    case timeout
    case connectionLost
    
    var errorDescription: String? {
        switch self {
        case .processExited(let message):
            return "Backend process exited: \(message)"
        case .timeout:
            return "Backend failed to start within timeout period"
        case .connectionLost:
            return "Lost connection to backend"
        }
    }
}

