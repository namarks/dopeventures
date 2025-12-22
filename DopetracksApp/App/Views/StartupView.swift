import SwiftUI

enum StartupStepState {
    case pending, active, done, error(String)
}

struct StartupView: View {
    @ObservedObject var backendManager: BackendManager
    @ObservedObject var chatListViewModel: ChatListViewModel
    let onChatsLoaded: () -> Void
    let loadChats: () async -> Bool
    
    @State private var hasFullDiskAccess: Bool? = nil
    @State private var backendState: StartupStepState = .pending
    @State private var chatState: StartupStepState = .pending
    @State private var isRunning = false
    @State private var elapsed: TimeInterval = 0
    @State private var startDate: Date?
    @State private var chatErrorMessage: String?
    
    private let timer = Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()
    
    var body: some View {
        VStack(spacing: 24) {
            Text("Getting things ready…")
                .font(.title2)
                .fontWeight(.semibold)
            
            if hasFullDiskAccess == false {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(.orange)
                    Text("Full Disk Access Required")
                        .font(.headline)
                    Text("Dopetracks needs Full Disk Access to read your Messages database.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                    Text("Go to: System Settings > Privacy & Security > Full Disk Access")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    HStack(spacing: 12) {
                        Button("Open System Settings") {
                            PermissionManager.shared.openFullDiskAccessSettings()
                        }
                        .buttonStyle(.borderedProminent)
                        Button("Check Again") {
                            Task { await verifyPermissionAndStartIfAllowed() }
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.ultraThickMaterial)
                .cornerRadius(12)
            } else {
                VStack(alignment: .leading, spacing: 16) {
                    stepRow(
                        title: "Backend",
                        detail: backendDetail,
                        state: backendState
                    )
                    stepRow(
                        title: "Chats",
                        detail: chatDetail,
                        state: chatState
                    )
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.ultraThickMaterial)
                .cornerRadius(12)
                
                if case .error = backendState {
                    Button("Retry backend") {
                        Task { await runStartup() }
                    }
                    .buttonStyle(.borderedProminent)
                } else if case .error = chatState {
                    if let msg = chatErrorMessage {
                        Text(msg)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    Button("Retry loading chats") {
                        Task { await runStartup() }
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    ProgressView()
                        .controlSize(.large)
                }
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.windowBackgroundColor))
        .task {
            await verifyPermissionAndStartIfAllowed()
        }
        .onReceive(timer) { _ in
            if let start = startDate, isRunning {
                elapsed = Date().timeIntervalSince(start)
            }
        }
    }
    
    private func runStartup() async {
        guard !isRunning else { return }
        guard hasFullDiskAccess != false else { return }
        isRunning = true
        startDate = Date()
        backendState = .active
        chatState = .pending
        elapsed = 0
        chatErrorMessage = nil
        
        let backendOK = await backendManager.ensureBackendRunning()
        if backendOK {
            backendState = .done
            chatState = .active
            let chatsOK = await loadChats()
            if chatsOK {
                chatState = .done
                onChatsLoaded()
                isRunning = false
                startDate = nil
            } else {
                chatErrorMessage = chatListViewModel.error?.localizedDescription ?? "Failed to load chats. Please retry."
                chatState = .error(chatErrorMessage ?? "Failed to load chats. Please retry.")
                isRunning = false
            }
        } else {
            backendState = .error("Could not start backend. Check logs or retry.")
            isRunning = false
        }
    }
    
    private var backendDetail: String {
        switch backendState {
        case .pending: return "Waiting to start"
        case .active: return "Starting local backend"
        case .done: return "Running"
        case .error(let msg): return msg
        }
    }
    
    private var chatDetail: String {
        switch chatState {
        case .pending: return "Waiting for backend"
        case .active: return "Fetching chat list (first load may take ~20s). Elapsed \(formattedElapsed)"
        case .done: return "Chats loaded"
        case .error(let msg): return msg
        }
    }
    
    private var formattedElapsed: String {
        String(format: "%.1fs", elapsed)
    }
    
    @ViewBuilder
    private func stepRow(title: String, detail: String, state: StartupStepState) -> some View {
        HStack(alignment: .top, spacing: 10) {
            stateIcon(for: state)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .fontWeight(.semibold)
                Text(detail)
                    .font(.caption)
                    .foregroundColor(.secondary)
                if case .active = state {
                    Text("This may take a moment; we’re reading your Messages database.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
    }
    
    @ViewBuilder
    private func stateIcon(for state: StartupStepState) -> some View {
        switch state {
        case .pending:
            Image(systemName: "circle")
                .foregroundColor(.secondary)
        case .active:
            ProgressView()
                .controlSize(.small)
        case .done:
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
        case .error:
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.orange)
        }
    }
}

extension StartupView {
    private func verifyPermissionAndStartIfAllowed() async {
        let granted = PermissionManager.shared.checkFullDiskAccess()
        await MainActor.run {
            hasFullDiskAccess = granted
        }
        if granted {
            await runStartup()
        }
    }
}


