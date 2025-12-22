//
//  PlaylistListView.swift
//  DopetracksApp
//
//  View for displaying created playlists
//

import SwiftUI

struct PlaylistListView: View {
    @StateObject private var viewModel: PlaylistListViewModel
    
    init(apiClient: APIClient) {
        _viewModel = StateObject(wrappedValue: PlaylistListViewModel(apiClient: apiClient))
    }
    
    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = viewModel.error {
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
                                await viewModel.loadPlaylists()
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
                } else if viewModel.playlists.isEmpty {
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
                    List(viewModel.playlists) { playlist in
                        PlaylistRow(playlist: playlist)
                    }
                }
            }
            .navigationTitle("Playlists")
            .task {
                viewModel.onAppear()
            }
        }
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
    PlaylistListView(apiClient: APIClient())
}

