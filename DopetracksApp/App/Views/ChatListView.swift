//
//  ChatListView.swift
//  DopetracksApp
//
//  View for searching and selecting chats
//

import SwiftUI
import AppKit

struct ChatListView: View {
    @ObservedObject var viewModel: ChatListViewModel
    @State private var showingPlaylistCreation = false
    @State private var detailChatId: Chat.ID?
    
    private var selectedChat: Chat? {
        guard let detailChatId else { return nil }
        return viewModel.chats.first { $0.id == detailChatId }
    }
    
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                // Search bar
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.secondary)
                        TextField("Search chats...", text: $viewModel.searchText)
                            .textFieldStyle(.plain)
                            .onChange(of: viewModel.searchText) { newValue in
                                viewModel.onSearchTextChange(newValue)
                            }
                            .onSubmit {
                                Task {
                                    await viewModel.performSearch()
                                }
                            }
                    }
                    .padding()
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(8)
                    
                    if viewModel.isLoading {
                        HStack(spacing: 8) {
                            ProgressView()
                                .controlSize(.small)
                            Text("Searching chats…")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding(.horizontal, 4)
                    }
                }
                .padding(.horizontal)
                .padding(.top)
                
                // Inline advanced search filters (always visible)
                VStack(alignment: .leading, spacing: 8) {
                    SearchFiltersView(filters: $viewModel.searchFilters)
                        .onChange(of: viewModel.searchFilters) { _ in
                            Task { await viewModel.performSearch() }
                        }
                    
                    if viewModel.searchFilters.hasFilters {
                        HStack {
                            Label("Filters active", systemImage: "line.3.horizontal.decrease.circle.fill")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Button("Clear Filters") {
                                viewModel.clearFilters()
                            }
                            .buttonStyle(.borderless)
                            .font(.caption)
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 8)
                
                // Chat list
                if viewModel.isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = viewModel.error {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text("Error loading chats")
                            .font(.headline)
                        
                        let errorMessage = error.localizedDescription
                        let isPermissionError = errorMessage.contains("No Messages database found") || 
                                               errorMessage.contains("Full Disk Access") ||
                                               errorMessage.contains("400") ||
                                               errorMessage.contains("database")
                        
                        if isPermissionError {
                            VStack(spacing: 12) {
                                Text("Full Disk Access Required")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                Text("Dopetracks needs Full Disk Access to read your Messages database.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                Text("Go to: System Settings > Privacy & Security > Full Disk Access")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                
                                VStack(spacing: 8) {
                                    Button("Open System Settings") {
                                        PermissionManager.shared.openFullDiskAccessSettings()
                                    }
                                    .buttonStyle(.borderedProminent)
                                    
                                    Button("Check Again") {
                                        viewModel.refreshPermissions()
                                        Task {
                                            await viewModel.loadAllChats()
                                        }
                                    }
                                    .buttonStyle(.bordered)
                                }
                            }
                            .padding(.horizontal)
                        } else {
                            Text(errorMessage)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        
                        if !errorMessage.contains("Full Disk Access") {
                            Button("Retry") {
                                Task {
                                    await viewModel.loadAllChats()
                                }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
                } else if viewModel.chats.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: viewModel.searchText.isEmpty && !viewModel.searchFilters.hasFilters ? "magnifyingglass" : "message.fill")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        if viewModel.searchText.isEmpty && !viewModel.searchFilters.hasFilters {
                            Text("Search for chats")
                                .font(.headline)
                                .foregroundColor(.secondary)
                            Text("Enter a search term above to find your conversations")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        } else {
                            Text("No chats found for your search/filters")
                                .font(.headline)
                                .foregroundColor(.secondary)
                            if !viewModel.searchText.isEmpty {
                                Text("Tried: “\(viewModel.searchText)”")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            if viewModel.searchFilters.hasFilters {
                                Text("Filters are active—try clearing them to see all chats.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            HStack(spacing: 12) {
                                Button("Clear Filters") {
                                    viewModel.clearFilters()
                                }
                                .buttonStyle(.bordered)
                                
                                if !viewModel.searchText.isEmpty {
                                    Button("Clear Search") {
                                        viewModel.searchText = ""
                                        Task { await viewModel.loadAllChats() }
                                    }
                                    .buttonStyle(.bordered)
                                }
                            }
                            .padding(.top, 4)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(viewModel.chats) { chat in
                            ChatRow(
                                chat: chat,
                                isSelected: viewModel.selectedChats.contains(chat.id),
                                toggleSelection: { toggleChatSelection(chat.id) },
                                selectForDetail: { selectChatForDetail(chat.id) }
                            )
                            .tag(chat.id)
                        }
                    }
                    .listStyle(.sidebar)
                }
            }
            .navigationTitle("Chats")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Create Playlist") {
                        UIEventLogger.shared.log("chatlist_create_playlist_tap", metadata: ["selected_chats": "\(viewModel.selectedChats.count)"])
                        showingPlaylistCreation = true
                    }
                    .disabled(viewModel.selectedChats.isEmpty)
                }
            }
            .sheet(isPresented: $showingPlaylistCreation) {
                PlaylistCreationView(selectedChatIds: Array(viewModel.selectedChats))
            }
            .task {
                viewModel.onAppear()
                detailChatId = viewModel.selectedChats.first ?? viewModel.chats.first?.id
            }
            .onChange(of: viewModel.selectedChats) { newSelection in
                // Update detail focus to the first selected chat (if any)
                if detailChatId == nil {
                    detailChatId = newSelection.first
                }
            }
            .onChange(of: viewModel.chats) { chats in
                if let current = detailChatId, !chats.contains(where: { $0.id == current }) {
                    detailChatId = viewModel.selectedChats.first
                }
            }
        } detail: {
            if let selectedChat = selectedChat {
                ChatDetailView(chat: selectedChat, apiClient: viewModel.apiClient)
                    .id(selectedChat.id) // ensure detail rebinds when selection changes
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "message.fill")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("Select a chat to view details")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    Text("Choose a conversation from the list to see messages and information")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }

    // MARK: - Selection helpers
    private func toggleChatSelection(_ id: Chat.ID) {
        var updated = viewModel.selectedChats
        if updated.contains(id) {
            updated.remove(id)
        } else {
            updated.insert(id)
        }
        viewModel.selectedChats = updated
    }
    
    private func selectChatForDetail(_ id: Chat.ID) {
        detailChatId = id
        UIEventLogger.shared.log("chat_selected", metadata: ["chat_id": "\(id)"])
    }
}

struct ChatRow: View {
    let chat: Chat
    let isSelected: Bool
    let toggleSelection: () -> Void
    let selectForDetail: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            Button(action: toggleSelection) {
                Image(systemName: isSelected ? "checkmark.square.fill" : "square")
                    .font(.title3)
            }
            .buttonStyle(.plain)
            .padding(.trailing, 4)
            
            VStack(alignment: .leading, spacing: 6) {
            Text(chat.displayName)
                .font(.headline)
                    .lineLimit(1)
            
                HStack(spacing: 12) {
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
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 4)
        .contentShape(Rectangle())
        .onTapGesture {
            selectForDetail()
        }
    }
}

#Preview {
    let api = APIClient()
    let vm = ChatListViewModel(apiClient: api)
    return ChatListView(viewModel: vm)
}

