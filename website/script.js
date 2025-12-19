console.log("script.js loaded!");
console.log("BASE_URL:", typeof BASE_URL !== 'undefined' ? BASE_URL : 'NOT DEFINED');

// Global variables for authentication
let isAuthenticated = false;
let currentUser = null;
let isInResetMode = false; // Track if we're in password reset mode
let resetToken = null; // Store the reset token from URL
// BASE_URL is defined in config.js - make sure it's loaded first
// Since config.js loads before this script, BASE_URL should always be defined
// Just use it directly - if it's undefined, we'll get a clear error
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
    
    // First, check if we're in local mode (no auth endpoints)
    try {
        const healthResponse = await fetch(`${BASE_URL}/health`);
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            // If health endpoint indicates local mode, skip auth
            if (healthData.environment === "local" || !healthData.hasOwnProperty("environment")) {
                console.log("Local mode detected - skipping authentication");
                isAuthenticated = true; // Set to true for local mode
                console.log("Calling showMainApp()...");
                showMainApp();
                console.log("showMainApp() called");
                // Enable Spotify button
                const spotifyButton = document.getElementById("authorizeSpotify");
                if (spotifyButton) {
                    spotifyButton.disabled = false;
                    spotifyButton.title = "Authorize Spotify to create playlists";
                    spotifyButton.style.opacity = "1";
                    spotifyButton.style.cursor = "pointer";
                }
                return; // Skip auth check
            }
        }
    } catch (error) {
        console.log("Health check failed, will try auth check:", error);
    }
    
    // Try auth endpoint (legacy - not used in local mode)
    try {
        const response = await fetch(`${AUTH_BASE_URL}/status`, {
            credentials: 'include'  // Ensure cookies are sent
        });
        
        if (!response.ok) {
            // If 404, auth endpoint doesn't exist - assume local mode
            if (response.status === 404) {
                console.log("Auth endpoint not found - assuming local mode");
                isAuthenticated = true;
                showMainApp();
                const spotifyButton = document.getElementById("authorizeSpotify");
                if (spotifyButton) {
                    spotifyButton.disabled = false;
                    spotifyButton.title = "Authorize Spotify to create playlists";
                    spotifyButton.style.opacity = "1";
                    spotifyButton.style.cursor = "pointer";
                }
                return;
            }
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
        // If auth endpoint doesn't exist (network error), assume local mode
        console.log("Auth check failed - assuming local mode:", error);
        isAuthenticated = true;
        showMainApp();
        const spotifyButton = document.getElementById("authorizeSpotify");
        if (spotifyButton) {
            spotifyButton.disabled = false;
            spotifyButton.title = "Authorize Spotify to create playlists";
            spotifyButton.style.opacity = "1";
            spotifyButton.style.cursor = "pointer";
        }
    }
}

// Show authentication modal
function showAuthModal() {
    console.log('showAuthModal called, authOverlay:', authOverlay);
    if (!authOverlay) {
        console.error('authOverlay not initialized! Trying to initialize now...');
        initializeAuthElements();
        if (!authOverlay) {
            console.error('Failed to initialize authOverlay!');
            return;
        }
    }
    authOverlay.style.display = 'flex';
    if (userBar) userBar.style.display = 'none';
    if (mainContent) {
        mainContent.classList.remove('visible');
    }
    document.body.classList.remove('authenticated');
    
    // Make sure login form is visible
    if (loginForm) {
        loginForm.style.display = 'block';
    }
    if (registerForm) {
        registerForm.style.display = 'none';
    }
    if (forgotPasswordForm) {
        forgotPasswordForm.style.display = 'none';
    }
    if (resetPasswordForm) {
        resetPasswordForm.style.display = 'none';
    }
    
    console.log('Auth modal should now be visible');
}

// Show main application
function showMainApp() {
    // Ensure all elements are initialized
    if (!authOverlay || !mainContent || !userBar) {
        console.log('Elements not initialized, initializing now...');
        initializeDOMElements();
        initializeAuthElements();
    }
    
    if (authOverlay) authOverlay.style.display = 'none';
    
    // In local mode (no currentUser), hide the user bar
    if (userBar) {
        if (currentUser) {
            userBar.style.display = 'flex';
        } else {
            // Local mode - hide user bar
            userBar.style.display = 'none';
        }
    }
    
    if (mainContent) {
        mainContent.classList.add('visible');
        // Also set display style directly as fallback
        mainContent.style.display = 'block';
        console.log('Main content should now be visible, class:', mainContent.className);
    } else {
        console.error('mainContent element not found!');
        // Try to get it directly
        mainContent = document.getElementById('mainContent');
        if (mainContent) {
            mainContent.classList.add('visible');
            mainContent.style.display = 'block';
            console.log('Main content found and made visible');
        } else {
            console.error('Could not find mainContent element at all!');
        }
    }
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
    // In local mode (isAuthenticated but no currentUser), enable the button
    const spotifyButton = document.getElementById("authorizeSpotify");
    if (spotifyButton) {
        if (isAuthenticated && (currentUser || !currentUser)) {  // Allow local mode
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
            const userProfileEl = document.getElementById('userProfile');
            const userProfileContainer = document.getElementById('userProfileContainer');
            if (userProfileEl) {
                userProfileEl.innerHTML = `
                    <strong>Name:</strong> ${profile.display_name}<br>
                    <strong>Email:</strong> ${profile.email || 'N/A'}<br>
                    <strong>Country:</strong> ${profile.country || 'N/A'}
                `;
            }
            if (userProfileContainer) {
                userProfileContainer.style.display = 'block';
            }
            
            // Update button text
            const spotifyButton = document.getElementById("authorizeSpotify");
            if (spotifyButton) {
                spotifyButton.textContent = "Reconnect to Spotify";
            }
            
            // Enable next steps
            isSpotifyAuthorized = true;
            completeCurrentStep();
            console.log("Spotify authorization confirmed - step completed");
        } else {
            // User doesn't have valid Spotify tokens
            updateStatus(
                document.getElementById("spotifyStatus"),
                document.getElementById("spotifyStatusText"),
                "Not connected to Spotify",
                "pending"
            );
            isSpotifyAuthorized = false;
        }
    } catch (error) {
        console.log('Spotify not connected yet:', error);
        isSpotifyAuthorized = false;
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
            authSwitchText.innerHTML = 'Already have an account? <a href="javascript:void(0)" data-auth-action="login">Login</a>';
            // Re-attach event listeners to new links
            attachAuthLinkListeners();
            break;
            
        case 'forgot-password':
            authTitle.textContent = 'Reset Password';
            forgotPasswordForm.style.display = 'block';
            authSwitchText.innerHTML = 'Remember your password? <a href="javascript:void(0)" data-auth-action="login">Login</a>';
            // Re-attach event listeners to new links
            attachAuthLinkListeners();
            break;
            
        case 'reset-password':
            authTitle.textContent = 'Set New Password';
            resetPasswordForm.style.display = 'block';
            authSwitchText.innerHTML = 'Go back to <a href="javascript:void(0)" data-auth-action="login">Login</a>';
            // Re-attach event listeners to new links
            attachAuthLinkListeners();
            break;
            
        default: // login
            authTitle.textContent = 'Welcome Back';
            loginForm.style.display = 'block';
            const newHTML = 'Don\'t have an account? <a href="javascript:void(0)" data-auth-action="register">Register</a> | <a href="javascript:void(0)" data-auth-action="forgot-password">Forgot Password?</a>';
            console.log('Setting authSwitchText innerHTML to:', newHTML);
            authSwitchText.innerHTML = newHTML;
            // Re-attach event listeners to new links
            attachAuthLinkListeners();
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

// Helper function to attach listeners to auth links (must be defined before initializeAuthElements)
function attachAuthLinkListeners() {
    if (!authSwitchText) return;
    
    const authLinks = authSwitchText.querySelectorAll('a[data-auth-action]');
    authLinks.forEach(link => {
        // Remove any existing listeners by cloning the node
        const newLink = link.cloneNode(true);
        link.parentNode.replaceChild(newLink, link);
        
        // Attach new listener
        newLink.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            const action = newLink.getAttribute('data-auth-action');
            console.log('Auth link clicked:', action);
            if (action === 'login') {
                isInResetMode = false;
                resetToken = null;
                switchAuthMode('login');
            } else if (action === 'register') {
                switchAuthMode('register');
            } else if (action === 'forgot-password') {
                switchAuthMode('forgot-password');
            }
            return false;
        });
    });
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
    
    console.log('Elements found:', {
        loginForm: !!loginForm,
        registerForm: !!registerForm,
        authSwitchText: !!authSwitchText,
        authOverlay: !!authOverlay
    });
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
    // Use event delegation on the parent container to catch all clicks
    if (authSwitchText) {
        console.log('Setting up event listener on authSwitchText');
        authSwitchText.addEventListener('click', (e) => {
            console.log('Click detected on authSwitchText, target:', e.target, 'tagName:', e.target.tagName);
            // Find the closest <a> tag (handles clicks on text inside links)
            const link = e.target.closest('a[data-auth-action]');
            console.log('Closest link found:', link);
            if (link) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                const action = link.getAttribute('data-auth-action');
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
                return false;
            }
        }, true); // Use capture phase to catch events earlier
        console.log('Event listener attached to authSwitchText');
        
        // Also attach directly to each link as a backup
        attachAuthLinkListeners();
    } else {
        console.error('authSwitchText element not found!');
    }
}

