console.log("script.js loaded!");

// Global variables for authentication
let isAuthenticated = false;
let currentUser = null;
let isInResetMode = false; // Track if we're in password reset mode
let resetToken = null; // Store the reset token from URL
// BASE_URL is defined in config.js
const AUTH_BASE_URL = `${BASE_URL}/auth`;

// Cache refresh: 2025-06-01 20:32 - Force reload for forgot password link

// DOM elements for authentication (will be set when DOM is ready)
let authOverlay, userBar, mainContent, loginForm, registerForm, forgotPasswordForm, resetPasswordForm;
let authTitle, authError, authSuccess, switchToRegister, authSwitchText;
let currentUsername, currentUserRole, adminLink, logoutBtn;

// Check for reset token in URL parameters
function checkForResetToken() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    if (token) {
        resetToken = token;
        isInResetMode = true;
        // Clear the token from URL for security
        window.history.replaceState({}, document.title, window.location.pathname);
        return true;
    }
    return false;
}

// Check authentication status on page load
async function checkAuthStatus() {
    // Check if we're in password reset mode first
    if (checkForResetToken()) {
        await verifyResetToken();
        return;
    }
    
    try {
        const response = await fetch(`${AUTH_BASE_URL}/status`, {
            credentials: 'include'  // Ensure cookies are sent
        });
        
        if (!response.ok) {
            console.warn(`Auth status check failed: ${response.status} ${response.statusText}`);
            showAuthModal();
            return;
        }
        
        const data = await response.json();
        console.log("Auth status check response:", data);
        
        if (data.authenticated) {
            currentUser = data.user;
            isAuthenticated = true;
            showMainApp();
            // Update Spotify button state after authentication is confirmed
            const spotifyButton = document.getElementById("authorizeSpotify");
            if (spotifyButton) {
                spotifyButton.disabled = false;
                spotifyButton.title = "Authorize Spotify to create playlists";
                spotifyButton.style.opacity = "1";
                spotifyButton.style.cursor = "pointer";
            }
        } else {
            showAuthModal();
            // Ensure button is disabled if not authenticated
            const spotifyButton = document.getElementById("authorizeSpotify");
            if (spotifyButton) {
                spotifyButton.disabled = true;
                spotifyButton.title = "Please log in first to authorize Spotify";
                spotifyButton.style.opacity = "0.6";
                spotifyButton.style.cursor = "not-allowed";
            }
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        showAuthModal();
    }
}

// Show authentication modal
function showAuthModal() {
    authOverlay.style.display = 'flex';
    userBar.style.display = 'none';
    mainContent.classList.remove('visible');
    document.body.classList.remove('authenticated');
}

// Show main application
function showMainApp() {
    authOverlay.style.display = 'none';
    userBar.style.display = 'flex';
    mainContent.classList.add('visible');
    document.body.classList.add('authenticated');
    
    if (currentUser) {
        currentUsername.textContent = currentUser.username;
        currentUserRole.textContent = currentUser.role || 'user';
        currentUserRole.className = `user-role ${currentUser.role || 'user'}`;
        
        // Show admin link for admin users
        if (currentUser.role === 'admin' || currentUser.role === 'super_admin') {
            adminLink.style.display = 'inline-block';
        }
    }
    
    // Update Spotify button state based on authentication
    const spotifyButton = document.getElementById("authorizeSpotify");
    if (spotifyButton) {
        if (isAuthenticated && currentUser) {
            spotifyButton.disabled = false;
            spotifyButton.title = "Authorize Spotify to create playlists";
            spotifyButton.style.opacity = "1";
            spotifyButton.style.cursor = "pointer";
        } else {
            spotifyButton.disabled = true;
            spotifyButton.title = "Please log in first to authorize Spotify";
            spotifyButton.style.opacity = "0.6";
            spotifyButton.style.cursor = "not-allowed";
        }
    }
    
    // Check Spotify authorization status
    checkSpotifyAuthStatus();
    
    // Also check if we just came back from Spotify callback
    // Check URL for callback parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('code') || window.location.pathname === '/callback') {
        // We're coming back from Spotify - check status after a brief delay
        setTimeout(() => {
            checkSpotifyAuthStatus();
        }, 1000);
    }
}

// Check Spotify authorization status
async function checkSpotifyAuthStatus() {
    try {
        const response = await apiFetch('/user-profile');
        if (response.ok) {
            // User has Spotify tokens and they're valid
            const profile = await response.json();
            updateStatus(
                document.getElementById("spotifyStatus"),
                document.getElementById("spotifyStatusText"),
                "✅ Connected to Spotify",
                "success"
            );
            
            // Update profile display
            document.getElementById('userProfile').innerHTML = `
                <strong>Name:</strong> ${profile.display_name}<br>
                <strong>Email:</strong> ${profile.email}<br>
                <strong>Country:</strong> ${profile.country}
            `;
            document.getElementById('userProfileContainer').style.display = 'block';
            
            // Update button text
            const spotifyButton = document.getElementById("authorizeSpotify");
            if (spotifyButton) {
                spotifyButton.textContent = "Reconnect to Spotify";
            }
            
            // Enable next steps
            isSpotifyAuthorized = true;
            completeCurrentStep();
        } else {
            // User doesn't have valid Spotify tokens
            updateStatus(
                document.getElementById("spotifyStatus"),
                document.getElementById("spotifyStatusText"),
                "Not connected to Spotify",
                "pending"
            );
        }
    } catch (error) {
        console.log('Spotify not connected yet:', error);
        updateStatus(
            document.getElementById("spotifyStatus"),
            document.getElementById("spotifyStatusText"),
            "Not connected to Spotify",
            "pending"
        );
    }
}

// Show/hide auth error
function showAuthError(message) {
    authError.textContent = message;
    authError.style.display = 'block';
    authSuccess.style.display = 'none';
}

// Show/hide auth success
function showAuthSuccess(message) {
    authSuccess.textContent = message;
    authSuccess.style.display = 'block';
    authError.style.display = 'none';
}

// Clear auth messages
function clearAuthMessages() {
    authError.style.display = 'none';
    authSuccess.style.display = 'none';
}

