//
//  ChatDetailViewModel.swift
//  DopetracksApp
//
//  ViewModel for chat details and messages
//

import Foundation

@MainActor
final class ChatDetailViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isLoading = false
    @Published var isLoadingMore = false
    @Published var error: Error?
    @Published var searchText: String = ""
    @Published var sortOrder: MessageSortOrder = .newestFirst
    @Published var hasMore = true
    
    private let apiClient: APIClient
    private let chatId: String
    
    private let pageSize = 50
    private var offset = 0
    
    init(chatId: String, apiClient: APIClient) {
        self.chatId = chatId
        self.apiClient = apiClient
    }
    
    func loadInitial() async {
        await MainActor.run {
            messages = []
            offset = 0
            hasMore = true
            error = nil
        }
        await loadMore(resetLoading: true)
    }
    
    func loadMore(resetLoading: Bool = false) async {
        guard hasMore, !isLoadingMore else { return }
        await MainActor.run {
            if resetLoading {
                isLoading = true
            }
            isLoadingMore = true
            error = nil
        }
        
        do {
            let limit = pageSize + 1 // fetch one extra to detect more pages
            let fetched = try await apiClient.getMessages(
                chatId: chatId,
                limit: limit,
                offset: offset,
                order: sortOrder,
                search: searchText.isEmpty ? nil : searchText
            )
            
            let hasExtra = fetched.count > pageSize
            let page = hasExtra ? Array(fetched.prefix(pageSize)) : fetched
            
            await MainActor.run {
                messages.append(contentsOf: page)
                offset += page.count
                hasMore = hasExtra
                isLoading = false
                isLoadingMore = false
            }
        } catch {
            await MainActor.run {
                self.error = error
                self.isLoading = false
                self.isLoadingMore = false
                self.hasMore = false
            }
        }
    }
    
    func refreshWithFilters(search: String, sort: MessageSortOrder) async {
        await MainActor.run {
            searchText = search
            sortOrder = sort
        }
        await loadInitial()
    }
}

