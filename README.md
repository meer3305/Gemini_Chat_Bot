# Gemini Chat Bot

<!-- Badges -->
![GitHub stars](https://img.shields.io/github/stars/meer3305/Gemini_Chat_Bot?style=for-the-badge)
![GitHub forks](https://img.shields.io/github/forks/meer3305/Gemini_Chat_Bot?style=for-the-badge)
![License](https://img.shields.io/github/license/meer3305/Gemini_Chat_Bot?style=for-the-badge)

## Overview

**Gemini Chat Bot** is a full-stack AI chatbot powered by Google’s Gemini models. It allows users to interact in natural language via a responsive UI, sending prompts and receiving real-time AI responses.


### Features

- Conversational AI with Gemini integration
- Persistent chat history
- Clean and responsive frontend UI
- Backend API for processing prompts

### Tech Stack

| Component | Tech |
|-----------|------|
| Frontend  | React / HTML / CSS |
| Backend   | Python / FastAPI  |
| AI Model  | Gemini API |

---

## 🚀 Installation

### Clone

```bash
git clone https://github.com/meer3305/Gemini_Chat_Bot.git
cd Gemini_Chat_Bot

Backend Setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your_api_key_here"
python app.py

Frontend Setup
cd frontend
npm install
npm start
