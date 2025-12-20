//
//  ChatDetailView.swift
//  DopetracksApp
//
//  View for displaying chat details and messages
//

import SwiftUI

struct ChatDetailView: View {
    let chat: Chat
    @EnvironmentObject var apiClient: APIClient
    @State private var messages: [Message] = []
    @State private var isLoading = false
    @State private var error: Error?
    
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
                
                // Messages section
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Recent Messages")
                            .font(.headline)
                        Spacer()
                        if isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        }
                    }
                    
                    if let error = error {
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
                                    await loadMessages()
                                }
                            }
                            .buttonStyle(.bordered)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                    } else if messages.isEmpty && !isLoading {
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
                            ForEach(messages) { message in
                                MessageRow(message: message)
                            }
                        }
                    }
                }
                .padding()
            }
            .padding()
        }
        .navigationTitle(chat.displayName)
        .task {
            await loadMessages()
        }
    }
    
    private func loadMessages() async {
        isLoading = true
        error = nil
        
        do {
            messages = try await apiClient.getRecentMessages(chatId: chat.id)
        } catch {
            self.error = error
        }
        
        isLoading = false
    }
}

struct MessageRow: View {
    let message: Message
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                if let sender = message.sender {
                    Text(sender)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                } else {
                    Text("Unknown")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                }
                
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
                .textSelection(.enabled)
            
            if message.hasSpotifyLink, let spotifyUrl = message.spotifyUrl {
                HStack {
                    Image(systemName: "music.note")
                        .foregroundColor(.green)
                    Link("Open in Spotify", destination: URL(string: spotifyUrl)!)
                        .font(.caption)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
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
        ))
        .environmentObject(APIClient())
    }
}

