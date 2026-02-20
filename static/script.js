// Global state
let isProcessing = false;
let currentChatId = null;

// Initialize marked for markdown rendering
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true
    });
}

// Initialize
window.addEventListener('load', function () {
    checkExistingSession();
    setupAuthForms();
});

// Check if user has an existing session
function checkExistingSession() {
    const userId = sessionStorage.getItem('userId');
    const authenticated = sessionStorage.getItem('authenticated');

    if (userId && authenticated === 'true') {
        showChatInterface();
        updateUserDisplay();
        loadChatList();
    }
}

// Auth Mode Switching
function switchAuthMode(mode) {
    const loginTab = document.getElementById('loginTab');
    const signupTab = document.getElementById('signupTab');
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');

    if (mode === 'login') {
        loginTab.classList.add('active');
        signupTab.classList.remove('active');
        loginForm.style.display = 'block';
        signupForm.style.display = 'none';
    } else {
        signupTab.classList.add('active');
        loginTab.classList.remove('active');
        signupForm.style.display = 'block';
        loginForm.style.display = 'none';
    }
}

// Setup Auth Forms
function setupAuthForms() {
    // Login form handler
    document.getElementById('loginForm').addEventListener('submit', async function (e) {
        e.preventDefault();

        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        const errorDiv = document.getElementById('loginError');
        const loadingDiv = document.getElementById('loginLoading');

        errorDiv.textContent = '';
        loadingDiv.style.display = 'flex';

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                // Store in session storage
                sessionStorage.setItem('userId', data.user_id);
                sessionStorage.setItem('authenticated', 'true');
                currentChatId = data.chat_id;

                setTimeout(() => {
                    showChatInterface();
                    updateUserDisplay();
                    loadChatList();
                }, 800);
            } else {
                errorDiv.textContent = data.message || 'Login failed. Please try again.';
            }
        } catch (error) {
            errorDiv.textContent = 'Network error. Please check your connection.';
            console.error('Error:', error);
        } finally {
            loadingDiv.style.display = 'none';
        }
    });

    // Signup form handler
    document.getElementById('signupForm').addEventListener('submit', async function (e) {
        e.preventDefault();

        const email = document.getElementById('signupEmail').value;
        const password = document.getElementById('signupPassword').value;
        const name = document.getElementById('signupName').value;
        const age = document.getElementById('signupAge').value;
        const location = document.getElementById('signupLocation').value;
        const gender = document.getElementById('signupGender').value;

        const errorDiv = document.getElementById('signupError');
        const loadingDiv = document.getElementById('signupLoading');

        errorDiv.textContent = '';
        loadingDiv.style.display = 'flex';

        try {
            const response = await fetch('/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, name, age, location, gender })
            });

            const data = await response.json();

            if (data.success) {
                // Store in session storage
                sessionStorage.setItem('userId', data.user_id);
                sessionStorage.setItem('authenticated', 'true');
                currentChatId = data.chat_id;

                setTimeout(() => {
                    showChatInterface();
                    updateUserDisplay();
                    loadChatList();
                    addIntroMessage(name);
                }, 800);
            } else {
                errorDiv.textContent = data.message || 'Signup failed. Please try again.';
            }
        } catch (error) {
            errorDiv.textContent = 'Network error. Please check your connection.';
            console.error('Error:', error);
        } finally {
            loadingDiv.style.display = 'none';
        }
    });
}

// Show chat interface
function showChatInterface() {
    document.getElementById('authContainer').style.display = 'none';
    document.getElementById('chatContainer').style.display = 'flex';
    document.getElementById('messageInput').focus();
}

// Update user display in header & sidebar
function updateUserDisplay() {
    const age = sessionStorage.getItem('userAge');
    const gender = sessionStorage.getItem('userGender');
    const location = sessionStorage.getItem('userLocation');
    const name = sessionStorage.getItem('userName');

    let displayText = `${age}, ${gender}`;
    if (location) {
        displayText += ` · ${location}`;
    }

    const displayUserInfo = document.getElementById('displayUserInfo');
    if (displayUserInfo) {
        displayUserInfo.textContent = displayText;
    }

    const displayUserName = document.getElementById('displayUserName');
    if (displayUserName) {
        displayUserName.textContent = name || "User";
    }
}

