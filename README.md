# 🧠 Iota, IdentityClone: Multi-Tenant Generative AI Behavioral Replication Platform

Iota is a production-ready SaaS platform that lets you create and chat with highly customized AI personas. You can clone a real person's conversational style from a WhatsApp chat export, or design a fully custom AI character from scratch using a 7-step interactive wizard. All powered by **Google Gemini 2.5 Flash** and a hybrid **MongoDB + Pinecone** memory architecture.

---

## ✨ Features

- **🤖 WhatsApp Clone Pipeline** — Upload a `.txt` chat export. Iota automatically strips timestamps, filters system noise (`<Media omitted>`, deleted messages), extracts the target persona's messages, and trains the AI using Pinecone vector embeddings.
- **🧙 7-Step Manual Persona Wizard** — Design a custom AI character by configuring Identity, Relationship, Personality Traits, Communication Style, Expertise, and providing example conversations.
- **📚 Hybrid Long-Term Memory** — MongoDB stores short-term context (last 10 messages). Pinecone stores semantic vector embeddings for infinite long-term memory recall via RAG.
- **🔀 Dynamic Persona Switching** — Switch between multiple clones and personas instantly from the sidebar. Each persona maintains its own isolated conversation history.
- **💾 Persistent Chat History** — All conversations are stored in MongoDB and automatically hydrated on page load or persona switch.
- **🔐 Dual Authentication** — Supports Google OAuth (one-click login) and traditional Email/Password login via Authlib.
- **🚀 Production-Ready** — Runs on Waitress (Windows) locally and Gunicorn (Linux) on Render for zero-crash concurrent serving.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Flask (Python), Blueprints architecture |
| **AI Generation** | Google Gemini `gemini-2.5-flash` |
| **AI Embeddings** | Google `models/gemini-embedding-2` |
| **Long-Term Memory** | Pinecone (Vector DB) |
| **Short-Term Memory + Personas** | MongoDB Atlas |
| **File Storage** | Supabase Storage |
| **Auth** | Authlib (Google OAuth + Email/Password) |
| **Frontend** | HTML5, Tailwind CSS, Vanilla JavaScript |
| **Production Server** | Waitress (Windows) / Gunicorn (Linux/Render) |

---

## 🚀 Quick Start

### 1. Clone and Set Up Environment

```bash
git clone https://github.com/shekharsharma100001/Iota-chat-bot.git
cd Iota-chat-bot-main
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Flask
SECRET_KEY=your-super-secret-key-here

# Google Gemini
GOOGLE_API_KEY=your_gemini_api_key_here

# MongoDB Atlas
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/
MONGO_DB_NAME=echo_mind

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=your_index_name_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key_here

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

### 3. Run Locally

```bash
python app.py
```

On **Windows**, this automatically starts the **Waitress** production server at `http://127.0.0.1:5000`. No more socket crashes.

---

## ☁️ Deploying to Render

1. Push your code to GitHub.
2. Create a new **Web Service** on [render.com](https://render.com).
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: *(leave blank — Render reads the `Procfile` automatically)*
5. Add all your `.env` variables as **Environment Variables** in the Render dashboard.
6. Deploy. Render uses `Gunicorn` with 4 workers for production-grade stability.

---

## 🔧 How It Works

### WhatsApp Clone Pipeline
1. **Upload:** User uploads a `.txt` WhatsApp export.
2. **Parse & Clean:** `core/parser.py` strips iOS/Android timestamps, removes `<Media omitted>`, deleted messages, and missed call notices.
3. **Speaker Detection:** Extracts all unique speaker names and presents them to the user.
4. **Targeted Extraction:** User selects a target persona (e.g., "Sarah"). Only Sarah's messages (and their conversational context) are kept.
5. **Vectorize:** Context-response pairs are embedded using `gemini-embedding-2` and stored in Pinecone under a unique `clone_id`.
6. **Chat:** At runtime, user messages are semantically matched against Pinecone to retrieve the most relevant past exchanges, which are injected into the Gemini system prompt.

### Manual Persona Pipeline
1. **7-Step Wizard:** User configures Name, Gender, Language, Relationship Type, up to 3 Personality Traits, Communication Style (Tone/Length/Emojis), up to 5 Expertise areas, and provides example conversations.
2. **Save:** The full configuration is saved as a document in MongoDB's `clones` collection.
3. **Inject:** At runtime, all traits are dynamically assembled into a strict character system prompt before every Gemini API call.
4. **Memory:** Live conversations are continuously vectorized into Pinecone via a background thread (every 10 messages), giving the manual persona long-term memory.

---

## 📂 Project Structure

```
├── app.py                    # Flask app factory + Waitress/Gunicorn entry
├── config.py                 # Dev/Production configuration classes
├── Procfile                  # Render/Gunicorn deployment command
├── requirements.txt          # All Python dependencies
├── .env                      # Local secrets (never commit this)
│
├── blueprints/
│   ├── auth.py               # Login, Register, Google OAuth, Password Reset
│   ├── admin.py              # Admin dashboard
│   └── chat.py               # All chat, clone, and persona API routes
│
├── core/
│   ├── gemini_engine.py      # Gemini generation + embedding logic
│   ├── pinecone_db.py        # Pinecone upsert and search helpers
│   ├── parser.py             # WhatsApp chat log parser + cleaner
│   ├── database.py           # MongoDB connection + collection helpers
│   └── oauth_service.py      # Authlib OAuth client setup
│
├── templates/
│   ├── chat.html             # Main chat UI + 7-step persona wizard
│   ├── auth.html             # Login / Register page
│   ├── admin.html            # Admin dashboard
│   ├── forgot_password.html  # Password reset request
│   └── reset_password.html   # Password reset form
│
└── static/
    └── js/
        └── chat.js           # Full frontend state machine (wizard, sidebar, history)
```

---

## 🔍 Troubleshooting

| Problem | Fix |
|---|---|
| `WinError 10038` on Windows | Use `python app.py` — it now runs Waitress automatically, eliminating this error. |
| Pinecone dimension mismatch | `gemini-embedding-2` outputs **3072-dimensional** vectors. Ensure your Pinecone index is created with `dimension=3072`. |
| Google OAuth redirect error | Add `http://127.0.0.1:5000/auth/google/callback` to your Google Cloud Console authorized redirect URIs. |
| Render deployment crash | Ensure all `.env` variables are set as Render Environment Variables. The `Procfile` handles the rest. |

---

## 📝 License

Personal use only. Respect privacy — do not share personal conversation data.
