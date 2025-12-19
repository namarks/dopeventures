//
//  Message.swift
//  DopetracksApp
//
//  Message model matching FastAPI response
//

import Foundation

struct Message: Identifiable, Codable {
    let id: String
    let text: String
    let date: Date
    let sender: String?
    let hasSpotifyLink: Bool
    let spotifyUrl: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case text
        case date
        case sender
        case hasSpotifyLink = "has_spotify_link"
        case spotifyUrl = "spotify_url"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        text = try container.decode(String.self, forKey: .text)
        
        let dateString = try container.decode(String.self, forKey: .date)
        let formatter = ISO8601DateFormatter()
        guard let parsedDate = formatter.date(from: dateString) else {
            throw DecodingError.dataCorruptedError(forKey: .date, in: container, debugDescription: "Invalid date format")
        }
        date = parsedDate
        
        sender = try? container.decode(String.self, forKey: .sender)
        hasSpotifyLink = try container.decode(Bool.self, forKey: .hasSpotifyLink)
        spotifyUrl = try? container.decode(String.self, forKey: .spotifyUrl)
    }
}

