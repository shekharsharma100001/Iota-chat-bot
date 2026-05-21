from flask import Flask, redirect, url_for, session, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config_by_name

# Import core initializations
from core.database import init_db
from core.gemini_engine import init_gemini
from core.pinecone_db import init_pinecone
from core.oauth_service import init_oauth

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.admin import admin_bp
from blueprints.chat import chat_bp

def create_app(config_name='default'):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(config_by_name[config_name])

    # Initialize Core Services
    init_db(app)
    init_gemini(app)
    init_pinecone(app)
    init_oauth(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('chat.chat_ui'))
        return render_template('landing.html')
        
    return app

if __name__ == '__main__':
    import os
    app = create_app('development')
    
    if os.name == 'nt':
        # Windows: Use Waitress to prevent WinError 10038 sockets crashing
        from waitress import serve
        print("Starting Waitress production server on http://127.0.0.1:5000")
        serve(app, host='127.0.0.1', port=5000)
    else:
        # Mac/Linux local fallback (Render will use Gunicorn directly via start command)
        app.run(debug=True, port=5000)
