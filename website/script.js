console.log("script.js loaded!");

// Helper function to update fetch calls to use BASE_URL
function apiFetch(path, options) {
    return fetch(BASE_URL + path, options);
}

// The main logic from index.html's inline script should be pasted here.

////////////////////////////////////////////////
//////// Create helper functions here //////////
//////////////////////////////////////////////

// Helper function to get the current timestamp
function getCurrentTimestamp() {
    const now = new Date();
    return now.toLocaleTimeString(); // Format: "hh:mm:ss AM/PM" or "HH:mm:ss"
}

// Enable Playlist Creation
function enablePlaylistCreation() {
    if (isSpotifyAuthorized) {
        document.getElementById("playlistCreation").classList.remove("disabled");
        updatePlaylistButtonState(); // Use the new button state logic
    }
}

///////////////////////////////////////////////////////////////
//////// Create dynamic variables here functions here /////////
///////////////////////////////////////////////////////////////

// State variables to track progress
let isSpotifyAuthorized = false;
let isSystemSetup = false;
let isDataPrepared = false;
let isDataPreparing = false;

// Step management
const steps = ['spotifyAuth', 'systemSetup', 'dataPreparation', 'chatSearch', 'playlistCreation'];
const stepTitles = {
    'spotifyAuth': 'Spotify Authorization',
    'systemSetup': 'System Setup', 
    'dataPreparation': 'Data Preparation',
    'chatSearch': 'Chat Search & Selection',
    'playlistCreation': 'Playlist Creation'
};
let currentStep = 0;

// DOM elements
const floatingProgress = document.getElementById("floatingProgress");
const spotifySection = document.getElementById("spotifyAuth");
const systemSection = document.getElementById("systemSetup");
const dataSection = document.getElementById("dataPreparation");
const chatSection = document.getElementById("chatSearch");
const playlistSection = document.getElementById("playlistCreation");

const prepareDataButton = document.getElementById("prepareDataButton");
const dataStatus = document.getElementById("dataStatus");
const dataStatusText = document.getElementById("dataStatusText");
const dataPreparationProgress = document.getElementById("dataPreparationProgress");
const progressMessages = document.getElementById("progressMessages");

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const chatTable = document.getElementById("chatTable");
const chatTableBody = document.getElementById("chatTableBody");
const selectedChatsDisplay = document.getElementById("selectedChatsDisplay");
const clearSelectedChatsButton = document.getElementById("clearSelectedChats");

// Chat selection state
const selectedChats = new Set();

// Initialize floating progress with all steps
function initializeFloatingProgress() {
    floatingProgress.innerHTML = ''; // Clear any existing content
    
    steps.forEach((stepId, index) => {
        const floatingStep = document.createElement('div');
        floatingStep.className = 'floating-step incomplete';
        floatingStep.id = `floating-${stepId}`;
        floatingStep.textContent = index + 1;
        floatingStep.dataset.stepId = stepId;
        floatingStep.dataset.stepIndex = index;
        
        // Add tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = `Step ${index + 1}: ${stepTitles[stepId]}`;
        floatingStep.appendChild(tooltip);
        
        // Add click handler for completed/collapsed steps
        floatingStep.addEventListener('click', () => {
            if (floatingStep.classList.contains('completed') && index < 3) {
                restoreSection(stepId);
            }
        });
        
        floatingProgress.appendChild(floatingStep);
    });
    
    // Set first step as active
    updateFloatingProgress();
}

// Update floating progress indicator
function updateFloatingProgress() {
    const floatingSteps = floatingProgress.querySelectorAll('.floating-step');
    
    floatingSteps.forEach((step, index) => {
        step.classList.remove('incomplete', 'active', 'completed');
        
        if (index < currentStep) {
            step.classList.add('completed');
        } else if (index === currentStep) {
            step.classList.add('active');
        } else {
            step.classList.add('incomplete');
        }
    });
}

