from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from core.database import get_users_collection
from core.oauth_service import oauth
import secrets
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login_ui')
def login_ui():
    return render_template('auth.html')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({"error": "Missing required fields"}), 400
        
    users = get_users_collection()
    
    if users.find_one({"$or": [{"username": username}, {"email": email}]}):
        return jsonify({"error": "User already exists"}), 409
        
    hashed_password = generate_password_hash(password)
    user_doc = {
        "username": username,
        "email": email,
        "password_hash": hashed_password
    }
    
    result = users.insert_one(user_doc)
    return jsonify({"message": "User registered successfully", "user_id": str(result.inserted_id)}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not all([email, password]):
        return jsonify({"error": "Missing email or password"}), 400
        
    users = get_users_collection()
    user = users.find_one({"email": email})
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid credentials"}), 401
        
    session['user_id'] = str(user['_id'])
    session['username'] = user['username']
    
    return jsonify({"message": "Logged in successfully", "username": user['username']}), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

# ==========================================
# Google OAuth Logic
# ==========================================
@auth_bp.route('/login/google')
def login_google():
    redirect_uri = url_for('auth.authorize_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/authorize')
def authorize_google():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return "Failed to fetch user info from Google", 400
        
    email = user_info.get('email')
    username = user_info.get('name') or email.split('@')[0]
    
    users = get_users_collection()
    user = users.find_one({"email": email})
    
    if not user:
        # Create a new user without a password hash
        user_doc = {
            "username": username,
            "email": email,
            "auth_provider": "google",
            "created_at": datetime.utcnow()
        }
        result = users.insert_one(user_doc)
        user_id = str(result.inserted_id)
    else:
        user_id = str(user['_id'])
        
    session['user_id'] = user_id
    session['username'] = username
    
    return redirect(url_for('chat.chat_ui'))

# ==========================================
# Password Reset Logic
# ==========================================
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')
        
    data = request.get_json() or request.form
    email = data.get('email')
    
    if not email:
        return jsonify({"error": "Email required"}), 400
        
    users = get_users_collection()
    user = users.find_one({"email": email})
    
    if user:
        # Generate token
        token = secrets.token_urlsafe(32)
        expiration = datetime.utcnow() + timedelta(hours=1)
        
        users.update_one(
            {"_id": user['_id']},
            {"$set": {"reset_token": token, "reset_expiration": expiration}}
        )
        
        # Mocking email delivery
        reset_link = url_for('auth.reset_password', token=token, _external=True)
        print("\n" + "="*50)
        print("MOCK EMAIL DELIVERY")
        print(f"To: {email}")
        print(f"Subject: Password Reset Request")
        print(f"Link: {reset_link}")
        print("="*50 + "\n")
        
    # Always return success to prevent email enumeration
    if request.is_json:
        return jsonify({"message": "If an account exists, a reset link has been printed to the console."}), 200
    else:
        # For form submissions
        return "If an account exists, a reset link has been printed to the console.", 200

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)
        
    data = request.get_json() or request.form
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({"error": "New password required"}), 400
        
    users = get_users_collection()
    user = users.find_one({
        "reset_token": token,
        "reset_expiration": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        return jsonify({"error": "Invalid or expired token"}), 400
        
    hashed_password = generate_password_hash(new_password)
    users.update_one(
        {"_id": user['_id']},
        {
            "$set": {"password_hash": hashed_password},
            "$unset": {"reset_token": "", "reset_expiration": ""}
        }
    )
    
    if request.is_json:
        return jsonify({"message": "Password updated successfully"}), 200
    else:
        return redirect(url_for('auth.login_ui'))
