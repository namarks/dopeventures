//
//  Chat.swift
//  DopetracksApp
//
//  Chat model matching FastAPI response
//

import Foundation

struct Chat: Identifiable, Codable, Hashable {
    let id: String
    let displayName: String
    let participantCount: Int
    let messageCount: Int
    let lastMessageDate: Date?
    let hasSpotifyLinks: Bool
    
    enum CodingKeys: String, CodingKey {
        case id = "chat_id"
        case displayName = "display_name"
        case participantCount = "participant_count"
        case messageCount = "message_count"
        case lastMessageDate = "last_message_date"
        case hasSpotifyLinks = "has_spotify_links"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        displayName = try container.decode(String.self, forKey: .displayName)
        participantCount = try container.decode(Int.self, forKey: .participantCount)
        messageCount = try container.decode(Int.self, forKey: .messageCount)
        
        // Handle optional date
        if let dateString = try? container.decode(String.self, forKey: .lastMessageDate) {
            let formatter = ISO8601DateFormatter()
            lastMessageDate = formatter.date(from: dateString)
        } else {
            lastMessageDate = nil
        }
        
        hasSpotifyLinks = try container.decode(Bool.self, forKey: .hasSpotifyLinks)
    }
}