// Section Management Functions
function updateSectionStates() {
    steps.forEach((stepId, index) => {
        const section = document.getElementById(stepId);
        
        // Skip sections that are in floating progress
        if (section.classList.contains('completed-floating')) {
            return;
        }
        
        section.classList.remove('active', 'disabled', 'collapsed');
        
        if (index < currentStep) {
            // Only collapse steps 1-3 (index 0,1,2)
            if (index < 3) {
                section.classList.add('collapsed');
            }
            // Steps 3 and above (chatSearch, playlistCreation) stay open
        } else if (index === currentStep) {
            // Current step - make it active
            section.classList.add('active');
        } else {
            // Future step - disable it
            section.classList.add('disabled');
        }
    });
}

function completeCurrentStep(completionText) {
    const stepId = steps[currentStep]; // Capture the current step ID
    const section = document.getElementById(stepId);
    
    // Only add steps 1-3 to floating progress (collapse them)
    if (currentStep < 3) {
        // Hide the completed section
        section.classList.add('completed-floating');
    } else {
        // For steps 4-5, keep them visible but mark as completed
        const h2 = section.querySelector('h2');
        if (!h2.querySelector('.completion-badge')) {
            const badge = document.createElement('span');
            badge.className = 'completion-badge';
            badge.textContent = '✓ Complete';
            h2.appendChild(badge);
        }
    }
    
    // Move to next step
    currentStep++;
    
    // Update floating progress and section states
    updateFloatingProgress();
    updateSectionStates();
    
    // Scroll to next section if available
    if (currentStep < steps.length) {
        setTimeout(() => {
            const nextSection = document.getElementById(steps[currentStep]);
            if (nextSection && !nextSection.classList.contains('completed-floating')) {
                nextSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }, 300);
    }
}

function restoreSection(stepId) {
    const section = document.getElementById(stepId);
    const stepIndex = steps.indexOf(stepId);
    
    // Remove from floating and restore to main view
    section.classList.remove('completed-floating');
    
    // Remove completion badge if present
    const h2 = section.querySelector('h2');
    const badge = h2.querySelector('.completion-badge');
    if (badge) {
        badge.remove();
    }
    
    // Temporarily set as current step for proper display
    const originalCurrentStep = currentStep;
    currentStep = stepIndex;
    updateSectionStates();
    updateFloatingProgress();
    
    // Scroll to the restored section
    setTimeout(() => {
        section.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
        
        // After scrolling, restore the original current step
        setTimeout(() => {
            currentStep = originalCurrentStep;
            updateSectionStates();
            updateFloatingProgress();
        }, 1000);
    }, 300);
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    section.classList.toggle('collapsed');
}

function updateStatus(statusElement, statusTextElement, message, type) {
    statusTextElement.textContent = message;
    statusElement.className = `status-indicator status-${type}`;
}

///////////////////////////////////////////////////////////////
//////// Data Preparation Functions /////////////////////////
///////////////////////////////////////////////////////////////

// Update data status display
function updateDataStatus(status, preparing = false) {
    isDataPrepared = status;
    isDataPreparing = preparing;
    
    if (preparing) {
        dataStatus.style.backgroundColor = '#fff3cd';
        dataStatus.style.color = '#856404';
        dataStatusText.textContent = 'Preparing data...';
        prepareDataButton.disabled = true;
        prepareDataButton.textContent = 'Preparing...';
    } else if (status) {
        dataStatus.style.backgroundColor = '#d4edda';
        dataStatus.style.color = '#155724';
        dataStatusText.textContent = '✅ Data ready for search and playlist creation';
        prepareDataButton.disabled = true;
        prepareDataButton.textContent = 'Data Prepared';
        enableDependentSections();
    } else {
        dataStatus.style.backgroundColor = '#f8d7da';
        dataStatus.style.color = '#721c24';
        dataStatusText.textContent = '❌ Data not prepared';
        prepareDataButton.disabled = false;
        prepareDataButton.textContent = 'Prepare Data';
        disableDependentSections();
    }
}

// Enable sections that depend on data preparation
function enableDependentSections() {
    chatSection.classList.remove("disabled");
    searchInput.disabled = false;
    searchButton.disabled = false;
    updatePlaylistButtonState();
}

// Disable sections that depend on data preparation
function disableDependentSections() {
    chatSection.classList.add("disabled");
    searchInput.disabled = true;
    searchButton.disabled = true;
    document.getElementById("playlistCreation").classList.add("disabled");
    updatePlaylistButtonState();
}

// Check initial data status
async function checkInitialDataStatus() {
    try {
        const response = await apiFetch('/chat-search-status');
        const status = await response.json();
        updateDataStatus(status.has_cached_data, status.is_processing);
    } catch (error) {
        console.error("Error checking data status:", error);
        updateDataStatus(false);
    }
}

// Start data preparation
async function startDataPreparation() {
    return new Promise((resolve, reject) => {
        // Close any existing EventSource
        if (window.currentEventSource) {
            window.currentEventSource.close();
        }
        
        updateDataStatus(false, true);
        dataPreparationProgress.style.display = 'block';
        progressMessages.innerHTML = '';
        
        const eventSource = new EventSource('/chat-search-progress');
        window.currentEventSource = eventSource; // Track the connection
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                const timestamp = new Date().toLocaleTimeString();
                const messageDiv = document.createElement('div');
                messageDiv.style.fontSize = '0.9em';
                messageDiv.style.marginTop = '5px';
                
                if (data.status === 'cached') {
                    messageDiv.innerHTML = `[${timestamp}] ✅ ${data.message}`;
                    messageDiv.style.color = '#28a745';
                    progressMessages.appendChild(messageDiv);
                    eventSource.close();
                    window.currentEventSource = null;
                    updateDataStatus(true, false);
                    resolve();
                } else if (data.status === 'starting') {
                    messageDiv.innerHTML = `[${timestamp}] 🔄 ${data.message}`;
                    messageDiv.style.color = '#007bff';
                    progressMessages.appendChild(messageDiv);
                } else if (data.status === 'progress') {
                    messageDiv.innerHTML = `[${timestamp}] ⏳ ${data.message}`;
                    messageDiv.style.color = '#6c757d';
                    progressMessages.appendChild(messageDiv);
                } else if (data.status === 'completed') {
                    messageDiv.innerHTML = `[${timestamp}] ✅ ${data.message}`;
                    messageDiv.style.color = '#28a745';
                    messageDiv.style.fontWeight = 'bold';
                    progressMessages.appendChild(messageDiv);
                    eventSource.close();
                    window.currentEventSource = null;
                    updateDataStatus(true, false);
                    resolve();
                } else if (data.status === 'error') {
                    messageDiv.innerHTML = `[${timestamp}] ❌ ${data.message}`;
                    messageDiv.style.color = '#dc3545';
                    progressMessages.appendChild(messageDiv);
                    eventSource.close();
                    window.currentEventSource = null;
                    updateDataStatus(false, false);
                    reject(new Error(data.message));
                } else if (data.status === 'already_processing') {
                    messageDiv.innerHTML = `[${timestamp}] ⚠️ ${data.message}`;
                    messageDiv.style.color = '#ffc107';
                    progressMessages.appendChild(messageDiv);
                    eventSource.close();
                    window.currentEventSource = null;
                    updateDataStatus(false, false);
                    reject(new Error(data.message));
                }
                
                // Auto-scroll to bottom
                progressMessages.scrollTop = progressMessages.scrollHeight;
                
            } catch (parseError) {
                console.error("Error parsing SSE data:", parseError);
            }
        };
        
        eventSource.onerror = function(error) {
            console.error("SSE connection error:", error);
            eventSource.close();
            window.currentEventSource = null;
            updateDataStatus(false, false);
            reject(error);
        };
    });
}

