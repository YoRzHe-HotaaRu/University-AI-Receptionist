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
        API_STREAM_ENDPOINT: '/api/chat/stream',
        MEMORY_ENDPOINT: '/api/memory',
        RESET_ENDPOINT: '/api/reset',
        HEALTH_ENDPOINT: '/api/health',
        TTS_ENDPOINT: '/api/tts',
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
        quickButtons: document.querySelectorAll('.quick-btn'),
        ttsToggleBtn: document.getElementById('tts-toggle-btn'),
        ttsIconOff: document.getElementById('tts-icon-off'),
        ttsIconOn: document.getElementById('tts-icon-on'),
        ttsToggleLabel: document.getElementById('tts-toggle-label')
    };

    // =========================================================================
    // State
    // =========================================================================
    let isProcessing = false;
    let ttsEnabled = false;        // TTS auto-play toggle state
    let currentAudio = null;       // Track playing audio so we can stop it
    let autoScrollEnabled = true;  // Auto-scroll toggle state
    let userScrolled = false;      // Track if user manually scrolled

    // =========================================================================
    // Auto-scroll Detection
    // =========================================================================
    
    /**
     * Check if user is near bottom of chat
     * @returns {boolean} True if near bottom
     */
    function isNearBottom() {
        const container = elements.chatMessages;
        const threshold = 100; // pixels from bottom
        return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
    }
    
    /**
     * Smart scroll to bottom - only if auto-scroll is enabled
     */
    function smartScrollToBottom() {
        if (autoScrollEnabled && !userScrolled) {
            elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
        }
    }
    
    // Detect user scroll to disable auto-scroll
    elements.chatMessages.addEventListener('scroll', () => {
        if (!isNearBottom()) {
            userScrolled = true;
            autoScrollEnabled = false;
        } else {
            userScrolled = false;
            autoScrollEnabled = true;
        }
    });
    
    // Re-enable auto-scroll when user sends a new message
    elements.messageInput.addEventListener('focus', () => {
        autoScrollEnabled = true;
        userScrolled = false;
    });

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
     * Scroll chat to bottom (legacy - uses smart scroll)
     */
    function scrollToBottom() {
        smartScrollToBottom();
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
     * @param {string} reasoning - AI reasoning/thinking process
     */
    function appendAiMessage(text, timestamp, reasoning = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        
        // Parse markdown
        const formattedText = parseMarkdown(text);
        
        // Build reasoning section if present
        let reasoningHtml = '';
        if (reasoning && reasoning.trim()) {
            const formattedReasoning = escapeHtml(reasoning);
            reasoningHtml = `
                <div class="reasoning-section">
                    <button class="reasoning-toggle" onclick="this.classList.toggle('expanded'); this.nextElementSibling.classList.toggle('visible');">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                        <span>Lihat fikiran AI</span>
                        <svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <div class="reasoning-content">
                        <pre>${formattedReasoning}</pre>
                    </div>
                </div>
            `;
        }
        
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
                ${reasoningHtml}
                <div class="markdown-content">${formattedText}</div>
                <span class="message-time">${formatTime(timestamp)}</span>
            </div>
        `;
        
        elements.chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }
    
    /**
     * Create a streaming AI message container for real-time updates
     * @returns {Object} Object with messageDiv, updateReasoning, updateContent, finalize
     */
    function createStreamingAiMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        
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
                <div class="reasoning-section streaming">
                    <div class="reasoning-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                        <span>AI sedang berfikir...</span>
                        <span class="streaming-indicator"></span>
                    </div>
                    <div class="reasoning-content visible">
                        <pre></pre>
                    </div>
                </div>
                <div class="markdown-content" style="display: none;"></div>
                <span class="message-time"></span>
            </div>
        `;
        
        elements.chatMessages.appendChild(messageDiv);
        scrollToBottom();
        
        const reasoningPre = messageDiv.querySelector('.reasoning-section pre');
        const reasoningSection = messageDiv.querySelector('.reasoning-section');
        const reasoningHeader = messageDiv.querySelector('.reasoning-header');
        const contentDiv = messageDiv.querySelector('.markdown-content');
        const timeSpan = messageDiv.querySelector('.message-time');
        
        return {
            messageDiv,
            updateReasoning: (text) => {
                reasoningPre.textContent += text;
                smartScrollToBottom();
            },
            showContent: () => {
                reasoningSection.classList.add('completed');
                // Get the reasoning content before restructuring
                const reasoningText = reasoningPre.textContent;
                
                // Restructure: header becomes clickable toggle, content is separate and hidden by default
                reasoningSection.innerHTML = `
                    <button class="reasoning-toggle">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                        <span>Lihat fikiran AI</span>
                        <svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <div class="reasoning-content">
                        <pre>${escapeHtml(reasoningText)}</pre>
                    </div>
                `;
                
                // Add click event listener to the new toggle button
                const newToggle = reasoningSection.querySelector('.reasoning-toggle');
                const newContent = reasoningSection.querySelector('.reasoning-content');
                newToggle.addEventListener('click', () => {
                    newToggle.classList.toggle('expanded');
                    newContent.classList.toggle('visible');
                });
                
                // Show the answer content
                contentDiv.style.display = 'block';
                smartScrollToBottom();
            },
            updateContent: (text) => {
                contentDiv.textContent += text;
                smartScrollToBottom();
            },
            finalize: (timestamp) => {
                timeSpan.textContent = formatTime(timestamp);
                // Final markdown parsing
                contentDiv.innerHTML = parseMarkdown(contentDiv.textContent);
                smartScrollToBottom();
            }
        };
    }
    
    /**
     * Auto-play TTS for a given text (used when toggle is enabled).
     * Optimized for low latency - starts fetching immediately and plays as soon as ready.
     * @param {string} text - Text to convert to speech
     */
    async function playTTSAuto(text) {
        if (!ttsEnabled) return;

        // Stop any currently playing audio immediately
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            currentAudio = null;
        }

        // Show subtle loading indicator without blocking
        elements.ttsToggleBtn.classList.add('loading');

        try {
            // Use AbortController for timeout control
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

            const response = await fetch(CONFIG.TTS_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('TTS error:', errorData.error || response.status);
                elements.ttsToggleBtn.classList.remove('loading');
                return;
            }

            // Get audio blob and start playing immediately
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);

            // Preload audio for faster playback start
            audio.preload = 'auto';
            currentAudio = audio;

            // Set up cleanup handlers
            audio.onended = () => {
                currentAudio = null;
                URL.revokeObjectURL(audioUrl);
                elements.ttsToggleBtn.classList.remove('loading');
            };

            audio.onerror = () => {
                currentAudio = null;
                URL.revokeObjectURL(audioUrl);
                elements.ttsToggleBtn.classList.remove('loading');
                console.error('TTS audio playback error');
            };

            // Start playing as soon as possible
            // Use play() with catch to handle autoplay restrictions
            const playPromise = audio.play();
            if (playPromise !== undefined) {
                playPromise.catch(error => {
                    console.error('Audio play failed:', error);
                    elements.ttsToggleBtn.classList.remove('loading');
                });
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('TTS request timed out');
            } else {
                console.error('TTS auto-play error:', error);
            }
            elements.ttsToggleBtn.classList.remove('loading');
        }
    }

    /**
     * Toggle the TTS auto-play feature on/off.
     */
    function toggleTTS() {
        ttsEnabled = !ttsEnabled;

        if (ttsEnabled) {
            elements.ttsToggleBtn.classList.add('active');
            elements.ttsToggleBtn.setAttribute('aria-pressed', 'true');
            elements.ttsToggleBtn.title = 'Toggle auto voice (TTS on)';
            elements.ttsIconOff.style.display = 'none';
            elements.ttsIconOn.style.display = 'inline-block';
            elements.ttsToggleLabel.textContent = 'Suara: Hidup';
        } else {
            // Stop any playing audio immediately
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }
            elements.ttsToggleBtn.classList.remove('active', 'loading');
            elements.ttsToggleBtn.setAttribute('aria-pressed', 'false');
            elements.ttsToggleBtn.title = 'Toggle auto voice (TTS off)';
            elements.ttsIconOff.style.display = 'inline-block';
            elements.ttsIconOn.style.display = 'none';
            elements.ttsToggleLabel.textContent = 'Suara: Mati';
        }
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
     * Send message to the chat API (non-streaming fallback)
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
     * Send message to the chat API with streaming response
     * @param {string} message - User message
     * @param {Function} onChunk - Callback for each chunk: ({type, data}) => void
     * @returns {Promise<Object>} Final response with full content and reasoning
     */
    async function sendChatMessageStreaming(message, onChunk) {
        const response = await fetch(CONFIG.API_STREAM_ENDPOINT, {
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

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let fullReasoning = '';
        let timestamp = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const chunk = JSON.parse(line.slice(6));
                        
                        if (chunk.type === 'reasoning') {
                            fullReasoning += chunk.data;
                            onChunk({ type: 'reasoning', data: chunk.data });
                        } else if (chunk.type === 'content') {
                            fullContent += chunk.data;
                            onChunk({ type: 'content', data: chunk.data });
                        } else if (chunk.type === 'done') {
                            timestamp = chunk.timestamp;
                        } else if (chunk.type === 'error') {
                            throw new Error(chunk.data);
                        }
                    } catch (e) {
                        console.error('Error parsing SSE chunk:', e);
                    }
                }
            }
        }

        return {
            success: true,
            response: fullContent,
            reasoning: fullReasoning,
            timestamp: timestamp || new Date().toISOString()
        };
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
        
        // Re-enable auto-scroll when user sends a message
        autoScrollEnabled = true;
        userScrolled = false;
        
        // Add user message to chat
        const timestamp = new Date().toISOString();
        appendUserMessage(message, timestamp);
        
        // Clear input
        elements.messageInput.value = '';
        
        // Create streaming message container immediately (no typing indicator)
        const streamingMsg = createStreamingAiMessage();
        let hasReceivedContent = false;
        
        try {
            // Use streaming API for real-time reasoning display
            const result = await sendChatMessageStreaming(message, (chunk) => {
                if (chunk.type === 'reasoning') {
                    // Update reasoning in real-time
                    streamingMsg.updateReasoning(chunk.data);
                } else if (chunk.type === 'content') {
                    // First content chunk - transition from reasoning to answer
                    if (!hasReceivedContent) {
                        hasReceivedContent = true;
                        streamingMsg.showContent();
                    }
                    streamingMsg.updateContent(chunk.data);
                }
            });

            if (result.success) {
                // Finalize the message
                streamingMsg.finalize(result.timestamp);
                updateStatus('ready', 'Ready');
                
                // Start TTS after streaming completes
                if (ttsEnabled) {
                    playTTSAuto(result.response).catch(err => console.error('TTS error:', err));
                }
            } else {
                streamingMsg.messageDiv.remove();
                appendErrorMessage(result.error || 'An error occurred');
                updateStatus('error', 'Error');
            }
        } catch (error) {
            console.error('Chat error:', error);
            streamingMsg.messageDiv.remove();
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
                    <p>Selamat datang ke <strong>UiTM AI Receptionist</strong>!</p>
                    <p>Perbualan baharu telah dimulakan. Bagaimana saya boleh membantu anda hari ini?</p>
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
        
        // Set up TTS toggle
        elements.ttsToggleBtn.addEventListener('click', toggleTTS);

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
