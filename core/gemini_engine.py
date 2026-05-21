import os
import time
import google.generativeai as genai
from flask import current_app

def init_gemini(app):
    api_key = app.config.get('GOOGLE_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
    else:
        app.logger.warning("GOOGLE_API_KEY is not set. Gemini API will fail.")

# Latest embedding model — 8192 token context, native Hinglish/multilingual support
EMBEDDING_MODEL = "models/gemini-embedding-2"

def generate_embedding(text: str, is_document: bool = True) -> list[float]:
    """
    Generate vector embeddings using the latest Gemini embedding model.
    task_type is 'retrieval_document' for saving documents,
    and 'retrieval_query' for live queries.
    Includes automatic retries with exponential backoff on 429 rate limit errors.
    """
    task_type = "retrieval_document" if is_document else "retrieval_query"
    max_retries = 5
    backoff = 2.0
    
    for attempt in range(max_retries):
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                sleep_time = backoff ** attempt + 1.0
                print(f"Rate limit hit in generate_embedding. Retrying in {sleep_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_time)
            else:
                raise e
                
    raise Exception("Failed to generate embedding after max retries due to 429 quota exhaustion.")

def generate_embeddings_batch(texts: list[str], is_document: bool = True) -> list[list[float]]:
    """
    Generate vector embeddings in batch (up to 20 items per request) to stay within 30K TPM rate limits.
    Includes automatic retries with exponential backoff on 429 rate limit errors.
    """
    if not texts:
        return []
        
    task_type = "retrieval_document" if is_document else "retrieval_query"
    batch_size = 20
    all_embeddings = []
    
    # Process in chunks of 20 to stay within 30K TPM (Tokens Per Minute) limit
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i+batch_size]
        
        max_retries = 5
        backoff = 2.0
        success = False
        
        for attempt in range(max_retries):
            try:
                result = genai.embed_content(
                    model=EMBEDDING_MODEL,
                    content=chunk,
                    task_type=task_type
                )
                all_embeddings.extend(result['embedding'])
                success = True
                break
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                    sleep_time = backoff ** attempt + 3.0
                    print(f"Rate limit hit in generate_embeddings_batch. Retrying in {sleep_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    raise e
                    
        if not success:
            raise Exception("Failed to generate batch embeddings after max retries due to 429 quota exhaustion.")
            
        # Add a 7-second sleep between batches to stay under the 30,000 TPM limit
        if i + batch_size < len(texts):
            print(f"Processed batch {i//batch_size + 1}/{len(texts)//batch_size + 1}. Sleeping 7s to prevent TPM rate limits...")
            time.sleep(7.0)
            
    return all_embeddings

def generate_global_persona_profile(pairs: list, target_persona: str) -> str:
    """
    Analyze actual conversation pairs of the target persona to extract their global writing style profile:
    capitalization, emoji usage, average length, Hinglish/English ratio, punctuation, and tone quirks.
    """
    if not pairs:
        return ""
        
    # Sample up to 60 responses to represent the persona
    responses_sample = [p['response'] for p in pairs[:60]]
    sample_text = "\n".join([f"- {r}" for r in responses_sample])
    
    prompt = (
        f"You are an expert sociolinguist. Analyze the following actual text messages sent by '{target_persona}':\n\n"
        f"{sample_text}\n\n"
        f"Identify the exact stylistic DNA of '{target_persona}' and write a concise, bulleted personality & writing style guide (max 150 words) detailing:\n"
        f"- Sentence structure & length (e.g., short, single-word, multi-line, fragmented)\n"
        f"- Capitalization style (e.g., strict lowercase, standard, chaotic)\n"
        f"- Punctuation style (e.g., omits full stops, uses trailing spaces, multiple question marks)\n"
        f"- Emoji usage (e.g., extremely rare/never, specific emojis only, frequent)\n"
        f"- Vocabulary quirks & language (e.g., Hinglish slang, abbreviations like 'clg', 'bhai', code words)\n"
        f"- Core tone (e.g., casual, direct, dry, enthusiastic)\n\n"
        f"Output ONLY the bulleted style guide. Do not add any introductory or concluding conversational text."
    )
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Failed to generate global persona profile: {e}")
        return f"Mimic the vocabulary and casual tone of {target_persona}."

def generate_chat_response(user_message: str, db_history: list[dict], pinecone_context: list[dict], target_persona: str = None, manual_config: dict = None, global_persona_prompt: str = None) -> str:
    """
    Generate a live response using Gemini 1.5 Flash.
    Uses Dual-Context Processing: DB history + Pinecone semantic matches.
    If manual_config is provided, builds a strict character prompt.
    Otherwise, if target_persona is provided, instructs the AI to mimic that specific persona from history.
    """
    GENERATION_MODEL = 'gemini-2.5-flash'
    
    model = genai.GenerativeModel(GENERATION_MODEL)
    
    # Construct System Prompt Context
    system_prompt = ""
    if manual_config:
        system_prompt += f"You are playing the role of a persona named '{target_persona}'.\n"
        system_prompt += f"- Gender: {manual_config.get('gender')}\n"
        system_prompt += f"- Language: {manual_config.get('language')}\n"
        system_prompt += f"- Relationship to User: {manual_config.get('relationship')}\n"
        system_prompt += f"- Personality Traits: {', '.join(manual_config.get('traits', []))}\n"
        system_prompt += f"- Communication Tone: {manual_config.get('tone')}\n"
        system_prompt += f"- Response Length: {manual_config.get('length')}\n"
        system_prompt += f"- Emoji Usage: {manual_config.get('emoji')}\n"
        system_prompt += f"- Expertise Areas: {', '.join(manual_config.get('expertise', []))}\n\n"
        
        examples = manual_config.get('examples', [])
        if examples:
            system_prompt += "### Example Conversations (Use these to shape your tone):\n"
            for ex in examples:
                system_prompt += f"User: {ex.get('user')}\nYou: {ex.get('ai')}\n"
            system_prompt += "\n"
            
        system_prompt += f"Your absolute priority is to perfectly mimic this persona based on the rules and examples above. Never break character. Respond exactly as {target_persona} would.\n\n"
        
    elif target_persona:
        system_prompt = f"You are an AI clone of {target_persona}. Your absolute priority is to perfectly mimic {target_persona}'s chatting style, tone, quirks, and vocabulary based on the provided semantic memories. Respond exactly as {target_persona} would.\n\n"
        if global_persona_prompt:
            system_prompt += f"### Writing Style DNA & Guidelines for {target_persona} (STRICTLY ADHERE TO THESE RULES):\n{global_persona_prompt}\n\n"
        else:
            system_prompt += (
                "### Writing Style Guidelines:\n"
                "- Do NOT use emojis unless they are explicitly present in the provided matches. If matches do not use emojis, you must never use them.\n"
                "- Mimic the exact capitalization (e.g. lowercase), sentence length (short and direct), and vocabulary/slang (Hinglish/English blend) of the matches.\n\n"
            )
    else:
        system_prompt = "You are an intelligent, conversational AI assistant.\n\n"
    
    # 1. Inject Semantic Context from Pinecone
    if pinecone_context:
        system_prompt += "### Relevant Past Information (Semantic Matches):\n"
        for idx, ctx in enumerate(pinecone_context):
            system_prompt += f"Match {idx+1}:\nContext: {ctx.get('context', '')}\nResponse: {ctx.get('response', '')}\n\n"
            
    # 2. Inject Recent Live History
    if db_history:
        system_prompt += "### Recent Conversation History:\n"
        for msg in db_history:
            speaker = msg.get("speaker", "unknown").capitalize()
            content = msg.get("message", "")
            system_prompt += f"{speaker}: {content}\n"
    
    # Create the final messages array for Gemini
    # Gemini generativeai SDK uses content arrays or a single combined prompt
    prompt = f"{system_prompt}\nUser: {user_message}\nAI:"
    
    response = model.generate_content(prompt)
    return response.text
