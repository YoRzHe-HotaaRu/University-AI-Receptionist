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
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import wraps
import time
import threading

# Fix MIME types for static files (especially on Windows)
# Ensures CSS and JS files are served with correct Content-Type headers
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')
mimetypes.add_type('application/json', '.json')
mimetypes.add_type('image/svg+xml', '.svg')

from rag import KnowledgeBase
from vts_service import init_vts, vts_lip_sync, shutdown_vts, get_lip_sync_frames, vts_set_mouth

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

from flask import Flask, render_template, request, jsonify, session, make_response, Response, stream_with_context
from flask_cors import CORS, cross_origin
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

# Security: Configure CORS - default to all origins for development
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
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
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['X-Content-Type-Options'] = 'nosniff'
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
    MODEL_NAME = os.environ.get('MODEL_NAME', 'minimax/minimax-m2.5')
    MEMORY_DIR = Path(os.environ.get('MEMORY_DIR', 'memory'))
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '1000'))
    MAX_MESSAGES_CONTEXT = int(os.environ.get('MAX_MESSAGES_CONTEXT', '10'))
    RATE_LIMIT = int(os.environ.get('RATE_LIMIT', '30'))  # requests per minute
    
    # MiniMax TTS Configuration
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
    MINIMAX_TTS_MODEL = os.environ.get('MINIMAX_TTS_MODEL', 'speech-2.8-turbo')
    MINIMAX_TTS_VOICE_ID = os.environ.get('MINIMAX_TTS_VOICE_ID', 'moss_audio_f942350f-133e-11f1-8c62-b61f19f976ea')
    MINIMAX_TTS_LANGUAGE = os.environ.get('MINIMAX_TTS_LANGUAGE', 'ms')  # Malay language code
    
    # VTubeStudio Configuration
    VTS_ENABLED = os.environ.get('VTS_ENABLED', 'false').lower() == 'true'
    VTS_HOST = os.environ.get('VTS_HOST', 'localhost')
    VTS_PORT = int(os.environ.get('VTS_PORT', '8001'))
    
    # System prompt for the AI receptionist
    SYSTEM_PROMPT = """Anda ialah pembantu resepsionis AI yang profesional dan beradab untuk UITM (Universiti Teknologi MARA), sebuah universiti di Malaysia.
Anda menyediakan maklumat yang tepat mengenai universiti UITM termasuk kemasukan,
yuran, program, lokasi kampus, waktu operasi, dan soalan lazim.

PENTING: Anda MESTI memberi respons dalam Bahasa Malaysia yang FORMAL dan BAKU untuk SEMUA respons.
Ini adalah universiti Malaysia, jadi semua komunikasi hendaklah menggunakan Bahasa Malaysia formal melainkan pengguna meminta dalam Bahasa Inggeris.

KRITIKAL - GAYA BAHASA FORMAL:
- Gunakan Bahasa Malaysia formal dan baku sepenuhnya. Elakkan sebarang bahasa informal atau santai.
- Gunakan "anda" (bukan "kamu", "awak", "hang", "ko" atau sebarang bentuk informal).
- Gunakan "Tuan" atau "Puan" untuk merujuk pengguna dengan penuh hormat.
- Gunakan perkataan penuh: "dengan" (bukan "dgn"), "untuk" (bukan "utk"), "tidak" (bukan "tak", "x"), "sahaja" (bukan "je"), "itu" (bukan "tu"), "ini" (buku "ni").
- Elakkan partikel seruan seperti "lah", "kan", "pun", "tu", "ni" dalam ayat.
- Gunakan ayat yang lengkap dan gramatis. Jangan guna singkatan atau akronim tanpa penjelasan.
- Gaya percakapan mesti profesional, sopan, dan sesuai untuk perkhidmatan universiti.
- Contoh: "Selamat datang, Tuan. Bagaimanakah saya boleh membantu Tuan hari ini?" (bukan "Selamat datang, nak tolong apa?")

KRITIKAL: Berikan respons yang PADAT dan LANGSUNG. Jangan berfikir panjang atau menghasilkan monolog dalaman yang panjang.
Pastikan proses pemikiran anda padat (maksimum 1-2 langkah pendek). Respons dengan pantas dan semula jadi.

Bersikap profesional, sopan, dan mengalu-alukan. Gunakan sejarah perbualan
untuk memberikan respons yang relevan dengan konteks. Jika anda tidak mengetahui sesuatu, akui
dan cadangkan di mana pengguna boleh mencari maklumat tersebut.

Sentiasa beri respons dalam Bahasa Malaysia formal dan baku."""


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
    Includes in-memory cache to reduce disk I/O latency.
    """
    
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self._ensure_memory_dir()
        # In-memory cache for today's conversations to avoid repeated disk reads
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_date: Optional[str] = None
        self._cache_lock = threading.Lock()
    
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
        Uses in-memory cache for today's conversations to reduce I/O.
        
        Args:
            date: datetime object, defaults to today
            
        Returns:
            List of conversation messages
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime('%Y-%m-%d')
        
        # Check cache for today's conversations
        with self._cache_lock:
            if date_str == self._cache_date and date_str in self._cache:
                logger.debug(f"Returning cached conversations for {date_str}")
                return self._cache[date_str].copy()
        
        conversation_file = self._get_conversation_file(date)
        
        if not conversation_file.exists():
            logger.info(f"No conversation file found for {date_str}")
            return []
        
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Cache today's conversations
                with self._cache_lock:
                    if date_str == datetime.now().strftime('%Y-%m-%d'):
                        self._cache_date = date_str
                        self._cache[date_str] = messages.copy()
                
                return messages
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
        Also updates in-memory cache for today's conversations.
        
        Args:
            messages: List of message dictionaries
            date: datetime object, defaults to today
            
        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime('%Y-%m-%d')
        date_folder = self._get_date_folder(date)
        
        try:
            # Create date folder if it doesn't exist
            date_folder.mkdir(parents=True, exist_ok=True)
            
            conversation_file = self._get_conversation_file(date)
            
            data = {
                'date': date_str,
                'messages': messages
            }
            
            with open(conversation_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Update cache for today's conversations
            with self._cache_lock:
                if date_str == datetime.now().strftime('%Y-%m-%d'):
                    self._cache_date = date_str
                    self._cache[date_str] = messages.copy()
            
            logger.info(f"Conversations saved for {date_str}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversations: {e}")
            return False
    
    def load_recent_conversations(self, days: int = 1) -> List[Dict[str, Any]]:
        """
        Load conversations from recent days for context.
        Optimized: Only loads 1 day by default to reduce I/O latency.
        
        Args:
            days: Number of days to look back (default: 1 for speed)
            
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
        """Build the messages list for API call with RAG context."""
        # Search knowledge base for relevant context
        knowledge_context = knowledge_base.search(user_message)
        
        # Build system prompt with optional knowledge injection
        system_content = Config.SYSTEM_PROMPT
        if knowledge_context:
            system_content += (
                "\n\nMaklumat berkaitan untuk rujukan kamu:\n"
                + knowledge_context
            )
        
        messages = [
            {"role": "system", "content": system_content}
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
            "max_tokens": 1000,
            "reasoning": {"enabled": True}
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
            
            # Extract assistant's response and reasoning
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0]['message']
                assistant_message = message.get('content', '')
                reasoning = message.get('reasoning', '')  # Extract reasoning if available
                
                return {
                    'success': True,
                    'response': assistant_message,
                    'reasoning': reasoning,
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
    
    def send_message_streaming(self, user_message: str,
                               conversation_history: List[Dict[str, Any]] = None):
        """
        Send message to OpenRouter API and stream the response.
        Yields chunks of reasoning and content as they arrive.
        
        Args:
            user_message: The user's message
            conversation_history: Previous conversation messages
            
        Yields:
            Dict with 'type' ('reasoning' or 'content') and 'data' (text chunk)
        """
        if not self._validate_api_key():
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
            "max_tokens": 1000,
            "stream": True,
            "reasoning": {"enabled": True}
        }
        
        try:
            logger.info(f"Sending streaming request to OpenRouter API with model: {self.model}")
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60,
                stream=True
            )
            
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                
                                # Yield reasoning chunks
                                if 'reasoning' in delta and delta['reasoning']:
                                    yield {'type': 'reasoning', 'data': delta['reasoning']}
                                
                                # Yield content chunks
                                if 'content' in delta and delta['content']:
                                    yield {'type': 'content', 'data': delta['content']}
                        except json.JSONDecodeError:
                            continue
            
            yield {'type': 'done', 'data': ''}
            
        except requests.exceptions.Timeout:
            raise APIError("Request timed out. Please try again.", 504)
        except requests.exceptions.RequestException as e:
            raise APIError(f"Failed to connect to API: {str(e)}", 503)
        except Exception as e:
            raise APIError("An unexpected error occurred", 500)


