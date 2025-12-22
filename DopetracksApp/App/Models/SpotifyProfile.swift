//
//  SpotifyProfile.swift
//  DopetracksApp
//
//  Spotify user profile model
//

import Foundation

struct SpotifyProfile: Codable {
    let id: String
    let displayName: String
    let email: String?
    let imageUrl: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case email
        case imageUrl = "image_url"
    }
}