// Reset intake (logout)
function resetIntake() {
    if (confirm('Are you sure you want to log out?')) {
        sessionStorage.clear();
        location.reload();
    }
}

// Load chat list
async function loadChatList() {
    try {
        const response = await fetch('/chats');
        const data = await response.json();

        if (data.success) {
            // Sync user profile if available
            if (data.user_profile) {
                if (data.user_profile.name) sessionStorage.setItem('userName', data.user_profile.name);
                if (data.user_profile.age) sessionStorage.setItem('userAge', data.user_profile.age);
                if (data.user_profile.gender) sessionStorage.setItem('userGender', data.user_profile.gender);
            }

            const chatList = document.getElementById('chatList');
            chatList.innerHTML = '';

            data.chats.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = `chat-item ${chat.id === currentChatId ? 'active' : ''}`;
                chatItem.innerHTML = `
                     <div class="chat-item-content" onclick="switchChat('${chat.id}')">
                         <i class="fas fa-message"></i>
                         <span>${escapeHtml(chat.title)}</span>
                     </div>
                     <button class="delete-chat-btn" onclick="deleteChat(event, '${chat.id}')" title="Delete chat">
                         <i class="fas fa-trash"></i>
                     </button>
                 `;
                chatList.appendChild(chatItem);
            });

            // If no chats exist, show intro message
            if (data.chats.length === 0) {
                const name = sessionStorage.getItem('userName') || "Friend";
                addIntroMessage(name);
            }
            // If no current chat is selected but chats exist, select the first one
            else if (!currentChatId && data.chats.length > 0) {
                switchChat(data.chats[0].id);
            } else if (currentChatId) {
                // Load messages for current chat
                loadChatHistory(currentChatId);
            }
        }

        // Ensure user display is up to date
        updateUserDisplay();
    } catch (error) {
        console.error("Error loading chat list:", error);
    }
}

// Create new chat
async function createNewChat() {
    try {
        const response = await fetch('/chats', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            currentChatId = data.chat_id;
            await loadChatList(); // Refresh list
            switchChat(currentChatId); // Switch to new chat

            // Use standard intro message with user's name
            const name = sessionStorage.getItem('userName') || "Friend";
            addIntroMessage(name);
        }
    } catch (error) {
        console.error("Error creating new chat:", error);
    }
}

