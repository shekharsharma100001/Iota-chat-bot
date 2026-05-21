import os
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from core.database import get_users_collection, get_chat_history_collection
from core.pinecone_db import purge_namespace
from bson.objectid import ObjectId

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def is_admin():
    return session.get('is_admin') is True

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if is_admin():
        return redirect(url_for('admin.dashboard'))
        
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Load from env or fallback to defaults
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@iota.com')
        admin_password = os.getenv('ADMIN_PASSWORD', 'adminpassword123')
        
        if email == admin_email and password == admin_password:
            session['is_admin'] = True
            # Set basic user details so they can preview/test chat app components if desired
            session['user_id'] = 'admin_user_id'
            session['username'] = 'Admin'
            return redirect(url_for('admin.dashboard'))
        else:
            error = "Invalid admin credentials"
            
    return render_template('admin_login.html', error=error)

@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    # Also pop user session elements if they were set by admin
    if session.get('user_id') == 'admin_user_id':
        session.pop('user_id', None)
        session.pop('username', None)
    return redirect(url_for('auth.login_ui'))

@admin_bp.route('/')
def dashboard():
    if not is_admin():
        return redirect(url_for('admin.login'))
    return render_template('admin.html')

@admin_bp.route('/users', methods=['GET'])
def list_users():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    users = get_users_collection()
    user_list = []
    for u in users.find():
        user_list.append({
            "id": str(u['_id']),
            "username": u['username'],
            "email": u['email']
        })
    return jsonify(user_list), 200

@admin_bp.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """
    Delete user from MongoDB and execute a wholesale purge against their Pinecone namespace.
    """
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        # 1. Delete from MongoDB
        users = get_users_collection()
        users.delete_one({"_id": ObjectId(user_id)})
        
        chat_history = get_chat_history_collection()
        chat_history.delete_many({"user_id": user_id})
        
        # 2. Purge from Pinecone (using default clone_id for now)
        try:
            purge_namespace(user_id=user_id, clone_id="default")
        except Exception as e:
            return jsonify({"warning": "User deleted from SQL, but Pinecone purge failed", "details": str(e)}), 200
            
        return jsonify({"message": f"User {user_id} and all associated data purged successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
