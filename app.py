"""
University AI Receptionist - Flask Server
A Flask-based AI receptionist that uses OpenRouter API for LLM responses.
Implements date-based conversation memory system with security best practices.
"""

import os
import re
import json
import logging
import html
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import wraps
import time

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

from flask import Flask, render_template, request, jsonify, session, make_response
from flask_cors import CORS
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# Security: Configure CORS - default to localhost for development
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000')
CORS(app, resources={
    r"/api/*": {
        "origins": CORS_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "expose_headers": ["Content-Type"],
        "max_age": 3600
    }
})

# Security Headers Middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    return response

# Rate Limiting Storage (simple in-memory for development)
rate_limit_storage: Dict[str, List[float]] = {}

def rate_limit(max_requests: int = 30, window_seconds: int = 60):
    """Rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get client IP
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            current_time = time.time()
            
            # Initialize or clean old entries
            if client_ip not in rate_limit_storage:
                rate_limit_storage[client_ip] = []
            
            # Remove old requests outside the window
            rate_limit_storage[client_ip] = [
                t for t in rate_limit_storage[client_ip] 
                if current_time - t < window_seconds
            ]
            
            # Check rate limit
            if len(rate_limit_storage[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({'error': 'Too many requests. Please try again later.'}), 429
            
            # Add current request
            rate_limit_storage[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Configuration
class Config:
    """Application configuration from environment variables."""
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
    OPENROUTER_API_URL = os.environ.get('OPENROUTER_API_URL', 
        'https://openrouter.ai/api/v1/chat/completions')
    MODEL_NAME = os.environ.get('MODEL_NAME', 'qwen/qwen3.5-flash-02-23')
    MEMORY_DIR = Path(os.environ.get('MEMORY_DIR', 'memory'))
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '1000'))
    MAX_MESSAGES_CONTEXT = int(os.environ.get('MAX_MESSAGES_CONTEXT', '10'))
    RATE_LIMIT = int(os.environ.get('RATE_LIMIT', '30'))  # requests per minute
    
    # System prompt for the AI receptionist
    SYSTEM_PROMPT = """You are a friendly and helpful university AI receptionist. 
You provide accurate information about the university including admissions, 
tuition, programs, campus location, hours of operation, and frequently asked questions.
Be concise, professional, and welcoming. Use the conversation history 
to provide context-aware responses. If you don't know something, admit it 
and suggest where the user might find the information."""


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: Raw user input
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # HTML escape to prevent XSS
    sanitized = html.escape(text)
    
    # Remove potential prompt injection patterns
    injection_patterns = [
        r'ignore previous instructions',
        r'ignore all instructions',
        r'system prompt:',
        r'\b jailbreak\b',
        r'dan mode',
        r'developer mode:'
    ]
    
    for pattern in injection_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Normalize whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized.strip()
class APIError(Exception):
    """Custom exception for API errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class MemoryError(Exception):
    """Custom exception for memory system errors."""
    pass


# ============================================================================
# Memory System
# ============================================================================

