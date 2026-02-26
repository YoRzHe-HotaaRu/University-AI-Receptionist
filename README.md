# 🎓 University AI Receptionist

An AI-powered virtual receptionist for universities, built with Flask and integrated with OpenRouter's LLM API. Features a modern split-panel interface with quick access buttons and intelligent conversation memory.

![University AI Receptionist](https://img.shields.io/badge/Flask-2.3+-black?style=flat&logo=flask)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat&logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **Smart Chat Interface**: Split-panel layout with quick access buttons on the left, chat on the right
- **Quick Access Buttons**: Pre-configured buttons for common queries (Admissions, Tuition, Programs, etc.)
- **Date-Based Memory**: Conversations are stored in organized date folders for easy retrieval
- **LLM Integration**: Powered by OpenRouter API with Qwen model
- **Responsive Design**: Works on desktop and mobile devices
- **Modern UI**: Clean university-themed design with teal accents
- **Industry Standards**: Secure coding practices, input validation, error handling

## 📁 Project Structure

```
AI_Receptionist/
├── app.py                    # Flask server with API endpoints
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── README.md                # This file
├── memory/                   # Conversation memory (auto-created)
│   └── YYYY-MM-DD/
│       └── conversations.json
├── static/
│   ├── css/
│   │   └── style.css        # Stylesheet
│   └── js/
│       └── main.js          # Frontend JavaScript
└── templates/
    └── index.html           # HTML template
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- OpenRouter API key

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
| `MODEL_NAME` | No | `qwen/qwen3.5-flash-02-23` | LLM model to use |
| `FLASK_DEBUG` | No | `False` | Enable debug mode |
| `PORT` | No | `5000` | Server port |
| `SECRET_KEY` | No | Random | Flask secret key |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max characters per message |
| `MAX_MESSAGES_CONTEXT` | No | `10` | Messages to keep in context |

### Getting an OpenRouter API Key

1. Go to [OpenRouter.ai](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Add credits to your account (required for API calls)

## 💬 Usage

### Quick Access Buttons

Click any button on the left panel to send a pre-configured question:
- **Admissions** - Information about application process
- **Tuition** - Fees and financial aid details
- **Programs** - Available courses and degrees
- **Schedule** - Academic calendar information
- **Location** - Campus directions
- **Contact** - Department contact details
- **Hours** - Operating hours
- **FAQ** - Frequently asked questions

### Custom Messages

Type your own question in the chat input and press Enter or click Send.

### Memory System

The system automatically saves conversations by date:
```
memory/
├── 2026-02-26/
│   └── conversations.json
├── 2026-02-25/
│   └── conversations.json
└── ...
```

You can ask questions like:
- "What did we discuss yesterday?"
- "What happened on February 20th?"

## 🔐 Security Considerations

- API keys are stored server-side only (never exposed to client)
- Input validation and sanitization implemented
- CORS configured for trusted origins
- Rate limiting on API endpoints
- Error messages don't leak internal details

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

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/chat` | POST | Send a chat message |
| `/api/memory` | GET | Get conversation history |
| `/api/reset` | POST | Reset conversation |
| `/api/health` | GET | Health check |

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

