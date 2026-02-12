//
//  BackendManager.swift
//  DopetracksApp
//
//  Manages the Python FastAPI backend process
//

import Foundation
import Combine

@MainActor
class BackendManager: ObservableObject {
    @Published var isBackendRunning = false
    @Published var isStarting = false
    @Published var error: Error?

    private var backendProcess: Process?
    private var healthCheckTask: Task<Void, Never>?

    // Reuse a single URLSession for health checks instead of creating one per call
    private let healthCheckSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10.0
        config.timeoutIntervalForResource = 20.0
        config.waitsForConnectivity = false
        return URLSession(configuration: config)
    }()
    
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
    
    /// Ensure backend is running; attempts start and waits up to timeout.
    @discardableResult
    func ensureBackendRunning(timeout: TimeInterval = 30) async -> Bool {
        await startBackend()
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if isBackendRunning {
                return true
            }
            if await checkBackendHealth() {
                isBackendRunning = true
                isStarting = false
                error = nil
                return true
            }
            try? await Task.sleep(nanoseconds: 500_000_000) // 0.5s
        }
        return isBackendRunning
    }
    
    func startBackend() async {
        guard !isBackendRunning else { return }

        isStarting = true
        error = nil
        
        // Check if backend is already running (for development mode)
        // Try multiple times with small delays to handle race conditions
        print("Checking if backend is already running...")
        var backendDetected = false
        for attempt in 1...3 {
            if await checkBackendHealth() {
                backendDetected = true
                break
            }
            // Wait a bit before retrying (only if not first attempt)
            if attempt < 3 {
                try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds
            }
        }
        
        if backendDetected {
            print("✅ Backend is already running, connecting to it")
            isBackendRunning = true
            isStarting = false
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
            // File structure: dopeventures/DopetracksApp/App/Services/BackendManager.swift
            // Go up 4 levels to reach project root (dopeventures/)
            let currentFile = URL(fileURLWithPath: #file) // BackendManager.swift
            let projectRoot = currentFile
                .deletingLastPathComponent() // Services/
                .deletingLastPathComponent() // App/
                .deletingLastPathComponent() // DopetracksApp/
                .deletingLastPathComponent() // dopeventures/
            
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
                self.error = BackendError.processExited("Launch script not found at: \(finalScript.path). Searched from: \(currentFile.path)")
                self.isStarting = false
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
                    isBackendRunning = true
                    isStarting = false
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
            self.error = error
            self.isStarting = false
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
    
    private nonisolated func checkBackendHealth() async -> Bool {
        do {
            guard let url = URL(string: "http://127.0.0.1:8888/health") else {
                return false
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 10.0
            request.cachePolicy = .reloadIgnoringLocalCacheData

            let session = await healthCheckSession
            let (_, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse {
                let isHealthy = httpResponse.statusCode == 200
                if !isHealthy {
                    print("Backend health check returned status code: \(httpResponse.statusCode)")
                }
                return isHealthy
            }
        } catch {
            if let urlError = error as? URLError {
                print("Backend health check failed: \(urlError.localizedDescription) (code: \(urlError.code.rawValue))")
            } else {
                print("Backend health check failed: \(error.localizedDescription)")
            }
        }
        return false
    }
    
    private func startHealthCheck() {
        healthCheckTask?.cancel()

        healthCheckTask = Task {
            // Give backend a bit more time to fully initialize before first health check
            try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds

            while !Task.isCancelled {
                // Check if process is still running
                if let process = backendProcess, !process.isRunning {
                    isBackendRunning = false
                    error = BackendError.processExited("Backend process exited unexpectedly")
                    backendProcess = nil
                    return
                }

                let isHealthy = await checkBackendHealth()

                if !isHealthy && isBackendRunning {
                    print("⚠️ Health check failed, will retry on next cycle")
                } else if isHealthy && !isBackendRunning {
                    isBackendRunning = true
                    error = nil
                }

                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds between checks
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

