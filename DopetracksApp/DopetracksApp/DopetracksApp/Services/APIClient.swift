//
//  APIClient.swift
//  DopetracksApp
//
//  HTTP client for communicating with FastAPI backend
//

import Foundation

class APIClient: ObservableObject {
    let baseURL = "http://127.0.0.1:8888"
    
    private let session: URLSession
    
    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Health Check
    
    func checkHealth() async throws -> Bool {
        let url = URL(string: "\(baseURL)/health")!
        let (_, response) = try await session.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse {
            return httpResponse.statusCode == 200
        }
        return false
    }
    
    // MARK: - Spotify OAuth
    
    func getClientID() async throws -> String {
        let url = URL(string: "\(baseURL)/get-client-id")!
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder().decode(ClientIDResponse.self, from: data)
        return response.clientId
    }
    
    // MARK: - Chat Search
    
    func getAllChats() async throws -> [Chat] {
        let url = URL(string: "\(baseURL)/chats")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        // API returns array directly
        let chats = try JSONDecoder().decode([Chat].self, from: data)
        return chats
    }
    
    func searchChats(query: String) async throws -> [Chat] {
        var components = URLComponents(string: "\(baseURL)/chat-search-optimized")!
        components.queryItems = [URLQueryItem(name: "query", value: query)]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        // API returns array directly, not wrapped in an object
        let chats = try JSONDecoder().decode([Chat].self, from: data)
        return chats
    }
    
    func advancedSearch(filters: SearchFilters, stream: Bool = true) async throws -> AsyncThrowingStream<Chat, Error> {
        var components = URLComponents(string: "\(baseURL)/chat-search-advanced")!
        var queryItems = filters.toQueryItems()
        queryItems.append(URLQueryItem(name: "stream", value: stream ? "true" : "false"))
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        if stream {
            // Streaming mode: return results as they arrive
            return AsyncThrowingStream { continuation in
                let task = Task {
                    do {
                        let (asyncBytes, response) = try await session.bytes(from: url)
                        
                        guard let httpResponse = response as? HTTPURLResponse else {
                            continuation.finish(throwing: APIError.invalidResponse)
                            return
                        }
                        
                        guard httpResponse.statusCode == 200 else {
                            continuation.finish(throwing: APIError.httpError(httpResponse.statusCode))
                            return
                        }
                        
                        // Parse Server-Sent Events
                        var lineCount = 0
                        for try await line in asyncBytes.lines {
                            // Check for cancellation
                            try Task.checkCancellation()
                            
                            lineCount += 1
                            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                            
                            // Skip empty lines
                            if trimmed.isEmpty {
                                continue
                            }
                            
                            if trimmed.hasPrefix("data: ") {
                                let jsonString = String(trimmed.dropFirst(6)) // Remove "data: "
                                
                                guard let jsonData = jsonString.data(using: .utf8) else {
                                    print("⚠️ Could not convert JSON string to data: \(jsonString.prefix(100))")
                                    continue
                                }
                                
                                // Inspect JSON to handle status vs chat
                                if let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] {
                                    if let status = json["status"] as? String, status.lowercased() == "complete" {
                                        print("📡 Stream completed")
                                        continuation.finish()
                                        return
                                    }
                                    
                                    // Skip non-chat payloads
                                    if json["chat_id"] == nil {
                                        // Not a chat object, ignore
                                        continue
                                    }
                                }
                                
                                // Try to decode as Chat
                                do {
                                    let chat = try JSONDecoder().decode(Chat.self, from: jsonData)
                                    print("📡 Decoded chat: \(chat.displayName)")
                                    continuation.yield(chat)
                                } catch {
                                    // Log decoding errors for debugging
                                    print("❌ Failed to decode chat from JSON: \(error)")
                                    print("❌ JSON string (first 300 chars): \(String(jsonString.prefix(300)))")
                                    if let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] {
                                        let keys = json.keys.joined(separator: ", ")
                                        print("❌ JSON keys: \(keys)")
                                    }
                                }
                            } else {
                                // Log non-data lines for debugging
                                if lineCount <= 5 {
                                    print("📡 Non-data line: \(trimmed.prefix(50))")
                                }
                            }
                        }
                        print("📡 Stream ended (no more lines)")
                        continuation.finish()
                    } catch is CancellationError {
                        continuation.finish(throwing: CancellationError())
                    } catch {
                        continuation.finish(throwing: error)
                    }
                }
                
                continuation.onTermination = { @Sendable _ in
                    task.cancel()
                }
            }
        } else {
            // Non-streaming mode: return all results at once
            return AsyncThrowingStream { continuation in
                Task {
                    do {
                        let (data, response) = try await session.data(from: url)
                        
                        guard let httpResponse = response as? HTTPURLResponse else {
                            continuation.finish(throwing: APIError.invalidResponse)
                            return
                        }
                        
                        guard httpResponse.statusCode == 200 else {
                            continuation.finish(throwing: APIError.httpError(httpResponse.statusCode))
                            return
                        }
                        
                        let chats = try JSONDecoder().decode([Chat].self, from: data)
                        for chat in chats {
                            continuation.yield(chat)
                        }
                        continuation.finish()
                    } catch {
                        continuation.finish(throwing: error)
                    }
                }
            }
        }
    }
    
    func getRecentMessages(chatId: String) async throws -> [Message] {
        let url = URL(string: "\(baseURL)/chat/\(chatId)/recent-messages")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        let messagesResponse = try JSONDecoder().decode(MessagesResponse.self, from: data)
        return messagesResponse.messages
    }
    
    // MARK: - Playlist Creation
    
    func createPlaylist(
        chatIds: [String],
        startDate: Date?,
        endDate: Date?,
        playlistName: String
    ) async throws -> Playlist {
        let url = URL(string: "\(baseURL)/create-playlist-optimized-stream")!
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "chat_ids": chatIds,
            "start_date": startDate?.ISO8601Format() ?? "",
            "end_date": endDate?.ISO8601Format() ?? "",
            "playlist_name": playlistName
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode(Playlist.self, from: data)
    }
    
    // MARK: - User Profile
    
    func getUserProfile() async throws -> SpotifyProfile {
        let url = URL(string: "\(baseURL)/user-profile")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode(SpotifyProfile.self, from: data)
    }
    
    func openFullDiskAccess() async throws {
        let url = URL(string: "\(baseURL)/open-full-disk-access")!
        let (_, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
    
    func getUserPlaylists() async throws -> [Playlist] {
        let url = URL(string: "\(baseURL)/user-playlists")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        let playlistsResponse = try JSONDecoder().decode(PlaylistsResponse.self, from: data)
        return playlistsResponse.playlists
    }
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(Int)
    case decodingError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let code):
            return "HTTP error: \(code)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        }
    }
}

// MARK: - Response Models

struct ClientIDResponse: Codable {
    let clientId: String
    
    enum CodingKeys: String, CodingKey {
        case clientId = "client_id"
    }
}

// ChatSearchResponse removed - API returns array directly

struct MessagesResponse: Decodable {
    let messages: [Message]
}

struct PlaylistsResponse: Decodable {
    let playlists: [Playlist]
}

