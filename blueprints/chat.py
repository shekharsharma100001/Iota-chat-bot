import os
import hashlib
import tempfile
import threading
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, current_app, redirect, url_for
from core.database import get_chat_history_collection, get_clones_collection, upload_file_to_supabase
from core.parser import parse_chat_log, get_unique_speakers
from core.gemini_engine import generate_embedding, generate_chat_response, generate_embeddings_batch, generate_global_persona_profile
from core.pinecone_db import upsert_vectors, search_vectors, purge_namespace

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
def chat_ui():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_ui'))
    return render_template('chat.html', is_admin=session.get('is_admin') is True)

@chat_bp.route('/upload_and_analyze', methods=['POST'])
def upload_and_analyze():
    """
    Step 1: Accept .txt logs, save to temp, and extract unique speakers.
    """
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if not file.filename.endswith('.txt'):
        return jsonify({"error": "Only .txt files are supported"}), 400

    content = file.read().decode('utf-8')
    
    # Save to temporary file with a consistent name tied to the user
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{user_id}_pending_upload.txt")
    
    with open(temp_path, 'w', encoding='utf-8') as temp_file:
        temp_file.write(content)
        
    # Get unique speakers
    speakers = get_unique_speakers(content)
    
    return jsonify({
        "message": "File analyzed successfully.",
        "speakers": speakers,
        "filename": file.filename
    }), 200

@chat_bp.route('/finalize_replica', methods=['POST'])
def finalize_replica():
    """
    Step 2: Read temp file, filter by target_persona, vectorise, upload to Supabase, create MongoDB clone.
    """
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.get_json()
    
    clone_name = data.get('clone_name')
    target_persona = data.get('target_persona')
    original_filename = data.get('filename', 'chat_log.txt')
    
    if not clone_name or not target_persona:
        return jsonify({"error": "Clone name and target persona are required"}), 400
        
    clones_col = get_clones_collection()
    if clones_col.find_one({"user_id": user_id, "name": clone_name}):
        return jsonify({"error": "A replica with this name already exists."}), 400

    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{user_id}_pending_upload.txt")
    
    if not os.path.exists(temp_path):
        return jsonify({"error": "No pending upload found. Please upload the file again."}), 400
        
    with open(temp_path, 'r', encoding='utf-8') as temp_file:
        content = temp_file.read()
        
    # 1. Parse log with target persona filtering
    pairs = parse_chat_log(content, target_persona=target_persona)
    
    if not pairs:
        os.remove(temp_path)
        return jsonify({"error": f"No responses found for {target_persona} in this chat log."}), 400
        
    # 2. Upload to Supabase
    try:
        destination = f"{user_id}/{clone_name}_{original_filename}"
        upload_file_to_supabase(temp_path, "chat_logs", destination)
    except Exception as e:
        current_app.logger.warning(f"Supabase upload failed: {e}")
        
    # Generate global persona style profile
    global_persona_prompt = ""
    try:
        global_persona_prompt = generate_global_persona_profile(pairs, target_persona=target_persona)
    except Exception as e:
        current_app.logger.warning(f"Global persona analysis failed: {e}")

    # 3. Create Clone in MongoDB
    clone_id = hashlib.md5(f"{user_id}_{clone_name}_{datetime.utcnow().isoformat()}".encode('utf-8')).hexdigest()
    clones_col.insert_one({
        "user_id": user_id,
        "clone_id": clone_id,
        "name": clone_name,
        "target_persona": target_persona,
        "global_persona_prompt": global_persona_prompt,
        "created_at": datetime.utcnow()
    })
    
    # 4. Generate vectors in batch (to stay under the 100 RPM quota) and upsert
    combined_texts = []
    metadata_list = []
    
    for pair in pairs:
        history  = pair.get('metadata_history', '')
        context  = pair['context']
        response = pair['response']
        
        combined_text = (
            f"[History]: {history}\n"
            f"[Context]: {context}\n"
            f"[Response]: {response}"
        )
        combined_texts.append(combined_text)
        metadata_list.append({
            "context":          context,
            "response":         response,
            "metadata_history": history
        })
        
    try:
        # Fetch all embeddings in a single batch call (chunks of 100 handled inside generate_embeddings_batch)
        embeddings = generate_embeddings_batch(combined_texts, is_document=True)
    except Exception as e:
        os.remove(temp_path)
        return jsonify({"error": f"Failed to generate embeddings: {str(e)}"}), 500
        
    vectors = []
    for idx, embedding in enumerate(embeddings):
        combined_text = combined_texts[idx]
        vector_id = hashlib.md5(combined_text.encode("utf-8")).hexdigest()
        
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata_list[idx]
        })
        
    if vectors:
        try:
            # Batch upsert in chunks of 50
            for i in range(0, len(vectors), 50):
                batch = vectors[i:i+50]
                upsert_vectors(user_id=user_id, clone_id=clone_id, vectors=batch)
        except Exception as e:
            # If pinecone fails, clean up temp file and return error
            os.remove(temp_path)
            return jsonify({"error": f"Pinecone upsert failed: {str(e)}"}), 500
            
    # Clean up temp file
    os.remove(temp_path)
    
    # Set this as the active clone in the session
    session['active_clone_id'] = clone_id
    session['active_clone_name'] = clone_name
    session['active_target_persona'] = target_persona
            
    return jsonify({
        "message": f"Successfully processed {len(pairs)} interactions for {target_persona}.",
        "clone_id": clone_id
    }), 200