// Switch between login and register forms
function switchAuthMode(mode = 'login') {
    console.log('switchAuthMode called with mode:', mode);
    clearAuthMessages();
    
    // Hide all forms first
    loginForm.style.display = 'none';
    registerForm.style.display = 'none';
    forgotPasswordForm.style.display = 'none';
    resetPasswordForm.style.display = 'none';
    
    switch (mode) {
        case 'register':
            authTitle.textContent = 'Create Account';
            registerForm.style.display = 'block';
            authSwitchText.innerHTML = 'Already have an account? <a href="#" data-auth-action="login">Login</a>';
            break;
            
        case 'forgot-password':
            authTitle.textContent = 'Reset Password';
            forgotPasswordForm.style.display = 'block';
            authSwitchText.innerHTML = 'Remember your password? <a href="#" data-auth-action="login">Login</a>';
            break;
            
        case 'reset-password':
            authTitle.textContent = 'Set New Password';
            resetPasswordForm.style.display = 'block';
            authSwitchText.innerHTML = 'Go back to <a href="#" data-auth-action="login">Login</a>';
            break;
            
        default: // login
            authTitle.textContent = 'Welcome Back';
            loginForm.style.display = 'block';
            const newHTML = 'Don\'t have an account? <a href="#" data-auth-action="register">Register</a> | <a href="#" data-auth-action="forgot-password">Forgot Password?</a>';
            console.log('Setting authSwitchText innerHTML to:', newHTML);
            authSwitchText.innerHTML = newHTML;
            break;
    }
    
    console.log('switchAuthMode completed, current authSwitchText innerHTML:', authSwitchText.innerHTML);
}

// Handle login
async function handleLogin(event) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:267',message:'handleLogin called',data:{eventType:event.type,defaultPrevented:event.defaultPrevented},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
    
    event.preventDefault();
    clearAuthMessages();
    
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:267',message:'handleLogin entry',data:{username:username,hasPassword:!!password},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (!username || !password) {
        showAuthError('Please enter both username and password');
        return;
    }
    
    const loginBtn = document.getElementById('loginBtn');
    loginBtn.disabled = true;
    loginBtn.textContent = 'Logging in...';
    
    try {
        const requestUrl = `${AUTH_BASE_URL}/login`;
        const requestBody = JSON.stringify({ username, password });
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:284',message:'fetch request start',data:{url:requestUrl,method:'POST',hasBody:!!requestBody},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        
        const response = await fetch(requestUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: requestBody,
            credentials: 'include'
        });
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:293',message:'response received',data:{status:response.status,ok:response.ok,statusText:response.statusText,headers:Object.fromEntries(response.headers.entries())},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        
        // Check if response is OK before parsing JSON
        if (!response.ok) {
            let errorMessage = 'Login failed';
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    if (Array.isArray(errorData.detail)) {
                        // Pydantic validation errors
                        errorMessage = errorData.detail.map(err => err.msg || err.message || String(err)).join(', ');
                    } else {
                        errorMessage = errorData.detail;
                    }
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (e) {
                // Response is not JSON, try to get text
                try {
                    const errorText = await response.text();
                    errorMessage = errorText || `HTTP ${response.status}: ${response.statusText}`;
                } catch (e2) {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
            }
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:318',message:'response not ok',data:{errorMessage:errorMessage},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
            // #endregion
            showAuthError(errorMessage);
            return;
        }
        
        // Response is OK, parse JSON
        const data = await response.json();
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:322',message:'response parsed',data:{hasUser:!!data.user,hasMessage:!!data.message,dataKeys:Object.keys(data)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        
        currentUser = data.user;
        isAuthenticated = true;
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:327',message:'login success state set',data:{isAuthenticated:isAuthenticated,hasCurrentUser:!!currentUser},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
        // #endregion
        
        showAuthSuccess('Login successful!');
        
        // Update Spotify button state after login
        const spotifyButton = document.getElementById("authorizeSpotify");
        if (spotifyButton) {
            spotifyButton.disabled = false;
            spotifyButton.title = "Authorize Spotify to create playlists";
            spotifyButton.style.opacity = "1";
            spotifyButton.style.cursor = "pointer";
        }
        
        setTimeout(() => {
            showMainApp();
        }, 1000);
    } catch (error) {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:340',message:'login exception',data:{errorName:error.name,errorMessage:error.message,errorStack:error.stack},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        console.error('Login error:', error);
        showAuthError(`Login failed: ${error.message || 'Please try again.'}`);
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Login';
    }
}

