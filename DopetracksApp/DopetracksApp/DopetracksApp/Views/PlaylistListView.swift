//
//  PlaylistListView.swift
//  DopetracksApp
//
//  View for displaying created playlists
//

import SwiftUI

struct PlaylistListView: View {
    @EnvironmentObject var apiClient: APIClient
    @State private var playlists: [Playlist] = []
    @State private var isLoading = false
    @State private var error: Error?
    @State private var hasLoadedOnce = false
    
    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = error {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text("Error loading playlists")
                            .font(.headline)
                        Text(error.localizedDescription)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Button("Retry") {
                            Task {
                                await loadPlaylists()
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
                } else if playlists.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "music.note.list")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No playlists yet")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text("Create your first playlist from the Chats tab")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List(playlists) { playlist in
                        PlaylistRow(playlist: playlist)
                    }
                }
            }
            .navigationTitle("Playlists")
            .task {
                // Avoid reloading every time user reopens the tab
                if !hasLoadedOnce {
                    await loadPlaylists()
                    hasLoadedOnce = true
                }
            }
        }
    }
    
    private func loadPlaylists() async {
        isLoading = true
        error = nil
        
        do {
            playlists = try await apiClient.getUserPlaylists()
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
}

struct PlaylistRow: View {
    let playlist: Playlist
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(playlist.name)
                .font(.headline)
            
            HStack {
                Label("\(playlist.trackCount) tracks", systemImage: "music.note")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                if let date = playlist.createdAt {
                    Text(date, style: .relative)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            if let spotifyUrl = playlist.spotifyUrl, let url = URL(string: spotifyUrl) {
                Link("Open in Spotify", destination: url)
                    .font(.caption)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    PlaylistListView()
        .environmentObject(APIClient())
}

