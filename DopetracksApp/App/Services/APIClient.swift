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
        // Allow longer searches (message content/filters can be slow on large DBs)
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 240
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Health Check
    
    func checkHealth() async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/health") else {
            throw APIError.invalidURL
        }
        let (_, response) = try await session.data(from: url)
        
        if let httpResponse = response as? HTTPURLResponse {
            return httpResponse.statusCode == 200
        }
        return false
    }
    
    // MARK: - Spotify OAuth
    
    func getClientID() async throws -> String {
        guard let url = URL(string: "\(baseURL)/get-client-id") else {
            throw APIError.invalidURL
        }
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder().decode(ClientIDResponse.self, from: data)
        return response.clientId
    }
    
    // MARK: - Chat Search
    
    func getAllChats() async throws -> [Chat] {
        guard let url = URL(string: "\(baseURL)/chats") else {
            throw APIError.invalidURL
        }
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            if let detail = decodeDetail(from: data) {
                throw APIError.httpErrorWithMessage(httpResponse.statusCode, detail)
            }
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        // API returns array directly
        let chats = try JSONDecoder().decode([Chat].self, from: data)
        return chats
    }
    
    func searchChats(query: String) async throws -> [Chat] {
        guard var components = URLComponents(string: "\(baseURL)/chat-search-prepared") else {
            throw APIError.invalidURL
        }
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
        // Use the streaming-capable endpoint so the UI can render results as they arrive.
        guard var components = URLComponents(string: "\(baseURL)/chat-search-advanced") else {
            throw APIError.invalidURL
        }
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
    
    func getMessages(
        chatId: String,
        limit: Int = 50,
        offset: Int = 0,
        order: MessageSortOrder = .newestFirst,
        search: String? = nil
    ) async throws -> [Message] {
        guard var components = URLComponents(string: "\(baseURL)/chat/\(chatId)/recent-messages") else {
            throw APIError.invalidURL
        }
        var items: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: "\(limit)"),
            URLQueryItem(name: "offset", value: "\(offset)"),
            URLQueryItem(name: "order", value: order.rawValue)
        ]
        if let search, !search.isEmpty {
            items.append(URLQueryItem(name: "search", value: search))
        }
        components.queryItems = items
        
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
        guard let url = URL(string: "\(baseURL)/create-playlist-optimized-stream") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        // Backend expects selected_chat_ids as a JSON string inside form data
        let chatIdInts = chatIds.compactMap { Int($0) }
        let chatIdsJSON = String(
            data: try JSONSerialization.data(withJSONObject: chatIdInts),
            encoding: .utf8
        ) ?? "[]"
        
        var formItems: [URLQueryItem] = [
            URLQueryItem(name: "playlist_name", value: playlistName),
            URLQueryItem(name: "selected_chat_ids", value: chatIdsJSON),
            URLQueryItem(name: "start_date", value: startDate?.ISO8601Format() ?? ""),
            URLQueryItem(name: "end_date", value: endDate?.ISO8601Format() ?? "")
        ]
        // Optional existing playlist support in the future
        request.httpBody = formEncodedBody(from: formItems)
        
        // Consume streaming Server-Sent Events until we get a complete event
        let (bytes, response) = try await session.bytes(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        var finalEvent: PlaylistStreamEvent?
        
        for try await line in bytes.lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            
            // Skip keep-alive/newline chatter
            if trimmed.isEmpty { continue }
            guard trimmed.hasPrefix("data: ") else { continue }
            
            let jsonString = String(trimmed.dropFirst(6)) // Remove "data: "
            guard let jsonData = jsonString.data(using: .utf8) else { continue }
            
            do {
                let event = try JSONDecoder().decode(PlaylistStreamEvent.self, from: jsonData)

                if let status = event.status?.lowercased() {
                    if status == "error" {
                        throw APIError.httpErrorWithMessage(
                            httpResponse.statusCode,
                            event.message ?? "Unknown error creating playlist"
                        )
                    }

                    if status == "complete" {
                        finalEvent = event
                    }
                }
            } catch let apiError as APIError {
                // Re-throw API errors so they surface to the user
                throw apiError
            } catch {
                // Log and continue on non-critical decode issues so we can keep consuming the stream
                print("⚠️ Failed to decode playlist event: \(error)")
            }
        }
        
        guard let event = finalEvent else {
            throw APIError.invalidResponse
        }
        
        if let playlist = event.playlist {
            return playlist
        }
        
        // Fallback: construct a minimal playlist from the final event payload
        return Playlist(
            id: event.playlistId ?? UUID().uuidString,
            name: event.playlistName ?? playlistName,
            spotifyId: event.playlistId,
            spotifyUrl: event.playlistUrl,
            trackCount: event.tracksAdded ?? 0,
            createdAt: Date(),
            chatIds: chatIds
        )
    }
    
    private func formEncodedBody(from items: [URLQueryItem]) -> Data? {
        var components = URLComponents()
        components.queryItems = items
        return components.percentEncodedQuery?.data(using: .utf8)
    }
    
    // MARK: - User Profile
    
    func getUserProfile() async throws -> SpotifyProfile {
        guard let url = URL(string: "\(baseURL)/user-profile") else {
            throw APIError.invalidURL
        }
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
        guard let url = URL(string: "\(baseURL)/open-full-disk-access") else {
            throw APIError.invalidURL
        }
        let (_, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
    
    func getUserPlaylists() async throws -> [Playlist] {
        guard let url = URL(string: "\(baseURL)/user-playlists") else {
            throw APIError.invalidURL
        }
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
    case httpErrorWithMessage(Int, String)
    case decodingError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let code):
            return "HTTP error: \(code)"
        case .httpErrorWithMessage(let code, let message):
            return "HTTP \(code): \(message)"
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

fileprivate struct PlaylistStreamEvent: Decodable {
    let status: String?
    let stage: String?
    let message: String?
    let progress: Int?
    let tracksAdded: Int?
    let totalTracksFound: Int?
    let playlistId: String?
    let playlistName: String?
    let playlistUrl: String?
    let playlist: Playlist?
    let chatIds: [String]?
    
    enum CodingKeys: String, CodingKey {
        case status
        case stage
        case message
        case progress
        case tracksAdded = "tracks_added"
        case totalTracksFound = "total_tracks_found"
        case playlistId = "playlist_id"
        case playlistName = "playlist_name"
        case playlistUrl = "playlist_url"
        case playlist
        case chatIds = "chat_ids"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        status = try container.decodeIfPresent(String.self, forKey: .status)
        stage = try container.decodeIfPresent(String.self, forKey: .stage)
        message = try container.decodeIfPresent(String.self, forKey: .message)
        progress = try container.decodeIfPresent(Int.self, forKey: .progress)
        tracksAdded = try container.decodeIfPresent(Int.self, forKey: .tracksAdded)
        totalTracksFound = try container.decodeIfPresent(Int.self, forKey: .totalTracksFound)
        playlistId = try container.decodeIfPresent(String.self, forKey: .playlistId)
        playlistName = try container.decodeIfPresent(String.self, forKey: .playlistName)
        playlistUrl = try container.decodeIfPresent(String.self, forKey: .playlistUrl)
        playlist = try container.decodeIfPresent(Playlist.self, forKey: .playlist)
        
        if let stringIds = try? container.decode([String].self, forKey: .chatIds) {
            chatIds = stringIds
        } else if let intIds = try? container.decode([Int].self, forKey: .chatIds) {
            chatIds = intIds.map { String($0) }
        } else {
            chatIds = nil
        }
    }
}

private struct APIErrorDetail: Decodable {
    let detail: String
}

private func decodeDetail(from data: Data) -> String? {
    guard let detail = try? JSONDecoder().decode(APIErrorDetail.self, from: data).detail else {
        return nil
    }
    return detail
}