// Initialize DOM elements
function initializeDOMElements() {
    // Initialize main content elements first (critical for showing app)
    mainContent = document.getElementById("mainContent");
    authOverlay = document.getElementById("authOverlay");
    userBar = document.getElementById("userBar");
    
    // Initialize other elements
    floatingProgress = document.getElementById("floatingProgress");
    spotifySection = document.getElementById("spotifyAuth");
    systemSection = document.getElementById("systemSetup");
    chatSection = document.getElementById("chatSearch");
    playlistSection = document.getElementById("playlistCreation");
    searchInput = document.getElementById("searchInput");
    searchButton = document.getElementById("searchButton");
    chatTable = document.getElementById("chatTable");
    chatTableBody = document.getElementById("chatTableBody");
    selectedChatsDisplay = document.getElementById("selectedChatsDisplay");
    clearSelectedChatsButton = document.getElementById("clearSelectedChats");
    
    console.log('DOMElements initialized:', {
        mainContent: !!mainContent,
        authOverlay: !!authOverlay,
        userBar: !!userBar
    });
}

// Initialize when DOM is ready
function initializeApp() {
    console.log('Initializing app, readyState:', document.readyState);
    
    // Initialize all DOM elements first
    initializeDOMElements();
    initializeAuthElements();
    
    // Hide auth overlay initially - checkAuthStatus will show it if needed
    // This prevents showing login modal in local mode
    if (authOverlay) {
        authOverlay.style.display = 'none';
    }
    
    // Show main content initially (will be hidden if auth is needed)
    if (mainContent) {
        mainContent.style.display = 'block';
        mainContent.classList.add('visible');
        document.body.classList.add('authenticated');
        console.log('Main content shown initially, will be hidden if auth needed');
    }
    
    // Enable Spotify button initially (will be disabled if auth check fails)
    const spotifyButton = document.getElementById("authorizeSpotify");
    if (spotifyButton) {
        spotifyButton.disabled = false;
        spotifyButton.style.opacity = "1";
        spotifyButton.style.cursor = "pointer";
        spotifyButton.title = "Authorize Spotify to create playlists";
        console.log('Spotify button enabled initially');
    }
    
    initializeLoginForm(); // Initialize login form after elements are ready
    
    // Check authentication status - this will determine if we show auth modal or main app
    checkAuthStatus();
    
    // Initialize other app features
    if (floatingProgress) {
        initializeFloatingProgress();
    }
    if (selectedChatsDisplay) {
        updateSelectedChatsDisplay();
    }
    
    // Set up all event listeners
    setupSearchHandlers();
    setupChatSelectionHandlers();
    setupSystemSetupHandlers();
    setupPlaylistHandlers();
    setupSpotifyHandlers();
    setupSortingHandlers();
    setupViewAllChatsHandler();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    // DOM is already loaded
    initializeApp();
}

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
const steps = ['spotifyAuth', 'systemSetup', 'chatSearch', 'playlistCreation'];
const stepTitles = {
    'spotifyAuth': 'Spotify Authorization',
    'systemSetup': 'System Setup', 
    'chatSearch': 'Chat Search & Selection',
    'playlistCreation': 'Playlist Creation'
};
let currentStep = 0;

// DOM elements - will be initialized when DOM is ready
let floatingProgress;
let spotifySection;
let systemSection;
let chatSection;
let playlistSection;
let searchInput;
let searchButton;
let chatTable;
let chatTableBody;
let selectedChatsDisplay;
let clearSelectedChatsButton;

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
            // Steps 2 and above (chatSearch, playlistCreation) stay open
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
    // Steps: 0=spotifyAuth, 1=systemSetup, 2=chatSearch, 3=playlistCreation
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
    searchInput.disabled = false;
    searchButton.disabled = false;
    updatePlaylistButtonState();
    updateStatsButtonState();
}

