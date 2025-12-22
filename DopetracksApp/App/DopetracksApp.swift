//
//  DopetracksApp.swift
//  DopetracksApp
//
//  Main application entry point for native macOS app
//

import SwiftUI

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
                    if newPhase == .inactive || newPhase == .background {
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

