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
    @State private var isDateFilterEnabled = false
    @State private var startDate: Date?
    @State private var endDate: Date?
    @State private var isCreating = false
    @State private var error: Error?
    @State private var showError = false
    @State private var createdPlaylist: Playlist?
    
    private var isDateRangeInvalid: Bool {
        if let startDate, let endDate { return endDate < startDate }
        return false
    }
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Playlist Details") {
                    TextField("Playlist Name", text: $playlistName)
                        .accessibilityLabel("Playlist name")
                }
                
                Section("Date Range (Optional)") {
                    Toggle("Filter by date range", isOn: $isDateFilterEnabled)
                        .onChange(of: isDateFilterEnabled) { enabled in
                            if enabled {
                                let now = Date()
                                startDate = Calendar.current.date(byAdding: .day, value: -30, to: now)
                                endDate = now
                            } else {
                                startDate = nil
                                endDate = nil
                            }
                        }

                    if isDateFilterEnabled {
                        DatePicker("Start Date", selection: Binding(
                            get: { startDate ?? Date() },
                            set: { startDate = $0 }
                        ), displayedComponents: .date)

                        DatePicker("End Date", selection: Binding(
                            get: { endDate ?? Date() },
                            set: { endDate = $0 }
                        ), displayedComponents: .date)

                        if isDateRangeInvalid {
                            Text("End date must be on or after start date.")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                }
                
                Section {
                    Text("Selected Chats: \(selectedChatIds.count)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Create Playlist")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        UIEventLogger.shared.log("playlist_creation_cancel")
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    if isCreating {
                        ProgressView().accessibilityLabel("Creating playlist")
                    } else {
                        Button("Create") {
                            UIEventLogger.shared.log("playlist_creation_create_tap", metadata: [
                                "chat_count": "\(selectedChatIds.count)"
                            ])
                            Task { await createPlaylist() }
                        }
                        .disabled(playlistName.isEmpty || isDateRangeInvalid)
                    }
                }
            }
            .alert("Error", isPresented: $showError) {
                Button("OK") {
                    error = nil
                }
            } message: {
                if let error = error {
                    Text(error.localizedDescription)
                }
            }
            .sheet(item: $createdPlaylist) { playlist in
                PlaylistCreatedView(playlist: playlist) {
                    dismiss()
                }
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
                playlistName: playlistName
            )
            
            await MainActor.run {
                createdPlaylist = playlist
                isCreating = false
            }
        } catch {
            await MainActor.run {
                self.error = error
                self.showError = true
                isCreating = false
            }
        }
    }
}

struct PlaylistCreatedView: View {
    let playlist: Playlist
    var onDone: (() -> Void)? = nil
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.green)
                .accessibilityLabel("Playlist successfully created")
            
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
                onDone?()
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
