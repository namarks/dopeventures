//
//  ChatListView.swift
//  DopetracksApp
//
//  View for searching and selecting chats
//

import SwiftUI
import AppKit

struct ChatListView: View {
    @EnvironmentObject var apiClient: APIClient
    @State private var searchText = ""
    @State private var chats: [Chat] = []
    @State private var isLoading = false
    @State private var error: Error?
    @State private var selectedChats: Set<Chat.ID> = []
    @State private var selectedChatId: Chat.ID?
    @State private var showingPlaylistCreation = false
    @State private var hasFullDiskAccess = false
    @State private var searchFilters = SearchFilters()
    @State private var showingFilters = false
    @State private var useAdvancedSearch = false
    @State private var currentSearchTask: Task<Void, Never>?
    @State private var hasLoadedOnce = false
    
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
                        .onChange(of: searchText) { newValue in
                            // Only update searchFilters.query if we have other filters
                            // Otherwise, use simple search for text-only queries
                            if searchFilters.startDate != nil || 
                               searchFilters.endDate != nil || 
                               !searchFilters.participantNames.isEmpty || 
                               !searchFilters.messageContent.isEmpty {
                                searchFilters.query = newValue
                            }
                            
                            // Auto-search as user types (macOS 13.0 compatible)
                            if !newValue.isEmpty || searchFilters.hasFilters {
                                Task {
                                    await performSearch()
                                }
                            } else {
                                // Clear results when search is empty and no filters
                                chats = []
                                selectedChatId = nil
                            }
                        }
                        .onSubmit {
                            Task {
                                await performSearch()
                            }
                        }
                    
