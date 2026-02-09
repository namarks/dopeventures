//
//  Chat.swift
//  DopetracksApp
//
//  Chat model matching FastAPI response
//

import Foundation

struct Chat: Identifiable, Decodable, Hashable {
    let id: String
    let displayName: String
    let participantCount: Int
    let messageCount: Int
    let lastMessageDate: Date?
    let hasSpotifyLinks: Bool

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()

    enum CodingKeys: String, CodingKey {
        case chatId = "chat_id"
        case name
        case members
        case totalMessages = "total_messages"
        case lastMessageDate = "last_message_date"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        
        // chat_id comes as Int from backend, convert to String
        let chatIdInt = try container.decode(Int.self, forKey: .chatId)
        id = String(chatIdInt)
        
        // name maps to displayName
        displayName = try container.decode(String.self, forKey: .name)
        
        // members maps to participantCount
        participantCount = try container.decode(Int.self, forKey: .members)
        
        // total_messages maps to messageCount
        messageCount = try container.decode(Int.self, forKey: .totalMessages)
        
        // Handle optional date - backend uses format "YYYY-MM-DD HH:MM:SS"
        if let dateString = try? container.decode(String.self, forKey: .lastMessageDate) {
            lastMessageDate = Chat.dateFormatter.date(from: dateString)
        } else {
            lastMessageDate = nil
        }
        
        // has_spotify_links is not in the API response, default to false
        // We could check this later when needed
        hasSpotifyLinks = false
    }
    
    // Memberwise initializer for testing/preview purposes
    init(id: String, displayName: String, participantCount: Int, messageCount: Int, lastMessageDate: Date?, hasSpotifyLinks: Bool) {
        self.id = id
        self.displayName = displayName
        self.participantCount = participantCount
        self.messageCount = messageCount
        self.lastMessageDate = lastMessageDate
        self.hasSpotifyLinks = hasSpotifyLinks
    }
}

