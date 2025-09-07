from __future__ import annotations
import os, json, hashlib, re
from typing import List, Dict, Any, Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from logging_config import logger
from cache import response_cache

# Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Optional: Pinecone flush buffer uses your embedder
from embeddings_provider import get_embedder

# ----------------------------- Model & Style -------------------------------

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")


try:
    import streamlit as st
except Exception:
    st = None

PUBLIC_NAME  = os.getenv("PUBLIC_NAME", "iota")
PRIVATE_NAME = os.getenv("PRIVATE_NAME")


def load_persona():
    raw = None
    # Streamlit Cloud secrets preferred
    if st and hasattr(st, "secrets") and "persona_json" in st.secrets:
        raw = st.secrets["persona_json"]
    # or from ENV
    elif os.getenv("PERSONA_JSON"):
        raw = os.getenv("PERSONA_JSON")

    if raw:
        try:
            return json.loads(raw)
        except Exception:
            # allow base64-encoded JSON if you ever choose to
            import base64
            try:
                return json.loads(base64.b64decode(raw).decode("utf-8"))
            except Exception:
                pass

    # Fallback default (public-safe)
    return {
        "name": PUBLIC_NAME,
        "rules": [
            "Keep replies short (1–3 sentences).",
            "Use Hinglish; 0–1 emoji only if it fits.",
            "Do not copy exemplar text verbatim.",
            "Be warm and practical; gentle tease is fine."
        ],
        "signatures": ["haan","arre","acha","okayss?","done na?"]
    }

GSP = load_persona()




def anonymize_text(s: str | None) -> str | None:
    if not s:
        return s
    # replace the private real name with the public alias, case-insensitive
    return re.sub(rf"\b{re.escape(PRIVATE_NAME)}\b", PUBLIC_NAME, s, flags=re.IGNORECASE)

DSES = {
    "hedges": ["haan", "arre", "acha", "ig"],
    "openers": ["Haan", "Okay", "Arre"],
    "closers": ["okayss?", "done na?"],
    "salient": ["don't change the topic haan", "try karna naa"],
}



# ----------------------------- Pinecone buffer -----------------------------

pending_pairs: List[Dict[str, str]] = []
BATCH_SIZE = 10
CLOSING_KEYWORDS = [
    "bye", "goodbye", "see you", "good night", "gn", "take care",
    "ok", "okay", "okk", "okies", "thik hai", "tik hai", "achha", "acha",
    "thanks", "thank you", "thx", "ok bye", "ok thanks"
]

def flush_buffer_to_pinecone(index):
    """Best-effort flush of buffered pairs to Pinecone; no changes to your schema."""
    global pending_pairs
    if not pending_pairs or index is None:
        pending_pairs = []
        return
    try:
        embeddings = get_embedder()
    except Exception as e:
        logger.warning(f"⚠️ Embeddings unavailable ({e}) - skipping Pinecone flush")
        pending_pairs = []
        return

    try:
        vectors = []
        for item in pending_pairs:
            context_text = f"passage: {item['context']}"  # keep E5 prefix
            embedding = embeddings.embed_query(context_text)
            vectors.append({
                "id": hashlib.md5(f"{item['context']}::{item['response']}".encode("utf-8")).hexdigest(),
                "values": embedding,
                "metadata": {"context": item["context"], "response": item["response"]}
            })

        # upsert in small batches
        for i in range(0, len(vectors), 50):
            batch = vectors[i:i+50]
            try:
                index.upsert(vectors=batch)
            except Exception as e:
                logger.warning(f"Upsert batch failed: {e}")
        logger.info(f"✅ Flushed {len(vectors)} pairs to Pinecone")
    except Exception as e:
        logger.warning(f"⚠️ Pinecone flush failed: {e}")
    finally:
        pending_pairs = []

# ----------------------------- Utils --------------------------------------

