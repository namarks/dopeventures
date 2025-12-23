//
//  ChatDetailView.swift
//  DopetracksApp
//
//  View for displaying chat details and messages
//

import SwiftUI

struct ChatDetailView: View {
    let chat: Chat
    @StateObject private var viewModel: ChatDetailViewModel
    @State private var searchText: String = ""
    @State private var sortOrder: MessageSortOrder = .newestFirst
    
    init(chat: Chat, apiClient: APIClient) {
        self.chat = chat
        _viewModel = StateObject(wrappedValue: ChatDetailViewModel(chatId: chat.id, apiClient: apiClient))
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Chat header info
                VStack(alignment: .leading, spacing: 12) {
                    Text(chat.displayName)
                        .font(.title)
                        .fontWeight(.bold)
                    
                    HStack(spacing: 16) {
                        Label("\(chat.participantCount)", systemImage: "person.2.fill")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        Label("\(chat.messageCount) messages", systemImage: "message.fill")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        if chat.hasSpotifyLinks {
                            Label("Spotify", systemImage: "music.note")
                                .font(.subheadline)
                                .foregroundColor(.green)
                        }
                    }
                    
                    if let date = chat.lastMessageDate {
                        Text("Last message: \(date, style: .relative)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(12)
                
                Divider()
                
                // Filters
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        TextField("Search messages...", text: $searchText)
                            .textFieldStyle(.roundedBorder)
                            .onSubmit {
                                Task { await viewModel.refreshWithFilters(search: searchText, sort: sortOrder) }
                            }
                        Button("Apply") {
                            Task { await viewModel.refreshWithFilters(search: searchText, sort: sortOrder) }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    
                    Picker("Sort", selection: $sortOrder) {
                        ForEach(MessageSortOrder.allCases, id: \.self) { order in
                            Text(order.label).tag(order)
                        }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: sortOrder) { newValue in
                        Task { await viewModel.refreshWithFilters(search: searchText, sort: newValue) }
                    }
                }
                .padding(.horizontal)
                
                // Messages section
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Recent Messages")
                            .font(.headline)
                        Spacer()
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        }
                    }
                    
                    if let error = viewModel.error {
                        VStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundColor(.orange)
                            Text("Error loading messages")
                                .font(.subheadline)
                            Text(error.localizedDescription)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Button("Retry") {
                                Task {
                                    await viewModel.loadInitial()
                                }
                            }
                            .buttonStyle(.bordered)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                    } else if viewModel.messages.isEmpty && !viewModel.isLoading {
                        VStack(spacing: 8) {
                            Image(systemName: "message.fill")
                                .font(.largeTitle)
                                .foregroundColor(.secondary)
                            Text("No messages found")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                    } else {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(viewModel.messages) { message in
                                MessageRow(message: message)
                                    .onAppear {
                                        if message.id == viewModel.messages.last?.id {
                                            Task { await viewModel.loadMore() }
                                        }
                                    }
                            }
                            
                            if viewModel.isLoadingMore {
                                HStack {
                                    ProgressView()
                                    Text("Loading more…")
                                        .foregroundColor(.secondary)
                                        .font(.caption)
                                }
                                .frame(maxWidth: .infinity)
                            } else if viewModel.hasMore {
                                Button("Load more") {
                                    Task { await viewModel.loadMore() }
                                }
                                .buttonStyle(.bordered)
                                .frame(maxWidth: .infinity)
                            }
                        }
                    }
                }
                .padding()
            }
            .padding()
        }
        .navigationTitle(chat.displayName)
        .id(chat.id) // Force a fresh StateObject when chat changes so messages refresh
        .task(id: chat.id) {
            // Reload messages when the selected chat changes
            searchText = ""
            sortOrder = .newestFirst
            await viewModel.loadInitial()
        }
    }
}

struct MessageRow: View {
    let message: Message
    
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            // Avatar / initials
            ZStack {
                Circle()
                    .fill(message.isFromMe ? Color.accentColor.opacity(0.15) : Color.secondary.opacity(0.15))
                    .frame(width: 34, height: 34)
                Text(message.initials)
                    .font(.footnote)
                    .fontWeight(.semibold)
                    .foregroundColor(message.isFromMe ? .accentColor : .primary)
            }
            
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(message.displaySender)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Spacer()
                    HStack(spacing: 4) {
                        Text(message.date, style: .time)
                        Text("•")
                        Text(message.date, style: .relative)
                    }
                    .font(.caption2)
                    .foregroundColor(.secondary)
                }
                
                Text(message.text)
                    .font(.body)
                    .lineSpacing(2)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                
                if message.hasSpotifyLink, let spotifyUrl = message.spotifyUrl {
                    HStack(spacing: 6) {
                        Image(systemName: "music.note")
                            .foregroundColor(.green)
                        Link("Open in Spotify", destination: URL(string: spotifyUrl)!)
                            .font(.caption)
                    }
                }
                
                if !message.reactions.isEmpty {
                    let grouped = Dictionary(grouping: message.reactions, by: { $0.type })
                    HStack(spacing: 6) {
                        ForEach(grouped.keys.sorted(), id: \.self) { key in
                            let emoji = reactionEmoji(key)
                            let count = grouped[key]?.count ?? 0
                            HStack(spacing: 4) {
                                Text(emoji)
                                Text("\(count)")
                                    .font(.caption2)
                            }
                            .padding(.vertical, 4)
                            .padding(.horizontal, 8)
                            .background(Color(NSColor.windowBackgroundColor))
                            .cornerRadius(8)
                        }
                    }
                }
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(10)
    }
    
    private func reactionEmoji(_ type: String) -> String {
        switch type.lowercased() {
        case "loved": return "❤️"
        case "liked": return "👍"
        case "disliked": return "👎"
        case "laughed": return "😂"
        case "emphasized": return "❗️"
        case "questioned": return "❓"
        default: return "💬"
        }
    }
}

#Preview {
    NavigationStack {
        ChatDetailView(chat: Chat(
            id: "1",
            displayName: "Test Chat",
            participantCount: 3,
            messageCount: 42,
            lastMessageDate: Date(),
            hasSpotifyLinks: true
        ), apiClient: APIClient())
    }
}

