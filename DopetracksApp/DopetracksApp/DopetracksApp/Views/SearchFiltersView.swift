//
//  SearchFiltersView.swift
//  DopetracksApp
//
//  View for advanced search filters
//

import SwiftUI

struct SearchFiltersView: View {
    @Binding var filters: SearchFilters
    @State private var participantInput: String = ""
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Advanced Search")
                .font(.headline)
            
            // Date Range
            VStack(alignment: .leading, spacing: 8) {
                Text("Date Range")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack(spacing: 12) {
                    DatePicker("From", selection: Binding(
                        get: { filters.startDate ?? Date().addingTimeInterval(-30 * 24 * 60 * 60) },
                        set: { filters.startDate = $0 }
                    ), displayedComponents: .date)
                    .labelsHidden()
                    
                    Text("to")
                        .foregroundColor(.secondary)
                    
                    DatePicker("To", selection: Binding(
                        get: { filters.endDate ?? Date() },
                        set: { filters.endDate = $0 }
                    ), displayedComponents: .date)
                    .labelsHidden()
                }
                
                Button("Clear Dates") {
                    filters.startDate = nil
                    filters.endDate = nil
                }
                .buttonStyle(.borderless)
                .font(.caption)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            
            // Participants
            VStack(alignment: .leading, spacing: 8) {
                Text("Participants")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack {
                    TextField("Add participant name...", text: $participantInput)
                        .textFieldStyle(.plain)
                        .onSubmit {
                            if !participantInput.isEmpty {
                                filters.participantNames.append(participantInput)
                                participantInput = ""
                            }
                        }
                    
                    Button("Add") {
                        if !participantInput.isEmpty {
                            filters.participantNames.append(participantInput)
                            participantInput = ""
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(participantInput.isEmpty)
                }
                
                if !filters.participantNames.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(filters.participantNames.indices, id: \.self) { index in
                                HStack(spacing: 4) {
                                    Text(filters.participantNames[index])
                                        .font(.caption)
                                    Button {
                                        filters.participantNames.remove(at: index)
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .font(.caption2)
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.accentColor.opacity(0.2))
                                .cornerRadius(12)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            
            // Message Content
            VStack(alignment: .leading, spacing: 8) {
                Text("Message Content")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                TextField("Search for words in messages...", text: $filters.messageContent)
                    .textFieldStyle(.plain)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            
            // Clear All
            if filters.hasFilters {
                Button("Clear All Filters") {
                    filters = SearchFilters()
                    participantInput = ""
                }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
    }
}


#Preview {
    SearchFiltersView(filters: .constant(SearchFilters()))
        .frame(width: 400)
}

