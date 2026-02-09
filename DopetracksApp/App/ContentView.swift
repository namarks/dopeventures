//
//  ContentView.swift
//  DopetracksApp
//
//  Main content view with navigation
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var backendManager: BackendManager
    @EnvironmentObject var apiClient: APIClient
    @ObservedObject var chatListViewModel: ChatListViewModel
    @State private var selectedTab = 0
    @State private var startupComplete = false
    
    var body: some View {
        Group {
            if startupComplete {
                TabView(selection: $selectedTab) {
                    ChatListView(viewModel: chatListViewModel)
                        .tabItem {
                            Label("Chats", systemImage: "message.fill")
                        }
                        .tag(0)
                    
                    PlaylistListView(apiClient: apiClient)
                        .tabItem {
                            Label("Playlists", systemImage: "music.note.list")
                        }
                        .tag(1)
                    
                    SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                        .tag(2)
                }
            } else {
                StartupView(
                    backendManager: backendManager,
                    chatListViewModel: chatListViewModel,
                    onChatsLoaded: { startupComplete = true },
                    loadChats: loadChatsForStartup
                )
            }
        }
    }
    
    private func loadChatsForStartup() async -> Bool {
        await chatListViewModel.loadAllChats()
        return true
    }
}

#Preview {
    let api = APIClient()
    let vm = ChatListViewModel(apiClient: api)
    return ContentView(chatListViewModel: vm)
        .environmentObject(BackendManager())
        .environmentObject(api)
}

