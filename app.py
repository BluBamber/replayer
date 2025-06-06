#!/usr/bin/env python3
"""
ROBLOX Game Replay System - Flask Application
Deploy this to Render.com as a Web Service
"""

import os
from flask import Flask
from flask_cors import CORS
from routes import api, views
from database import init_db

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(views)
    
    return app

if __name__ == '__main__':
    # Initialize database on startup
    print("Starting ROBLOX Replay System...")
    init_db()
    
    # Create Flask app
    app = create_app()
    
    # Get port from environment (Render uses PORT env var)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
