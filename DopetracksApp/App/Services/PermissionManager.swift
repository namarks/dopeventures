//
//  PermissionManager.swift
//  DopetracksApp
//
//  Manages Full Disk Access permission requests
//

import Foundation
import AppKit

class PermissionManager {
    static let shared = PermissionManager()
    
    private init() {}
    
    /// Check if we have Full Disk Access by attempting to read the Messages database
    /// This will trigger the macOS permission prompt if not already granted
    func checkFullDiskAccess() -> Bool {
        let messagesPath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library")
            .appendingPathComponent("Messages")
            .appendingPathComponent("chat.db")
        
        // Try to access the file - this will trigger the permission prompt if not granted
        do {
            // Try to read the file attributes - this triggers the permission check
            let _ = try FileManager.default.attributesOfItem(atPath: messagesPath.path)
            
            // If we got here, try to actually open the file
            if let fileHandle = FileHandle(forReadingAtPath: messagesPath.path) {
                fileHandle.closeFile()
                return true
            }
        } catch {
            // Permission denied or file doesn't exist
            // The system should have shown a permission prompt
            print("Permission check failed: \(error.localizedDescription)")
        }
        
        // Also try to check if we can read the Messages directory
        let messagesDir = messagesPath.deletingLastPathComponent()
        do {
            let _ = try FileManager.default.contentsOfDirectory(atPath: messagesDir.path)
            return true
        } catch {
            // Permission denied - this should trigger the system prompt
            print("Cannot access Messages directory: \(error.localizedDescription)")
            return false
        }
    }
    
    /// Open System Settings to Full Disk Access
    func openFullDiskAccessSettings() {
        // Try the modern Settings deep links first; fall back to the pane if needed.
        let candidates = [
            "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",        // macOS 13/14/15
            "x-apple.systempreferences:com.apple.preference.security?Privacy_FullDiskAccess",  // older variants
            "x-apple.systempreferences:com.apple.preference.security"                          // generic Security & Privacy
        ]
        
        for candidate in candidates {
            if let url = URL(string: candidate), NSWorkspace.shared.open(url) {
                return
            }
        }
        
        // Last resort: open the Security pref pane directly
        let prefPane = URL(fileURLWithPath: "/System/Library/PreferencePanes/Security.prefPane")
        NSWorkspace.shared.open(prefPane)
    }
}