def process_continuous_memory(user_id, clone_id):
    """
    Background thread worker: scans for 10+ unembedded messages,
    groups them into pairs (matching the sliding-window parser structure),
    generates vectors using models/gemini-embedding-2, and upserts to Pinecone.
    """
    try:
        chat_history_col = get_chat_history_collection()
        
        # 1. Fetch unembedded messages sorted by oldest first
        unembedded_cursor = chat_history_col.find({
            "user_id": user_id,
            "clone_id": clone_id,
            "embedded": False
        }).sort("timestamp", 1)
        
        unembedded_messages = list(unembedded_cursor)
        
        # 2. Check if we have hit the 10-message threshold
        if len(unembedded_messages) < 10:
            return
            
        clones_col = get_clones_collection()
        clone_record = clones_col.find_one({"clone_id": clone_id})
        target_persona = clone_record.get('target_persona', 'AI') if clone_record else 'AI'
            
        # 3. Create sliding-window Context-Response pairs
        vectors = []
        for i in range(len(unembedded_messages)):
            msg = unembedded_messages[i]
            
            # We pair when the AI (clone) responds
            if msg.get('speaker') == 'ai':
                # Did the user speak right before the AI?
                if i > 0 and unembedded_messages[i-1].get('speaker') == 'user':
                    user_msg = unembedded_messages[i-1]
                    
                    # Grab up to 2 preceding messages for history window context
                    history_window = []
                    for j in range(max(0, i-3), i-1):
                        h = unembedded_messages[j]
                        speaker_label = "User" if h.get('speaker') == 'user' else target_persona
                        history_window.append(f"{speaker_label}: {h['message']}")
                    
                    history = (
                        "\n".join(history_window)
                        if history_window
                        else "System: Cold Start / Initial Conversation Initialization"
                    )
                    
                    context = user_msg['message']
                    response = msg['message']
                    
                    # Exact format matching the WhatsApp parser
                    combined_text = (
                        f"[History]: {history}\n"
                        f"[Context]: {context}\n"
                        f"[Response]: {response}"
                    )
                    
                    try:
                        embedding = generate_embedding(combined_text, is_document=True)
                        vector_id = hashlib.md5(combined_text.encode("utf-8")).hexdigest()
                        
                        vectors.append({
                            "id": vector_id,
                            "values": embedding,
                            "metadata": {
                                "context":          context,
                                "response":         response,
                                "metadata_history": history
                            }
                        })
                    except Exception as e:
                        print(f"Background embedding failed for a pair: {e}")
                        
        # 4. Upsert to Pinecone
        if vectors:
            try:
                upsert_vectors(user_id=user_id, clone_id=clone_id, vectors=vectors)
            except Exception as e:
                print(f"Background Pinecone upsert failed: {e}")
                return # Don't mark as embedded if upsert failed
                
        # 5. Mark messages as embedded
        msg_ids = [msg['_id'] for msg in unembedded_messages]
        chat_history_col.update_many(
            {"_id": {"$in": msg_ids}},
            {"$set": {"embedded": True}}
        )
        print(f"Successfully consolidated {len(vectors)} memories for user {user_id}")
        
    except Exception as e:
        print(f"Continuous memory thread failed: {e}")

