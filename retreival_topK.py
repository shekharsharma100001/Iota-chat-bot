import json
import os
from pinecone import Pinecone
from embeddings_provider import get_embedder



# Pinecone setup - Get from environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# Initialize variables
pc = None
index = None

def connect_pinecone():
    """Connect to Pinecone if credentials are available"""
    global pc, index
    
    if not PINECONE_API_KEY or not INDEX_NAME:
        print("⚠️ Pinecone credentials not set - using mock data")
        return None
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(INDEX_NAME)
        print("✅ Pinecone index connected")
        return index
    except Exception as e:
        print(f"❌ Failed to connect to Pinecone: {e}")
        return None


class RetrievedDoc:
    """Represents a retrieved document with its ID, score, context, and response."""

    def __init__(self, id, score, context, response):
        self.id = id
        self.score = score
        self.context = context
        self.response = response

    def __repr__(self):
        return (f"RetrievedDoc(id='{self.id}', score={self.score:.4f}, "
                f"context='{self.context}', response='{self.response}')")


# in retreival_topK.py, replace embed_query() body
def embed_query(text: str):
    """Embed a query with proper E5-instruct prefix, with retries."""
    try:
        embeddings = get_embedder()
        payload = f"query: {text}"
        last_err = None
        for attempt in range(2):
            try:
                return embeddings.embed_query(payload)
            except Exception as e:
                last_err = e
                import time
                time.sleep(0.35 * (2 ** attempt))  # ~0.35s, 0.7s
                
        raise last_err
    except Exception as e:
        print(f"⚠️ Embedding failed after retries: {e} - using mock embedding")
        import random
        random.seed(hash(text) % 2**32)
        return [random.uniform(-0.1, 0.1) for _ in range(1024)]




def retrieve_topk(query_text, index, k=5, min_score=None):
    """Retrieve top-K documents for a query"""
    if index is None:
        # Return mock data if Pinecone is not available
        print("⚠️ Pinecone not available - returning mock data")
        return [
            RetrievedDoc("mock-1", 0.85, "print ho gaya?", "Haan, ho gaya. Spiral binding hi karwani hai na? ✨"),
            RetrievedDoc("mock-2", 0.80, "paise kitne hue?", "Don't change the topic haan 😏  kal ice-cream done?"),
            RetrievedDoc("mock-3", 0.75, "mood down hai", "Same scene yaar… par try karte rehna, ho jayega 🥹")
        ]
    
    try:
        query_embedding = embed_query(query_text)
        search_results = index.query(vector=query_embedding, top_k=k, include_metadata=True)

        retrieved_docs = []
        for match in search_results.matches:
            if min_score is None or match.score >= min_score:
                retrieved_docs.append(
                    RetrievedDoc(
                        id=match.id,
                        score=match.score,
                        context=match.metadata.get("context"),
                        response=match.metadata.get("response")
                    )
                )
        print(f"✅ Retrieved {len(retrieved_docs)} documents from Pinecone")
        return retrieved_docs
    except Exception as e:
        print(f"⚠️ Pinecone query failed: {e} - returning mock data")
        return [
            RetrievedDoc("mock-1", 0.85, "print ho gaya?", "Haan, ho gaya. Spiral binding hi karwani hai na? ✨"),
            RetrievedDoc("mock-2", 0.80, "paise kitne hue?", "Don't change the topic haan 😏  kal ice-cream done?")
        ]