// Delete chat
async function deleteChat(event, chatId) {
    event.stopPropagation(); // Prevent triggering chat switch

    if (!confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/chats/${chatId}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            // If we deleted the current chat, clear it
            if (currentChatId === chatId) {
                currentChatId = null;
            }

            // Reload chat list
            await loadChatList();

            // If no chats remain or current was deleted, show intro or switch to first chat
            const chatsResponse = await fetch('/chats');
            const chatsData = await chatsResponse.json();

            if (chatsData.success && chatsData.chats.length > 0) {
                if (!currentChatId) {
                    switchChat(chatsData.chats[0].id);
                }
            } else {
                // No chats left, clear messages and show intro
                const messagesArea = document.getElementById('messagesArea');
                messagesArea.innerHTML = '';
                const name = sessionStorage.getItem('userName') || "Friend";
                addIntroMessage(name);
            }
        } else {
            alert('Failed to delete chat: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error("Error deleting chat:", error);
        alert('Failed to delete chat. Please try again.');
    }
}

// Switch chat
async function switchChat(chatId) {
    currentChatId = chatId;
    // Update UI active state
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    // Find the item corresponding to this chat and make it active (simple approach)
    // A better way would be data attributes but loop works for now
    // Reload list to ensure titles are up to date? Maybe overkill. unique selection logic:
    const items = document.querySelectorAll('.chat-item');
    // Re-render list to set active class correctly is easier or manually toggle class
    loadChatList(); // Rerender to show active state
    loadChatHistory(chatId);
}

// Load chat history
async function loadChatHistory(chatId) {
    const messagesArea = document.getElementById('messagesArea');
    messagesArea.innerHTML = '<div class="intake-loading" style="display:flex"><div class="spinner"></div></div>';

    try {
        const response = await fetch(`/chats/${chatId}`);
        const data = await response.json();

        messagesArea.innerHTML = ''; // Clear loading

        if (data.success) {
            if (data.messages.length === 0) {
                // Show welcome/intro if empty
                // We can also re-add the welcome message here
                const name = sessionStorage.getItem('userName') || "Friend";
                addIntroMessage(name);
            } else {
                data.messages.forEach(msg => {
                    // Map 'assistant' to 'bot' for frontend
                    const type = (msg.role === 'assistant' || msg.role === 'bot') ? 'bot' : 'user';
                    addMessage(msg.content, type);
                });
                // Scroll to bottom
                messagesArea.scrollTop = messagesArea.scrollHeight;
            }
        }
    } catch (error) {
        messagesArea.innerHTML = '<p style="text-align:center; color:red">Error loading chat history</p>';
        console.error(error);
    }
}

// Add intro message
function addIntroMessage(name) {
    const messagesArea = document.getElementById('messagesArea');
    messagesArea.innerHTML = ''; // Clear existing

    const introDiv = document.createElement('div');
    introDiv.className = 'welcome-message';
    introDiv.innerHTML = `
        <div class="welcome-icon">
            <i class="fas fa-comments"></i>
        </div>
        <h3>Hello ${escapeHtml(name)}, I'm SafeMind</h3>
        <p>I'm here to listen, support, and guide you through your mental health journey.</p>
        <p>Feel free to share what's on your mind - this is a safe, judgment-free space.</p>
        <div class="quick-actions">
            <button class="quick-action-btn" onclick="sendQuickMessage('I am feeling stressed today')">
                <i class="fas fa-brain"></i> Feeling stressed
            </button>
            <button class="quick-action-btn" onclick="sendQuickMessage('I need help with anxiety')">
                <i class="fas fa-hand-holding-heart"></i> Need help with anxiety
            </button>
            <button class="quick-action-btn" onclick="sendQuickMessage('Tell me about self-care')">
                <i class="fas fa-spa"></i> Learn about self-care
            </button>
        </div>
     `;
    messagesArea.appendChild(introDiv);
}


// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message || isProcessing || !currentChatId) return;

    isProcessing = true;
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    // Remove welcome message on first user message
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.style.display = 'none';
    }

    // Add user message
    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';

    // Create a placeholder for the bot message (streaming target)
    // We will update this message in-place as tokens arrive
    const botMessageId = 'msg-' + Date.now();
    addMessage('', 'bot', null, botMessageId);

    try {
        const formData = new FormData();
        formData.append('msg', message);
        formData.append('chat_id', currentChatId);

        const response = await fetch('/get', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            let errorMessage = `Server error: ${response.statusText}`;
            try {
                const errData = await response.json();
                if (errData.message) errorMessage = errData.message;
            } catch (e) {
                console.warn("Could not parse error response JSON", e);
            }
            throw new Error(errorMessage);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullResponseText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse NDJSON lines
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep the last incomplete line in buffer

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const event = JSON.parse(line);

                    if (event.type === 'status') {
                        const statusId = 'status-' + botMessageId;
                        if (document.getElementById(statusId)) {
                            updateStatusIndicator(statusId, event.content);
                        } else {
                            showStatusIndicator(event.content, statusId);
                        }
                    }
                    else if (event.type === 'token') {
                        // Remove status if it exists
                        removeStatusIndicator('status-' + botMessageId);

                        fullResponseText += event.content;
                        updateBotMessage(botMessageId, fullResponseText);
                    }
                    else if (event.type === 'done') {
                        removeStatusIndicator('status-' + botMessageId);
                        console.log("Stream complete");
                    }
                } catch (e) {
                    console.error("Error parsing JSON line:", e, line);
                }
            }
        }

        // Final update
        updateBotMessage(botMessageId, fullResponseText);

        loadChatList();

    } catch (error) {
        // Prefer specific error message if available
        const displayMsg = error.message || 'I apologize, but I encountered an error. Please try again.';
        addMessage(displayMsg, 'bot');
        console.error('Error:', error);
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
    }
}


