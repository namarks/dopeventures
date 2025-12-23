//
//  Playlist.swift
//  DopetracksApp
//
//  Playlist model matching Spotify API response
//

import Foundation

struct Playlist: Identifiable, Decodable {
    let id: String
    let name: String
    let spotifyId: String?
    let spotifyUrl: String?
    let trackCount: Int
    let createdAt: Date?
    let chatIds: [String]
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case tracks
        case externalUrls = "external_urls"
        case spotifyId = "spotify_id"
        case spotifyUrl = "spotify_url"
        case trackCount = "track_count"
        case createdAt = "created_at"
        case chatIds = "chat_ids"
    }
    
    struct TracksInfo: Decodable {
        let total: Int
    }
    
    struct ExternalUrls: Decodable {
        let spotify: String?
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // id and name come directly from Spotify
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        
        // spotify_id is the same as id for Spotify playlists
        spotifyId = id
        
        // Get spotify_url from external_urls.spotify
        if let externalUrls = try? container.decode(ExternalUrls.self, forKey: .externalUrls) {
            spotifyUrl = externalUrls.spotify
        } else {
            // Fallback to spotify_url field if it exists
        spotifyUrl = try? container.decode(String.self, forKey: .spotifyUrl)
        }
        
        // Get track count from tracks.total
        if let tracksInfo = try? container.decode(TracksInfo.self, forKey: .tracks) {
            trackCount = tracksInfo.total
        } else {
            // Fallback to track_count field if it exists
            trackCount = (try? container.decode(Int.self, forKey: .trackCount)) ?? 0
        }
        
        // created_at might not exist in Spotify API response
        if let dateString = try? container.decode(String.self, forKey: .createdAt) {
            let formatter = ISO8601DateFormatter()
            createdAt = formatter.date(from: dateString)
        } else {
            createdAt = nil
        }
        
        // chat_ids won't exist in Spotify API response, default to empty array
        if let stringIds = try? container.decode([String].self, forKey: .chatIds) {
            chatIds = stringIds
        } else if let intIds = try? container.decode([Int].self, forKey: .chatIds) {
            chatIds = intIds.map { String($0) }
        } else {
            chatIds = []
        }
    }
    
    init(
        id: String,
        name: String,
        spotifyId: String?,
        spotifyUrl: String?,
        trackCount: Int,
        createdAt: Date?,
        chatIds: [String]
    ) {
        self.id = id
        self.name = name
        self.spotifyId = spotifyId
        self.spotifyUrl = spotifyUrl
        self.trackCount = trackCount
        self.createdAt = createdAt
        self.chatIds = chatIds
    }
}

