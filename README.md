# 🎓 AI Receptionist

An AI-powered virtual receptionist for University, built with Flask and integrated with OpenRouter's LLM API. Features a modern split-panel interface with quick access buttons, intelligent conversation memory, streaming AI responses with reasoning display, and Text-to-Speech (TTS) with voice cloning support.

![AI Receptionist](https://img.shields.io/badge/Flask-2.3+-black?style=flat&logo=flask)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat&logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **Smart Chat Interface**: Split-panel layout with quick access buttons on the left, chat on the right
- **Quick Access Buttons**: Pre-configured buttons for common queries (Admissions, Tuition, Programs, etc.)
- **RAG Knowledge Base**: Retrieval-augmented generation from local markdown files — AI answers are grounded in real university data
- **Streaming Responses**: Real-time AI response streaming with live reasoning/thinking display
- **AI Reasoning Display**: Expandable "Lihat fikiran AI" panel shows the model's thinking process
- **Date-Based Memory**: Conversations are stored in organized date folders for easy retrieval
- **LLM Integration**: Powered by OpenRouter API with MiniMax M2.5 model
- **Text-to-Speech (TTS)**: Auto-play voice output using MiniMax TTS API with voice cloning support
- **TTS Toggle**: Global toggle button in chat header — "Suara: Hidup / Mati" (Voice: On / Off)
- **Bahasa Malaysia**: AI responds in Malay language for local users
- **Markdown Rendering**: Rich formatting support including tables, lists, bold, italic, links
- **Responsive Design**: Works on desktop and mobile devices
- **Premium UI**: Modern shadcn/ui-inspired design with teal accents
- **Industry Standards**: Secure coding practices, input validation, error handling, rate limiting

## 📁 Project Structure

```
AI_Receptionist/
├── app.py                    # Flask server with API endpoints
├── rag.py                    # RAG knowledge retrieval engine
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── .env                     # Your local config (gitignored)
├── README.md                 # This file
├── knowledge/                # RAG knowledge base (markdown files)
│   ├── programs.md          # Courses, faculties, degrees
│   ├── admissions.md        # Requirements, application process
│   ├── fees.md              # Tuition, scholarships, payment
│   ├── campus.md            # Locations, facilities
│   ├── hours.md             # Operating hours
│   ├── links.md             # Official URLs, contacts
│   └── faq.md               # Frequently asked questions
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
| `MODEL_NAME` | No | `minimax/minimax-m2.5` | LLM model to use via OpenRouter |
| `FLASK_DEBUG` | No | `False` | Enable debug mode |
| `PORT` | No | `5000` | Server port |
| `SECRET_KEY` | No | Random | Flask secret key |
| `MAX_MESSAGE_LENGTH` | No | `1000` | Max characters per message |
| `MAX_MESSAGES_CONTEXT` | No | `10` | Messages to keep in context |
| `RATE_LIMIT` | No | `30` | Requests per minute per IP |
| `MINIMAX_API_KEY` | No | - | MiniMax API key for TTS |
| `MINIMAX_TTS_MODEL` | No | `speech-2.8-turbo` | TTS model |
| `MINIMAX_TTS_VOICE_ID` | No | (cloned voice) | Voice ID for TTS (see Voice Cloning) |
| `MINIMAX_TTS_LANGUAGE` | No | `ms` | TTS language (ms = Malay) |

### Getting an OpenRouter API Key

1. Go to [OpenRouter.ai](https://openrouter.ai/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Add credits to your account (required for API calls)

### Getting a MiniMax API Key (Optional — for TTS)

1. Go to [MiniMax Platform](https://platform.minimax.io)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Add credits to your account (required for TTS calls)

## 🎙️ Voice Cloning (TTS)

The app supports cloned voices via MiniMax. To use your own custom voice:

1. Go to the [MiniMax Platform](https://platform.minimax.io) **Voice Clone** section
2. Upload a **10–30 second** audio sample (MP3/WAV, clean speech, no background noise)
3. Copy the generated voice ID (format: `moss_audio_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
4. Set it in your `.env`:
   ```env
   MINIMAX_TTS_VOICE_ID=moss_audio_your-voice-id-here
   ```

### TTS Voice Settings

The following settings are configured in `app.py` under the `synthesize_speech()` method:

| Setting | Current Value | Description |
|---------|---------------|-------------|
| `speed` | `1.3` | Playback speed (0.5 – 2.0) |
| `vol` | `1.0` | Volume (0.1 – 10.0) |
| `pitch` | `0` | Pitch adjustment (-12 to 12) |
| `language_boost` | `Malay` | Language optimization |

## 📚 Knowledge Base (RAG)

The AI uses a lightweight Retrieval-Augmented Generation (RAG) system to ground its answers in real university data.

### How It Works

1. Markdown files in `knowledge/` are split into chunks by `##` headers
2. When a user asks a question, the most relevant chunks are retrieved using keyword + fuzzy matching
3. Retrieved chunks are injected into the AI's system prompt as context
4. Greetings and casual messages skip retrieval (relevance threshold)

### Knowledge Files

| File | Content |
|------|---------|
| `programs.md` | Faculties, courses, diplomas, degrees |
| `admissions.md` | Requirements, application dates, UPU process |
| `fees.md` | Tuition fees, scholarships, PTPTN, payment methods |
| `campus.md` | Campus locations, facilities, branches |
| `hours.md` | Operating hours for offices, library, sports |
| `links.md` | Official URLs, social media, contact info |
| `faq.md` | General frequently asked questions |

### Adding / Editing Knowledge

Simply edit the `.md` files in `knowledge/`. The system **auto-detects file changes** and reloads — no server restart needed.

Use `##` headers to create searchable subtopics:
```markdown
## Yuran Diploma
- Anggaran yuran: RM 1,000 - RM 3,000 setahun
- Yuran pendaftaran: RM 200 - RM 500
```

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

- Click the speaker toggle button in the chat header to enable/disable auto-voice
- When enabled, AI responses will be spoken aloud automatically after streaming completes
- Labels show **"Suara: Hidup"** (Voice: On) or **"Suara: Mati"** (Voice: Off)
- The toggle pulses while audio is loading/playing
- Click again to stop playback immediately

### AI Reasoning Display

- The app uses a reasoning-capable model (MiniMax M2.5) that shows its thinking process
- During streaming, reasoning appears in a compact scrollable box (120px max height)
- After the response completes, reasoning collapses to a **"Lihat fikiran AI"** toggle
- Click the toggle to expand/collapse the reasoning

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
- Security headers (X-Content-Type-Options, X-Frame-Options, CSP with `media-src blob:`)

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

### Model Throttled (503)
```
Too many requests. Your requests are being throttled due to system capacity limits.
```
**Solution**: This is a provider-side capacity issue, not your rate limit. Wait 30–60 seconds and try again, or switch to a different model in `.env`.

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/chat` | POST | Send a chat message (non-streaming) |
| `/api/chat/stream` | POST | Send a chat message (streaming with reasoning) |
| `/api/memory` | GET | Get conversation history |
| `/api/reset` | POST | Reset conversation |
| `/api/health` | GET | Health check |
| `/api/tts` | POST | Generate TTS audio (returns MP3) |

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