class MemorySystem:
    """
    Manages conversation memory with date-based folder organization.
    Structure: memory/YYYY-MM-DD/conversations.json
    """
    
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self._ensure_memory_dir()
    
    def _ensure_memory_dir(self) -> None:
        """Ensure base memory directory exists."""
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Memory directory initialized: {self.memory_dir}")
        except Exception as e:
            logger.error(f"Failed to create memory directory: {e}")
            raise MemoryError(f"Failed to initialize memory directory: {e}")
    
    def _get_date_folder(self, date: datetime) -> Path:
        """Get the folder path for a specific date."""
        date_str = date.strftime('%Y-%m-%d')
        return self.memory_dir / date_str
    
    def _get_conversation_file(self, date: datetime) -> Path:
        """Get the conversation file path for a specific date."""
        return self._get_date_folder(date) / 'conversations.json'
    
    def _validate_date(self, date_str: str) -> Optional[datetime]:
        """Validate and parse date string to prevent path traversal."""
        try:
            # Only allow YYYY-MM-DD format to prevent path traversal
            if not date_str or len(date_str) != 10:
                return None
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None
    
    def load_conversations(self, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Load conversations for a specific date.
        
        Args:
            date: datetime object, defaults to today
            
        Returns:
            List of conversation messages
        """
        if date is None:
            date = datetime.now()
        
        conversation_file = self._get_conversation_file(date)
        
        if not conversation_file.exists():
            logger.info(f"No conversation file found for {date.strftime('%Y-%m-%d')}")
            return []
        
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('messages', [])
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in conversation file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading conversations: {e}")
            return []
    
    def save_conversations(self, messages: List[Dict[str, Any]], 
                          date: Optional[datetime] = None) -> bool:
        """
        Save conversations for a specific date.
        
        Args:
            messages: List of message dictionaries
            date: datetime object, defaults to today
            
        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = datetime.now()
        
        date_folder = self._get_date_folder(date)
        
        try:
            # Create date folder if it doesn't exist
            date_folder.mkdir(parents=True, exist_ok=True)
            
            conversation_file = self._get_conversation_file(date)
            
            data = {
                'date': date.strftime('%Y-%m-%d'),
                'messages': messages
            }
            
            with open(conversation_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Conversations saved for {date.strftime('%Y-%m-%d')}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversations: {e}")
            return False
    
    def load_recent_conversations(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Load conversations from recent days for context.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Combined list of recent messages
        """
        all_messages = []
        today = datetime.now()
        
        for i in range(days):
            date = today - timedelta(days=i)
            messages = self.load_conversations(date)
            all_messages.extend(messages)
        
        # Return most recent messages up to MAX_MESSAGES_CONTEXT
        return all_messages[-Config.MAX_MESSAGES_CONTEXT:]
    
    def get_conversation_for_date(self, date_str: str) -> Dict[str, Any]:
        """
        Get conversation for a specific date string.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Dictionary with date and messages
        """
        date = self._validate_date(date_str)
        if date is None:
            return {'error': 'Invalid date format', 'messages': []}
        
        messages = self.load_conversations(date)
        return {
            'date': date_str,
            'messages': messages
        }


# Initialize memory system
memory_system = MemorySystem(Config.MEMORY_DIR)


# ============================================================================
# OpenRouter API Integration
# ============================================================================

class OpenRouterService:
    """Service for interacting with OpenRouter API."""
    
    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.api_url = Config.OPENROUTER_API_URL
        self.model = Config.MODEL_NAME
    
    def _validate_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key and self.api_key.strip())
    
    def _build_messages(self, user_message: str, 
                       conversation_history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Build the messages list for API call."""
        messages = [
            {"role": "system", "content": Config.SYSTEM_PROMPT}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            if msg.get('role') in ['user', 'assistant']:
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def send_message(self, user_message: str, 
                    conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send message to OpenRouter API and get response.
        
        Args:
            user_message: The user's message
            conversation_history: Previous conversation messages
            
        Returns:
            Dictionary with response and metadata
        """
        if not self._validate_api_key():
            logger.error("OpenRouter API key not configured")
            raise APIError("API key not configured. Please set OPENROUTER_API_KEY.", 503)
        
        if conversation_history is None:
            conversation_history = []
        
        messages = self._build_messages(user_message, conversation_history)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get('HTTP_REFERER', 'http://localhost:5000'),
            "X-Title": os.environ.get('APP_TITLE', 'University AI Receptionist')
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            logger.info(f"Sending request to OpenRouter API with model: {self.model}")
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            result = response.json()
            
            # Extract assistant's response
            if 'choices' in result and len(result['choices']) > 0:
                assistant_message = result['choices'][0]['message']['content']
                
                return {
                    'success': True,
                    'response': assistant_message,
                    'model': self.model,
                    'usage': result.get('usage', {})
                }
            else:
                logger.error(f"Unexpected API response structure: {result}")
                raise APIError("Invalid response from API", 500)
                
        except requests.exceptions.Timeout:
            logger.error("API request timed out")
            raise APIError("Request timed out. Please try again.", 504)
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise APIError(f"Failed to connect to API: {str(e)}", 503)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from API: {e}")
            raise APIError("Invalid response from API", 500)
        except Exception as e:
            logger.error(f"Unexpected error in API call: {e}")
            raise APIError("An unexpected error occurred", 500)


# Initialize OpenRouter service
openrouter_service = OpenRouterService()


# ============================================================================
# Flask Routes
# ============================================================================

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def chat():
    """
    Handle chat requests.
    
    Request JSON:
        {
            "message": "user message",
            "use_memory": true (optional)
        }
        
    Response JSON:
        {
            "response": "AI response",
            "timestamp": "ISO timestamp"
        }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        
        # Validate message
        user_message = data.get('message', '').strip()
        
        # Sanitize input to prevent injection attacks
        user_message = sanitize_input(user_message)
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if len(user_message) > Config.MAX_MESSAGE_LENGTH:
            return jsonify({
                'error': f'Message too long. Maximum {Config.MAX_MESSAGE_LENGTH} characters.'
            }), 400
        
        # Get conversation history
        use_memory = data.get('use_memory', True)
        
        if use_memory:
            # Load recent conversations for context
            conversation_history = memory_system.load_recent_conversations()
        else:
            conversation_history = session.get('current_conversation', [])
        
        # Get AI response
        result = openrouter_service.send_message(user_message, conversation_history)
        
        # Create message objects
        timestamp = datetime.now().isoformat()
        
        user_msg = {
            'role': 'user',
            'content': user_message,
            'timestamp': timestamp
        }
        
        ai_msg = {
            'role': 'assistant',
            'content': result['response'],
            'timestamp': timestamp
        }
        
        # Update session conversation
        current_conv = session.get('current_conversation', [])
        current_conv.extend([user_msg, ai_msg])
        
        # Keep only recent messages in session
        max_session_messages = Config.MAX_MESSAGES_CONTEXT * 2
        session['current_conversation'] = current_conv[-max_session_messages:]
        
        # Save to memory if enabled
        if use_memory:
            today_messages = memory_system.load_conversations()
            today_messages.extend([user_msg, ai_msg])
            memory_system.save_conversations(today_messages)
        
        logger.info(f"Chat request processed successfully")
        
        return jsonify({
            'response': result['response'],
            'timestamp': timestamp,
            'success': True
        })
        
    except APIError as e:
        logger.error(f"API Error: {e.message}")
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@app.route('/api/memory', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
def get_memory():
    """
    Get conversation memory for a specific date.
    
    Query params:
        date: Date in YYYY-MM-DD format (optional, defaults to today)
        
    Response JSON:
        {
            "date": "2026-02-26",
            "messages": [...]
        }
    """
    try:
        date_str = request.args.get('date')
        
        if date_str:
            result = memory_system.get_conversation_for_date(date_str)
        else:
            # Get today's conversations
            messages = memory_system.load_conversations()
            result = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'messages': messages
            }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting memory: {e}")
        return jsonify({'error': 'Failed to retrieve memory'}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """
    Reset the current conversation session.
    
    Response JSON:
        {
            "success": true,
            "message": "Conversation reset successfully"
        }
    """
    try:
        session.pop('current_conversation', None)
        return jsonify({
            'success': True,
            'message': 'Conversation reset successfully'
        })
    except Exception as e:
        logger.error(f"Error resetting conversation: {e}")
        return jsonify({'error': 'Failed to reset conversation'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    api_key_configured = openrouter_service._validate_api_key()
    memory_dir_exists = Config.MEMORY_DIR.exists()
    
    return jsonify({
        'status': 'healthy',
        'api_key_configured': api_key_configured,
        'memory_dir_exists': memory_dir_exists,
        'model': Config.MODEL_NAME
    })


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == '__main__':
    # Validate configuration
    if not Config.OPENROUTER_API_KEY:
        logger.warning("WARNING: OPENROUTER_API_KEY is not set. API calls will fail.")
    
    # Ensure memory directory exists
    Config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting University AI Receptionist on port {port}")
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"Model: {Config.MODEL_NAME}")
    logger.info(f"Memory directory: {Config.MEMORY_DIR}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