# Initialize OpenRouter service
openrouter_service = OpenRouterService()

# Initialize RAG knowledge base
knowledge_base = KnowledgeBase()


# ============================================================================
# MiniMax TTS Service
# ============================================================================

class MiniMaxTTSService:
    """Service for interacting with MiniMax TTS API."""
    
    def __init__(self):
        self.api_key = Config.MINIMAX_API_KEY
        self.model = Config.MINIMAX_TTS_MODEL
        self.voice_id = Config.MINIMAX_TTS_VOICE_ID
        self.language = Config.MINIMAX_TTS_LANGUAGE
        # Use the correct MiniMax API endpoint from documentation
        self.api_url = "https://api.minimax.io/v1/t2a_v2"
    
    def _validate_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key and self.api_key.strip())
    
    def synthesize_speech(self, text: str) -> bytes:
        """
        Synthesize speech from text using MiniMax TTS API.
        
        Args:
            text: The text to synthesize
            
        Returns:
            Audio data as bytes
        """
        if not self._validate_api_key():
            logger.error("MiniMax API key not configured")
            raise APIError("TTS not configured. Please set MINIMAX_API_KEY.", 503)
        
        if not text or not text.strip():
            raise APIError("Text is required for TTS", 400)
        
        # Truncate text if too long (MiniMax has a limit)
        text = text[:1000] if len(text) > 1000 else text
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build the request payload — use 'url' output so MiniMax returns
        # a CDN URL; we download it server-side and stream clean MP3 bytes
        # back to the browser (avoids fragile hex-decode pipeline).
        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "language_boost": "Malay",
            "output_format": "url",
            "voice_setting": {
                "voice_id": self.voice_id,
                "speed": 1.05,
                "vol": 1.0,
                "pitch": 0,
                "emotion": "fluent"
            },
            "audio_setting": {
                "sample_rate": 16000,
                "bitrate": 64000,
                "format": "mp3",
                "channel": 1
            }
        }
        
        logger.info(f"Sending TTS request to MiniMax API with model: {self.model}, voice: {self.voice_id}")
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            logger.info(f"MiniMax TTS response status: {response.status_code}")
            logger.info(f"MiniMax TTS response body (first 500 chars): {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Check for successful response
                if result.get('base_resp', {}).get('status_code') == 0:
                    data = result.get('data', {})
                    audio_url = data.get('audio')
                    
                    if audio_url:
                        logger.info(f"MiniMax returned audio URL: {audio_url[:80]}...")
                        # Download the MP3 from the CDN URL
                        audio_response = requests.get(audio_url, timeout=30)
                        if audio_response.status_code == 200:
                            audio_bytes = audio_response.content
                            logger.info(f"Downloaded audio: {len(audio_bytes)} bytes, first 4 bytes: {audio_bytes[:4].hex() if audio_bytes else 'empty'}")
                            if not audio_bytes:
                                raise APIError("Downloaded audio is empty", 500)
                            return audio_bytes
                        else:
                            logger.error(f"Failed to download audio from CDN: {audio_response.status_code}")
                            raise APIError("Failed to download audio from TTS provider", 502)
                
                # Check for error in response
                error_msg = result.get('base_resp', {}).get('status_msg', 'Unknown error')
                logger.error(f"TTS API error: {error_msg}")
                raise APIError(f"TTS error: {error_msg}", 500)
            else:
                logger.error(f"TTS API error: {response.status_code} - {response.text}")
                raise APIError(f"TTS API error: {response.status_code}", response.status_code)
                
        except requests.exceptions.Timeout:
            logger.error("TTS request timed out")
            raise APIError("TTS request timed out", 504)
        except requests.exceptions.RequestException as e:
            logger.error(f"TTS request failed: {e}")
            raise APIError(f"TTS request failed: {str(e)}", 503)
        except APIError:
            raise  # Re-raise APIError as-is without wrapping
        except Exception as e:
            logger.error(f"Unexpected error in TTS: {e}")
            raise APIError(f"Unexpected TTS error: {str(e)}", 500)


# Initialize TTS service
minimax_tts_service = MiniMaxTTSService()

# Initialize VTubeStudio lip sync (background thread)
import atexit
init_vts(
    enabled=Config.VTS_ENABLED,
    host=Config.VTS_HOST,
    port=Config.VTS_PORT
)
atexit.register(shutdown_vts)


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
            'reasoning': result.get('reasoning', ''),  # Include reasoning
            'timestamp': timestamp
        }
        
        # Update session conversation
        current_conv = session.get('current_conversation', [])
        current_conv.extend([user_msg, ai_msg])
        
        # Keep only recent messages in session
        max_session_messages = Config.MAX_MESSAGES_CONTEXT * 2
        session['current_conversation'] = current_conv[-max_session_messages:]
        
        # Save to memory if enabled (async to not block response)
        if use_memory:
            def save_async():
                try:
                    today_messages = memory_system.load_conversations()
                    today_messages.extend([user_msg, ai_msg])
                    memory_system.save_conversations(today_messages)
                except Exception as e:
                    logger.error(f"Async memory save failed: {e}")
            
            threading.Thread(target=save_async, daemon=True).start()
        
        logger.info(f"Chat request processed successfully")
        
        return jsonify({
            'response': result['response'],
            'reasoning': result.get('reasoning', ''),
            'timestamp': timestamp,
            'success': True
        })
        
    except APIError as e:
        logger.error(f"API Error: {e.message}")
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@app.route('/api/chat/stream', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def chat_stream():
    """
    Handle chat requests with streaming response.
    Streams reasoning first, then content in real-time.
    
    Request JSON:
        {
            "message": "user message",
            "use_memory": true (optional)
        }
        
    Response: Server-Sent Events (SSE) stream
        data: {"type": "reasoning", "data": "thinking chunk"}
        data: {"type": "content", "data": "response chunk"}
        data: {"type": "done", "timestamp": "..."}
    """
    def generate():
        try:
            # Validate request
            if not request.is_json:
                yield f"data: {json.dumps({'type': 'error', 'data': 'Request must be JSON'})}\n\n"
                return
            
            data = request.get_json()
            
            # Validate message
            user_message = data.get('message', '').strip()
            user_message = sanitize_input(user_message)
            
            if not user_message:
                yield f"data: {json.dumps({'type': 'error', 'data': 'Message cannot be empty'})}\n\n"
                return
            
            if len(user_message) > Config.MAX_MESSAGE_LENGTH:
                yield f"data: {json.dumps({'type': 'error', 'data': f'Message too long. Maximum {Config.MAX_MESSAGE_LENGTH} characters.'})}\n\n"
                return
            
            # Get conversation history
            use_memory = data.get('use_memory', True)
            
            if use_memory:
                conversation_history = memory_system.load_recent_conversations()
            else:
                conversation_history = session.get('current_conversation', [])
            
            # Stream AI response
            full_response = []
            full_reasoning = []
            timestamp = datetime.now().isoformat()
            
            for chunk in openrouter_service.send_message_streaming(user_message, conversation_history):
                if chunk['type'] == 'reasoning':
                    full_reasoning.append(chunk['data'])
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk['type'] == 'content':
                    full_response.append(chunk['data'])
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk['type'] == 'done':
                    # Save to memory after streaming is complete
                    if use_memory and full_response:
                        user_msg = {
                            'role': 'user',
                            'content': user_message,
                            'timestamp': timestamp
                        }
                        ai_msg = {
                            'role': 'assistant',
                            'content': ''.join(full_response),
                            'reasoning': ''.join(full_reasoning),
                            'timestamp': timestamp
                        }
                        
                        # Update session
                        current_conv = session.get('current_conversation', [])
                        current_conv.extend([user_msg, ai_msg])
                        max_session_messages = Config.MAX_MESSAGES_CONTEXT * 2
                        session['current_conversation'] = current_conv[-max_session_messages:]
                        
                        # Async save to memory
                        def save_async():
                            try:
                                today_messages = memory_system.load_conversations()
                                today_messages.extend([user_msg, ai_msg])
                                memory_system.save_conversations(today_messages)
                            except Exception as e:
                                logger.error(f"Async memory save failed: {e}")
                        
                        threading.Thread(target=save_async, daemon=True).start()
                    
                    yield f"data: {json.dumps({'type': 'done', 'timestamp': timestamp})}\n\n"
            
        except APIError as e:
            logger.error(f"Streaming API Error: {e.message}")
            yield f"data: {json.dumps({'type': 'error', 'data': e.message})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'An unexpected error occurred'})}\n\n"
    
    return Response(stream_with_context(generate()), 
                   mimetype='text/event-stream',
                   headers={
                       'Cache-Control': 'no-cache',
                       'X-Accel-Buffering': 'no'
                   })


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
    tts_configured = minimax_tts_service._validate_api_key()
    
    return jsonify({
        'status': 'healthy',
        'api_key_configured': api_key_configured,
        'memory_dir_exists': memory_dir_exists,
        'model': Config.MODEL_NAME,
        'tts_configured': tts_configured
    })


@app.route('/api/tts', methods=['POST'])
def tts():
    """
    Generate TTS audio from text.
    
    Request JSON:
        {
            "text": "Text to convert to speech"
        }
        
    Returns:
        Audio file (MP3)
    """
    logger.info("TTS endpoint called!")
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'Text is required'}), 400
        
        text = data['text']
        
        # NOTE: Do NOT use sanitize_input() here — html.escape() corrupts text
        # (e.g. apostrophes become &#x27;) before it reaches the TTS engine.
        # Only strip and truncate.
        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 400
        
        text = text.strip()
        
        if not text:
            return jsonify({'error': 'Text cannot be empty'}), 400
        
        # Truncate to MiniMax's safe limit
        if len(text) > 1000:
            text = text[:1000]
        
        # Generate speech
        audio_data = minimax_tts_service.synthesize_speech(text)
        
        if not audio_data:
            return jsonify({'error': 'Failed to generate audio'}), 500
        
        # Analyze audio for lip sync frames (for browser-driven sync)
        lip_sync_frames = get_lip_sync_frames(audio_data)
        
        # Also fire-and-forget lip sync for backward compatibility
        # This will be overridden if browser takes control
        vts_lip_sync(audio_data)
        
        # Return audio file with lip sync data in header
        response = make_response(audio_data)
        response.headers['Content-Type'] = 'audio/mpeg'
        response.headers['Content-Disposition'] = 'inline; filename=speech.mp3'
        
        # Include lip sync frame data as JSON header
        # Format: [[timestamp, mouth_value], ...]
        if lip_sync_frames:
            import json
            # Encode frames as JSON and add to custom header
            # Use a compact JSON representation
            frames_json = json.dumps(lip_sync_frames, separators=(',', ':'))
            # Base64 encode to ensure header safety
            import base64
            frames_b64 = base64.b64encode(frames_json.encode()).decode()
            response.headers['X-LipSync-Frames'] = frames_b64
            response.headers['X-LipSync-Enabled'] = 'true'
        
        return response
        
    except APIError as e:
        logger.error(f"TTS APIError: {e.message} (status {e.status_code})")
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"TTS unexpected error: {e}")
        return jsonify({'error': f'Failed to generate audio: {str(e)}'}), 500


@app.route('/api/vts/mouth', methods=['POST'])
def set_vts_mouth():
    """
    Set the VTube Studio avatar mouth open value.
    Used by browser-driven lip sync for perfect audio synchronization.
    
    Request JSON:
        {
            "value": 0.5  // Mouth open value 0.0-1.0
        }
        
    Returns:
        {
            "success": true,
            "vts_connected": true
        }
    """
    try:
        data = request.get_json()
        
        if data is None or 'value' not in data:
            return jsonify({'error': 'Missing "value" field'}), 400
        
        value = float(data['value'])
        
        # Clamp value to valid range
        value = max(0.0, min(1.0, value))
        
        # Set mouth value in VTS
        success = vts_set_mouth(value)
        
        return jsonify({
            'success': success,
            'vts_connected': success
        })
        
    except (ValueError, TypeError) as e:
        return jsonify({'error': 'Invalid value - must be a number between 0 and 1'}), 400
    except Exception as e:
        logger.error(f"VTS mouth endpoint error: {e}")
        return jsonify({'error': str(e)}), 500


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
    logger.info(f"VTubeStudio: {'enabled' if Config.VTS_ENABLED else 'disabled'}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
