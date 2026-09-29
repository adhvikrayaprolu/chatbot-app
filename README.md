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
└── README.md # 
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

---

## Backend Logic (app.py + gpt_handler.py)

### app.py

- Serves the main frontend (index.html)
- Defines /chat route:
  - Accepts POST requests with user messages
  - Calls GPT via gpt_handler.py
  - Returns chatbot's reply as JSON

### gpt_handler.py

- Manages the OpenAI client
- Maintains conversation_history list with roles (user, assistant)
- Sends messages to GPT and handles responses
- Includes example logic to format specialized queries (e.g. football-related queries return structured output)

## Frontend (templates/index.html)

- Sidebar for conversation switching and creation
- Main panel for chat history
- JS functions:
  - sendMessage(): Sends messages to backend
  - appendMessage(): Displays messages in DOM
  - newConversation(), renderConversationList(): Handle conversation storage and switching
  - renderConversationList() – shows saved chats from localStorage
- Conversations are stored via localStorage
- Markdown support via marked.js
- Designed to be responsive and minimal

## notebooks/ Folder – Experiments & Learning Playground

This folder contains Jupyter-style Python scripts to test GPT logic before integration into the main app.

### chatbot_intro.ipynb

- Simple one-off prompt responses using getLLMResponse() and getLLMResponseNew() functions.
- Optionally stores previous conversation history for coherent replies.

### chatbot_conversation_history.ipynb

- Console-based infinite chat loop
- Maintains full conversation history with GPT (like a terminal chatbot)
- Illustrates role-based interactions using OpenAI's Python SDK

### chatbot_document_uploading.ipynb

- Use of Retrieval-Augmented Generation (RAG) using llama_index.
- Uploads PDFs/documents, creates vector embeddings, and allows question answering from them

## Engineering workflow

See [engineering setup, validation and known blockers](docs/engineering-control-plane.md) and [agent instructions](AGENTS.md). Canonical validation: `make check` after the documented dependency setup.