// Handle registration
async function handleRegister(event) {
    event.preventDefault();
    clearAuthMessages();
    
    const username = document.getElementById('registerUsername').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    
    if (!username || !email || !password) {
        showAuthError('Please fill in all fields');
        return;
    }
    
    if (password.length < 8) {
        showAuthError('Password must be at least 8 characters long');
        return;
    }
    
    const registerBtn = document.getElementById('registerBtn');
    registerBtn.disabled = true;
    registerBtn.textContent = 'Creating account...';
    
    try {
        const response = await fetch(`${AUTH_BASE_URL}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            isAuthenticated = true;
            showAuthSuccess('Account created successfully!');
            
            setTimeout(() => {
                showMainApp();
            }, 1000);
        } else {
            // Handle different error response formats
            let errorMessage = 'Registration failed';
            if (data.detail) {
                if (Array.isArray(data.detail)) {
                    // Pydantic validation errors
                    errorMessage = data.detail.map(err => {
                        if (err.msg) return err.msg;
                        if (err.message) return err.message;
                        if (typeof err === 'string') return err;
                        return String(err);
                    }).join(', ');
                } else {
                    errorMessage = data.detail;
                }
            } else if (data.message) {
                errorMessage = data.message;
            }
            console.log('Registration error details:', data);
            showAuthError(errorMessage);
        }
    } catch (error) {
        console.error('Registration error:', error);
        showAuthError('Registration failed. Please try again.');
    } finally {
        registerBtn.disabled = false;
        registerBtn.textContent = 'Register';
    }
}

// Handle logout
async function handleLogout() {
    try {
        await fetch(`${AUTH_BASE_URL}/logout`, {
            method: 'POST',
            credentials: 'include'
        });
    } catch (error) {
        console.error('Logout error:', error);
    }
    
    currentUser = null;
    isAuthenticated = false;
    showAuthModal();
}

// Verify reset token
async function verifyResetToken() {
    if (!resetToken) {
        showAuthError('Invalid reset link');
        switchAuthMode('login');
        return;
    }
    
    try {
        const response = await fetch(`${AUTH_BASE_URL}/verify-reset-token?token=${encodeURIComponent(resetToken)}`);
        const data = await response.json();
        
        if (response.ok) {
            showAuthModal();
            switchAuthMode('reset-password');
            showAuthSuccess(`Reset password for ${data.user_email}`);
        } else {
            showAuthError(data.detail || 'Invalid or expired reset token');
            switchAuthMode('login');
            isInResetMode = false;
            resetToken = null;
        }
    } catch (error) {
        console.error('Token verification error:', error);
        showAuthError('Error verifying reset token');
        switchAuthMode('login');
        isInResetMode = false;
        resetToken = null;
    }
}

// Handle forgot password
async function handleForgotPassword(event) {
    event.preventDefault();
    clearAuthMessages();
    
    const email = document.getElementById('forgotPasswordEmail').value.trim();
    
    if (!email) {
        showAuthError('Please enter your email address');
        return;
    }
    
    const forgotBtn = document.getElementById('forgotPasswordBtn');
    forgotBtn.disabled = true;
    forgotBtn.textContent = 'Sending...';
    
    try {
        const response = await fetch(`${AUTH_BASE_URL}/forgot-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAuthSuccess(data.message);
            // Show additional development info
            setTimeout(() => {
                showAuthSuccess(data.message + '\n\nDEV MODE: Check the browser console for the reset link.');
            }, 100);
        } else {
            showAuthError(data.detail || 'Error sending reset email');
        }
    } catch (error) {
        console.error('Forgot password error:', error);
        showAuthError('Error sending reset email. Please try again.');
    } finally {
        forgotBtn.disabled = false;
        forgotBtn.textContent = 'Send Reset Link';
    }
}