def _normalize_retrieved(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not items:
        return out
    for x in items:
        if isinstance(x, dict):
            out.append({
                "score": x.get("score"),
                "context": x.get("context"),
                "response": x.get("response"),
            })
        else:
            out.append({
                "score": getattr(x, "score", None),
                "context": getattr(x, "context", None),
                "response": getattr(x, "response", None),
            })
    return out

def _mini_context_signature(history: List[Dict[str, str]], exemplars: List[Dict[str, Any]]) -> str:
    """Stable, tiny signature of the chat tail + exemplar snippets."""
    last = (history or [])[-4:]
    hist_bits = [(m.get("role","?"), (m.get("content") or "")[:120]) for m in last]
    ex_bits = [((e.get("context") or "")[:80], (e.get("response") or "")[:80]) for e in (exemplars or [])[:3]]
    payload = json.dumps({"h": hist_bits, "r": ex_bits}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()

def _compose_prompt(user_turn: str, history: List[Dict[str, str]], exemplars: List[Dict[str, Any]]) -> str:
    hist_text = "\n".join([f"{m.get('role','user')}: {(m.get('content') or '').strip()}" for m in (history or [])[-4:]])
    ex_text = "\n".join([f"- ctx: {(e.get('context') or '')[:140]}\n  rsp: {(e.get('response') or '')[:140]}" for e in (exemplars or [])[:3]])
    # 👇 use .get(...) so a missing key can’t raise
    rules_line = ", ".join(GSP.get("rules", []))

    return (
        "You are mimicking Iota in Hinglish. Be concise and warm.\n"
        f"Persona: {GSP.get('name',PRIVATE_NAME)}\n"
        f"Rules: {rules_line}\n"
        f"Style hints (openers/closers/hedges): {', '.join(DSES['openers'])} | {', '.join(DSES['closers'])} | {', '.join(DSES['hedges'])}\n"
        "Do not copy exemplar text verbatim. 0–1 emoji only if it fits.\n\n"
        f"Chat tail:\n{hist_text}\n\n"
        f"Relevant past chat snippets (ctx→rsp):\n{ex_text}\n\n"
        f"User: {user_turn}\n"
        "Assistant:"
    )


_LLM = None
def get_llm(temp: float = 0.3):
    global _LLM
    if _LLM is None:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        _LLM = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=temp, google_api_key=key)
    return _LLM

# ----------------------------- Public API ----------------------------------

def respond_like_iota(user_turn: str,
                           history: List[Dict[str, str]],
                           retrieved_topk: List[Dict[str, Any]],
                           index=None) -> str:
    """Return the assistant reply string. Signature preserved for the UI."""
    global pending_pairs

    start_time = datetime.now()
    user_turn = (user_turn or "").strip()
    safe_history = history or []
    exemplars = _normalize_retrieved(retrieved_topk)
    print(exemplars)

    # Tiny context hash for the cache
    context_hash = _mini_context_signature(safe_history, exemplars)

    # Cache check
    cached = response_cache.get(user_turn, context_hash)
    if cached is not None:
        logger.info(f"Returning cached response in {(datetime.now() - start_time).total_seconds():.2f}s")
        return cached

    # Compose + generate (single LLM hop)
    prompt = _compose_prompt(user_turn, safe_history, exemplars)
    try:
        llm = get_llm(0.6)
        msg = llm.invoke([SystemMessage(content="You are a helpful AI."), HumanMessage(content=prompt)])
        final_reply = (getattr(msg, "content", None) or "").strip() or "Okay, bol na… 🙂"
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        final_reply = "Haan, samajh gaya. Kya hua?"

    # Cache store
    response_cache.set(user_turn, context_hash, final_reply)

    # Buffer for Pinecone (same behavior as before)
    try:
        pending_pairs.append({"context": user_turn, "response": final_reply})
        if len(pending_pairs) >= BATCH_SIZE:
            flush_buffer_to_pinecone(index)
        lowered = user_turn.lower()
        if any(w in lowered for w in CLOSING_KEYWORDS):
            flush_buffer_to_pinecone(index)
    except Exception as e:
        logger.warning(f"Buffering/flush skipped: {e}")

    logger.info(f"Generated new response in {(datetime.now() - start_time).total_seconds():.2f}s")
    return final_reply

# Optional CLI (unchanged usage)
if __name__ == "__main__":
    import argparse
    def _load_json_arg(maybe_json: Optional[str]) -> Any:
        if not maybe_json:
            return None
        try:
            if os.path.exists(maybe_json):
                with open(maybe_json, "r", encoding="utf-8") as f:
                    return json.load(f)
            return json.loads(maybe_json)
        except Exception as e:
            raise SystemExit(f"Failed to parse JSON argument: {e}")

    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--history", default="[]")
    ap.add_argument("--topk", default=None)
    args = ap.parse_args()

    history = _load_json_arg(args.history) or []
    topk = _load_json_arg(args.topk) or []
    print(respond_like_iota(args.user, history, topk))
