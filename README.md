# 🎓 UiTM AI Receptionist

An AI-powered virtual receptionist for UiTM (Universiti Teknologi MARA), built with Flask and integrated with OpenRouter's LLM API. Features a modern split-panel interface with quick access buttons, intelligent conversation memory, and Text-to-Speech (TTS) capability.

![UiTM AI Receptionist](https://img.shields.io/badge/Flask-2.3+-black?style=flat&logo=flask)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat&logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **Smart Chat Interface**: Split-panel layout with quick access buttons on the left, chat on the right
- **Quick Access Buttons**: Pre-configured buttons for common queries (Admissions, Tuition, Programs, etc.)
- **Date-Based Memory**: Conversations are stored in organized date folders for easy retrieval
- **LLM Integration**: Powered by OpenRouter API with Qwen model
- **Text-to-Speech (TTS)**: Built-in voice output using MiniMax TTS API
- **Bahasa Malaysia**: AI responds in Malay language for local users
- **Responsive Design**: Works on desktop and mobile devices
- **Premium UI**: Modern shadcn/ui-inspired design with teal accents
- **Industry Standards**: Secure coding practices, input validation, error handling, rate limiting

## 📁 Project Structure

```
AI_Receptionist/
├── app.py                    # Flask server with API endpoints
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── README.md                 # This file
├── memory/                   # Conversation memory (auto-created)
│   └── YYYY-MM-DD/
│       └── conversations.json
├── static/
│   ├── css/
│   │   └── style.css        # Stylesheet (Premium UI)
│   └── js/
│       └── main.js          # Frontend JavaScript
└── templates/
    └── index.html           # HTML template
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- OpenRouter API key
- (Optional) MiniMax API key for TTS functionality

### Installation

1. **Clone or download this repository**

2. **Create a virtual environment (recommended)**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   # Copy the example file
   copy .env.example .env
   
   # Edit .env and add your OpenRouter API key
   # Get your key from: https://openrouter.ai/keys
   
   # (Optional) Add MiniMax API key for TTS
   # Get your key from: https://platform.minimax.io
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open in browser**
   Navigate to: `http://localhost:5000`

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | - | Your OpenRouter API key |
| `MODEL_NAME` | No | `qwen/qwen3.5-plus-02-15` | LLM model to use |
| `FLASK_DEBUG` | No | `False` | Enable debug mode |
| `PORT` | No | `5000` | Server port |
| `SECRET_KEY` | No | Random | Flask secret key |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max characters per message |
| `MAX_MESSAGES_CONTEXT` | No | `10` | Messages to keep in context |
| `RATE_LIMIT` | No | `30` | Requests per minute per IP |
| `MINIMAX_API_KEY` | No | - | MiniMax API key for TTS |
| `MINIMAX_TTS_MODEL` | No | `speech-2.6-turbo` | TTS model |
| `MINIMAX_TTS_VOICE_ID` | No | (varies) | Voice ID for TTS |
| `MINIMAX_TTS_LANGUAGE` | No | `ms` | TTS language (ms=Malay) |

### Getting an OpenRouter API Key

1. Go to [OpenRouter.ai](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Add credits to your account (required for API calls)

### Getting a MiniMax API Key (Optional - for TTS)

1. Go to [MiniMax Platform](https://platform.minimax.io)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Add credits to your account (required for TTS calls)

## 💬 Usage

### Quick Access Buttons

Click any button on the left panel to send a pre-configured question (in Malay):
- **Admissions** - Information about application process (Proses pengambilan)
- **Tuition** - Fees and financial aid details (Yuran tuisyen)
- **Programs** - Available courses and degrees (Program ditawarkan)
- **Schedule** - Academic calendar information (Kalendar akademik)
- **Location** - Campus directions (Lokasi universiti)
- **Contact** - Department contact details (Maklumat hubungan)
- **Hours** - Operating hours (Waktu operasi)
- **FAQ** - Frequently asked questions (Soalan lazim)

### Custom Messages

Type your own question in the chat input and press Enter or click Send.

### Text-to-Speech (TTS)

- Click the speaker icon in the chat header to enable/disable auto-voice
- When enabled, AI responses will be spoken aloud automatically
- Labels show "Suara: Hidup" (Voice: On) or "Suara: Mati" (Voice: Off)

### Memory System

The system automatically saves conversations by date:
```
memory/
├── 2026-02-28/
│   └── conversations.json
├── 2026-02-27/
│   └── conversations.json
└── ...
```

You can ask questions like:
- "Apa yang kita bincangkan semalam?" (What did we discuss yesterday?)
- "Apa yang berlaku pada 20 Februari?" (What happened on February 20th?)

## 🔐 Security Considerations

- API keys are stored server-side only (never exposed to client)
- Input validation and sanitization implemented
- CORS configured for trusted origins
- Rate limiting on API endpoints (30 requests/minute per IP)
- Error messages don't leak internal details
- Security headers (X-Content-Type-Options, X-Frame-Options, CSP)

## 🐛 Troubleshooting

### API Key Error
```
API key not configured. Please set OPENROUTER_API_KEY.
```
**Solution**: Add your OpenRouter API key to the `.env` file.

### Connection Refused
```
Failed to connect to API
```
**Solution**: Check your internet connection and verify the API key is valid.

### Port Already in Use
```
Port 5000 is already in use
```
**Solution**: Change the PORT in `.env` or stop the other application.

### TTS Not Working
```
TTS not configured. Please set MINIMAX_API_KEY.
```
**Solution**: Add your MiniMax API key to the `.env` file for Text-to-Speech functionality.

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/chat` | POST | Send a chat message |
| `/api/memory` | GET | Get conversation history |
| `/api/reset` | POST | Reset conversation |
| `/api/health` | GET | Health check |
| `/api/tts` | POST | Generate TTS audio |

## 🛠️ Development

### Running in Debug Mode
```bash
FLASK_DEBUG=True python app.py
```

### Using with Gunicorn (Production)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📄 License

MIT License - feel free to use this for your university or organization.

---

