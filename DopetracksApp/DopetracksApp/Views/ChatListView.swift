//
//  ChatListView.swift
//  DopetracksApp
//
//  View for searching and selecting chats
//

import SwiftUI

struct ChatListView: View {
    @EnvironmentObject var apiClient: APIClient
    @State private var searchText = ""
    @State private var chats: [Chat] = []
    @State private var isLoading = false
    @State private var error: Error?
    @State private var selectedChats: Set<Chat.ID> = []
    @State private var selectedChatId: Chat.ID?
    @State private var showingPlaylistCreation = false
    
    private var selectedChat: Chat? {
        guard let selectedChatId = selectedChatId else { return nil }
        return chats.first { $0.id == selectedChatId }
    }
    
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                // Search bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("Search chats...", text: $searchText)
                        .textFieldStyle(.plain)
                        .onSubmit {
                            Task {
                                await searchChats()
                            }
                        }
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
                .padding()
                
                // Chat list
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = error {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text("Error loading chats")
                            .font(.headline)
                        Text(error.localizedDescription)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") {
                            Task {
                                await searchChats()
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
                } else if chats.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "message.fill")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No chats found")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        if !searchText.isEmpty {
                            Text("Try a different search term")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        } else {
                            Text("Enter a search term to find chats")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List(selection: $selectedChatId) {
                        ForEach(chats) { chat in
                            ChatRow(chat: chat, isSelected: selectedChats.contains(chat.id))
                            .tag(chat.id)
                        }
                    }
                }
            }
            .navigationTitle("Chats")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Create Playlist") {
                        showingPlaylistCreation = true
                    }
                    .disabled(selectedChats.isEmpty)
                }
            }
            .sheet(isPresented: $showingPlaylistCreation) {
                PlaylistCreationView(selectedChatIds: Array(selectedChats))
            }
        } detail: {
            Group {
                if let selectedChat = selectedChat {
                    ChatDetailView(chat: selectedChat)
                } else {
            Text("Select a chat to view details")
                .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .onChange(of: selectedChatId) { oldValue, newValue in
            // Debug: Print when selection changes
            print("Selected chat ID changed: \(String(describing: newValue))")
        }
    }
    
    private func searchChats() async {
        guard !searchText.isEmpty else {
            chats = []
            return
        }
        
        isLoading = true
        error = nil
        
        do {
            chats = try await apiClient.searchChats(query: searchText)
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
}

struct ChatRow: View {
    let chat: Chat
    let isSelected: Bool
    
    var body: some View {
        HStack {
        VStack(alignment: .leading, spacing: 4) {
            Text(chat.displayName)
                .font(.headline)
            
            HStack {
                Label("\(chat.participantCount)", systemImage: "person.2.fill")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Label("\(chat.messageCount)", systemImage: "message.fill")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                if chat.hasSpotifyLinks {
                    Label("Spotify", systemImage: "music.note")
                        .font(.caption)
                        .foregroundColor(.green)
                }
            }
            
            if let date = chat.lastMessageDate {
                Text(date, style: .relative)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.accentColor)
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

#Preview {
    ChatListView()
        .environmentObject(APIClient())
}