// Data preparation button event listener
prepareDataButton.addEventListener("click", async () => {
    if (isDataPreparing) return;
    
    isDataPreparing = true;
    
    try {
        await startDataPreparation();
        updateStatus(dataStatus, dataStatusText, "✅ Data preparation complete!", "success");
        prepareDataButton.textContent = "Data Prepared";
        isDataPrepared = true;
        completeCurrentStep();
    } catch (error) {
        console.error("Data preparation failed:", error);
        updateStatus(dataStatus, dataStatusText, `❌ Error: ${error.message}`, "error");
        prepareDataButton.disabled = false;
        prepareDataButton.textContent = "Retry Data Preparation";
    } finally {
        isDataPreparing = false;
    }
});

//////////////////////////////////////////////
//////// Add File Upload Script Here //////////
//////////////////////////////////////////////

// File upload functionality removed - elements don't exist in current HTML

///////////////////////////////////////////////////////////////
//////// Spotify Authorization
///////////////////////////////////////////////////////////////

// Check if user returned from Spotify authorization
const urlParams = new URLSearchParams(window.location.search);
const authCode = urlParams.get('code');

if (authCode) {
    // User returned from Spotify authorization
    updateStatus(
        document.getElementById("spotifyStatus"),
        document.getElementById("spotifyStatusText"),
        "✅ Spotify authorization successful!",
        "success"
    );
    isSpotifyAuthorized = true;
    fetchUserProfile();
    completeCurrentStep();
}