@chat_bp.route('/send', methods=['POST'])
def send_message():
    """
    Live Generation Pipeline:
    1. Save user message to MongoDB.
    2. Pull last 5 rows of ChatHistory.
    3. Query Pinecone via semantic matching.
    4. Pass dual-context to Gemini Flash.
    5. Save response back to MongoDB.
    """
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.get_json()
    user_message = data.get('message')
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
        
    chat_history_col = get_chat_history_collection()
    
    active_clone_id = session.get('active_clone_id', 'default')
    
    # 1. Save User Message
    chat_history_col.insert_one({
        "user_id": user_id,
        "clone_id": active_clone_id,
        "speaker": "user",
        "message": user_message,
        "timestamp": datetime.utcnow(),
        "embedded": False
    })
    
    # 2. Pull last 10 rows for tight recent context (isolated by user and clone)
    recent_cursor = chat_history_col.find({"user_id": user_id, "clone_id": active_clone_id}).sort("timestamp", -1).limit(10)
    # Reverse to chronological order
    recent_history = list(recent_cursor)[::-1]
    # Remove _id for JSON serializability
    for h in recent_history:
        h.pop('_id', None)
        
    # 3. Query Pinecone
    try:
        query_embedding = generate_embedding(user_message, is_document=False)
        pinecone_context = search_vectors(user_id=user_id, clone_id=active_clone_id, query_embedding=query_embedding, top_k=3)
    except Exception as e:
        current_app.logger.warning(f"Pinecone search failed: {e}")
        pinecone_context = []
        
    # Check if this clone is manual to pass the config or if it has a global persona prompt
    clones_col = get_clones_collection()
    clone_record = clones_col.find_one({"clone_id": active_clone_id})
    manual_config = clone_record.get('config') if clone_record and clone_record.get('is_manual') else None
    global_persona_prompt = clone_record.get('global_persona_prompt') if clone_record else None
        
    # 4. Generate Response
    try:
        active_persona = session.get('active_target_persona')
        ai_response = generate_chat_response(
            user_message, 
            recent_history, 
            pinecone_context, 
            target_persona=active_persona, 
            manual_config=manual_config,
            global_persona_prompt=global_persona_prompt
        )
    except Exception as e:
        return jsonify({"error": f"Gemini generation failed: {str(e)}"}), 500
        
    # 5. Save AI Response
    chat_history_col.insert_one({
        "user_id": user_id,
        "clone_id": active_clone_id,
        "speaker": "ai",
        "message": ai_response,
        "timestamp": datetime.utcnow(),
        "embedded": False
    })
    
    # 6. Trigger Continuous Memory Consolidation Thread (Non-blocking)
    threading.Thread(target=process_continuous_memory, args=(user_id, active_clone_id), daemon=True).start()
    
    return jsonify({
        "message": ai_response,
        "sources_used": len(pinecone_context)
    }), 200

@chat_bp.route('/create_manual_persona', methods=['POST'])
def create_manual_persona():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.json
    
    name = data.get('name')
    if not name:
        return jsonify({"error": "Persona name is required"}), 400
        
    clone_id = str(uuid.uuid4())
    clones_col = get_clones_collection()
    
    clone_record = {
        "user_id": user_id,
        "clone_id": clone_id,
        "name": name,
        "target_persona": name, # We use the bot's name as the target persona
        "is_manual": True,
        "config": {
            "gender": data.get('gender'),
            "language": data.get('language'),
            "relationship": data.get('relationship'),
            "traits": data.get('traits', []),
            "tone": data.get('tone'),
            "length": data.get('length'),
            "emoji": data.get('emoji'),
            "expertise": data.get('expertise', []),
            "examples": data.get('examples', [])
        },
        "created_at": datetime.utcnow()
    }
    
    clones_col.insert_one(clone_record)
    
    # Set this manual clone as active
    session['active_clone_id'] = clone_id
    session['active_target_persona'] = name
    session['active_clone_is_manual'] = True
    
    return jsonify({
        "success": True,
        "clone_id": clone_id,
        "target_persona": name
    })