// Handle reset password
async function handleResetPassword(event) {
    event.preventDefault();
    clearAuthMessages();
    
    if (!resetToken) {
        showAuthError('Invalid reset session');
        return;
    }
    
    const newPassword = document.getElementById('resetNewPassword').value;
    const confirmPassword = document.getElementById('resetConfirmPassword').value;
    
    if (!newPassword || !confirmPassword) {
        showAuthError('Please fill in both password fields');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        showAuthError('Passwords do not match');
        return;
    }
    
    if (newPassword.length < 8) {
        showAuthError('Password must be at least 8 characters long');
        return;
    }
    
    const resetBtn = document.getElementById('resetPasswordBtn');
    resetBtn.disabled = true;
    resetBtn.textContent = 'Resetting...';
    
    try {
        const response = await fetch(`${AUTH_BASE_URL}/reset-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                token: resetToken, 
                new_password: newPassword 
            }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAuthSuccess(data.message);
            
            // Reset state and switch to login
            isInResetMode = false;
            resetToken = null;
            
            setTimeout(() => {
                switchAuthMode('login');
            }, 2000);
        } else {
            showAuthError(data.detail || 'Error resetting password');
        }
    } catch (error) {
        console.error('Reset password error:', error);
        showAuthError('Error resetting password. Please try again.');
    } finally {
        resetBtn.disabled = false;
        resetBtn.textContent = 'Reset Password';
    }
}

// Add event listeners for authentication
// Initialize DOM elements and attach event handlers when DOM is ready
function initializeAuthElements() {
    console.log('initializeAuthElements called');
    authOverlay = document.getElementById('authOverlay');
    userBar = document.getElementById('userBar');
    mainContent = document.getElementById('mainContent');
    loginForm = document.getElementById('loginForm');
    registerForm = document.getElementById('registerForm');
    forgotPasswordForm = document.getElementById('forgotPasswordForm');
    resetPasswordForm = document.getElementById('resetPasswordForm');
    authTitle = document.getElementById('authTitle');
    authError = document.getElementById('authError');
    authSuccess = document.getElementById('authSuccess');
    switchToRegister = document.getElementById('switchToRegister');
    authSwitchText = document.getElementById('authSwitchText');
    currentUsername = document.getElementById('currentUsername');
    currentUserRole = document.getElementById('currentUserRole');
    adminLink = document.getElementById('adminLink');
    logoutBtn = document.getElementById('logoutBtn');
    
    console.log('loginForm found:', !!loginForm);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:620',message:'initializing auth elements',data:{loginFormExists:!!loginForm,registerFormExists:!!registerForm},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
    
    if (loginForm) {
        console.log('Attaching submit listener to loginForm');
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:640',message:'attaching loginForm listener',data:{loginFormId:loginForm.id},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'E'})}).catch(()=>{});
        // #endregion
        loginForm.addEventListener('submit', handleLogin);
        console.log('Submit listener attached to loginForm');
    } else {
        console.error('loginForm element not found during initialization!');
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/d321815d-44ec-4859-8309-98b45104f79c',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'script.js:645',message:'loginForm not found during init',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run3',hypothesisId:'E'})}).catch(()=>{});
        // #endregion
    }
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener('submit', handleForgotPassword);
    }
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener('submit', handleResetPassword);
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    if (switchToRegister) {
        switchToRegister.addEventListener('click', () => switchAuthMode('register'));
    }
    
    // Event delegation for auth switch links (register, forgot password, etc.)
    if (authSwitchText) {
        authSwitchText.addEventListener('click', (e) => {
            if (e.target.tagName === 'A' && e.target.hasAttribute('data-auth-action')) {
                e.preventDefault();
                const action = e.target.getAttribute('data-auth-action');
                console.log('Auth switch link clicked:', action);
                
                if (action === 'login') {
                    isInResetMode = false;
                    resetToken = null;
                    switchAuthMode('login');
                } else if (action === 'register') {
                    switchAuthMode('register');
                } else if (action === 'forgot-password') {
                    switchAuthMode('forgot-password');
                }
            }
        });
    }

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAuthElements);
} else {
    // DOM is already loaded
    initializeAuthElements();
}

// Initialize authentication when page loads
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
});

// Helper function to update fetch calls to use BASE_URL
// Always includes credentials to ensure cookies are sent/received
function apiFetch(path, options = {}) {
    const defaultOptions = {
        credentials: 'include',  // Always include cookies for authentication
        ...options
    };
    return fetch(BASE_URL + path, defaultOptions);
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
        document.getElementById("summaryStats").classList.remove("disabled");
        updatePlaylistButtonState(); // Use the new button state logic
        updateStatsButtonState();
    }
}

///////////////////////////////////////////////////////////////
//////// Create dynamic variables here functions here /////////
///////////////////////////////////////////////////////////////

// State variables to track progress
let isSpotifyAuthorized = false;
let isSystemSetup = false;
// Note: Data preparation step removed - optimized queries work directly with database

// Step management
const steps = ['spotifyAuth', 'systemSetup', 'chatSearch', 'summaryStats', 'playlistCreation'];
const stepTitles = {
    'spotifyAuth': 'Spotify Authorization',
    'systemSetup': 'System Setup', 
    'chatSearch': 'Chat Search & Selection',
    'summaryStats': 'Summary Statistics',
    'playlistCreation': 'Playlist Creation'
};
let currentStep = 0;

// DOM elements
const floatingProgress = document.getElementById("floatingProgress");
const spotifySection = document.getElementById("spotifyAuth");
const systemSection = document.getElementById("systemSetup");
const chatSection = document.getElementById("chatSearch");
const playlistSection = document.getElementById("playlistCreation");

// Data preparation elements removed - no longer needed with optimized queries

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const chatTable = document.getElementById("chatTable");
const chatTableBody = document.getElementById("chatTableBody");
const selectedChatsDisplay = document.getElementById("selectedChatsDisplay");
const clearSelectedChatsButton = document.getElementById("clearSelectedChats");

// Chat selection state
// Store selected chats by chat_id (integer) for multi-chat playlist creation
const selectedChats = new Set(); // Set of chat_ids (integers)
const selectedChatsInfo = new Map(); // Map<chat_id, chat_info> for display purposes

// Initialize floating progress with all steps (updated for new step order)
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
            // Only collapse steps 1-2 (index 0,1) - spotifyAuth and systemSetup
            if (index < 2) {
                section.classList.add('collapsed');
            }
            // Steps 2 and above (chatSearch, summaryStats, playlistCreation) stay open
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
    
    // Only add steps 1-2 to floating progress (collapse them)
    // Steps: 0=spotifyAuth, 1=systemSetup, 2=chatSearch, 3=summaryStats, 4=playlistCreation
    if (currentStep < 2) {
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
    
    // Set as current step for proper display and keep it open
    currentStep = stepIndex;
    updateSectionStates();
    updateFloatingProgress();
    
    // Scroll to the restored section
    setTimeout(() => {
        section.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
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
//////// Data Preparation Functions - REMOVED
///////////////////////////////////////////////////////////////
// Data preparation is no longer needed - optimized queries work directly with database

// Enable sections that depend on system setup (no data preparation needed with optimized queries)
function enableDependentSections() {
    chatSection.classList.remove("disabled");
    const summaryStatsSection = document.getElementById("summaryStats");
    if (summaryStatsSection) {
        summaryStatsSection.classList.remove("disabled");
    }
    searchInput.disabled = false;
    searchButton.disabled = false;
    updatePlaylistButtonState();
    updateStatsButtonState();
}

// Disable sections that depend on data preparation
function disableDependentSections() {
    chatSection.classList.add("disabled");
    const summaryStatsSection = document.getElementById("summaryStats");
    if (summaryStatsSection) {
        summaryStatsSection.classList.add("disabled");
    }
    searchInput.disabled = true;
    searchButton.disabled = true;
    document.getElementById("playlistCreation").classList.add("disabled");
    updatePlaylistButtonState();
    updateStatsButtonState();
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
// Data preparation functions removed - no longer needed with optimized queries
// The optimized endpoints work directly with the database without upfront processing

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
    
    // Function to update button state based on authentication
    function updateSpotifyButtonState() {
        if (spotifyButton) {
            if (!isAuthenticated || !currentUser) {
                spotifyButton.disabled = true;
                spotifyButton.title = "Please log in first to authorize Spotify";
                spotifyButton.style.opacity = "0.6";
                spotifyButton.style.cursor = "not-allowed";
                console.log("Spotify button disabled - user not authenticated");
            } else {
                spotifyButton.disabled = false;
                spotifyButton.title = "Authorize Spotify to create playlists";
                spotifyButton.style.opacity = "1";
                spotifyButton.style.cursor = "pointer";
                console.log("Spotify button enabled - user authenticated:", currentUser.username);
            }
        }
    }
    
    // Update button state initially (will be disabled until auth check completes)
    updateSpotifyButtonState();
    
    // Also update after a short delay to catch async auth checks
    setTimeout(updateSpotifyButtonState, 500);
    
    spotifyButton.addEventListener("click", async (event) => {
        console.log("Spotify button clicked!");
        console.log("Event object:", event);
        console.log("Current auth state - isAuthenticated:", isAuthenticated, "currentUser:", currentUser);
        
        // Double-check authentication before proceeding - re-check if needed
        if (!isAuthenticated || !currentUser) {
            console.warn("Auth state appears invalid, re-checking authentication status...");
            // Try to re-check auth status
            try {
                const authCheck = await fetch(`${AUTH_BASE_URL}/status`, {
                    credentials: 'include'
                });
                const authData = await authCheck.json();
                console.log("Re-check auth response:", authData);
                
                if (authData.authenticated && authData.user) {
                    // Update auth state
                    isAuthenticated = true;
                    currentUser = authData.user;
                    console.log("Auth state updated - proceeding with Spotify authorization");
                    // Continue with the flow below
                } else {
                    console.error("User not authenticated - showing login modal");
                    alert("You must be logged in to authorize Spotify. Please log in first.");
                    showAuthModal();
                    return;
                }
            } catch (error) {
                console.error("Error re-checking auth:", error);
                alert("You must be logged in to authorize Spotify. Please log in first.");
                showAuthModal();
                return;
            }
        }
        
        try {
            console.log("Fetching client ID...");
            const response = await apiFetch('/get-client-id');
            console.log("Response received:", response);
            const data = await response.json();
            console.log("Data parsed:", data);
            
            if (response.ok) {
                const clientId = data.client_id;
                // CRITICAL: Use redirect_uri from backend - it MUST match Spotify Dashboard exactly
                const redirectUri = data.redirect_uri;
                
                console.log("=== SPOTIFY OAUTH DEBUG ===");
                console.log("Full response data:", data);
                console.log("Authenticated status:", data.authenticated);
                
                if (!redirectUri) {
                    console.error("ERROR: Backend did not provide redirect_uri!");
                    alert("Error: Spotify redirect URI not configured. Please check server configuration.");
                    return;
                }
                
                // Validate redirect URI format
                if (redirectUri.includes('localhost')) {
                    console.error("ERROR: Redirect URI contains 'localhost' - Spotify requires 127.0.0.1!");
                    alert("Error: Redirect URI configuration error. Server is using 'localhost' but Spotify requires '127.0.0.1'. Please check server configuration.");
                    return;
                }
                
                // Check authentication status
                if (!data.authenticated || !data.session_id) {
                    console.error("ERROR: User not authenticated or no session ID");
                    console.error("Auth status:", data.authenticated, "Session ID:", data.session_id ? "present" : "missing");
                    alert("Error: You must be logged in to authorize Spotify. Please log in and try again.");
                    // Force re-check of auth status
                    await checkAuthStatus();
                    return;
                }
                
                const scope = 'playlist-modify-public playlist-modify-private';
                
                // Get session ID from backend response (cookie is httponly, so JS can't read it)
                // This ensures we can identify the user even if cookies aren't sent on redirect
                const sessionId = data.session_id;
                
                console.log("Client ID:", clientId);
                console.log("Redirect URI (from backend):", redirectUri);
                console.log("Current window.location.origin:", window.location.origin);
                console.log("Scope:", scope);
                console.log("Session ID (from backend):", sessionId ? sessionId.substring(0, 10) + '...' : 'NOT FOUND');
                
                // Double-check the redirect URI before sending
                const expectedUri = "http://127.0.0.1:8888/callback";
                if (redirectUri !== expectedUri) {
                    console.error(`ERROR: Redirect URI mismatch!`);
                    console.error(`  Expected: ${expectedUri}`);
                    console.error(`  Got: ${redirectUri}`);
                    alert(`Configuration Error: Redirect URI is "${redirectUri}" but should be "${expectedUri}". Please check server .env file and restart server.`);
                    return;
                }
                
                // Build auth URL with state parameter containing session ID
                // CRITICAL: Always include state parameter with session ID
                const authUrl = `https://accounts.spotify.com/authorize?response_type=code&client_id=${clientId}&scope=${encodeURIComponent(scope)}&redirect_uri=${encodeURIComponent(redirectUri)}&state=${encodeURIComponent(sessionId)}`;
                
                console.log("Including session ID in state parameter");
                console.log("Full Auth URL (first 200 chars):", authUrl.substring(0, 200) + '...');
                console.log("===========================");
                
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
    const count = selectedChats.size;
    const countElement = document.getElementById('selectedChatCount');
    if (countElement) {
        countElement.textContent = count;
    }
    
    if (selectedChats.size === 0) {
        selectedChatsDisplay.innerHTML = '<p style="color: #666; font-style: italic;">No chats selected</p>';
        clearSelectedChatsButton.style.display = 'none';
    } else {
        const chatItems = Array.from(selectedChats).map(chatId => {
            const chatInfo = selectedChatsInfo.get(chatId);
            const displayName = chatInfo ? chatInfo.name : `Chat ${chatId}`;
            return `<span class="selected-chat-badge">
                ${displayName} (ID: ${chatId})
                <button class="remove-chat" onclick="removeSelectedChat(${chatId})" title="Remove chat">×</button>
            </span>`;
        }).join('');
        selectedChatsDisplay.innerHTML = chatItems;
        clearSelectedChatsButton.style.display = 'inline-block';
    }
    updatePlaylistButtonState();
    updateStatsButtonState();
}

// Update stats button state based on selected chats
function updateStatsButtonState() {
    const statsButton = document.getElementById("generateStatsButton");
    if (statsButton) {
        if (selectedChats.size > 0) {
            statsButton.disabled = false;
            statsButton.style.opacity = "1";
            statsButton.title = `Generate statistics for ${selectedChats.size} selected chat(s)`;
        } else {
            statsButton.disabled = true;
            statsButton.style.opacity = "0.6";
            statsButton.title = "Please select at least one chat first";
        }
    }
}

// Remove a selected chat (by chat_id)
function removeSelectedChat(chatId) {
    selectedChats.delete(chatId);
    selectedChatsInfo.delete(chatId);
    updateSelectedChatsDisplay();
    
    // Uncheck the checkbox if it's currently visible
    const checkboxes = document.querySelectorAll('.chat-checkbox');
    checkboxes.forEach(checkbox => {
        if (parseInt(checkbox.dataset.chatId) === chatId) {
            checkbox.checked = false;
        }
    });
}

// Make removeSelectedChat available globally
window.removeSelectedChat = removeSelectedChat;

// Clear all selected chats
clearSelectedChatsButton.addEventListener('click', () => {
    selectedChats.clear();
    selectedChatsInfo.clear();
    updateSelectedChatsDisplay();
    
    // Uncheck all checkboxes
    const checkboxes = document.querySelectorAll('.chat-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = false);
});

// Handle chat checkbox changes (now using chat_id)
function handleChatSelection(event) {
    const checkbox = event.target;
    const chatId = parseInt(checkbox.dataset.chatId);
    const chatInfo = JSON.parse(checkbox.dataset.chatInfo || '{}');
    
    if (checkbox.checked) {
        selectedChats.add(chatId);
        selectedChatsInfo.set(chatId, chatInfo);
    } else {
        selectedChats.delete(chatId);
        selectedChatsInfo.delete(chatId);
    }
    
    updateSelectedChatsDisplay();
}

// Perform chat search (using optimized endpoint)
async function performSearch(searchTerm) {
    try {
        searchButton.disabled = true;
        searchButton.textContent = "Searching...";
        chatTableBody.innerHTML = "<tr><td colspan='8'>Searching chats...</td></tr>";
        chatTable.style.display = "table";
        
        // Use optimized endpoint that returns chat_id and recent_messages
        const response = await apiFetch(`/chat-search-optimized?query=${encodeURIComponent(searchTerm)}`);
        const results = await response.json();
        
        if (Array.isArray(results)) {
            displaySearchResults(results);
        } else {
            chatTableBody.innerHTML = `<tr><td colspan='8'>${results.message || 'No results found'}</td></tr>`;
        }
    } catch (error) {
        console.error('Error performing search:', error);
        chatTableBody.innerHTML = "<tr><td colspan='8'>Error occurred while searching</td></tr>";
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = "Search Chats";
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Global variables for sorting
let currentSortColumn = null;
let currentSortDirection = 'asc'; // 'asc' or 'desc'
let currentSearchResults = []; // Store results for sorting

// Display search results (updated - no recent messages in main table)
function displaySearchResults(results) {
    currentSearchResults = results; // Store for sorting
    chatTableBody.innerHTML = "";
    
    if (results.length === 0) {
        chatTableBody.innerHTML = "<tr><td colspan='8'>No chats found matching your search</td></tr>";
        return;
    }
    
    // Add header note about multi-select
    const headerNote = document.createElement('tr');
    headerNote.style.backgroundColor = '#e3f2fd';
    headerNote.innerHTML = `
        <td colspan="8" style="padding: 8px; text-align: center; font-size: 0.9em; font-weight: bold;">
            💡 You can select multiple chats to combine them in one playlist! Check the boxes to select.<br>
            <span style="font-size: 0.85em; color: #666;">Click "View Details" to see recent messages and more info</span>
        </td>
    `;
    chatTableBody.appendChild(headerNote);
    
    // Sort results if needed
    const sortedResults = sortResults(results, currentSortColumn, currentSortDirection);
    
    sortedResults.forEach(chat => {
        const row = chatTableBody.insertRow();
        const chatId = chat.chat_id;
        const isSelected = selectedChats.has(chatId);
        
        // Format last message date
        let lastMessageDate = 'N/A';
        if (chat.last_message_date) {
            try {
                const date = new Date(chat.last_message_date);
                lastMessageDate = date.toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
                });
            } catch (e) {
                lastMessageDate = chat.last_message_date.substring(0, 10);
            }
        }
        
        row.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="chat-checkbox" 
                       data-chat-id="${chatId}"
                       data-chat-info='${JSON.stringify(chat).replace(/'/g, "&#39;")}'
                       ${isSelected ? 'checked' : ''}
                       title="Select to include in playlist">
            </td>
            <td style="font-weight: 500;">${chat.name || 'Unnamed Chat'}</td>
            <td style="font-size: 0.85em; color: #666;">${chatId}</td>
            <td>${chat.members || 0}</td>
            <td>${chat.total_messages || 0}</td>
            <td>${chat.user_messages || 0}</td>
            <td style="font-size: 0.9em;">${lastMessageDate}</td>
            <td style="text-align: center;">
                <button class="view-details-btn" data-chat-id="${chatId}" 
                        style="background: #007bff; color: white; border: none; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                    View Details
                </button>
            </td>
        `;
        
        // Add event listener to checkbox
        const checkbox = row.querySelector('.chat-checkbox');
        if (checkbox) {
            checkbox.addEventListener('change', handleChatSelection);
        }
        
        // Add event listener to view details button
        const detailsBtn = row.querySelector('.view-details-btn');
        if (detailsBtn) {
            detailsBtn.addEventListener('click', () => showChatDetails(chat));
        }
    });
}

// Sort results function
function sortResults(results, column, direction) {
    if (!column) return results;
    
    const sorted = [...results].sort((a, b) => {
        let aVal, bVal;
        
        switch(column) {
            case 'name':
                aVal = (a.name || '').toLowerCase();
                bVal = (b.name || '').toLowerCase();
                break;
            case 'members':
                aVal = a.members || 0;
                bVal = b.members || 0;
                break;
            case 'total_messages':
                aVal = a.total_messages || 0;
                bVal = b.total_messages || 0;
                break;
            case 'last_message_date':
                aVal = a.last_message_date ? new Date(a.last_message_date).getTime() : 0;
                bVal = b.last_message_date ? new Date(b.last_message_date).getTime() : 0;
                break;
            default:
                return 0;
        }
        
        if (aVal < bVal) return direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return direction === 'asc' ? 1 : -1;
        return 0;
    });
    
    return sorted;
}

// Show chat details modal
function showChatDetails(chat) {
    const modal = document.getElementById('chatDetailsModal');
    const title = document.getElementById('chatDetailsTitle');
    const content = document.getElementById('chatDetailsContent');
    
    title.textContent = `${chat.name || 'Unnamed Chat'} (ID: ${chat.chat_id})`;
    
    // Format last message date
    let lastMessageDate = 'N/A';
    if (chat.last_message_date) {
        try {
            const date = new Date(chat.last_message_date);
            lastMessageDate = date.toLocaleString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });
        } catch (e) {
            lastMessageDate = chat.last_message_date;
        }
    }
    
    let html = `
        <div style="margin-bottom: 20px;">
            <h3 style="margin-bottom: 10px;">Chat Information</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Chat Name:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.name || 'Unnamed Chat'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Chat ID:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.chat_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Chat Identifier:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.chat_identifier || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Members:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.members || 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Total Messages:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.total_messages || 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">My Messages:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${chat.user_messages || 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: 500;">Most Recent Message:</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${lastMessageDate}</td>
                </tr>
            </table>
        </div>
    `;
    
    // Add recent messages section
    if (chat.recent_messages && chat.recent_messages.length > 0) {
        html += `
            <div>
                <h3 style="margin-bottom: 10px;">Recent Messages</h3>
                <div class="chat-details-messages">
        `;
        
        chat.recent_messages.forEach((msg) => {
            const text = msg.text || 'No text';
            let dateStr = '';
            if (msg.date) {
                try {
                    const date = new Date(msg.date);
                    dateStr = date.toLocaleString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit'
                    });
                } catch (e) {
                    dateStr = msg.date.substring(0, 16);
                }
            }
            const isFromMe = msg.is_from_me;
            const messageClass = isFromMe ? 'from-me' : '';
            // Use sender_name from backend (name, phone number, or email)
            const senderName = msg.sender_name || (isFromMe ? 'You' : 'Unknown');
            const senderLabel = isFromMe 
                ? '<strong style="color: #007bff;">You</strong>' 
                : `<strong style="color: #6c757d;">${escapeHtml(senderName)}</strong>`;
            
            html += `
                <div class="chat-details-message ${messageClass}">
                    <div style="margin-bottom: 5px;">
                        ${senderLabel} <span style="color: #999; font-size: 0.85em;">${dateStr}</span>
                    </div>
                    <div style="color: #333; line-height: 1.5;">${escapeHtml(text)}</div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    } else {
        html += `
            <div>
                <h3 style="margin-bottom: 10px;">Recent Messages</h3>
                <p style="color: #999; font-style: italic;">No recent messages available</p>
            </div>
        `;
    }
    
    content.innerHTML = html;
    modal.style.display = 'block';
}

// Close chat details modal
const chatDetailsModal = document.getElementById('chatDetailsModal');
const closeChatDetailsBtn = document.getElementById('closeChatDetails');
if (closeChatDetailsBtn) {
    closeChatDetailsBtn.addEventListener('click', () => {
        chatDetailsModal.style.display = 'none';
    });
}
// Close modal when clicking outside
if (chatDetailsModal) {
    chatDetailsModal.addEventListener('click', (e) => {
        if (e.target === chatDetailsModal) {
            chatDetailsModal.style.display = 'none';
        }
    });
}

// Search button click handler
searchButton.addEventListener("click", () => {
    const searchTerm = searchInput.value.trim();
    if (searchTerm) {
        performSearch(searchTerm);
    }
});

// Add sorting functionality to table headers
// Wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSorting);
} else {
    initSorting();
}

function initSorting() {
    const sortableHeaders = document.querySelectorAll('#chatTable .sortable');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const column = header.dataset.sort;
            
            // Update sort direction
            if (currentSortColumn === column) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = column;
                currentSortDirection = 'asc';
            }
            
            // Update visual indicators
            sortableHeaders.forEach(h => {
                h.classList.remove('sort-asc', 'sort-desc');
            });
            header.classList.add(`sort-${currentSortDirection}`);
            
            // Re-display results with new sort
            if (currentSearchResults.length > 0) {
                displaySearchResults(currentSearchResults);
            }
        });
    });
}

