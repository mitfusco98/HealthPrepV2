"""
HealthPrep Medical Screening System
Clean Flask application factory
"""
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from datetime import datetime
import os
import logging
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    # Database configuration - Use SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///healthprep.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    csrf.init_app(app)
    migrate.init_app(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Template filters and context processors
    register_template_utilities(app)

    # Create tables
    with app.app_context():
        import models  # Import after app context
        db.create_all()
        logger.info("Database tables created successfully")

    # Root route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('ui.dashboard'))
        else:
            return redirect(url_for('auth.login'))

    return app

def register_blueprints(app):
    """Register all blueprints"""
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.screening_routes import screening_bp
    from routes.prep_sheet_routes import prep_sheet_bp
    from routes.api_routes import api_bp
    from ui.routes import ui_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep-sheet')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ui_bp)

def register_error_handlers(app):
    """Register error handlers"""
    @app.errorhandler(400)
    def bad_request(error):
        from flask import render_template
        return render_template('error/400.html'), 400

    @app.errorhandler(401)
    def unauthorized(error):
        from flask import render_template
        return render_template('error/401.html'), 401

    @app.errorhandler(403)
    def forbidden(error):
        from flask import render_template
        return render_template('error/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('error/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('error/500.html'), 500

def register_template_utilities(app):
    """Register template filters and context processors"""
    @app.template_filter('datetime')
    def datetime_filter(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        return value.strftime(format)

    @app.context_processor
    def inject_cache_timestamp():
        import time
        return dict(cache_timestamp=int(time.time()))

    @app.context_processor
    def inject_csrf_token():
        from secrets import token_urlsafe
        return dict(csrf_token=lambda: token_urlsafe(32))