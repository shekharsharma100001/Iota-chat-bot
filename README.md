# 🤖 Iota-Chat-Bot

A chatbot that mimics your friend's chatting style using Google Gemini, semantic search using HuggingFace embeddings, and Pinecone vector database. It comes with
caching, logging, and a Streamlit web interface for easy interaction and
analytics.

✨ **Features**

-   **Style Mimicking:** Replicates natural Hinglish/Hindi-English
    casual chat style\
-   **Retrieval-Augmented Generation (RAG):** Finds the most relevant
    past responses using Pinecone\
-   **LLM Response Generation:** Uses Gemini for final response
    crafting\
-   **Response Caching:** Saves frequent answers to reduce API costs and
    latency\
-   **Logging:** Tracks performance, errors, and conversations\
-   **Streamlit Web Interface:** Chat + Analytics dashboard\
-   **Environment Configurable:** All keys managed via .env or Streamlit
    Cloud Secrets

------------------------------------------------------------------------

## 🚀 Quick Start

### 1. Clone and Install Dependencies

``` bash
git clone https://github.com/your-username/friend-chatbot.git
cd friend-chatbot
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file or set secrets in Streamlit Cloud:

    GOOGLE_API_KEY = your_gemini_api_key_here
    GEMINI_MODEL = gemini-2.5-pro  
    HF_API_KEY = your_huggingface_api_key_here
    HF_EMBED_MODEL = intfloat/multilingual-e5-large-instruct  
    PINECONE_API_KEY = your_pinecone_api_key_here
    PINECONE_INDEX_NAME = your_index_name_here

Optional persona fields:

    PUBLIC_NAME = Public name of your freind
    PRIVATE_NAME = Private name of your friend (Actual name)
    PERSONA_JSON={"voice":"casual","tone":"warm"} define it as per you need

### 3. Run the Web App

``` bash
streamlit run app.py
```

On Streamlit Cloud, just point to `app.py` as the entrypoint.

------------------------------------------------------------------------

## 🔧 How It Works

1.  **Input:** User enters a message\
2.  **Cache Check:** Looks for previous responses\
3.  **Vector Search:** Pinecone retrieves similar past chats\
4.  **Prompt Build:** Style + history + retrieved context\
5.  **LLM:** Gemini generates final response\
6.  **Cache/Store:** Logs conversation, caches reply, updates Pinecone

------------------------------------------------------------------------

## 📊 Pinecone Setup

1.  Create a Pinecone account → [pinecone.io](https://www.pinecone.io)\
2.  Create an index (matching your embedding dimension, default 1024)

``` python
from pinecone import Pinecone

pc = Pinecone(api_key="your_api_key")
pc.create_index("friend-chat", dimension=1024, metric="cosine")
```

The bot automatically stores:

``` json
{
  "context": "user message",
  "response": "friend's reply",
  "score": 0.87
}
```

------------------------------------------------------------------------

## 🧪 Testing

Single-message test from CLI:

``` bash
python workflow.py --user "kya kar rahi hai?" --history "[]"
```

Interactive chat via web interface:

``` bash
streamlit run app.py
```

------------------------------------------------------------------------

## 🌐 Web Interface

-   **Main Chat:** Real-time conversation view\
-   **Analytics Dashboard:** Trends, response stats, cache efficiency\
-   **Sidebar:** Clear session, manage cache, check API status

------------------------------------------------------------------------

## 📂 Project Structure

    ├── app.py                # Streamlit app entrypoint
    ├── workflow.py        # Core chat logic + Gemini wrapper
    ├── embeddings_provider.py # HuggingFace embeddings
    ├── retreival_topK.py     # Pinecone retrieval
    ├── cache.py              # Cache logic
    ├── cache_manager.py      # CLI cache tools
    ├── logging_config.py     # Centralized logging
    ├── requirements.txt      # Dependencies
    └── README.md             # Project docs

------------------------------------------------------------------------

## 🔍 Troubleshooting

-   **Missing responses?** → Check if Pinecone index exists and
    embedding dimension matches\
-   **API errors?** → Verify API keys in `.env` or Streamlit Secrets\
-   **Cache stale?** → Clear via sidebar or delete `cache/` directory\
-   **Deployment crash?** → Ensure `requirements.txt` matches provided
    updated version

------------------------------------------------------------------------

## 📈 Performance Tips

-   Adjust `TOP_K` retrieval in `retreival_topK.py`\
-   Monitor cache hit rate in sidebar analytics\
-   Use smaller/larger embedding model depending on budget/performance

------------------------------------------------------------------------

## 📝 License

Personal use only. Respect privacy---do not share personal conversation
