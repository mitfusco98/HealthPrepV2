import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__)

    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Import models and routes
    with app.app_context():
        import models
        db.create_all()
        logging.info("Database tables created successfully")

    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.main_routes import main_bp
    from routes.patient_routes import patient_bp
    from routes.screening_routes import screening_bp
    from ui.routes import ui_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin') 
    app.register_blueprint(main_bp)
    app.register_blueprint(patient_bp, url_prefix='/patients')
    app.register_blueprint(screening_bp, url_prefix='/screenings')
    app.register_blueprint(ui_bp)

    # Add a simple index route
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('ui.dashboard'))
        else:
            return redirect(url_for('auth.login'))

    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return render_template('error/400.html'), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return render_template('error/401.html'), 401

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('error/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error/500.html'), 500

    # Initialize security
    from config.security import init_security, security_manager
    init_security(app)

    # Add CSRF token to template context
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=security_manager.generate_csrf_token)

    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    return app

# Create the app instance
app = create_app()