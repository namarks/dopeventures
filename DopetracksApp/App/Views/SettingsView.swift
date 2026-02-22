//
//  SettingsView.swift
//  DopetracksApp
//
//  Settings and configuration view
//

import SwiftUI
import Foundation
import AppKit

struct SettingsView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var backendManager: BackendManager
    @StateObject private var bugReporter = BugReportCollector()
    
    @State private var profile: SpotifyProfile?
    @State private var isLoading = false
    @State private var error: Error?
    
    // Spotify credentials (stored in ~/.d dopetracks/.env for bundled; same path used here)
    @State private var clientId: String = ""
    @State private var clientSecret: String = ""
    @State private var isSaving = false
    @State private var saveMessage: String?
    @State private var saveError: String?
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Spotify Account") {
                    if isLoading {
                        ProgressView()
                    } else if let profile = profile {
                        HStack {
                            if let imageUrl = profile.imageUrl, let url = URL(string: imageUrl) {
                                AsyncImage(url: url) { image in
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fit)
                                } placeholder: {
                                    Image(systemName: "person.circle.fill")
                                        .foregroundColor(.secondary)
                                }
                                .frame(width: 50, height: 50)
                                .clipShape(Circle())
                            } else {
                                Image(systemName: "person.circle.fill")
                                    .font(.system(size: 50))
                                    .foregroundColor(.secondary)
                            }
                            
                            VStack(alignment: .leading) {
                                Text(profile.displayName)
                                    .font(.headline)
                                if let email = profile.email {
                                    Text(email)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    } else if let error = error {
                        Text("Error: \(error.localizedDescription)")
                            .foregroundColor(.red)
                    } else {
                        Text("Not connected to Spotify")
                            .foregroundColor(.secondary)
                    }
                    
                    Button("Refresh Profile") {
                        UIEventLogger.shared.log("settings_refresh_profile")
                        Task {
                            await loadProfile()
                        }
                    }
                }
                
                Section("Spotify Credentials") {
                    TextField("Client ID", text: $clientId)
                        .disableAutocorrection(true)
                    SecureField("Client Secret", text: $clientSecret)
                        .disableAutocorrection(true)
                    
                    if let saveError = saveError {
                        Text(saveError)
                            .foregroundColor(.red)
                    } else if let saveMessage = saveMessage {
                        Text(saveMessage)
                            .foregroundColor(.green)
                    }
                    
                    Button {
                        UIEventLogger.shared.log("settings_save_credentials_and_restart")
                        Task {
                            await saveCredentialsAndRestartBackend()
                        }
                    } label: {
                        if isSaving {
                            HStack {
                                ProgressView()
                                Text("Saving…")
                            }
                        } else {
                            Text("Save & Restart Backend")
                        }
                    }
                    .disabled(isSaving || clientId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || clientSecret.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    
                    if let repoURL = URL(string: "https://github.com/namarks/dopeventures") {
                        Link("GitHub Repository", destination: repoURL)
                    }
                }
                
                Section("Support") {
                    VStack(alignment: .leading, spacing: 8) {
                        Button {
                            UIEventLogger.shared.log("settings_collect_bug_report")
                            Task { await bugReporter.collect() }
                        } label: {
                            if bugReporter.isCollecting {
                                HStack {
                                    ProgressView()
                                    Text("Collecting…")
                                }
                            } else {
                                Text("Collect Bug Report (last 10 min logs)")
                            }
                        }
                        .disabled(bugReporter.isCollecting)
                        
                        if let status = bugReporter.status {
                            Text(status)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        if let error = bugReporter.errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                        
                        if let zipURL = bugReporter.zipURL {
                            Text("Saved to: \(zipURL.path)")
                                .font(.caption2)
                                .textSelection(.enabled)
                            
                            HStack {
                                Button("Reveal in Finder") {
                                    UIEventLogger.shared.log("settings_bug_report_reveal")
                                    NSWorkspace.shared.activateFileViewerSelecting([zipURL])
                                }
                                Button("Copy Path") {
                                    UIEventLogger.shared.log("settings_bug_report_copy_path")
                                    let pb = NSPasteboard.general
                                    pb.clearContents()
                                    pb.setString(zipURL.path, forType: .string)
                                }
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
            }
            .navigationTitle("Settings")
            .task {
                await loadProfile()
                loadEnvCredentials()
            }
        }
    }
    
    private func loadProfile() async {
        isLoading = true
        error = nil
        
        do {
            profile = try await apiClient.getUserProfile()
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
    
    private var envFileURL: URL {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("Dopetracks")
            .appendingPathComponent(".env")
    }
    
    private func loadEnvCredentials() {
        let url = envFileURL
        guard let content = try? String(contentsOf: url, encoding: .utf8) else {
            return
        }
        let parsed = parseEnv(content)
        clientId = parsed["SPOTIFY_CLIENT_ID"] ?? ""
        clientSecret = parsed["SPOTIFY_CLIENT_SECRET"] ?? ""
    }
    
    private func parseEnv(_ content: String) -> [String: String] {
        var result: [String: String] = [:]
        for line in content.split(separator: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }
            if let eq = trimmed.firstIndex(of: "=") {
                let key = String(trimmed[..<eq]).trimmingCharacters(in: .whitespaces)
                let value = String(trimmed[trimmed.index(after: eq)...]).trimmingCharacters(in: .whitespaces)
                result[key] = value
            }
        }
        return result
    }
    
    private func saveEnv(_ values: [String: String]) throws {
        var existing: [String: String] = [:]
        if let content = try? String(contentsOf: envFileURL, encoding: .utf8) {
            existing = parseEnv(content)
        }
        for (k, v) in values {
            existing[k] = v
        }
        // Ensure directory exists
        try FileManager.default.createDirectory(at: envFileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        
        let lines = existing.map { "\($0.key)=\($0.value)" }.sorted()
        let body = lines.joined(separator: "\n") + "\n"
        try body.write(to: envFileURL, atomically: true, encoding: .utf8)
    }
    
    private func saveCredentialsAndRestartBackend() async {
        await MainActor.run {
            isSaving = true
            saveError = nil
            saveMessage = nil
        }
        
        let trimmedId = clientId.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedSecret = clientSecret.trimmingCharacters(in: .whitespacesAndNewlines)
        
        guard !trimmedId.isEmpty, !trimmedSecret.isEmpty else {
            await MainActor.run {
                isSaving = false
                saveError = "Client ID and Secret are required."
            }
            return
        }
        
        do {
            try saveEnv([
                "SPOTIFY_CLIENT_ID": trimmedId,
                "SPOTIFY_CLIENT_SECRET": trimmedSecret,
                "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback"
            ])
            
            // Restart backend so new env vars take effect
            backendManager.stopBackend()
            await backendManager.startBackend()
            
            await MainActor.run {
                isSaving = false
                saveMessage = "Saved. Backend restarted."
            }
        } catch {
            await MainActor.run {
                isSaving = false
                saveError = "Failed to save credentials: \(error.localizedDescription)"
            }
        }
    }
}

#Preview {
    SettingsView()
        .environmentObject(APIClient())
        .environmentObject(BackendManager())
}

