//
//  DopetracksApp.swift
//  DopetracksApp
//
//  Main application entry point for native macOS app
//

import SwiftUI
import AppKit

@main
struct DopetracksApp: App {
    @StateObject private var backendManager = BackendManager()
    @StateObject private var apiClient: APIClient
    @StateObject private var chatListViewModel: ChatListViewModel
    @Environment(\.scenePhase) private var scenePhase
    
    init() {
        let api = APIClient()
        _apiClient = StateObject(wrappedValue: api)
        _chatListViewModel = StateObject(wrappedValue: ChatListViewModel(apiClient: api))
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView(chatListViewModel: chatListViewModel)
                .environmentObject(backendManager)
                .environmentObject(apiClient)
                .onAppear {
                    // Start backend when app launches
                    Task {
                        await backendManager.startBackend()
                    }
                }
                .onChange(of: scenePhase) { newPhase in
                    // Only stop backend when app is fully backgrounded or terminated.
                    // On macOS, .inactive fires on every window focus loss, which would
                    // kill the backend whenever the user switches apps.
                    if newPhase == .background {
                        backendManager.stopBackend()
                    }
                }
        }
        .commands {
            // Add native menu bar commands
            CommandGroup(replacing: .appInfo) {
                Button("About Dopetracks") {
                    // Show about window
                }
            }
        }
    }
}

