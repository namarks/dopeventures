//
//  ContentView.swift
//  DopetracksApp
//
//  Main content view with navigation
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var backendManager: BackendManager
    @EnvironmentObject var apiClient: APIClient
    @State private var selectedTab = 0
    
    var body: some View {
        Group {
            if backendManager.isBackendRunning {
                TabView(selection: $selectedTab) {
                    ChatListView()
                        .tabItem {
                            Label("Chats", systemImage: "message.fill")
                        }
                        .tag(0)
                    
                    PlaylistListView()
                        .tabItem {
                            Label("Playlists", systemImage: "music.note.list")
                        }
                        .tag(1)
                    
                    SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                        .tag(2)
                }
            } else {
                // Backend starting or error state
                VStack(spacing: 20) {
                    if backendManager.isStarting {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Starting Dopetracks backend...")
                            .font(.headline)
                            .foregroundColor(.secondary)
                    } else if let error = backendManager.error {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.orange)
                        Text("Backend Error")
                            .font(.title2)
                            .fontWeight(.bold)
                        Text(error.localizedDescription)
                            .font(.body)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding()
                        Button("Retry") {
                            Task {
                                await backendManager.startBackend()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(BackendManager())
        .environmentObject(APIClient())
}

