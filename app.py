import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # OCR Configuration
    app.config['TESSERACT_CMD'] = os.environ.get('TESSERACT_CMD', '/usr/bin/tesseract')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    # FHIR Configuration
    app.config['FHIR_BASE_URL'] = os.environ.get('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
    app.config['FHIR_CLIENT_ID'] = os.environ.get('FHIR_CLIENT_ID', 'demo_client')
    app.config['FHIR_CLIENT_SECRET'] = os.environ.get('FHIR_CLIENT_SECRET', 'demo_secret')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    with app.app_context():
        # Import models to ensure they are registered
        import models
        
        # Create all database tables
        db.create_all()
        
        # Initialize default data
        from config.settings import initialize_default_data
        initialize_default_data()
    
    # Register blueprints
    from routes import register_blueprints
    register_blueprints(app)
    
    return app

# Create app instance
app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
