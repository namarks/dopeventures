//
//  ChatListViewModel.swift
//  DopetracksApp
//
//  ViewModel for chat list and search (MVVM)
//

import Foundation
import SwiftUI

@MainActor
final class ChatListViewModel: ObservableObject {
    @Published var searchText: String = ""
    @Published var chats: [Chat] = []
    @Published var isLoading = false
    @Published var error: Error?
    @Published var selectedChats: Set<Chat.ID> = []
    @Published var selectedChatId: Chat.ID?
    @Published var hasFullDiskAccess = false
    @Published var searchFilters = SearchFilters()
    @Published var hasLoadedOnce = false
    
    private var currentSearchTask: Task<Void, Never>?
    let apiClient: APIClient
    
    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }
    
    func onAppear() {
        guard !hasLoadedOnce else { return }
        checkPermissions()
        Task { await loadAllChats() }
        hasLoadedOnce = true
    }
    
    func onSearchTextChange(_ newValue: String) {
        if searchFilters.startDate != nil ||
            searchFilters.endDate != nil ||
            !searchFilters.participantNames.isEmpty ||
            !searchFilters.messageContent.isEmpty {
            searchFilters.query = newValue
        }
        
        if !newValue.isEmpty || searchFilters.hasFilters {
            Task { await performSearch() }
        } else {
            chats = []
            selectedChatId = nil
        }
    }
    
    func clearFilters() {
        searchFilters = SearchFilters()
        searchText = ""
        Task { await loadAllChats() }
    }
    
    func refreshPermissions() {
        checkPermissions()
    }
    
    func loadAllChats() async {
        isLoading = true
        error = nil
        do {
            let fetched = try await apiClient.getAllChats()
            chats = sortChats(fetched)
        } catch {
            self.error = error
        }
        isLoading = false
    }
    
    func performSearch() async {
        currentSearchTask?.cancel()
        
        let task = Task {
            await MainActor.run {
                isLoading = true
                error = nil
                chats = []
            }
            do {
                try Task.checkCancellation()
                
                let hasOnlyTextQuery = !searchText.isEmpty &&
                    searchFilters.startDate == nil &&
                    searchFilters.endDate == nil &&
                    searchFilters.participantNames.isEmpty &&
                    searchFilters.messageContent.isEmpty
                
                if hasOnlyTextQuery {
                    var filters = SearchFilters()
                    filters.query = searchText
                    filters.messageContent = searchText
                    
                    var newChats: [Chat] = []
                    let stream = try await apiClient.advancedSearch(filters: filters, stream: true)
                    for try await chat in stream {
                        try Task.checkCancellation()
                        newChats.append(chat)
                        await MainActor.run { chats = sortChats(newChats) }
                    }
                    await MainActor.run {
                        chats = sortChats(newChats)
                        isLoading = false
                    }
                } else if searchFilters.hasFilters {
                    var newChats: [Chat] = []
                    let stream = try await apiClient.advancedSearch(filters: searchFilters, stream: true)
                    for try await chat in stream {
                        try Task.checkCancellation()
                        newChats.append(chat)
                        await MainActor.run { chats = sortChats(newChats) }
                    }
                    await MainActor.run {
                        chats = sortChats(newChats)
                        isLoading = false
                    }
                } else {
                    try Task.checkCancellation()
                    await loadAllChats()
                    return
                }
            } catch is CancellationError {
                // ignore
            } catch {
                await MainActor.run {
                    self.error = error
                    self.isLoading = false
                }
            }
        }
        currentSearchTask = task
        await task.value
    }
    
    private func sortChats(_ list: [Chat]) -> [Chat] {
        list.sorted { lhs, rhs in
            let lDate = lhs.lastMessageDate ?? Date.distantPast
            let rDate = rhs.lastMessageDate ?? Date.distantPast
            return lDate > rDate
        }
    }
    
    private func checkPermissions() {
        hasFullDiskAccess = PermissionManager.shared.checkFullDiskAccess()
    }
}