// Simulate typing effect
async function simulateTyping(elementId, text) {
    const minDelay = 10;
    const maxDelay = 30;
    let currentText = "";

    // Split by characters but be careful with emojis or complex chars if strictly needed, 
    // but simple split is usually fine for this demo.
    const chars = Array.from(text);

    for (const char of chars) {
        currentText += char;
        updateBotMessage(elementId, currentText);

        // Random delay for natural feel
        const delay = Math.floor(Math.random() * (maxDelay - minDelay + 1)) + minDelay;
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    // Ensure final state is exactly the full text (re-render one last time)
    updateBotMessage(elementId, text);
}

// Send quick message
function sendQuickMessage(message) {
    document.getElementById('messageInput').value = message;
    sendMessage();
}

// Add message to chat with markdown rendering
function addMessage(text, type, duration = null, elementId = null) {
    const messagesArea = document.getElementById('messagesArea');

    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    if (elementId) messageDiv.id = elementId;

    let formattedText;

    if (type === 'bot') {
        // Use markdown rendering for bot messages
        try {
            formattedText = marked.parse(text);
        } catch (e) {
            formattedText = escapeHtml(text).replace(/\n/g, '<br>');
        }
    } else {
        // Simple escape for user messages
        formattedText = escapeHtml(text).replace(/\n/g, '<br>');
    }

    if (type === 'bot') {
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-heart"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">${formattedText}</div>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-bubble">${formattedText}</div>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
        `;
    }

    messagesArea.appendChild(messageDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesArea = document.getElementById('messagesArea');
    const typingDiv = document.createElement('div');
    const typingId = 'typing-' + Date.now();
    typingDiv.id = typingId;
    typingDiv.className = 'message message-bot typing-indicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-heart"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
    messagesArea.appendChild(typingDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
    return typingId;
}

// Remove typing indicator
function removeTypingIndicator(typingId) {
    const typingDiv = document.getElementById(typingId);
    if (typingDiv) {
        typingDiv.remove();
    }
}

// Handle keyboard events
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Auto-resize textarea
document.getElementById('messageInput').addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}


function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// Responsive Sidebar Toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    sidebar.classList.toggle('active');
    overlay.classList.toggle('active');
}

// Desktop Sidebar Toggle
function toggleSidebarDesktop() {
    const sidebar = document.getElementById('sidebar');
    const isCollapsed = sidebar.classList.toggle('collapsed');

    // Persist state
    localStorage.setItem('sidebarCollapsed', isCollapsed);
}

// Restore sidebar state on load
document.addEventListener('DOMContentLoaded', () => {
    // Default to collapsed if no preference or if preference is 'true'
    const storedState = localStorage.getItem('sidebarCollapsed');
    const shouldBeCollapsed = storedState === null ? true : storedState === 'true';
    const sidebar = document.getElementById('sidebar');

    if (window.innerWidth > 768) {
        if (shouldBeCollapsed) {
            sidebar.classList.add('collapsed');
        } else {
            sidebar.classList.remove('collapsed');
        }
    }
});

// === Real-time Status Helpers ===

function showStatusIndicator(text, id) {
    const messagesArea = document.getElementById('messagesArea');
    const statusDiv = document.createElement('div');
    statusDiv.id = id;
    statusDiv.className = 'status-indicator';
    statusDiv.innerHTML = `
        <i class="fas fa-spinner fa-spin"></i>
        <span>${escapeHtml(text)}</span>
    `;
    messagesArea.appendChild(statusDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

function updateStatusIndicator(id, text) {
    const statusDiv = document.getElementById(id);
    if (statusDiv) {
        const span = statusDiv.querySelector('span');
        if (span) span.textContent = text;
    }
}

function removeStatusIndicator(id) {
    const statusDiv = document.getElementById(id);
    if (statusDiv) {
        statusDiv.remove();
    }
}

// Update an existing bot message (for streaming)
function updateBotMessage(elementId, text) {
    let messageDiv = document.getElementById(elementId);

    // Format markdown
    let formattedText;
    try {
        formattedText = marked.parse(text);
    } catch (e) {
        formattedText = escapeHtml(text).replace(/\n/g, '<br>');
    }

    const htmlContent = `
        <div class="message-avatar">
            <i class="fas fa-heart"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble">${formattedText}</div>
            <div class="message-time">${getCurrentTime()}</div>
        </div>
    `;

    if (!messageDiv) {
        console.warn("Message div not found for update.");
    } else {
        messageDiv.innerHTML = htmlContent;
        const messagesArea = document.getElementById('messagesArea');
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }
}
