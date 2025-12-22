//
//  SearchFilters.swift
//  DopetracksApp
//
//  Model for advanced search filters
//

import Foundation

struct SearchFilters: Equatable {
    var query: String = ""
    var startDate: Date?
    var endDate: Date?
    var participantNames: [String] = []
    var messageContent: String = ""
    
    var hasFilters: Bool {
        !query.isEmpty || startDate != nil || endDate != nil || !participantNames.isEmpty || !messageContent.isEmpty
    }
    
    func toQueryItems() -> [URLQueryItem] {
        var items: [URLQueryItem] = []
        
        if !query.isEmpty {
            items.append(URLQueryItem(name: "query", value: query))
        }
        
        if let startDate = startDate {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withFullDate]
            items.append(URLQueryItem(name: "start_date", value: formatter.string(from: startDate)))
        }
        
        if let endDate = endDate {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withFullDate]
            items.append(URLQueryItem(name: "end_date", value: formatter.string(from: endDate)))
        }
        
        if !participantNames.isEmpty {
            items.append(URLQueryItem(name: "participant_names", value: participantNames.joined(separator: ",")))
        }
        
        if !messageContent.isEmpty {
            items.append(URLQueryItem(name: "message_content", value: messageContent))
        }
        
        return items
    }
}