// Disable sections that depend on data preparation
function disableDependentSections() {
    chatSection.classList.add("disabled");
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
    console.log("Detected Spotify callback - checking authorization status...");
    // Clear the code from URL for cleaner navigation
    window.history.replaceState({}, document.title, window.location.pathname);
    
    // Check Spotify status and update UI
    checkSpotifyAuthStatus();
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
function setupSpotifyHandlers() {
    const spotifyButton = document.getElementById("authorizeSpotify");
    console.log("Spotify button element:", spotifyButton);
    if (!spotifyButton) {
        console.error("Spotify button not found!");
        return;
    }
    console.log("Adding event listener to Spotify button...");
    
    // Function to update button state based on authentication
    function updateSpotifyButtonState() {
        if (spotifyButton) {
            // In local mode, isAuthenticated is true but currentUser is null
            // Allow button if authenticated (either with user or in local mode)
            if (!isAuthenticated || (!currentUser && !isAuthenticated)) {
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
                if (currentUser) {
                    console.log("Spotify button enabled - user authenticated:", currentUser.username);
                } else {
                    console.log("Spotify button enabled - local mode (no user required)");
                }
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
        
        // In local mode, isAuthenticated is true but currentUser is null - that's OK, proceed
        // Only check auth if not authenticated
        if (!isAuthenticated) {
            console.warn("Not authenticated, checking if we're in local mode...");
            // Check if we're in local mode first
            try {
                const healthResponse = await fetch(`${BASE_URL}/health`);
                if (healthResponse.ok) {
                    const healthData = await healthResponse.json();
                    if (healthData.environment === "local") {
                        console.log("Local mode detected - proceeding without auth");
                        isAuthenticated = true;
                        // Continue with the flow below
                    } else {
                        // Not local mode, need auth
                        console.warn("Not in local mode, checking auth status...");
                        try {
                            const authCheck = await fetch(`${AUTH_BASE_URL}/status`, {
                                credentials: 'include'
                            });
                            const authData = await authCheck.json();
                            console.log("Re-check auth response:", authData);
                            
                            if (authData.authenticated) {
                                isAuthenticated = true;
                                currentUser = authData.user || null;
                                console.log("Auth state updated - proceeding with Spotify authorization");
                                // Continue with the flow below
                            } else {
                                console.error("User not authenticated - showing login modal");
                                alert("You must be logged in to authorize Spotify. Please log in first.");
                                showAuthModal();
                                return;
                            }
                        } catch (authError) {
                            console.error("Error checking auth:", authError);
                            alert("You must be logged in to authorize Spotify. Please log in first.");
                            showAuthModal();
                            return;
                        }
                    }
                }
            } catch (error) {
                console.error("Error checking health/local mode:", error);
                // If health check fails, try auth endpoint
                try {
                    const authCheck = await fetch(`${AUTH_BASE_URL}/status`, {
                        credentials: 'include'
                    });
                    if (authCheck.ok) {
                        const authData = await authCheck.json();
                        if (authData.authenticated) {
                            isAuthenticated = true;
                            currentUser = authData.user || null;
                            // Continue
                        } else {
                            alert("You must be logged in to authorize Spotify. Please log in first.");
                            showAuthModal();
                            return;
                        }
                    } else if (authCheck.status === 404) {
                        // Auth endpoint doesn't exist - assume local mode
                        console.log("Auth endpoint not found - assuming local mode");
                        isAuthenticated = true;
                        // Continue
                    } else {
                        alert("You must be logged in to authorize Spotify. Please log in first.");
                        showAuthModal();
                        return;
                    }
                } catch (authError) {
                    // If auth endpoint doesn't exist (network error), assume local mode
                    console.log("Auth endpoint not accessible - assuming local mode, proceeding");
                    isAuthenticated = true;
                    // Continue with the flow below
                }
            }
        }
        
        // If we get here, we're authenticated (either with user or in local mode) - proceed
        
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
                // In local mode, these fields won't exist - that's OK
                // Legacy multi-user mode support (not used)
                if (data.hasOwnProperty('authenticated') && (!data.authenticated || !data.session_id)) {
                    console.error("ERROR: User not authenticated or no session ID");
                    console.error("Auth status:", data.authenticated, "Session ID:", data.session_id ? "present" : "missing");
                    alert("Error: You must be logged in to authorize Spotify. Please log in and try again.");
                    // Force re-check of auth status
                    await checkAuthStatus();
                    return;
                }
                
                // If we're in local mode (no authenticated/session_id fields), proceed
                console.log("Proceeding with Spotify authorization (local mode or authenticated)");
                
                const scope = 'playlist-modify-public playlist-modify-private';
                
                // Get session ID from backend response (legacy multi-user mode)
                // In local mode, there's no session_id - that's OK
                const sessionId = data.session_id || null;
                
                console.log("Client ID:", clientId);
                console.log("Redirect URI (from backend):", redirectUri);
                console.log("Current window.location.origin:", window.location.origin);
                console.log("Scope:", scope);
                console.log("Session ID (from backend):", sessionId ? sessionId.substring(0, 10) + '...' : 'NOT FOUND (local mode)');
                
                // Double-check the redirect URI before sending
                const expectedUri = "http://127.0.0.1:8888/callback";
                if (redirectUri !== expectedUri) {
                    console.error(`ERROR: Redirect URI mismatch!`);
                    console.error(`  Expected: ${expectedUri}`);
                    console.error(`  Got: ${redirectUri}`);
                    alert(`Configuration Error: Redirect URI is "${redirectUri}" but should be "${expectedUri}". Please check server .env file and restart server.`);
                    return;
                }
                
                // Build auth URL
                // In local mode, state parameter is optional (no session_id needed)
                let authUrl = `https://accounts.spotify.com/authorize?response_type=code&client_id=${clientId}&scope=${encodeURIComponent(scope)}&redirect_uri=${encodeURIComponent(redirectUri)}`;
                
                // Only add state parameter if we have a session ID (legacy multi-user mode)
                if (sessionId) {
                    authUrl += `&state=${encodeURIComponent(sessionId)}`;
                    console.log("Including session ID in state parameter (legacy mode)");
                } else {
                    console.log("No session ID - local mode, proceeding without state parameter");
                }
                
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

function setupSystemSetupHandlers() {
    const validateUsernameBtn = document.getElementById("validateUsername");
    if (validateUsernameBtn) {
        validateUsernameBtn.addEventListener("click", async () => {
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
    }
    
    const validateChatFileBtn = document.getElementById("validateChatFile");
    if (validateChatFileBtn) {
        validateChatFileBtn.addEventListener("click", async () => {
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
    }
}

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
function setupChatSelectionHandlers() {
    if (clearSelectedChatsButton) {
        clearSelectedChatsButton.addEventListener('click', () => {
    selectedChats.clear();
    selectedChatsInfo.clear();
    updateSelectedChatsDisplay();
    
    // Uncheck all checkboxes
    const checkboxes = document.querySelectorAll('.chat-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = false);
    });
    }
}

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

function renderSenderCell(senderInfo) {
    /**
     * Render a sender cell with photo and name.
     * @param {Object} senderInfo - Object with sender_full_name, sender_name, sender_unique_id, is_from_me
     * @returns {string} HTML string for the sender cell
     */
    const sender = senderInfo.sender_full_name || senderInfo.sender_name || "—";
    const uniqueId = senderInfo.sender_unique_id;
    const isFromMe = senderInfo.is_from_me || false;
    
    if (uniqueId && !isFromMe) {
        const photoUrl = `${BASE_URL}/contact-photo/${encodeURIComponent(uniqueId)}`;
        return `
            <div style="display: flex; align-items: center; gap: 8px;">
                <img src="${photoUrl}" 
                     alt="${escapeHtml(sender)}" 
                     style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid #ddd;"
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div style="display: none; width: 32px; height: 32px; border-radius: 50%; background-color: #007bff; color: white; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9em;">
                    ${sender !== "—" ? sender.charAt(0).toUpperCase() : "?"}
                </div>
                <span style="font-weight: ${isFromMe ? 'bold' : 'normal'}; color: ${isFromMe ? '#007bff' : '#333'};">
                    ${escapeHtml(sender)}
                </span>
            </div>
        `;
    } else {
        // Fallback: show initial in circle if no photo
        const initial = sender !== "—" ? (isFromMe ? 'Y' : sender.charAt(0).toUpperCase()) : "?";
        return `
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 32px; height: 32px; border-radius: 50%; background-color: ${isFromMe ? '#007bff' : '#6c757d'}; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9em;">
                    ${initial}
                </div>
                <span style="font-weight: ${isFromMe ? 'bold' : 'normal'}; color: ${isFromMe ? '#007bff' : '#333'};">
                    ${escapeHtml(sender)}
                </span>
            </div>
        `;
    }
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
            
            // Debug: log message data
            console.log('Recent message data:', msg);
            
            // Use renderSenderCell for consistent display with photos
            const senderCell = renderSenderCell({
                sender_full_name: msg.sender_full_name || msg.sender_name,
                sender_name: msg.sender_name,
                sender_unique_id: msg.sender_unique_id,
                is_from_me: isFromMe
            });
            
            html += `
                <div class="chat-details-message ${messageClass}" style="margin-bottom: 15px; padding: 10px; background-color: ${isFromMe ? '#e3f2fd' : '#f5f5f5'}; border-radius: 8px;">
                    <div style="margin-bottom: 5px; display: flex; align-items: center; gap: 8px;">
                        ${senderCell}
                        <span style="color: #999; font-size: 0.85em; margin-left: auto;">${dateStr}</span>
                    </div>
                    <div style="color: #333; line-height: 1.5; margin-top: 5px;">${escapeHtml(text)}</div>
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
function setupSearchHandlers() {
    if (searchButton) {
        searchButton.addEventListener("click", () => {
    const searchTerm = searchInput.value.trim();
    if (searchTerm) {
        performSearch(searchTerm);
    }
    });
    }
    
    if (searchInput) {
        searchInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                if (searchButton) searchButton.click();
            }
        });
    }
}

// Add sorting functionality to table headers
function setupSortingHandlers() {
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
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSorting);
    } else {
        initSorting();
    }
}

// View All Chats button
function setupViewAllChatsHandler() {
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
}

// Allow Enter key to trigger search - moved to setupSearchHandlers()

///////////////////////////////////////////////////////////////
//////// Playlist Creation
///////////////////////////////////////////////////////////////

// Update playlist creation button state
function updatePlaylistButtonState() {
    const hasSelections = selectedChats.size > 0;
    const hasSpotifyAuth = isSpotifyAuthorized;
    
    const createButton = document.getElementById("createPlaylist");
    const warningMessage = document.getElementById("playlistWarningMessage");
    const playlistSectionEl = document.getElementById("playlistCreation");
    
    if (hasSelections && hasSpotifyAuth) {
        if (createButton) {
            createButton.disabled = false;
            createButton.style.opacity = "1";
            createButton.title = "";
        }
        if (playlistSectionEl) {
            playlistSectionEl.classList.remove("disabled");
        }
        if (playlistSection) {
            playlistSection.classList.remove("disabled");
        }
        
        // Hide warning message when chats are selected and Spotify is authorized
        if (warningMessage) {
            warningMessage.style.display = "none";
        }
        
        // Move to playlist creation step if we're not already there
        // Note: Steps are now: 0=spotifyAuth, 1=systemSetup, 2=chatSearch, 3=playlistCreation
        if (currentStep < 3) {
            currentStep = 3;
            updateSectionStates();
        }
    } else {
        if (createButton) {
            createButton.disabled = true;
            createButton.style.opacity = "0.6";
            
            if (!hasSpotifyAuth) {
                createButton.title = "Please complete Spotify authorization first";
            } else if (!hasSelections) {
                createButton.title = "Please select at least one chat";
            }
        }
        
        // Show warning message when prerequisites aren't met
        if (warningMessage) {
            warningMessage.style.display = "block";
        }
    }
}

// Handle playlist form submission
function setupPlaylistHandlers() {
    const playlistForm = document.getElementById("playlistForm");
    if (playlistForm) {
        playlistForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const statusDiv = document.getElementById("playlistStatus");
    const createButton = document.getElementById("createPlaylist");
    
    // Validate form inputs
    const isNewPlaylist = playlistTypeNew && playlistTypeNew.checked;
    const playlistName = document.getElementById("playlistName").value.trim();
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;
    const selectedChatIds = Array.from(selectedChats);
    
    // Validate based on playlist type
    if (isNewPlaylist && !playlistName) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Please enter a playlist name</div>';
        return;
    }
    
    if (!isNewPlaylist && !selectedPlaylistId) {
        statusDiv.innerHTML = '<div class="status-indicator status-error">❌ Please select an existing playlist</div>';
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

    // Prepare request data as FormData (FastAPI expects form data for simple string parameters)
    const formDataObj = new FormData();
    
    // For new playlists, use the name. For existing, use the selected ID
    if (isNewPlaylist) {
        formDataObj.append("playlist_name", playlistName);
    } else {
        // For existing playlists, we still need a name (it will be ignored if existing_playlist_id is provided)
        // But let's use the selected playlist's name if available
        formDataObj.append("playlist_name", playlistName || "Existing Playlist");
        const existingPlaylistId = document.getElementById("selectedPlaylistId")?.value;
        if (existingPlaylistId) {
            formDataObj.append("existing_playlist_id", existingPlaylistId);
        }
    }
    
    formDataObj.append("start_date", startDate);
    formDataObj.append("end_date", endDate);
    formDataObj.append("selected_chat_ids", JSON.stringify(selectedChatIds));  // Backend expects JSON string
    
    // createButton and statusDiv are already declared above, reuse them

    try {
        createButton.disabled = true;
        createButton.textContent = "Creating Playlist...";
        statusDiv.innerHTML = '';
        
        // Show progress bar
        const progressContainer = document.getElementById("playlistProgressContainer");
        const progressBar = document.getElementById("progressBar");
        const progressPercent = document.getElementById("progressPercent");
        const progressMessage = document.getElementById("progressMessage");
        const progressStage = document.getElementById("progressStage");
        
        if (progressContainer) {
            progressContainer.style.display = "block";
        }
        if (progressBar) {
            progressBar.style.width = "0%";
        }
        if (progressPercent) {
            progressPercent.textContent = "0%";
        }
        if (progressMessage) {
            progressMessage.textContent = "Starting playlist creation...";
        }
        if (progressStage) {
            progressStage.textContent = "Initializing...";
        }

        // Use streaming endpoint for progress updates
        let response;
        try {
            response = await fetch(`${BASE_URL}/create-playlist-optimized-stream`, {
                method: "POST",
                body: formDataObj,
                credentials: 'include',
                headers: {
                    // Don't set Content-Type - browser will set it with boundary for FormData
                }
            });
        } catch (fetchError) {
            console.error("Fetch error:", fetchError);
            throw new Error(`Network error: ${fetchError.message}`);
        }
        
        if (!response.ok) {
            // Try to get error message from response
            let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.message || errorMsg;
            } catch (e) {
                // If JSON parsing fails, use status text
            }
            throw new Error(errorMsg);
        }
        
        // Handle Server-Sent Events stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;
        
        console.log("Starting to read SSE stream...");
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                console.log("Stream finished");
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                const trimmedLine = line.trim();
                if (trimmedLine === '') continue; // Skip empty lines
                
                if (trimmedLine.startsWith('data: ')) {
                    try {
                        const jsonStr = trimmedLine.slice(6);
                        const data = JSON.parse(jsonStr);
                        console.log("Received SSE data:", data);
                        
                        // Update progress bar
                        if (data.status === 'progress') {
                            const progress = data.progress || 0;
                            if (progressBar) {
                                progressBar.style.width = `${progress}%`;
                            }
                            if (progressPercent) {
                                progressPercent.textContent = `${progress}%`;
                            }
                            if (progressMessage) {
                                progressMessage.textContent = data.message || '';
                            }
                            if (progressStage) {
                                const stageNames = {
                                    'querying': 'Querying Messages',
                                    'extracting': 'Extracting URLs',
                                    'processing': 'Processing Tracks',
                                    'adding': 'Adding to Playlist'
                                };
                                progressStage.textContent = stageNames[data.stage] || 'Processing...';
                            }
                            
                            // Show current/total if available
                            if (data.current !== undefined && data.total !== undefined) {
                                if (progressMessage) {
                                    progressMessage.textContent = `${data.message} (${data.current}/${data.total})`;
                                }
                            }
                        } else if (data.status === 'complete' || data.status === 'completed') {
                            // Backend sends 'complete' with data directly (not wrapped in 'result')
                            finalResult = {
                                status: 'success',
                                message: data.message || 'Playlist created successfully',
                                tracks_added: data.tracks_added || 0,
                                playlist_id: data.playlist_id,
                                playlist_name: data.playlist_name,
                                playlist_url: data.playlist_url,
                                track_details: data.track_details || [],
                                skipped_urls: data.skipped_urls || [],
                                other_links: data.other_links || []
                            };
                            // Set progress to 100%
                            if (progressBar) {
                                progressBar.style.width = "100%";
                            }
                            if (progressPercent) {
                                progressPercent.textContent = "100%";
                            }
                            if (progressMessage) {
                                progressMessage.textContent = "Playlist creation completed!";
                            }
                            break; // Stream is complete
                        } else if (data.status === 'error' || data.status === 'warning') {
                            // Handle errors/warnings - store the data for later processing
                            finalResult = {
                                status: data.status,
                                message: data.message || 'Unknown error',
                                tracks_added: data.tracks_added || 0,
                                track_details: data.track_details || [],
                                skipped_urls: data.skipped_urls || [],
                                other_links: data.other_links || []
                            };
                            break;
                        }
                    } catch (e) {
                        console.error("Error parsing SSE data:", e, line);
                    }
                }
            }
        }
        
        // Hide progress bar and show results
        if (progressContainer) {
            progressContainer.style.display = "none";
        }
        
        // Process final result (reuse existing result handling code)
        if (!finalResult) {
            throw new Error("No result received from server");
        }
        
        const result = finalResult;
        
        // Handle result based on status
        if (result.status === "error" || result.status === "warning") {
            let errorMessage = result.message || 'Unknown error';
            let errorDetails = result;
            let trackDetails = result.track_details || [];
            let statistics = result.statistics || null;
            // Get skipped_links and other_links from result if available
            if (result.skipped_links) {
                errorDetails = {...errorDetails, skipped_links: result.skipped_links};
            }
            if (result.other_links) {
                errorDetails = {...errorDetails, other_links: result.other_links};
            }
            
            // Build error display with track details table if available
            let errorHtml = `<div class="status-indicator status-error">❌ ${errorMessage}`;
            if (statistics) {
                errorHtml += `<br><strong>Summary:</strong> ${statistics.added || 0} added, ${statistics.skipped || 0} skipped, ${statistics.error || 0} errors (${statistics.total || 0} total)`;
            }
            errorHtml += `</div>`;
            
            // Add track details table if available
            if (trackDetails && trackDetails.length > 0) {
                errorHtml += `<div style="margin-top: 20px; max-height: 500px; overflow-y: auto;">
                    <h4 style="margin-bottom: 10px;">Track Details:</h4>
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                    <thead>
                        <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Status</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Track Name</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Artist</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Track ID</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL / Error</th>
                        </tr>
                    </thead>
                    <tbody>`;
                
                trackDetails.forEach(track => {
                    let rowClass = "";
                    let statusText = track.status;
                    let statusColor = "#333";
                    
                    if (track.status === "added") {
                        rowClass = "background-color: #d4edda;";
                        statusText = "✅ Added";
                        statusColor = "#155724";
                    } else if (track.status === "skipped") {
                        rowClass = "background-color: #fff3cd;";
                        statusText = "⏭️ Skipped";
                        statusColor = "#856404";
                    } else if (track.status === "error") {
                        rowClass = "background-color: #f8d7da;";
                        statusText = "❌ Error";
                        statusColor = "#721c24";
                    } else if (track.status === "valid") {
                        statusText = "✓ Valid";
                        statusColor = "#0c5460";
                    }
                    
                    const trackName = track.track_name || "—";
                    const artist = track.artist || "—";
                    const messageDate = track.message_date || "—";
                    const messageText = track.message_text || "—";
                    const trackId = track.track_id || "—";
                    const urlOrError = track.error || (track.spotify_url ? `<a href="${track.spotify_url}" target="_blank">${track.url}</a>` : track.url || "—");
                    
                    // Format date if available
                    let formattedDate = messageDate;
                    if (messageDate && messageDate !== "—") {
                        try {
                            const date = new Date(messageDate);
                            if (!isNaN(date.getTime())) {
                                formattedDate = date.toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                    hour: 'numeric',
                                    minute: '2-digit'
                                });
                            }
                        } catch (e) {
                            // Keep original date string if parsing fails
                        }
                    }
                    
                    // Create unique ID for message cell to enable expand/collapse
                    const messageCellId = `msg-${track.track_id || Math.random().toString(36).substr(2, 9)}`;
                    const isLongMessage = messageText.length > 100;
                    
                    errorHtml += `
                        <tr style="${rowClass}">
                            <td style="border: 1px solid #ddd; padding: 8px; color: ${statusColor}; font-weight: bold;">${statusText}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${escapeHtml(trackName)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${escapeHtml(artist)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">
                                ${renderSenderCell(track)}
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                                <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                    ${isLongMessage 
                                        ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                           <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                        : escapeHtml(messageText)
                                    }
                                </div>
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-family: monospace; font-size: 0.85em;">${escapeHtml(trackId)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">${urlOrError}</td>
                        </tr>`;
                    
                    // Add click handler for expandable messages
                    if (isLongMessage) {
                        setTimeout(() => {
                            const msgCell = document.getElementById(messageCellId);
                            if (msgCell) {
                                msgCell.addEventListener('click', function() {
                                    const preview = this.querySelector('.message-preview');
                                    const full = this.querySelector('.message-full');
                                    if (preview && full) {
                                        if (preview.style.display !== 'none') {
                                            preview.style.display = 'none';
                                            full.style.display = 'inline';
                                        } else {
                                            preview.style.display = 'inline';
                                            full.style.display = 'none';
                                        }
                                    }
                                });
                            }
                        }, 100);
                    }
                });
                
                errorHtml += `</tbody></table></div>`;
            }
            
            // Add skipped non-track links section if available (for error responses too)
            if (errorDetails && errorDetails.skipped_links && errorDetails.skipped_links.length > 0) {
                errorHtml += `<div style="margin-top: 30px;">
                    <h4 style="margin-bottom: 10px;">Skipped Non-Track Spotify Links (${errorDetails.skipped_links.length}):</h4>
                    <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                        These Spotify links were found but skipped because they are not individual tracks (e.g., albums, playlists, artists, radio stations).
                    </p>
                    <div style="max-height: 400px; overflow-y: auto;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                            <thead>
                                <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Type</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                                </tr>
                            </thead>
                            <tbody>`;
                
                errorDetails.skipped_links.forEach(link => {
                    // Format date
                    let formattedDate = link.date || "—";
                    if (formattedDate && formattedDate !== "—") {
                        try {
                            const date = new Date(formattedDate);
                            if (!isNaN(date.getTime())) {
                                formattedDate = date.toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                    hour: 'numeric',
                                    minute: '2-digit'
                                });
                            }
                        } catch (e) {
                            // Keep original date string if parsing fails
                        }
                    }
                    
                    const entityType = link.entity_type || "unknown";
                    const entityTypeDisplay = entityType.charAt(0).toUpperCase() + entityType.slice(1);
                    const messageText = link.message_text || "—";
                    const messageCellId = `skipped-msg-${Math.random().toString(36).substr(2, 9)}`;
                    const isLongMessage = messageText.length > 100;
                    
                    errorHtml += `
                        <tr style="background-color: #f8f9fa;">
                            <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold; color: #856404;">${escapeHtml(entityTypeDisplay)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">
                                <a href="${escapeHtml(link.url)}" target="_blank" style="color: #007bff;">${escapeHtml(link.url)}</a>
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px;">
                                ${renderSenderCell(link)}
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                                <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                    ${isLongMessage 
                                        ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                           <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                        : escapeHtml(messageText)
                                    }
                                </div>
                            </td>
                        </tr>`;
                    
                    if (isLongMessage) {
                        if (!window.expandableMessages) {
                            window.expandableMessages = [];
                        }
                        window.expandableMessages.push(messageCellId);
                    }
                });
                
                errorHtml += `</tbody></table></div></div>`;
            }
            
            // Add other non-Spotify links section if available (for error responses too)
            if (errorDetails && errorDetails.other_links && errorDetails.other_links.length > 0) {
                // Group links by type for better organization
                const linksByType = {};
                errorDetails.other_links.forEach(link => {
                    const type = link.link_type || "other";
                    if (!linksByType[type]) {
                        linksByType[type] = [];
                    }
                    linksByType[type].push(link);
                });
                
                // Type display names
                const typeNames = {
                    "youtube": "YouTube",
                    "instagram": "Instagram",
                    "apple_music": "Apple Music",
                    "tiktok": "TikTok",
                    "twitter": "Twitter/X",
                    "facebook": "Facebook",
                    "soundcloud": "SoundCloud",
                    "bandcamp": "Bandcamp",
                    "tidal": "Tidal",
                    "amazon_music": "Amazon Music",
                    "deezer": "Deezer",
                    "pandora": "Pandora",
                    "iheart": "iHeartRadio",
                    "tunein": "TuneIn",
                    "other": "Other Links"
                };
                
                errorHtml += `<div style="margin-top: 30px;">
                    <h4 style="margin-bottom: 10px;">Other Links Found (${errorDetails.other_links.length}):</h4>
                    <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                        These are non-Spotify links found in the selected messages (Instagram, YouTube, Apple Music, etc.).
                    </p>`;
                
                // Display links grouped by type
                Object.keys(linksByType).sort().forEach(type => {
                    const links = linksByType[type];
                    const typeDisplayName = typeNames[type] || type.charAt(0).toUpperCase() + type.slice(1);
                    
                    errorHtml += `<div style="margin-bottom: 20px;">
                        <h5 style="margin-bottom: 8px; color: #495057;">${typeDisplayName} (${links.length})</h5>
                        <div style="max-height: 300px; overflow-y: auto;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                                <thead>
                                    <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL</th>
                                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                                    </tr>
                                </thead>
                                <tbody>`;
                    
                    links.forEach(link => {
                        // Format date
                        let formattedDate = link.date || "—";
                        if (formattedDate && formattedDate !== "—") {
                            try {
                                const date = new Date(formattedDate);
                                if (!isNaN(date.getTime())) {
                                    formattedDate = date.toLocaleString('en-US', {
                                        month: 'short',
                                        day: 'numeric',
                                        year: 'numeric',
                                        hour: 'numeric',
                                        minute: '2-digit'
                                    });
                                }
                            } catch (e) {
                                // Keep original date string if parsing fails
                            }
                        }
                        
                        const messageText = link.message_text || "—";
                        const messageCellId = `other-link-msg-${Math.random().toString(36).substr(2, 9)}`;
                        const isLongMessage = messageText.length > 100;
                        
                        errorHtml += `
                            <tr style="background-color: #ffffff;">
                                <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">
                                    <a href="${escapeHtml(link.url)}" target="_blank" style="color: #007bff;">${escapeHtml(link.url)}</a>
                                </td>
                                <td style="border: 1px solid #ddd; padding: 8px;">
                                    ${renderSenderCell(link)}
                                </td>
                                <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                                <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                                    <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                        ${isLongMessage 
                                            ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                               <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                            : escapeHtml(messageText)
                                        }
                                    </div>
                                </td>
                            </tr>`;
                        
                        if (isLongMessage) {
                            if (!window.expandableMessages) {
                                window.expandableMessages = [];
                            }
                            window.expandableMessages.push(messageCellId);
                        }
                    });
                    
                    errorHtml += `</tbody></table></div></div>`;
                });
                
                errorHtml += `</div>`;
            }
            
            statusDiv.innerHTML = errorHtml;
            return;
        }

        // Build status message with statistics
        let statusClass = "status-success";
        let statusIcon = "✅";
        if (result.status === "warning") {
            statusClass = "status-warning";
            statusIcon = "⚠️";
        } else if (result.status === "error") {
            statusClass = "status-error";
            statusIcon = "❌";
        }
        
        let statusHtml = `<div class="status-indicator ${statusClass}">${statusIcon} ${result.message}`;
        
        if (result.playlist_url) {
            statusHtml += `<br><a href="${result.playlist_url}" target="_blank" style="color: #007bff; text-decoration: underline;">Open Playlist on Spotify</a>`;
        }
        
        // Add statistics if available
        if (result.statistics) {
            const stats = result.statistics;
            let statsMsg = `<br><strong>Summary:</strong> ${stats.added || 0} added, ${stats.skipped || 0} skipped, ${stats.error || 0} errors (${stats.total || 0} total)`;
            if (stats.non_track_links && stats.non_track_links > 0) {
                statsMsg += `, ${stats.non_track_links} non-track Spotify link(s) skipped`;
            }
            if (stats.other_links && stats.other_links > 0) {
                statsMsg += `, ${stats.other_links} other link(s) found`;
            }
            statusHtml += statsMsg;
        } else {
            const tracksAdded = result.tracks_added || 0;
            const totalFound = result.total_tracks_found;
            if (totalFound !== undefined && totalFound > 0) {
                statusHtml += `<br>Added ${tracksAdded} tracks (found ${totalFound} total)`;
            } else {
                statusHtml += `<br>Added ${tracksAdded} tracks`;
            }
        }
        
        statusHtml += `</div>`;
        
        // Add track details table if available
        if (result.track_details && result.track_details.length > 0) {
            statusHtml += `<div style="margin-top: 20px; max-height: 500px; overflow-y: auto;">
                <h4 style="margin-bottom: 10px;">Track Details:</h4>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                    <thead>
                        <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Status</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Track Name</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Artist</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Track ID</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL / Error</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            result.track_details.forEach(track => {
                let rowClass = "";
                let statusText = track.status;
                let statusColor = "#333";
                
                if (track.status === "added") {
                    rowClass = "background-color: #d4edda;";
                    statusText = "✅ Added";
                    statusColor = "#155724";
                } else if (track.status === "skipped") {
                    rowClass = "background-color: #fff3cd;";
                    statusText = "⏭️ Skipped";
                    statusColor = "#856404";
                } else if (track.status === "error") {
                    rowClass = "background-color: #f8d7da;";
                    statusText = "❌ Error";
                    statusColor = "#721c24";
                } else if (track.status === "valid") {
                    statusText = "✓ Valid";
                    statusColor = "#0c5460";
                }
                
                const trackName = track.track_name || "—";
                const artist = track.artist || "—";
                const messageDate = track.message_date || "—";
                const messageText = track.message_text || "—";
                const trackId = track.track_id || "—";
                const urlOrError = track.error || (track.spotify_url ? `<a href="${track.spotify_url}" target="_blank">${track.url}</a>` : track.url || "—");
                
                // Format date if available
                let formattedDate = messageDate;
                if (messageDate && messageDate !== "—") {
                    try {
                        const date = new Date(messageDate);
                        if (!isNaN(date.getTime())) {
                            formattedDate = date.toLocaleString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                                hour: 'numeric',
                                minute: '2-digit'
                            });
                        }
                    } catch (e) {
                        // Keep original date string if parsing fails
                    }
                }
                
                // Create unique ID for message cell to enable expand/collapse
                const messageCellId = `msg-${track.track_id || Math.random().toString(36).substr(2, 9)}`;
                const isLongMessage = messageText.length > 100;
                
                statusHtml += `
                    <tr style="${rowClass}">
                        <td style="border: 1px solid #ddd; padding: 8px; color: ${statusColor}; font-weight: bold;">${statusText}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">${escapeHtml(trackName)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">${escapeHtml(artist)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">
                            ${renderSenderCell(track)}
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                            <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                ${isLongMessage 
                                    ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                       <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                    : escapeHtml(messageText)
                                }
                            </div>
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-family: monospace; font-size: 0.85em;">${escapeHtml(trackId)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">${urlOrError}</td>
                    </tr>`;
                
                // Add click handler for expandable messages (will be attached after HTML is inserted)
                if (isLongMessage) {
                    // Store the messageCellId for later attachment
                    if (!window.expandableMessages) {
                        window.expandableMessages = [];
                    }
                    window.expandableMessages.push(messageCellId);
                }
            });
            
            statusHtml += `</tbody></table></div>`;
        }
        
        // Add skipped non-track links section if available
        if (result.skipped_links && result.skipped_links.length > 0) {
            statusHtml += `<div style="margin-top: 30px;">
                <h4 style="margin-bottom: 10px;">Skipped Non-Track Spotify Links (${result.skipped_links.length}):</h4>
                <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                    These Spotify links were found but skipped because they are not individual tracks (e.g., albums, playlists, artists, radio stations).
                </p>
                <div style="max-height: 400px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                        <thead>
                            <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Type</th>
                                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL</th>
                                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                            </tr>
                        </thead>
                        <tbody>`;
            
            result.skipped_links.forEach(link => {
                // Format date
                let formattedDate = link.date || "—";
                if (formattedDate && formattedDate !== "—") {
                    try {
                        const date = new Date(formattedDate);
                        if (!isNaN(date.getTime())) {
                            formattedDate = date.toLocaleString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                                hour: 'numeric',
                                minute: '2-digit'
                            });
                        }
                    } catch (e) {
                        // Keep original date string if parsing fails
                    }
                }
                
                const entityType = link.entity_type || "unknown";
                const entityTypeDisplay = entityType.charAt(0).toUpperCase() + entityType.slice(1);
                const messageText = link.message_text || "—";
                const messageCellId = `skipped-msg-${Math.random().toString(36).substr(2, 9)}`;
                const isLongMessage = messageText.length > 100;

                statusHtml += `
                    <tr style="background-color: #f8f9fa;">
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold; color: #856404;">${escapeHtml(entityTypeDisplay)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">
                            <a href="${escapeHtml(link.url)}" target="_blank" style="color: #007bff;">${escapeHtml(link.url)}</a>
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px;">
                            ${renderSenderCell(link)}
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                            <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                ${isLongMessage 
                                    ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                       <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                    : escapeHtml(messageText)
                                }
                            </div>
                        </td>
                    </tr>`;
                
                if (isLongMessage) {
                    if (!window.expandableMessages) {
                        window.expandableMessages = [];
                    }
                    window.expandableMessages.push(messageCellId);
                }
            });
            
            statusHtml += `</tbody></table></div></div>`;
        }
        
        // Add other non-Spotify links section if available
        if (result.other_links && result.other_links.length > 0) {
            // Group links by type for better organization
            const linksByType = {};
            result.other_links.forEach(link => {
                const type = link.link_type || "other";
                if (!linksByType[type]) {
                    linksByType[type] = [];
                }
                linksByType[type].push(link);
            });
            
            // Type display names
            const typeNames = {
                "youtube": "YouTube",
                "instagram": "Instagram",
                "apple_music": "Apple Music",
                "tiktok": "TikTok",
                "twitter": "Twitter/X",
                "facebook": "Facebook",
                "soundcloud": "SoundCloud",
                "bandcamp": "Bandcamp",
                "tidal": "Tidal",
                "amazon_music": "Amazon Music",
                "deezer": "Deezer",
                "pandora": "Pandora",
                "iheart": "iHeartRadio",
                "tunein": "TuneIn",
                "other": "Other Links"
            };
            
            statusHtml += `<div style="margin-top: 30px;">
                <h4 style="margin-bottom: 10px;">Other Links Found (${result.other_links.length}):</h4>
                <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                    These are non-Spotify links found in the selected messages (Instagram, YouTube, Apple Music, etc.).
                </p>`;
            
            // Display links grouped by type
            Object.keys(linksByType).sort().forEach(type => {
                const links = linksByType[type];
                const typeDisplayName = typeNames[type] || type.charAt(0).toUpperCase() + type.slice(1);
                
                statusHtml += `<div style="margin-bottom: 20px;">
                    <h5 style="margin-bottom: 8px; color: #495057;">${typeDisplayName} (${links.length})</h5>
                    <div style="max-height: 300px; overflow-y: auto;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                            <thead>
                                <tr style="background-color: #f2f2f2; position: sticky; top: 0;">
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">URL</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Sender</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Date</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Message</th>
                                </tr>
                            </thead>
                            <tbody>`;
                
                links.forEach(link => {
                    // Format date
                    let formattedDate = link.date || "—";
                    if (formattedDate && formattedDate !== "—") {
                        try {
                            const date = new Date(formattedDate);
                            if (!isNaN(date.getTime())) {
                                formattedDate = date.toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                    hour: 'numeric',
                                    minute: '2-digit'
                                });
                            }
                        } catch (e) {
                            // Keep original date string if parsing fails
                        }
                    }
                    
                    const messageText = link.message_text || "—";
                    const messageCellId = `other-link-msg-${Math.random().toString(36).substr(2, 9)}`;
                    const isLongMessage = messageText.length > 100;
                    
                    statusHtml += `
                        <tr style="background-color: #ffffff;">
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; word-break: break-all;">
                                <a href="${escapeHtml(link.url)}" target="_blank" style="color: #007bff;">${escapeHtml(link.url)}</a>
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px;">
                                ${renderSenderCell(link)}
                            </td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; white-space: nowrap;">${escapeHtml(formattedDate)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 0.85em; max-width: 400px; word-wrap: break-word;">
                                <div id="${messageCellId}" style="cursor: ${isLongMessage ? 'pointer' : 'default'};">
                                    ${isLongMessage 
                                        ? `<span class="message-preview">${escapeHtml(messageText.substring(0, 100))}... <span style="color: #007bff; text-decoration: underline;">(click to expand)</span></span>
                                           <span class="message-full" style="display: none;">${escapeHtml(messageText)} <span style="color: #007bff; text-decoration: underline;">(click to collapse)</span></span>`
                                        : escapeHtml(messageText)
                                    }
                                </div>
                            </td>
                        </tr>`;
                    
                    if (isLongMessage) {
                        if (!window.expandableMessages) {
                            window.expandableMessages = [];
                        }
                        window.expandableMessages.push(messageCellId);
                    }
                });
                
                statusHtml += `</tbody></table></div></div>`;
            });
            
            statusHtml += `</div>`;
        }
        
        statusDiv.innerHTML = statusHtml;
        
        // Attach click handlers for expandable messages after HTML is inserted
        if (window.expandableMessages) {
            window.expandableMessages.forEach(messageCellId => {
                const msgCell = document.getElementById(messageCellId);
                if (msgCell) {
                    msgCell.addEventListener('click', function() {
                        const preview = this.querySelector('.message-preview');
                        const full = this.querySelector('.message-full');
                        if (preview && full) {
                            if (preview.style.display !== 'none') {
                                preview.style.display = 'none';
                                full.style.display = 'inline';
                            } else {
                                preview.style.display = 'inline';
                                full.style.display = 'none';
                            }
                        }
                    });
                }
            });
            window.expandableMessages = []; // Clear the array
        }

        // Clear form only on success
        if (result.status === "success") {
            // Optionally clear selected chats
            // Refresh playlist list if user is viewing existing playlists
            if (playlistTypeExisting && playlistTypeExisting.checked) {
                // Refresh the playlist list to show the newly created playlist
                userPlaylists = [];
                if (playlistSearchInput) {
                    playlistSearchInput.value = "";
                }
                loadPlaylists();
            }
            
            if (confirm("Playlist created successfully! Would you like to clear your selected chats for the next playlist?")) {
                selectedChats.clear();
                updateSelectedChatsDisplay();
                const checkboxes = document.querySelectorAll('.chat-checkbox');
                checkboxes.forEach(checkbox => checkbox.checked = false);
            }
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
    }
}

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


// Playlist search functionality
let userPlaylists = [];
let selectedPlaylistId = null;

const playlistTypeNew = document.getElementById("playlistTypeNew");
const playlistTypeExisting = document.getElementById("playlistTypeExisting");
const newPlaylistSection = document.getElementById("newPlaylistSection");
const existingPlaylistSection = document.getElementById("existingPlaylistSection");
const playlistNameInput = document.getElementById("playlistName");
const playlistSearchResults = document.getElementById("playlistSearchResults");
const playlistSearchInput = document.getElementById("playlistSearchInput");
const playlistList = document.getElementById("playlistList");
const playlistLoadingIndicator = document.getElementById("playlistLoadingIndicator");
const selectedPlaylistInfo = document.getElementById("selectedPlaylistInfo");
const clearPlaylistSelection = document.getElementById("clearPlaylistSelection");
const refreshPlaylistsButton = document.getElementById("refreshPlaylistsButton");

// Handle playlist type selection
function handlePlaylistTypeChange() {
    const isNew = playlistTypeNew.checked;
    
    if (isNew) {
        // Show new playlist section, hide existing
        newPlaylistSection.style.display = "block";
        existingPlaylistSection.style.display = "none";
        playlistNameInput.required = true;
        selectedPlaylistId = null;
        // Remove hidden input if it exists
        const hiddenInput = document.getElementById("selectedPlaylistId");
        if (hiddenInput) {
            hiddenInput.remove();
        }
    } else {
        // Show existing playlist section, hide new
        newPlaylistSection.style.display = "none";
        existingPlaylistSection.style.display = "block";
        playlistNameInput.required = false;
        // Auto-load playlists when switching to existing
        if (userPlaylists.length === 0) {
            loadPlaylists();
        } else {
            displayPlaylists(userPlaylists);
        }
    }
}

// Add refresh button handler
if (refreshPlaylistsButton) {
    refreshPlaylistsButton.addEventListener("click", () => {
        // Clear current list and reload
        userPlaylists = [];
        if (playlistSearchInput) {
            playlistSearchInput.value = "";
        }
        loadPlaylists();
    });
}

if (playlistTypeNew) {
    playlistTypeNew.addEventListener("change", handlePlaylistTypeChange);
}

if (playlistTypeExisting) {
    playlistTypeExisting.addEventListener("change", handlePlaylistTypeChange);
}

// Load playlists from Spotify
async function loadPlaylists() {
    if (!playlistList || !playlistLoadingIndicator) return;
    
    try {
        playlistLoadingIndicator.style.display = "block";
        playlistList.innerHTML = "<div style='padding: 10px; color: #666; text-align: center;'>Loading playlists...</div>";
        
        const response = await apiFetch("/user-playlists");
        
        if (!response.ok) {
            let errorMessage = 'Unknown error';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
            } catch (e) {
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }
            playlistList.innerHTML = `<div style='padding: 10px; color: #dc3545;'>Error: ${errorMessage}</div>`;
            return;
        }
        
        const data = await response.json();
        console.log("Playlists response:", data); // Debug log
        
        // Handle different response structures
        if (data.playlists && Array.isArray(data.playlists)) {
            userPlaylists = data.playlists;
            if (userPlaylists.length === 0) {
                playlistList.innerHTML = "<div style='padding: 10px; color: #666; text-align: center;'>No playlists found in your Spotify account.</div>";
                return;
            }
            displayPlaylists(userPlaylists);
        } else if (Array.isArray(data)) {
            userPlaylists = data;
            if (userPlaylists.length === 0) {
                playlistList.innerHTML = "<div style='padding: 10px; color: #666; text-align: center;'>No playlists found in your Spotify account.</div>";
                return;
            }
            displayPlaylists(userPlaylists);
        } else {
            console.error("Unexpected response structure:", data);
            playlistList.innerHTML = "<div style='padding: 10px; color: #dc3545;'>Unexpected response format. Check console for details.</div>";
        }
    } catch (error) {
        console.error("Error fetching playlists:", error);
        playlistList.innerHTML = "<div style='padding: 10px; color: #dc3545;'>Error loading playlists. Please try again.</div>";
    } finally {
        playlistLoadingIndicator.style.display = "none";
    }
}

if (playlistSearchInput) {
    playlistSearchInput.addEventListener("input", (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filtered = userPlaylists.filter(p => 
            p.name.toLowerCase().includes(searchTerm)
        );
        displayPlaylists(filtered);
    });
}

function displayPlaylists(playlists) {
    if (!playlistList) return;
    
    if (playlists.length === 0) {
        playlistList.innerHTML = "<div style='padding: 10px; color: #666;'>No playlists found</div>";
        return;
    }
    
    playlistList.innerHTML = playlists.map(playlist => {
        // Escape quotes for onclick attribute
        const escapedId = playlist.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const escapedName = playlist.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        return `
        <div style="padding: 8px; border-bottom: 1px solid #ddd; cursor: pointer; display: flex; justify-content: space-between; align-items: center;"
             onclick="selectPlaylist('${escapedId}', '${escapedName}', ${playlist.tracks_count})">
            <div>
                <strong>${escapeHtml(playlist.name)}</strong>
                <div style="font-size: 0.85em; color: #666;">
                    ${playlist.tracks_count} track(s)${playlist.public ? ' • Public' : ' • Private'}
                </div>
            </div>
            <div style="color: #007bff; font-size: 0.9em;">Select →</div>
        </div>
    `;
    }).join('');
}

function selectPlaylist(playlistId, playlistName, tracksCount) {
    selectedPlaylistId = playlistId;
    
    // Create or update hidden input
    let hiddenInput = document.getElementById("selectedPlaylistId");
    if (!hiddenInput) {
        hiddenInput = document.createElement("input");
        hiddenInput.type = "hidden";
        hiddenInput.id = "selectedPlaylistId";
        document.getElementById("playlistForm").appendChild(hiddenInput);
    }
    hiddenInput.value = playlistId;
    
    // Update display - show selected playlist info, hide search results
    document.getElementById("selectedPlaylistName").textContent = `${playlistName} (${tracksCount} tracks)`;
    selectedPlaylistInfo.style.display = "block";
    playlistSearchResults.style.display = "none";
}

// Make selectPlaylist available globally for onclick handlers
window.selectPlaylist = selectPlaylist;

if (clearPlaylistSelection) {
    clearPlaylistSelection.addEventListener("click", () => {
        selectedPlaylistId = null;
        const hiddenInput = document.getElementById("selectedPlaylistId");
        if (hiddenInput) {
            hiddenInput.remove();
        }
        selectedPlaylistInfo.style.display = "none";
        playlistSearchResults.style.display = "block";
        // Clear search input
        if (playlistSearchInput) {
            playlistSearchInput.value = "";
            displayPlaylists(userPlaylists);
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
// This will be called after elements are initialized in initializeApp()
function initializeLoginForm() {
    console.log('Initializing login form with forgot password link');
    if (authSwitchText && loginForm) {
        switchAuthMode('login');
    } else {
        console.warn('Cannot initialize login form - elements not ready yet');
    }
}

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

// Make selectPlaylist available globally
window.selectPlaylist = selectPlaylist;