                    Button {
                        showingFilters.toggle()
                    } label: {
                        Image(systemName: searchFilters.hasFilters ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                            .foregroundColor(searchFilters.hasFilters ? .accentColor : .secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Advanced Search Filters")
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
                .padding(.horizontal)
                .padding(.top)
                
                // Filter summary
                if searchFilters.hasFilters && !showingFilters {
                    HStack {
                        if searchFilters.startDate != nil || searchFilters.endDate != nil {
                            Label("Date range", systemImage: "calendar")
                                .font(.caption)
                        }
                        if !searchFilters.participantNames.isEmpty {
                            Label("\(searchFilters.participantNames.count) participant(s)", systemImage: "person.2")
                                .font(.caption)
                        }
                        if !searchFilters.messageContent.isEmpty {
                            Label("Message content", systemImage: "text.bubble")
                                .font(.caption)
                        }
                        Spacer()
                        Button("Clear") {
                            searchFilters = SearchFilters()
                            searchText = ""
                            Task {
                                await loadAllChats()
                            }
                        }
                        .buttonStyle(.borderless)
                        .font(.caption)
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 4)
                    .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
                }
                
                // Chat list
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = error {
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
                                        checkPermissions()
                                        Task {
                                            await loadAllChats()
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
                                    await loadAllChats()
                                }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
                } else if chats.isEmpty && !searchText.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "message.fill")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No chats found")
                            .font(.headline)
                            .foregroundColor(.secondary)
                            Text("Try a different search term")
                                .font(.caption)
                                .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if chats.isEmpty && searchText.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("Search for chats")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text("Enter a search term above to find your conversations")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List(selection: $selectedChatId) {
                        ForEach(chats) { chat in
                            ChatRow(chat: chat, isSelected: selectedChats.contains(chat.id))
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
                        showingPlaylistCreation = true
                    }
                    .disabled(selectedChats.isEmpty)
                }
            }
            .sheet(isPresented: $showingPlaylistCreation) {
                PlaylistCreationView(selectedChatIds: Array(selectedChats))
            }
            .sheet(isPresented: $showingFilters) {
                VStack {
                    SearchFiltersView(filters: $searchFilters)
                        .onChange(of: searchFilters) { _ in
                            // Auto-search when filters change
                            Task {
                                await performSearch()
                            }
                        }
                    
                    HStack {
                        Button("Close") {
                            showingFilters = false
                        }
                        .buttonStyle(.bordered)
                        
                        Spacer()
                        
                        Button("Search") {
                            showingFilters = false
                            Task {
                                await performSearch()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                }
                .frame(width: 500, height: 600)
            }
            .task {
                // Only load once; avoid reloading on every tab revisit
                if !hasLoadedOnce {
                    checkPermissions()
                    await loadAllChats()
                    hasLoadedOnce = true
                }
            }
        } detail: {
            if let selectedChat = selectedChat {
                ChatDetailView(chat: selectedChat)
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
    
    private func checkPermissions() {
        // Try to access Messages database to trigger permission prompt if needed
        hasFullDiskAccess = PermissionManager.shared.checkFullDiskAccess()
        
        if !hasFullDiskAccess {
            // Permission not granted - the system should show a prompt
            // If it doesn't, we'll show instructions in the error view
        }
    }
    
    private func loadAllChats() async {
        isLoading = true
        error = nil
        
        do {
            let fetched = try await apiClient.getAllChats()
            chats = sortChats(fetched)
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
    
    private func performSearch() async {
        // Cancel any existing search
        currentSearchTask?.cancel()
        
        // Create new search task
        let searchTask = Task {
            await MainActor.run {
                isLoading = true
                error = nil
                chats = [] // Clear existing results
            }
            
            do {
                // Check if task was cancelled before starting
                try Task.checkCancellation()
                
                print("🔍 performSearch called: searchText='\(searchText)', hasFilters=\(searchFilters.hasFilters)")
                
                // Check if we have only a text query (no other filters)
                let hasOnlyTextQuery = !searchText.isEmpty && 
                                      searchFilters.startDate == nil && 
                                      searchFilters.endDate == nil && 
                                      searchFilters.participantNames.isEmpty && 
                                      searchFilters.messageContent.isEmpty
                
                print("🔍 hasOnlyTextQuery=\(hasOnlyTextQuery), searchText='\(searchText)'")
                
                if hasOnlyTextQuery {
                    // For text-only queries, use advanced search with message_content
                    // This searches both chat names AND message content
                    var filters = SearchFilters()
                    filters.query = searchText
                    filters.messageContent = searchText  // Also search in messages
                    
                    print("🔍 Using advanced search with query='\(filters.query)', messageContent='\(filters.messageContent)'")
                    
                    var newChats: [Chat] = []
                    let stream = try await apiClient.advancedSearch(filters: filters, stream: true)
                    
                    print("🔍 Stream obtained, starting to read results...")
                    
                    for try await chat in stream {
                        try Task.checkCancellation()
                        newChats.append(chat)
                        print("Received chat: \(chat.displayName)")
                        await MainActor.run {
                            chats = sortChats(newChats)
                        }
                    }
                    
                    print("Stream completed. Total chats: \(newChats.count)")
                    
                    await MainActor.run {
                        chats = sortChats(newChats)
                        isLoading = false
                    }
                } else if searchFilters.hasFilters {
                    // Use advanced search with streaming for complex queries
                    var newChats: [Chat] = []
                    let stream = try await apiClient.advancedSearch(filters: searchFilters, stream: true)
                    
                    for try await chat in stream {
                        // Check for cancellation periodically
                        try Task.checkCancellation()
                        
                        newChats.append(chat)
                        // Update UI incrementally as results arrive
                        await MainActor.run {
                            chats = sortChats(newChats)
                        }
                    }
                    
                    await MainActor.run {
                        chats = sortChats(newChats)
                        isLoading = false
                    }
                } else {
                    // Load all chats if no search criteria
                    try Task.checkCancellation()
                    await loadAllChats()
                    return
                }
            } catch is CancellationError {
                // Search was cancelled - this is expected when starting a new search
                await MainActor.run {
                    // Don't update UI if cancelled
                }
            } catch {
                await MainActor.run {
                    self.error = error
                    self.isLoading = false
                }
            }
        }
        
        currentSearchTask = searchTask
        await searchTask.value
    }
    
    private func searchChats() async {
        await performSearch()
    }
    
    private func sortChats(_ list: [Chat]) -> [Chat] {
        list.sorted { lhs, rhs in
            let lDate = lhs.lastMessageDate ?? Date.distantPast
            let rDate = rhs.lastMessageDate ?? Date.distantPast
            return lDate > rDate
        }
    }
}

struct ChatRow: View {
    let chat: Chat
    let isSelected: Bool
    
    var body: some View {
        HStack(spacing: 12) {
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
            
            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.accentColor)
                    .font(.caption)
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 4)
        .contentShape(Rectangle())
    }
}

#Preview {
    ChatListView()
        .environmentObject(APIClient())
}

