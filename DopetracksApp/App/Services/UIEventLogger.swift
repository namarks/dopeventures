//
//  UIEventLogger.swift
//  DopetracksApp
//
//  Lightweight app-side UI event logging (no global event taps).
//

import Foundation
import OSLog

final class UIEventLogger {
    static let shared = UIEventLogger()
    private let logger = Logger(subsystem: "com.dopetracks.app", category: "ui")
    
    private init() {}
    
    func log(_ event: String, metadata: [String: CustomStringConvertible]? = nil) {
        var message = "ui_event name=\(event)"
        if let metadata = metadata {
            for (key, value) in metadata {
                message.append(" \(key)=\(value)")
            }
        }
        logger.info("\(message, privacy: .public)")
    }
}

