//
//  PlaylistCreationView.swift
//  DopetracksApp
//
//  View for creating playlists from selected chats
//

import SwiftUI

struct PlaylistCreationView: View {
    @EnvironmentObject var apiClient: APIClient
    @Environment(\.dismiss) var dismiss
    
    let selectedChatIds: [String]
    
    @State private var playlistName = ""
    @State private var startDate: Date?
    @State private var endDate: Date?
    @State private var isCreating = false
    @State private var error: Error?
    @State private var createdPlaylist: Playlist?
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Playlist Details") {
                    TextField("Playlist Name", text: $playlistName)
                }
                
                Section("Date Range (Optional)") {
                    Toggle("Filter by date range", isOn: Binding(
                        get: { startDate != nil || endDate != nil },
                        set: { enabled in
                            if !enabled {
                                startDate = nil
                                endDate = nil
                            } else {
                                startDate = Date().addingTimeInterval(-30 * 24 * 60 * 60) // 30 days ago
                                endDate = Date()
                            }
                        }
                    ))
                    
                    if startDate != nil || endDate != nil {
                        DatePicker("Start Date", selection: Binding(
                            get: { startDate ?? Date() },
                            set: { startDate = $0 }
                        ), displayedComponents: .date)
                        
                        DatePicker("End Date", selection: Binding(
                            get: { endDate ?? Date() },
                            set: { endDate = $0 }
                        ), displayedComponents: .date)
                    }
                }
                
                Section {
                    Text("Selected Chats: \(selectedChatIds.count)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Create Playlist")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        Task {
                            await createPlaylist()
                        }
                    }
                    .disabled(playlistName.isEmpty || isCreating)
                }
            }
            .alert("Error", isPresented: .constant(error != nil)) {
                Button("OK") {
                    error = nil
                }
            } message: {
                if let error = error {
                    Text(error.localizedDescription)
                }
            }
            .sheet(item: $createdPlaylist) { playlist in
                PlaylistCreatedView(playlist: playlist)
            }
        }
        .frame(width: 500, height: 400)
    }
    
    private func createPlaylist() async {
        isCreating = true
        error = nil
        
        do {
            let playlist = try await apiClient.createPlaylist(
                chatIds: selectedChatIds,
                startDate: startDate,
                endDate: endDate,
                playlistName: playlistName.isEmpty ? "New Playlist" : playlistName
            )
            
            await MainActor.run {
                createdPlaylist = playlist
                isCreating = false
            }
        } catch {
            await MainActor.run {
                self.error = error
                isCreating = false
            }
        }
    }
}

struct PlaylistCreatedView: View {
    let playlist: Playlist
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.green)
            
            Text("Playlist Created!")
                .font(.title2)
                .fontWeight(.bold)
            
            Text(playlist.name)
                .font(.headline)
            
            if let spotifyUrl = playlist.spotifyUrl, let url = URL(string: spotifyUrl) {
                Link("Open in Spotify", destination: url)
                    .buttonStyle(.borderedProminent)
            }
            
            Button("Done") {
                dismiss()
            }
            .buttonStyle(.bordered)
        }
        .padding()
        .frame(width: 400, height: 300)
    }
}

#Preview {
    PlaylistCreationView(selectedChatIds: ["chat1", "chat2"])
        .environmentObject(APIClient())
}

