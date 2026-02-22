//
//  ClickLogger.swift
//  DopetracksApp
//
//  Logs all mouse click events while the app is running.
//

import Foundation
import AppKit
import OSLog
import ApplicationServices

final class ClickLogger {
    static let shared = ClickLogger()
    
    private let logger = Logger(subsystem: "com.dopetracks.app", category: "clicks")
    private var globalMonitor: Any?
    private let syncQueue = DispatchQueue(label: "com.dopetracks.clicklogger")
    private var enabled: Bool {
        // Opt-in via env var to avoid impacting users by default
        ProcessInfo.processInfo.environment["ENABLE_CLICK_LOGGER"] == "1"
    }
    
    func start() {
        guard enabled else { return }
        guard hasAccessibilityPermission() else {
            logger.error("click_logger_disabled_missing_accessibility")
            return
        }
        syncQueue.sync {
            guard globalMonitor == nil else { return }
            
            globalMonitor = NSEvent.addGlobalMonitorForEvents(
                matching: [.leftMouseDown, .rightMouseDown, .otherMouseDown]
            ) { [weak self] event in
                self?.log(event: event, scope: "global")
            }
        }
    }
    
    func stop() {
        syncQueue.sync {
            if let monitor = globalMonitor {
                NSEvent.removeMonitor(monitor)
                globalMonitor = nil
            }
        }
    }
    
    private func log(event: NSEvent, scope: String) {
        let location = event.locationInWindow
        logger.info(
            "mouse_click scope=\(scope, privacy: .public) type=\(event.type.rawValue, privacy: .public) button=\(event.buttonNumber, privacy: .public) count=\(event.clickCount, privacy: .public) x=\(location.x, privacy: .public) y=\(location.y, privacy: .public) window=\(event.windowNumber, privacy: .public)"
        )
    }
    
    private func hasAccessibilityPermission() -> Bool {
        // Global event monitors require Accessibility permission. Prompt once if not granted.
        let options = [kAXTrustedCheckOptionPrompt.takeRetainedValue() as String: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(options)
    }
}

