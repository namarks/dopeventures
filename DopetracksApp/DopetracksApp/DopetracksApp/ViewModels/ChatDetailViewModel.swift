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
    @Published var error: Error?
    
    private let apiClient: APIClient
    private let chatId: String
    
    init(chatId: String, apiClient: APIClient) {
        self.chatId = chatId
        self.apiClient = apiClient
    }
    
    func loadMessages() async {
        isLoading = true
        error = nil
        do {
            messages = try await apiClient.getRecentMessages(chatId: chatId)
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

