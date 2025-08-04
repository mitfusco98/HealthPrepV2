
"""
HealthPrep Medical Screening System
Main Flask application entry point
"""
import logging
import os
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///healthprep.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    from app import db, login_manager
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Import models to ensure they're registered
    from models import User, Patient, Screening, ScreeningType, Document
    
    # Create tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created successfully")
    
    # Initialize routes
    from routes import init_routes
    init_routes(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    logger.info("Starting HealthPrep Medical Screening System")
    app.run(host='0.0.0.0', port=5000, debug=True)
