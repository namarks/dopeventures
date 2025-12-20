//
//  SettingsView.swift
//  DopetracksApp
//
//  Settings and configuration view
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var apiClient: APIClient
    @State private var profile: SpotifyProfile?
    @State private var isLoading = false
    @State private var error: Error?
    
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
                        Task {
                            await loadProfile()
                        }
                    }
                }
                
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    
                    Link("GitHub Repository", destination: URL(string: "https://github.com/namarks/dopeventures")!)
                }
            }
            .navigationTitle("Settings")
            .task {
                await loadProfile()
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
}

#Preview {
    SettingsView()
        .environmentObject(APIClient())
}