// View All Chats button
const viewAllChatsButton = document.getElementById("viewAllChatsButton");
if (viewAllChatsButton) {
    viewAllChatsButton.addEventListener("click", async () => {
        try {
            viewAllChatsButton.disabled = true;
            viewAllChatsButton.textContent = "Loading...";
            chatTableBody.innerHTML = "<tr><td colspan='8'>Loading all chats...</td></tr>";
            chatTable.style.display = "table";
            
            const response = await apiFetch("/chats");
            const results = await response.json();
            
            if (Array.isArray(results)) {
                displaySearchResults(results);
            } else {
                chatTableBody.innerHTML = `<tr><td colspan='8'>${results.message || 'No chats found'}</td></tr>`;
            }
        } catch (error) {
            console.error('Error loading all chats:', error);
            chatTableBody.innerHTML = "<tr><td colspan='8'>Error occurred while loading chats</td></tr>";
        } finally {
            viewAllChatsButton.disabled = false;
            viewAllChatsButton.textContent = "View All Chats";
        }
    });
}

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
    
    const createButton = document.getElementById("createPlaylist");
    
    if (hasSelections && hasSpotifyAuth) {
        createButton.disabled = false;
        createButton.style.opacity = "1";
        createButton.title = "";
        playlistSection.classList.remove("disabled");
        
        // Move to playlist creation step if we're not already there
        // Note: Steps are now: 0=spotifyAuth, 1=systemSetup, 2=chatSearch, 3=summaryStats, 4=playlistCreation
        if (currentStep < 4) {
            currentStep = 4;
            updateSectionStates();
        }
    } else {
        createButton.disabled = true;
        createButton.style.opacity = "0.6";
        
        if (!hasSpotifyAuth) {
            createButton.title = "Please complete Spotify authorization first";
        } else if (!hasSelections) {
            createButton.title = "Please select at least one chat";
        }
    }
}

