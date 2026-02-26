/**
 * University AI Receptionist - Main JavaScript
 * Handles chat functionality, API integration, and UI interactions.
 * Premium UI with shadcn/ui-inspired design
 */

(function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================
    const CONFIG = {
        API_ENDPOINT: '/api/chat',
        MEMORY_ENDPOINT: '/api/memory',
        RESET_ENDPOINT: '/api/reset',
        HEALTH_ENDPOINT: '/api/health',
        TYPING_INDICATOR_DELAY: 500,
        MAX_RETRIES: 3,
        RETRY_DELAY: 1000
    };

    // =========================================================================
    // DOM Elements
    // =========================================================================
    const elements = {
        chatForm: document.getElementById('chat-form'),
        messageInput: document.getElementById('message-input'),
        sendButton: document.getElementById('send-button'),
        chatMessages: document.getElementById('chat-messages'),
        typingIndicator: document.getElementById('typing-indicator'),
        statusIndicator: document.getElementById('status-indicator'),
        resetButton: document.getElementById('reset-btn'),
        quickButtons: document.querySelectorAll('.quick-btn')
    };

    // =========================================================================
    // State
    // =========================================================================
    let isProcessing = false;

    // =========================================================================
    // Utility Functions
    // =========================================================================

    /**
     * Escape HTML to prevent XSS attacks
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Format timestamp for display
     * @param {string} isoString - ISO timestamp string
     * @returns {string} Formatted time string
     */
    function formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }

    /**
     * Update status indicator
     * @param {string} status - Status type: 'ready', 'loading', 'error'
     * @param {string} text - Status text
     */
    function updateStatus(status, text) {
        const indicator = elements.statusIndicator;
        indicator.className = 'status-indicator';
        
        if (status === 'loading') {
            indicator.classList.add('loading');
        } else if (status === 'error') {
            indicator.classList.add('error');
        }
        
        indicator.querySelector('.status-text').textContent = text;
    }

    /**
     * Show typing indicator
     */
    function showTypingIndicator() {
        elements.typingIndicator.classList.add('active');
        scrollToBottom();
    }

    /**
     * Hide typing indicator
     */
    function hideTypingIndicator() {
        elements.typingIndicator.classList.remove('active');
    }

    /**
     * Scroll chat to bottom
     */
    function scrollToBottom() {
        requestAnimationFrame(() => {
            elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
        });
    }

    // =========================================================================
    // Markdown Parser
    // =========================================================================

    /**
     * Simple markdown parser
     * @param {string} text - Markdown text
     * @returns {string} HTML
     */
    function parseMarkdown(text) {
        if (!text) return '';
        
        let html = text;
        
        // Code blocks (```code```)
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Inline code (`code`)
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Bold (**text**)
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // Italic (*text*)
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
        // Strikethrough (~~text~~)
        html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');
        
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
        
        // Blockquotes (> text)
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
        
        // Horizontal rule
        html = html.replace(/^---$/gm, '<hr>');
        
        // Links [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        
        // Tables - handle markdown tables
        const lines = html.split('\n');
        let inTable = false;
        let tableContent = [];
        let newHtml = '';
        
        lines.forEach((line, index) => {
            // Check if this is a table row
            if (line.trim().startsWith('|') && line.includes('|')) {
                const trimmedLine = line.trim();
                
                // Check if this is a separator row (contains only -, :, |, and spaces)
                const isSeparator = /^\|?\s*[-:\s]+\s*(\|\s*[-:\s]+)*\|?\s*$/.test(trimmedLine.replace(/\|/g, '').trim());
                
                if (isSeparator) {
                    // Skip separator rows
                    return;
                }
                
                const nextLine = lines[index + 1] || '';
                
                // Check if next line is a table separator (contains ---)
                if (nextLine.includes('---')) {
                    if (!inTable) {
                        inTable = true;
                        tableContent = [];
                    }
                    // This is header row
                    const cells = line.split('|').filter(c => c.trim());
                    tableContent.push({ type: 'header', cells: cells });
                } else if (inTable || tableContent.length === 0) {
                    // This is a data row
                    const cells = line.split('|').filter(c => c.trim());
                    if (cells.length > 0) {
                        tableContent.push({ type: 'row', cells: cells });
                    }
                }
            } else {
                // Not a table line
                if (inTable && tableContent.length > 0) {
                    // Build table HTML
                    newHtml += '<table>';
                    tableContent.forEach((row, idx) => {
                        if (row.type === 'header') {
                            newHtml += '<thead><tr>';
                            row.cells.forEach(cell => {
                                newHtml += '<th>' + cell.trim() + '</th>';
                            });
                            newHtml += '</tr></thead><tbody>';
                        } else {
                            newHtml += '<tr>';
                            row.cells.forEach(cell => {
                                newHtml += '<td>' + cell.trim() + '</td>';
                            });
                            newHtml += '</tr>';
                        }
                    });
                    newHtml += '</tbody></table>';
                    tableContent = [];
                    inTable = false;
                }
                newHtml += line + (index < lines.length - 1 ? '\n' : '');
            }
        });
        
        // Handle any remaining table at end
        if (inTable && tableContent.length > 0) {
            newHtml += '<table>';
            tableContent.forEach(row => {
                if (row.type === 'header') {
                    newHtml += '<thead><tr>';
                    row.cells.forEach(cell => {
                        newHtml += '<th>' + cell.trim() + '</th>';
                    });
                    newHtml += '</tr></thead><tbody>';
                } else {
                    newHtml += '<tr>';
                    row.cells.forEach(cell => {
                        newHtml += '<td>' + cell.trim() + '</td>';
                    });
                    newHtml += '</tr>';
                }
            });
            newHtml += '</tbody></table>';
        }
        
        html = newHtml || html;
        
        // Unordered lists (- item)
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        
        // Convert consecutive li to ul
        html = html.replace(/(<li>.*?<\/li>)+/g, function(match) {
            return '<ul>' + match + '</ul>';
        });
        
        // Task lists (- [ ] or - [x])
        html = html.replace(/- \[ \] (.+)/g, '<input type="checkbox" disabled> $1');
        html = html.replace(/- \[x\] (.+)/g, '<input type="checkbox" checked disabled> $1');
        
        // Line breaks to paragraphs
        html = html.split('\n\n').map(p => p.trim()).filter(p => p).map(p => '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
        
        return html;
    }

    // =========================================================================
    // Message Rendering
    // =========================================================================

    /**
     * Create and append a user message
     * @param {string} text - Message text
     * @param {string} timestamp - ISO timestamp
     */
    function appendUserMessage(text, timestamp) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            </div>
            <div class="message-content">
                <p>${escapeHtml(text)}</p>
                <span class="message-time">${formatTime(timestamp)}</span>
            </div>
        `;
        
        elements.chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * Create and append an AI message
     * @param {string} text - Message text
     * @param {string} timestamp - ISO timestamp
     */
    function appendAiMessage(text, timestamp) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        
        // Parse markdown
        const formattedText = parseMarkdown(text);
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 8V4H8"></path>
                    <rect x="8" y="8" width="8" height="8" rx="2"></rect>
                    <path d="M4 14h2"></path>
                    <path d="M4 18h2"></path>
                    <path d="M4 22h2"></path>
                    <path d="M18 14h2"></path>
                    <path d="M18 18h2"></path>
                    <path d="M18 22h2"></path>
                </svg>
            </div>
            <div class="message-content">
                <div class="markdown-content">${formattedText}</div>
                <span class="message-time">${formatTime(timestamp)}</span>
            </div>
        `;
        
        elements.chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * Create and append an error message
     * @param {string} errorMessage - Error message to display
     */
    function appendErrorMessage(errorMessage) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message error-message';
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
            </div>
            <div class="message-content">
                <p>${escapeHtml(errorMessage)}</p>
                <span class="message-time">${formatTime(new Date().toISOString())}</span>
            </div>
        `;
        
        elements.chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // =========================================================================
    // API Communication
    // =========================================================================

    /**
     * Send message to the chat API
     * @param {string} message - User message
     * @returns {Promise<Object>} API response
     */
    async function sendChatMessage(message) {
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                use_memory: true
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Reset conversation
     * @returns {Promise<void>}
     */
    async function resetConversation() {
        const response = await fetch(CONFIG.RESET_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to reset conversation');
        }

        return response.json();
    }

    /**
     * Check API health
     * @returns {Promise<Object>} Health status
     */
    async function checkHealth() {
        try {
            const response = await fetch(CONFIG.HEALTH_ENDPOINT);
            return await response.json();
        } catch (error) {
            console.error('Health check failed:', error);
            return { status: 'unhealthy' };
        }
    }

    // =========================================================================
    // Event Handlers
    // =========================================================================

    /**
     * Handle form submission
     * @param {Event} event - Form submit event
     */
    async function handleFormSubmit(event) {
        event.preventDefault();
        
        if (isProcessing) return;
        
        const message = elements.messageInput.value.trim();
        
        if (!message) {
            elements.messageInput.focus();
            return;
        }

        isProcessing = true;
        updateStatus('loading', 'Processing...');
        
        // Disable input
        elements.messageInput.disabled = true;
        elements.sendButton.disabled = true;
        
        // Add user message to chat
        const timestamp = new Date().toISOString();
        appendUserMessage(message, timestamp);
        
        // Clear input
        elements.messageInput.value = '';
        
        // Show typing indicator after a short delay
        setTimeout(showTypingIndicator, CONFIG.TYPING_INDICATOR_DELAY);
        
        try {
            const result = await sendChatMessage(message);
            
            hideTypingIndicator();
            
            if (result.success) {
                appendAiMessage(result.response, result.timestamp);
                updateStatus('ready', 'Ready');
            } else {
                appendErrorMessage(result.error || 'An error occurred');
                updateStatus('error', 'Error');
            }
        } catch (error) {
            hideTypingIndicator();
            console.error('Chat error:', error);
            appendErrorMessage(error.message || 'Failed to connect to server');
            updateStatus('error', 'Error');
        } finally {
            isProcessing = false;
            elements.messageInput.disabled = false;
            elements.sendButton.disabled = false;
            elements.messageInput.focus();
        }
    }

    /**
     * Handle quick access button click
     * @param {Event} event - Click event
     */
    async function handleQuickButtonClick(event) {
        const button = event.currentTarget;
        const prompt = button.dataset.prompt;
        
        if (!prompt || isProcessing) return;
        
        // Visual feedback
        button.style.transform = 'scale(0.95)';
        setTimeout(() => {
            button.style.transform = '';
        }, 150);
        
        // Update input value
        elements.messageInput.value = prompt;
        
        // Trigger form submission
        await handleFormSubmit(new Event('submit'));
    }

    /**
     * Handle reset button click
     * @param {Event} event - Click event
     */
    async function handleResetClick(event) {
        event.preventDefault();
        
        if (isProcessing) return;
        
        const confirmed = confirm('Are you sure you want to start a new conversation?');
        
        if (!confirmed) return;
        
        isProcessing = true;
        updateStatus('loading', 'Resetting...');
        
        try {
            await resetConversation();
            
            // Clear chat messages
            elements.chatMessages.innerHTML = '';
            
            // Add welcome message
            const welcomeMessage = document.createElement('div');
            welcomeMessage.className = 'message ai-message';
            welcomeMessage.innerHTML = `
                <div class="message-avatar">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 8V4H8"></path>
                        <rect x="8" y="8" width="8" height="8" rx="2"></rect>
                        <path d="M4 14h2"></path>
                        <path d="M4 18h2"></path>
                        <path d="M4 22h2"></path>
                        <path d="M18 14h2"></path>
                        <path d="M18 18h2"></path>
                        <path d="M18 22h2"></path>
                    </svg>
                </div>
                <div class="message-content">
                    <p>Welcome to <strong>University AI Receptionist</strong>!</p>
                    <p>I've started a new conversation. How can I help you today?</p>
                    <span class="message-time">${formatTime(new Date().toISOString())}</span>
                </div>
            `;
            elements.chatMessages.appendChild(welcomeMessage);
            
            updateStatus('ready', 'Ready');
        } catch (error) {
            console.error('Reset error:', error);
            appendErrorMessage('Failed to reset conversation');
            updateStatus('error', 'Error');
        } finally {
            isProcessing = false;
            elements.messageInput.focus();
        }
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the application
     */
    async function init() {
        // Check API health
        const health = await checkHealth();
        
        if (health.status === 'unhealthy') {
            console.warn('API health check failed');
            updateStatus('error', 'API Unavailable');
        } else if (health.api_key_configured) {
            updateStatus('ready', 'Ready');
        } else {
            updateStatus('error', 'API Key Missing');
        }
        
        // Set up event listeners
        elements.chatForm.addEventListener('submit', handleFormSubmit);
        
        elements.quickButtons.forEach(button => {
            button.addEventListener('click', handleQuickButtonClick);
        });
        
        elements.resetButton.addEventListener('click', handleResetClick);
        
        // Set up enter key handling
        elements.messageInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleFormSubmit(event);
            }
        });
        
        // Focus input on load
        elements.messageInput.focus();
        
        console.log('University AI Receptionist initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
