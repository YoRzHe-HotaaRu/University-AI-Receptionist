# AI University Receptionist - Project Context

## Project Overview

This is a **Flask-based AI chatbot** application that serves as a university receptionist. It uses OpenRouter's LLM API (specifically `qwen/qwen3.5-flash-02-23`) to answer questions about a university.

## Current Tech Stack

- **Backend**: Flask (Python) with Flask-CORS
- **Frontend**: Plain HTML, CSS, JavaScript (no framework)
- **LLM API**: OpenRouter API with Qwen model
- **Dependencies**: Flask, Flask-CORS, requests, python-dotenv

## Project Structure

```
AI_Receptionist/
├── app.py                 # Flask server with all API routes
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── .env                  # Local environment (not committed)
├── .gitignore           # Git ignore rules
├── README.md            # User-facing documentation
├── static/
│   ├── css/style.css   # All styling (premium UI)
│   └── js/main.js      # Frontend JavaScript
├── templates/
│   └── index.html      # Main HTML page
├── memory/              # Conversation storage (auto-created)
│   └── YYYY-MM-DD/
│       └── conversations.json
└── context/            # This documentation
```

## Key Features

### 1. Split-Panel UI
- Left sidebar: 8 quick-access buttons (Admissions, Tuition, Programs, Schedule, Location, Contact, Hours, FAQ)
- Right panel: Chat interface with message history

### 2. Quick Access Buttons
Each button sends a predefined prompt to the LLM:
- Admissions → "Tell me about the admissions process and requirements"
- Tuition → "What are the tuition fees and financial aid options?"
- Programs → "What programs and courses do you offer?"
- Schedule → "What is the academic calendar and class schedule?"
- Location → "Where is the university located and how do I get there?"
- Contact → "How can I contact the university and various departments?"
- Hours → "What are the university operating hours?"
- FAQ → "What are frequently asked questions?"

### 3. Memory System
- Conversations stored in `memory/YYYY-MM-DD/conversations.json`
- Loads recent conversations (up to 10 messages) for context
- Allows questions like "what happened yesterday?"

### 4. Markdown Rendering
Custom JavaScript parser supports:
- **Bold** (`**text**`), *italic* (`*text*`)
- Lists (`- item`)
- Tables (markdown table syntax)
- Code blocks (```code```)
- Links (`[text](url)`)
- Headers (`#`, `##`, `###`)

### 5. Color Theme
University-style dark theme:
- Primary Background: `#222831` (Dark charcoal)
- Secondary Background: `#393E46` (Gray)
- Accent: `#00ADB5` (Teal)
- Text: `#EEEEEE` (Off-white)

### 6. SVG Icons
Inline SVG icons throughout (no external icon library needed):
- Each quick-access button has a unique colored icon
- Chat messages use avatar icons
- Send button has gradient effect

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve main page |
| `/api/chat` | POST | Send message to LLM |
| `/api/memory` | GET | Get conversation history |
| `/api/reset` | POST | Reset conversation |
| `/api/health` | GET | Health check |

## Configuration (.env)

Required:
- `OPENROUTER_API_KEY` - OpenRouter API key

Optional:
- `MODEL_NAME` - Default: `qwen/qwen3.5-flash-02-23`
- `FLASK_DEBUG` - Default: `False`
- `PORT` - Default: `5000`
- `CORS_ORIGINS` - Default: localhost
- `MAX_MESSAGE_LENGTH` - Default: `1000`
- `MAX_MESSAGES_CONTEXT` - Default: `10`

## Security Features

- Server-side API key (never exposed to client)
- Input sanitization (HTML escaping, prompt injection prevention)
- Rate limiting (30 requests/minute per IP)
- CORS restricted to localhost
- Security headers (X-Content-Type-Options, X-Frame-Options, CSP)
- Path traversal prevention in memory system

## Running the Project

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure .env
copy .env.example .env
# Edit .env with your OPENROUTER_API_KEY

# Run
python app.py
```

Access at: http://localhost:5000

## Customization

### Adding More Quick Access Buttons

1. In `templates/index.html`, add a button:
```html
<button class="quick-btn" data-prompt="Your prompt here">
    <span class="btn-icon">
        <!-- SVG icon -->
    </span>
    <span class="btn-label">Button Name</span>
</button>
```

2. In `static/css/style.css`, add a color for the new button:
```css
.quick-btn:nth-child(9) .btn-icon svg { color: #YOUR_COLOR; }
```

### Modifying the System Prompt

In `app.py`, find the `SYSTEM_PROMPT` constant and modify it.

### Styling

All styles are in `static/css/style.css`. It uses CSS custom properties (variables) for theming.

## Important Notes

- The `.env` file contains the API key and should NEVER be committed
- Memory folders are created automatically when conversations happen
- The JavaScript includes a custom markdown parser (no external dependencies)
- SVG icons are inline (no CDN required)
- All security features are implemented server-side

## For Future Development

When working on this project with another LLM:

1. Start by reading this file to understand the architecture
2. Check `app.py` for backend logic
3. Check `templates/index.html` and `static/css/style.css` for frontend
4. The memory system is in `MemorySystem` class in `app.py`
5. The markdown parser is in `parseMarkdown()` function in `static/js/main.js`
