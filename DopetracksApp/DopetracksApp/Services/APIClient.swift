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
    
    func getUserPlaylists() async throws -> [Playlist] {
        let url = URL(string: "\(baseURL)/user-playlists")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode([Playlist].self, from: data)
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

struct MessagesResponse: Codable {
    let messages: [Message]
}