async function fetchUserProfile() {
    try {
        const response = await apiFetch('/user-profile');
        if (response.ok) {
            const profile = await response.json();
            document.getElementById('userProfile').innerHTML = `
                <strong>Name:</strong> ${profile.display_name}<br>
                <strong>Email:</strong> ${profile.email}<br>
                <strong>Country:</strong> ${profile.country}
            `;
            document.getElementById('userProfileContainer').style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching user profile:', error);
    }
}

// Debug: Check if button exists and add event listener
const spotifyButton = document.getElementById("authorizeSpotify");
console.log("Spotify button element:", spotifyButton);
if (!spotifyButton) {
    console.error("Spotify button not found!");
} else {
    console.log("Adding event listener to Spotify button...");
    spotifyButton.addEventListener("click", async (event) => {
        console.log("Spotify button clicked!");
        console.log("Event object:", event);
        try {
            console.log("Fetching client ID...");
            const response = await apiFetch('/get-client-id');
            console.log("Response received:", response);
            const data = await response.json();
            console.log("Data parsed:", data);
            
            if (response.ok) {
                const clientId = data.client_id;
                const redirectUri = window.location.origin + '/callback';
                const scope = 'playlist-modify-public playlist-modify-private';
                
                const authUrl = `https://accounts.spotify.com/authorize?response_type=code&client_id=${clientId}&scope=${encodeURIComponent(scope)}&redirect_uri=${encodeURIComponent(redirectUri)}`;
                console.log("Redirecting to:", authUrl);
                window.location.href = authUrl;
            } else {
                console.log("Error response from server");
                updateStatus(
                    document.getElementById("spotifyStatus"),
                    document.getElementById("spotifyStatusText"),
                    "❌ Error: Spotify client ID not configured",
                    "error"
                );
            }
        } catch (error) {
            console.error("Error in Spotify authorization:", error);
            updateStatus(
                document.getElementById("spotifyStatus"),
                document.getElementById("spotifyStatusText"),
                "❌ Error connecting to Spotify",
                "error"
            );
        }
    });
    console.log("Event listener added successfully!");
}

///////////////////////////////////////////////////////////////
//////// System Setup
///////////////////////////////////////////////////////////////

document.getElementById("validateUsername").addEventListener("click", async () => {
    const username = document.getElementById("username").value.trim();
    if (!username) {
        updateStatus(
            document.getElementById("systemStatus"),
            document.getElementById("systemStatusText"),
            "❌ Please enter your macOS username",
            "error"
        );
        return;
    }

    try {
        const response = await apiFetch(`/validate-username?username=${encodeURIComponent(username)}`);
        const data = await response.json();

        if (response.ok) {
            updateStatus(
                document.getElementById("systemStatus"),
                document.getElementById("systemStatusText"),
                `✅ Messages database found: ${data.filepath}`,
                "success"
            );
            isSystemSetup = true;
            completeCurrentStep();
        } else {
            updateStatus(
                document.getElementById("systemStatus"),
                document.getElementById("systemStatusText"),
                `❌ ${data.error}`,
                "error"
            );
        }
    } catch (error) {
        updateStatus(
            document.getElementById("systemStatus"),
            document.getElementById("systemStatusText"),
            "❌ Error validating username",
            "error"
        );
    }
});

document.getElementById("validateChatFile").addEventListener("click", async () => {
    const fileInput = document.getElementById("chatFileInput");
    const file = fileInput.files[0];
    
    if (!file) {
        updateStatus(
            document.getElementById("systemStatus"),
            document.getElementById("systemStatusText"),
            "❌ Please select a database file",
            "error"
        );
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await apiFetch('/validate-chat-file/', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (response.ok) {
            updateStatus(
                document.getElementById("systemStatus"),
                document.getElementById("systemStatusText"),
                `✅ Database file validated: ${data.filepath}`,
                "success"
            );
            isSystemSetup = true;
            completeCurrentStep();
        } else {
            updateStatus(
                document.getElementById("systemStatus"),
                document.getElementById("systemStatusText"),
                `❌ ${data.error}`,
                "error"
            );
        }
    } catch (error) {
        updateStatus(
            document.getElementById("systemStatus"),
            document.getElementById("systemStatusText"),
            "❌ Error uploading file",
            "error"
        );
    }
});

///////////////////////////////////////////////////////////////
//////// Chat Search Functions
///////////////////////////////////////////////////////////////

// Update selected chats display
function updateSelectedChatsDisplay() {
    if (selectedChats.size === 0) {
        selectedChatsDisplay.innerHTML = '<p style="color: #666; font-style: italic;">No chats selected</p>';
        clearSelectedChatsButton.style.display = 'none';
    } else {
        const chatItems = Array.from(selectedChats).map(chat => 
            `<span class="selected-chat-badge">
                ${chat}
                <button class="remove-chat" onclick="removeSelectedChat('${chat.replace(/'/g, "\\'")}')" title="Remove chat">×</button>
            </span>`
        ).join('');
        selectedChatsDisplay.innerHTML = chatItems;
        clearSelectedChatsButton.style.display = 'inline-block';
    }
    updatePlaylistButtonState();
}

// Remove a selected chat
function removeSelectedChat(chatName) {
    selectedChats.delete(chatName);
    updateSelectedChatsDisplay();
    
    // Uncheck the checkbox if it's currently visible
    const checkboxes = document.querySelectorAll('.chat-checkbox');
    checkboxes.forEach(checkbox => {
        if (checkbox.dataset.name === chatName) {
            checkbox.checked = false;
        }
    });
}

// Make removeSelectedChat available globally
window.removeSelectedChat = removeSelectedChat;

// Clear all selected chats
clearSelectedChatsButton.addEventListener('click', () => {
    selectedChats.clear();
    updateSelectedChatsDisplay();
    
    // Uncheck all checkboxes
    const checkboxes = document.querySelectorAll('.chat-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = false);
});

// Handle chat checkbox changes
function handleChatSelection(event) {
    const checkbox = event.target;
    const chatName = checkbox.dataset.name;
    
    if (checkbox.checked) {
        selectedChats.add(chatName);
    } else {
        selectedChats.delete(chatName);
    }
    
    updateSelectedChatsDisplay();
}

// Perform chat search
async function performSearch(searchTerm) {
    try {
        searchButton.disabled = true;
        searchButton.textContent = "Searching...";
        chatTableBody.innerHTML = "<tr><td colspan='6'>Searching chats...</td></tr>";
        chatTable.style.display = "table";
        
        const response = await apiFetch(`/chat-search?query=${encodeURIComponent(searchTerm)}`);
        const results = await response.json();
        
        if (Array.isArray(results)) {
            displaySearchResults(results);
        } else {
            chatTableBody.innerHTML = `<tr><td colspan='6'>${results.message || 'No results found'}</td></tr>`;
        }
    } catch (error) {
        console.error('Error performing search:', error);
        chatTableBody.innerHTML = "<tr><td colspan='6'>Error occurred while searching</td></tr>";
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = "Search Chats";
    }
}

// Display search results
function displaySearchResults(results) {
    chatTableBody.innerHTML = "";
    
    if (results.length === 0) {
        chatTableBody.innerHTML = "<tr><td colspan='6'>No chats found matching your search</td></tr>";
        return;
    }
    
    results.forEach(chat => {
        const row = chatTableBody.insertRow();
        const isSelected = selectedChats.has(chat.name);
        
        row.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="chat-checkbox" 
                       data-name="${chat.name.replace(/"/g, '&quot;')}"
                       ${isSelected ? 'checked' : ''}>
            </td>
            <td>${chat.name}</td>
            <td>${chat.members}</td>
            <td>${chat.total_messages}</td>
            <td>${chat.user_messages}</td>
            <td>${chat.urls}</td>
            <td>${chat.most_recent_song_date ? chat.most_recent_song_date : ''}</td>
        `;
        
        // Add event listener to checkbox
        row.querySelector('.chat-checkbox').addEventListener('change', handleChatSelection);
    });
}

// Search button click handler
searchButton.addEventListener("click", () => {
    const searchTerm = searchInput.value.trim();
    if (searchTerm) {
        performSearch(searchTerm);
    }
});

// Allow Enter key to trigger search
searchInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        searchButton.click();
    }
});

///////////////////////////////////////////////////////////////
//////// Playlist Creation
///////////////////////////////////////////////////////////////

// Update playlist creation button state
function updatePlaylistButtonState() {
    const hasSelections = selectedChats.size > 0;
    const hasSpotifyAuth = isSpotifyAuthorized;
    const hasDataPrepared = isDataPrepared;
    
    const createButton = document.getElementById("createPlaylist");
    
    if (hasSelections && hasSpotifyAuth && hasDataPrepared) {
        createButton.disabled = false;
        createButton.style.opacity = "1";
        createButton.title = "";
        playlistSection.classList.remove("disabled");
        
        // Move to playlist creation step if we're not already there
        if (currentStep < 4) {
            currentStep = 4;
            updateSectionStates();
        }
    } else {
        createButton.disabled = true;
        createButton.style.opacity = "0.6";
        
        if (!hasSpotifyAuth) {
            createButton.title = "Please complete Spotify authorization first";
        } else if (!hasDataPrepared) {
            createButton.title = "Please complete data preparation first";
        } else if (!hasSelections) {
            createButton.title = "Please select at least one chat";
        }
    }
}

// Handle playlist form submission
document.getElementById("playlistForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const playlistNameInput = document.getElementById("playlistName");
    const wasDisabled = playlistNameInput.disabled;
    if (wasDisabled) playlistNameInput.disabled = false; // Enable if disabled

    const formData = new FormData(event.target);

    if (wasDisabled) playlistNameInput.disabled = true; // Restore disabled state

    const selectedChatNames = Array.from(selectedChats);
    formData.append("selected_chats", JSON.stringify(selectedChatNames));

    // Add selected playlist ID if any
    const playlistDropdown = document.getElementById('playlistDropdown');
    if (playlistDropdown && playlistDropdown.value) {
        formData.append('existing_playlist_id', playlistDropdown.value);
    }

    const createButton = document.getElementById("createPlaylist");
    const statusDiv = document.getElementById("playlistStatus");

    try {
        createButton.disabled = true;
        createButton.textContent = "Creating Playlist...";
        statusDiv.innerHTML = '<div class="status-indicator status-info">Creating playlist...</div>';

        const response = await apiFetch("/create-playlist/", {
            method: "POST",
            body: formData,
        });

        const result = await response.json();

        if (result.status === "success") {
            statusDiv.innerHTML = `<div class="status-indicator status-success">✅ ${result.message}</div>`;

            // Clear form
            document.getElementById("playlistName").value = "";
            document.getElementById("startDate").value = "";
            document.getElementById("endDate").value = "";

            // Optionally clear selected chats
            if (confirm("Playlist created successfully! Would you like to clear your selected chats for the next playlist?")) {
                selectedChats.clear();
                updateSelectedChatsDisplay();
                const checkboxes = document.querySelectorAll('.chat-checkbox');
                checkboxes.forEach(checkbox => checkbox.checked = false);
            }
        } else {
            statusDiv.innerHTML = `<div class="status-indicator status-error">❌ ${result.message}</div>`;
        }
    } catch (error) {
        console.error("Error creating playlist:", error);
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ An error occurred while creating the playlist</div>';
    } finally {
        createButton.disabled = false;
        createButton.textContent = "Create Playlist";
    }
});

///////////////////////////////////////////////////////////////
//////// Initialization
///////////////////////////////////////////////////////////////

// Clean up any existing connections and reset state
function cleanupAndReset() {
    // Close any existing EventSource connections
    if (window.currentEventSource) {
        window.currentEventSource.close();
        window.currentEventSource = null;
    }
    
    // Reset button states
    const validateButton = document.getElementById("validateChatFile");
    if (validateButton) {
        validateButton.disabled = false;
        validateButton.textContent = "Validate File";
    }
    
    const prepareButton = document.getElementById("prepareDataButton");
    if (prepareButton) {
        prepareButton.disabled = false;
        prepareButton.textContent = "Prepare Data";
    }
    
    // Reset flags
    isDataPreparing = false;
    
    console.log("Page state cleaned up and reset");
}

// Initialize the interface
cleanupAndReset();
initializeFloatingProgress();
updateSelectedChatsDisplay();
updatePlaylistButtonState();

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (window.currentEventSource) {
        window.currentEventSource.close();
    }
});

// Add logic to fetch playlists and populate dropdown
async function fetchUserPlaylists() {
    try {
        const response = await apiFetch('/user-playlists');
        if (!response.ok) return [];
        return await response.json();
    } catch (e) {
        console.error('Error fetching playlists:', e);
        return [];
    }
}

// Function to refresh the playlist dropdown
async function refreshPlaylistDropdown() {
    const playlistDropdown = document.getElementById('playlistDropdown');
    const refreshButton = document.getElementById('refreshPlaylists');
    const playlistNameInput = document.getElementById('playlistName');
    
    try {
        // Disable the refresh button while loading
        refreshButton.disabled = true;
        refreshButton.style.opacity = '0.5';
        
        // Fetch updated playlists
        const playlists = await fetchUserPlaylists();
        
        // Store current selection
        const currentSelection = playlistDropdown.value;
        const currentText = playlistDropdown.options[playlistDropdown.selectedIndex]?.text;
        
        // Clear and repopulate dropdown
        playlistDropdown.innerHTML = '<option value="">-- Select existing playlist --</option>';
        playlists.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            playlistDropdown.appendChild(opt);
        });
        
        // Restore previous selection if it still exists
        if (currentSelection) {
            const option = Array.from(playlistDropdown.options).find(opt => opt.value === currentSelection);
            if (option) {
                playlistDropdown.value = currentSelection;
                playlistNameInput.value = currentText;
                playlistNameInput.disabled = true;
            } else {
                // If the previously selected playlist no longer exists, clear the selection
                playlistDropdown.value = '';
                playlistNameInput.value = '';
                playlistNameInput.disabled = false;
            }
        }
    } catch (error) {
        console.error('Error refreshing playlists:', error);
    } finally {
        // Re-enable the refresh button
        refreshButton.disabled = false;
        refreshButton.style.opacity = '1';
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    // Playlist dropdown logic
    const playlistNameInput = document.getElementById('playlistName');
    const playlistForm = document.getElementById('playlistForm');
    const refreshButton = document.getElementById('refreshPlaylists');
    
    // Create dropdown
    const playlistDropdown = document.createElement('select');
    playlistDropdown.id = 'playlistDropdown';
    playlistDropdown.style.marginLeft = '10px';
    playlistDropdown.innerHTML = '<option value="">-- Select existing playlist --</option>';
    playlistNameInput.parentNode.insertBefore(playlistDropdown, playlistNameInput.nextSibling);
    
    // Initial fetch and populate playlists
    await refreshPlaylistDropdown();
    
    // Add refresh button click handler
    refreshButton.addEventListener('click', refreshPlaylistDropdown);
    
    // When dropdown changes, update input
    playlistDropdown.addEventListener('change', function() {
        if (playlistDropdown.value) {
            playlistNameInput.value = playlistDropdown.options[playlistDropdown.selectedIndex].text;
            playlistNameInput.disabled = true;
        } else {
            playlistNameInput.value = '';
            playlistNameInput.disabled = false;
        }
    });
});
