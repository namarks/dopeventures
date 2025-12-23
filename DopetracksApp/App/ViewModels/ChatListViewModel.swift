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
    private var hasLoadedOnce = false
    
    private var currentSearchTask: Task<Void, Never>?
    let apiClient: APIClient
    
    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }
    
    func onAppear() {
        guard !hasLoadedOnce else { return }
        hasLoadedOnce = true
        
        Task { @MainActor in
            hasFullDiskAccess = PermissionManager.shared.checkFullDiskAccess()
        }
        
        Task { _ = await loadAllChats() }

        // Default-select the most recent chat on first load
        Task { @MainActor in
            if selectedChatId == nil, let first = chats.first {
                selectedChatId = first.id
            }
        }
    }
    
    func onSearchTextChange(_ newValue: String) {
        // Defer mutations off the immediate view update cycle to avoid
        // "Publishing changes from within view updates is not allowed".
        Task { @MainActor in
            if searchFilters.startDate != nil ||
                searchFilters.endDate != nil ||
                !searchFilters.participantNames.isEmpty ||
                !searchFilters.messageContent.isEmpty {
                searchFilters.query = newValue
            }
            
            if !newValue.isEmpty || searchFilters.hasFilters {
                await performSearch()
            } else {
                currentSearchTask?.cancel()
                await loadAllChats()
            }
        }
    }
    
    func clearFilters() {
        searchFilters = SearchFilters()
        searchText = ""
        selectedChats = []
        selectedChatId = nil
        Task { _ = await loadAllChats() }
    }
    
    func refreshPermissions() {
        checkPermissions()
    }
    
    @discardableResult
    func loadAllChats() async -> Bool {
        isLoading = true
        error = nil
        do {
            let fetched = try await apiClient.getAllChats()
            chats = sortChats(fetched)
            hasLoadedOnce = true
            // Auto-select first chat when none is selected
            if selectedChatId == nil, let first = chats.first {
                selectedChatId = first.id
            }
            isLoading = false
            return true
        } catch {
            self.error = error
            isLoading = false
            return false
        }
    }
    
    func performSearch() async {
        currentSearchTask?.cancel()
        
        let task = Task {
            await MainActor.run {
                isLoading = true
                error = nil
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
                await MainActor.run {
                    isLoading = false
                }
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

