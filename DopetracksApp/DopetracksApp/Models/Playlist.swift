//
//  Playlist.swift
//  DopetracksApp
//
//  Playlist model matching FastAPI response
//

import Foundation

struct Playlist: Identifiable, Codable {
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
        case spotifyId = "spotify_id"
        case spotifyUrl = "spotify_url"
        case trackCount = "track_count"
        case createdAt = "created_at"
        case chatIds = "chat_ids"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        spotifyId = try? container.decode(String.self, forKey: .spotifyId)
        spotifyUrl = try? container.decode(String.self, forKey: .spotifyUrl)
        trackCount = try container.decode(Int.self, forKey: .trackCount)
        
        if let dateString = try? container.decode(String.self, forKey: .createdAt) {
            let formatter = ISO8601DateFormatter()
            createdAt = formatter.date(from: dateString)
        } else {
            createdAt = nil
        }
        
        chatIds = try container.decode([String].self, forKey: .chatIds)
    }
}

