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
        
        isStarting = true
        error = nil
        
        // Check if backend is already running
        if await checkBackendHealth() {
            isBackendRunning = true
            isStarting = false
            startHealthCheck()
            return
        }
        
        // Start backend process
        let process = Process()
        
        if let executablePath = backendExecutablePath {
            // Use bundled executable
            process.executableURL = executablePath
        } else {
            // Development mode: use system Python
            // This requires Python and dependencies to be installed
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            
            // Get path to launch script
            let projectRoot = URL(fileURLWithPath: #file)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
            
            let launchScript = projectRoot
                .appendingPathComponent("scripts")
                .appendingPathComponent("launch")
                .appendingPathComponent("launch_bundled.py")
            
            process.arguments = [launchScript.path]
        }
        
        // Set up environment
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        
        // Set up output pipes (optional, for debugging)
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        
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
                    let errorData = try errorPipe.fileHandleForReading.readToEnd()
                    let errorString = String(data: errorData ?? Data(), encoding: .utf8) ?? "Unknown error"
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
    
    private func checkBackendHealth() async -> Bool {
        do {
            let url = URL(string: "http://127.0.0.1:8888/health")!
            let (_, response) = try await URLSession.shared.data(from: url)
            
            if let httpResponse = response as? HTTPURLResponse {
                return httpResponse.statusCode == 200
            }
        } catch {
            // Backend not ready yet
        }
        return false
    }
    
    private func startHealthCheck() {
        healthCheckTask?.cancel()
        
        healthCheckTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
                
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

