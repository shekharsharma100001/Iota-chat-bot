# embeddings_provider.py
from functools import lru_cache
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpointEmbeddings

# Load environment variables
load_dotenv()

HF_MODEL = os.getenv("HF_EMBED_MODEL", "intfloat/multilingual-e5-large-instruct")

@lru_cache(maxsize=1)
def get_embedder():
    token = os.getenv("HF_API_KEY")
    if not token:
        raise RuntimeError("HF_API_KEY not set")

    # LangChain wrapper that exposes .embed_query()
    return HuggingFaceEndpointEmbeddings(
        model=HF_MODEL,
        huggingfacehub_api_token=token,
        task="feature-extraction",
    )