// Handle playlist form submission
document.getElementById("playlistForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const statusDiv = document.getElementById("playlistStatus");
    const createButton = document.getElementById("createPlaylist");
    
    // Validate form inputs
    const playlistName = document.getElementById("playlistName").value.trim();
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const selectedChatIds = Array.from(selectedChats);
    
    if (!playlistName) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Please enter a playlist name</div>';
        return;
    }
    
    if (!startDate || !endDate) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Please select both start and end dates</div>';
        return;
    }
    
    if (selectedChatIds.length === 0) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Please select at least one chat</div>';
        return;
    }
    
    // Validate date range
    if (new Date(startDate) > new Date(endDate)) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Start date must be before end date</div>';
        return;
    }

    const playlistNameInput = document.getElementById("playlistName");
    const wasDisabled = playlistNameInput.disabled;
    if (wasDisabled) playlistNameInput.disabled = false; // Enable if disabled

    const formData = new FormData(event.target);

    if (wasDisabled) playlistNameInput.disabled = true; // Restore disabled state

    // Use chat_ids instead of chat names for the optimized endpoint
    formData.append("selected_chat_ids", JSON.stringify(selectedChatIds));

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

        // Use optimized endpoint that supports multiple chat_ids
        const response = await apiFetch("/create-playlist-optimized", {
            method: "POST",
            body: formData,
        });

        // Check if response is OK
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: `;
            try {
                const errorData = await response.json();
                errorMessage += errorData.detail || errorData.message || 'Unknown error';
            } catch (e) {
                errorMessage += await response.text() || 'Unknown error';
            }
            statusDiv.innerHTML = `<div class="status-indicator status-error">❌ ${errorMessage}</div>`;
            console.error("Playlist creation failed:", errorMessage);
            return;
        }

        const result = await response.json();

        if (result.status === "success") {
            const successMessage = result.playlist_url 
                ? `${result.message}<br><a href="${result.playlist_url}" target="_blank" style="color: #007bff; text-decoration: underline;">Open Playlist on Spotify</a>`
                : result.message;
            statusDiv.innerHTML = `<div class="status-indicator status-success">✅ ${successMessage}<br>Added ${result.tracks_added || 0} tracks (found ${result.total_tracks_found || 0} total)</div>`;

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
        } else if (result.status === "warning") {
            statusDiv.innerHTML = `<div class="status-indicator status-warning" style="background-color: #fff3cd; color: #856404; border-color: #ffeaa7;">⚠️ ${result.message}</div>`;
        } else {
            statusDiv.innerHTML = `<div class="status-indicator status-error">❌ ${result.message || result.detail || 'Unknown error occurred'}</div>`;
        }
    } catch (error) {
        console.error("Error creating playlist:", error);
        const errorMessage = error.message || 'An error occurred while creating the playlist';
        statusDiv.innerHTML = `<div class="status-indicator status-error">❌ ${errorMessage}</div>`;
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
    
    console.log("Page state cleaned up and reset");
}

// Generate Summary Statistics
const generateStatsButton = document.getElementById("generateStatsButton");
if (generateStatsButton) {
    generateStatsButton.addEventListener("click", async () => {
        if (selectedChats.size === 0) {
            alert("Please select at least one chat first.");
            return;
        }
        
        const startDate = document.getElementById("startDate").value;
        const endDate = document.getElementById("endDate").value;
        
        if (!startDate || !endDate) {
            alert("Please set start and end dates first (in Playlist Creation section).");
            return;
        }
        
        const statusDiv = document.getElementById("statsStatus");
        const resultsDiv = document.getElementById("statsResults");
        const contentDiv = document.getElementById("statsContent");
        
        try {
            generateStatsButton.disabled = true;
            generateStatsButton.textContent = "Generating...";
            statusDiv.innerHTML = '<div class="status-indicator status-info">Generating statistics...</div>';
            resultsDiv.style.display = "none";
            
            const chatIds = Array.from(selectedChats);
            const response = await apiFetch("/summary-stats", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    chat_ids: JSON.stringify(chatIds),
                    start_date: startDate,
                    end_date: endDate
                })
            });
            
            const stats = await response.json();
            
            if (response.ok && stats) {
                // Format and display statistics
                let html = "<h3>📊 Chat Statistics</h3>";
                
                if (stats.total_messages) {
                    html += `<p><strong>Total Messages:</strong> ${stats.total_messages}</p>`;
                }
                
                if (stats.spotify_links && stats.spotify_links.length > 0) {
                    html += `<p><strong>Total Spotify Links:</strong> ${stats.spotify_links.length}</p>`;
                }
                
                if (stats.top_senders && stats.top_senders.length > 0) {
                    html += "<h4>🎵 Top Song Senders:</h4><ul>";
                    stats.top_senders.slice(0, 10).forEach((sender, idx) => {
                        html += `<li>${idx + 1}. ${sender.name || sender.handle}: ${sender.count} song(s)</li>`;
                    });
                    html += "</ul>";
                }
                
                if (stats.most_liked_songs && stats.most_liked_songs.length > 0) {
                    html += "<h4>❤️ Most Liked Songs:</h4><ul>";
                    stats.most_liked_songs.slice(0, 10).forEach((song, idx) => {
                        html += `<li>${idx + 1}. ${song.title || song.url}: ${song.like_count} like(s)</li>`;
                    });
                    html += "</ul>";
                }
                
                if (stats.date_range) {
                    html += `<p><strong>Date Range:</strong> ${stats.date_range.start} to ${stats.date_range.end}</p>`;
                }
                
                contentDiv.innerHTML = html;
                resultsDiv.style.display = "block";
                statusDiv.innerHTML = '<div class="status-indicator status-success">✅ Statistics generated successfully!</div>';
            } else {
                statusDiv.innerHTML = `<div class="status-indicator status-error">❌ ${stats.detail || 'Error generating statistics'}</div>`;
            }
        } catch (error) {
            console.error("Error generating statistics:", error);
            statusDiv.innerHTML = '<div class="status-indicator status-error">❌ An error occurred while generating statistics</div>';
        } finally {
            generateStatsButton.disabled = false;
            generateStatsButton.textContent = "Generate Statistics";
        }
    });
}

// Initialize the interface
cleanupAndReset();
initializeFloatingProgress();
updateSelectedChatsDisplay();
updatePlaylistButtonState();
updateStatsButtonState();

// Make sure summary stats section is enabled when chat search is enabled
const chatSearchSection = document.getElementById("chatSearch");
if (chatSearchSection) {
    const observer = new MutationObserver(() => {
        if (!chatSearchSection.classList.contains("disabled")) {
            const summaryStatsSection = document.getElementById("summaryStats");
            if (summaryStatsSection) {
                summaryStatsSection.classList.remove("disabled");
            }
        }
    });
    observer.observe(chatSearchSection, { attributes: true, attributeFilter: ['class'] });
}

// Explicitly initialize the login form with forgot password link
console.log('Initializing login form with forgot password link');
switchAuthMode('login');

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