@chat_bp.route('/get_clones', methods=['GET'])
def get_clones():
    """Returns a list of all clones created by the current user."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    clones_col = get_clones_collection()
    
    cursor = clones_col.find({"user_id": user_id})
    
    clones = []
    for doc in cursor:
        clones.append({
            "clone_id": doc.get('clone_id'),
            "name": doc.get('name'),
            "target_persona": doc.get('target_persona'),
            "is_manual": doc.get('is_manual', False),
            "pinned": doc.get('pinned', False),
            "created_at": doc.get('created_at')
        })
        
    # Sort: newest first, then pinned first
    clones.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
    clones.sort(key=lambda x: x.get('pinned', False), reverse=True)
    
    # Format created_at for JSON serialization
    for c in clones:
        if c.get('created_at'):
            c['created_at'] = c['created_at'].isoformat()
            
    return jsonify({
        "clones": clones,
        "active_clone_id": session.get('active_clone_id')
    })

@chat_bp.route('/switch_clone', methods=['POST'])
def switch_clone():
    """Switches the active persona in the user's session."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.json
    clone_id = data.get('clone_id')
    
    if not clone_id:
        return jsonify({"error": "clone_id is required"}), 400
        
    clones_col = get_clones_collection()
    clone_record = clones_col.find_one({"clone_id": clone_id, "user_id": user_id})
    
    if not clone_record:
        return jsonify({"error": "Clone not found"}), 404
        
    session['active_clone_id'] = clone_id
    session['active_target_persona'] = clone_record.get('target_persona')
    session['active_clone_is_manual'] = clone_record.get('is_manual', False)
    
    return jsonify({
        "success": True,
        "clone_id": clone_id,
        "target_persona": clone_record.get('target_persona'),
        "is_manual": clone_record.get('is_manual', False)
    })

@chat_bp.route('/get_history', methods=['GET'])
def get_history():
    """Returns the last 50 messages for the active persona."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    active_clone_id = session.get('active_clone_id')
    
    if not active_clone_id:
        return jsonify({"history": []})
        
    chat_history_col = get_chat_history_collection()
    
    # Fetch last 50 messages
    cursor = chat_history_col.find(
        {"user_id": user_id, "clone_id": active_clone_id}
    ).sort("timestamp", -1).limit(50)
    
    # Reverse to chronological order
    history = list(cursor)[::-1]
    
    # Format for JSON
    formatted_history = []
    for msg in history:
        formatted_history.append({
            "speaker": msg.get("speaker"),
            "message": msg.get("message"),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None
        })
        
    return jsonify({"history": formatted_history})

@chat_bp.route('/delete_clone', methods=['POST'])
def delete_clone():
    """Deletes a clone from UI, MongoDB, and Pinecone."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.json
    clone_id = data.get('clone_id')
    
    if not clone_id:
        return jsonify({"error": "clone_id is required"}), 400
        
    clones_col = get_clones_collection()
    chat_history_col = get_chat_history_collection()
    
    # 1. Delete from MongoDB clones collection
    res = clones_col.delete_one({"clone_id": clone_id, "user_id": user_id})
    if res.deleted_count == 0:
        return jsonify({"error": "Clone not found"}), 404
        
    # 2. Delete chat history associated with this clone
    chat_history_col.delete_many({"clone_id": clone_id, "user_id": user_id})
    
    # 3. Purge from Pinecone namespace
    try:
        purge_namespace(user_id=user_id, clone_id=clone_id)
    except Exception as e:
        current_app.logger.error(f"Pinecone purge failed during clone deletion: {e}")
        
    # 4. If this clone was active, clear active clone session keys
    if session.get('active_clone_id') == clone_id:
        session.pop('active_clone_id', None)
        session.pop('active_clone_name', None)
        session.pop('active_target_persona', None)
        session.pop('active_clone_is_manual', None)
        
    return jsonify({"success": True})

@chat_bp.route('/rename_clone', methods=['POST'])
def rename_clone():
    """Renames a clone in MongoDB."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.json
    clone_id = data.get('clone_id')
    new_name = data.get('new_name')
    
    if not clone_id or not new_name:
        return jsonify({"error": "clone_id and new_name are required"}), 400
        
    clones_col = get_clones_collection()
    
    res = clones_col.update_one(
        {"clone_id": clone_id, "user_id": user_id},
        {"$set": {"name": new_name}}
    )
    
    if res.matched_count == 0:
        return jsonify({"error": "Clone not found"}), 404
        
    # If active in session, update session name
    if session.get('active_clone_id') == clone_id:
        session['active_clone_name'] = new_name
        
    return jsonify({"success": True})

@chat_bp.route('/pin_clone', methods=['POST'])
def pin_clone():
    """Pins or unpins a clone in MongoDB."""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    data = request.json
    clone_id = data.get('clone_id')
    pinned = data.get('pinned', False)
    
    if not clone_id:
        return jsonify({"error": "clone_id is required"}), 400
        
    clones_col = get_clones_collection()
    
    res = clones_col.update_one(
        {"clone_id": clone_id, "user_id": user_id},
        {"$set": {"pinned": pinned}}
    )
    
    if res.matched_count == 0:
        return jsonify({"error": "Clone not found"}), 404
        
    return jsonify({"success": True})
