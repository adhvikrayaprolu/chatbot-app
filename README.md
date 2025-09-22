# Chatbot App

This is a lightweight web-based chatbot interface built with **Flask** on the backend and **vanilla HTML/CSS/JS** on the frontend. The bot integrates with OpenAI's GPT models to respond to user prompts with contextual memory and markdown-formatted replies. The UI supports multiple chat sessions with persistent conversation history stored in `localStorage`.

---

## Features

- GPT-backed chatbot responses via OpenAI API
- Persistent multi-conversation support (locally stored in browser)
- Clean and responsive UI using only HTML, CSS, and JavaScript
- Chat history scroll, title renaming, markdown rendering, and message roles
- Easily extendable to support document input, history sync, PDF ingestion, etc.

---

## Project Structure

```text
ai_chatbot/
│
├── app.py # Flask server to route frontend/backend logic
├── gpt_handler.py # Handles all communication with OpenAI and stores conversation history
├── templates/
│ └── index.html # Main UI – single-page chat interface
├── notebooks/ # functions to build practice
└── README.md # You are here :)
```

---

## Setup Instructions

1. **Clone the repo**

```bash
git clone https://github.com/adhvikrayaprolu/chatbot-app.git
cd chatbot-app
```

2. **Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install openai flask
```

4. **Add your OpenAI API key**
Update gpt_handler.py with your own OpenAI key:

```bash
api_key = "your-openai-api-key"
```

5. **Run the app**
python app.py

```bash
python app.py
Then open http://localhost:5000 in your browser.
```

