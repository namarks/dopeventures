//
//  PlaylistListViewModel.swift
//  DopetracksApp
//
//  ViewModel for playlists
//

import Foundation

@MainActor
final class PlaylistListViewModel: ObservableObject {
    @Published var playlists: [Playlist] = []
    @Published var isLoading = false
    @Published var error: Error?
    private var hasLoadedOnce = false
    
    private let apiClient: APIClient
    
    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }
    
    func onAppear() {
        guard !hasLoadedOnce else { return }
        hasLoadedOnce = true
        Task { await loadPlaylists() }
    }
    
    func loadPlaylists() async {
        isLoading = true
        error = nil
        do {
            playlists = try await apiClient.getUserPlaylists()
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

