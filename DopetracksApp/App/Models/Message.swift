//
//  Message.swift
//  DopetracksApp
//
//  Message model matching FastAPI response
//

import Foundation

enum MessageSortOrder: String, CaseIterable, Codable {
    case newestFirst = "desc"
    case oldestFirst = "asc"
    
    var label: String {
        switch self {
        case .newestFirst: return "Newest"
        case .oldestFirst: return "Oldest"
        }
    }
}

struct Message: Identifiable, Decodable {
    let id: String
    let text: String
    let date: Date
    let sender: String?
    let isFromMe: Bool
    let hasSpotifyLink: Bool
    let spotifyUrl: String?
    let reactions: [Reaction]

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        return formatter
    }()

    // Computed for UI
    var displaySender: String {
        if isFromMe { return "You" }
        return sender?.isEmpty == false ? sender! : "Unknown"
    }
    
    var initials: String {
        let components = displaySender
            .split(separator: " ")
            .map { String($0) }
        let first = components.first?.prefix(1) ?? ""
        let second = components.dropFirst().first?.prefix(1) ?? ""
        let candidate = (first + second)
        if candidate.isEmpty, let c = displaySender.first {
            return String(c)
        }
        return candidate.uppercased()
    }
    
    enum CodingKeys: String, CodingKey {
        case text
        case date
        case senderName = "sender_name"
        case senderFullName = "sender_full_name"
        case isFromMe = "is_from_me"
        case hasSpotifyLink = "has_spotify_link"
        case spotifyUrl = "spotify_url"
        case reactions
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        let textValue = try container.decode(String.self, forKey: .text)
        let dateString = try container.decode(String.self, forKey: .date)
        // Use a hash of the full text + date for a collision-resistant id
        let hashValue = abs("\(textValue)_\(dateString)".hashValue)
        self.id = "\(dateString)_\(hashValue)"

        self.text = textValue

        guard let parsedDate = Message.dateFormatter.date(from: dateString) else {
            throw DecodingError.dataCorruptedError(forKey: .date, in: container, debugDescription: "Invalid date format: \(dateString)")
        }
        self.date = parsedDate
        
        // Use sender_full_name if available, otherwise sender_name
        if let fullName = try? container.decode(String.self, forKey: .senderFullName), !fullName.isEmpty {
            self.sender = fullName
        } else if let name = try? container.decode(String.self, forKey: .senderName), !name.isEmpty {
            self.sender = name
        } else {
            self.sender = nil
        }
        
        self.isFromMe = (try? container.decode(Bool.self, forKey: .isFromMe)) ?? false
        
        // These fields may not be in the API response, default to false/nil
        self.hasSpotifyLink = (try? container.decode(Bool.self, forKey: .hasSpotifyLink)) ?? false
        self.spotifyUrl = try? container.decode(String.self, forKey: .spotifyUrl)
        self.reactions = (try? container.decode([Reaction].self, forKey: .reactions)) ?? []
    }
}

struct Reaction: Identifiable, Decodable {
    let id: String
    let type: String
    let sender: String
    let isFromMe: Bool
    let date: Date
    
    enum CodingKeys: String, CodingKey {
        case type
        case sender
        case isFromMe = "is_from_me"
        case date
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.type = try container.decode(String.self, forKey: .type)
        self.sender = try container.decode(String.self, forKey: .sender)
        self.isFromMe = (try? container.decode(Bool.self, forKey: .isFromMe)) ?? false
        let dateString = try container.decode(String.self, forKey: .date)

        guard let parsedDate = Message.dateFormatter.date(from: dateString) else {
            throw DecodingError.dataCorruptedError(forKey: .date, in: container, debugDescription: "Invalid date format: \(dateString)")
        }
        self.date = parsedDate

        self.id = "\(type)_\(sender)_\(dateString)"
    }
}

