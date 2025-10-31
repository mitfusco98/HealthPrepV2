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
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress health check logs from Sentry monitoring
class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        # Filter out Sentry health check requests to /api and /api/
        if ('HEAD /api HTTP/1.1' in message or 
            'HEAD /api/ HTTP/1.1' in message):
            return False
        return True

# Apply filter to werkzeug logger to suppress health check spam
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(HealthCheckFilter())

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

    # Add proxy fix for proper URL generation behind reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Validate all required secrets on startup
    from utils.secrets_validator import validate_secrets_on_startup, SecretsValidationError
    
    try:
        # Determine environment from FLASK_ENV or default to development
        environment = os.environ.get('FLASK_ENV', 'development')
        validate_secrets_on_startup(environment)
    except SecretsValidationError as e:
        logger.error(f"Secrets validation failed: {e}")
        raise
    
    # Configuration - SECRET_KEY validated above
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

    # Database configuration with fallback
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/healthprep.db')

    # If using PostgreSQL, try to connect, but fallback to SQLite if it fails
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        try:
            # Test if we can resolve the hostname
            from urllib.parse import urlparse
            import socket
            parsed = urlparse(database_url)
            if parsed.hostname:
                socket.gethostbyname(parsed.hostname)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            print(f"Using PostgreSQL database: {parsed.hostname}")
        except Exception as e:
            print(f"PostgreSQL connection failed ({e}), falling back to SQLite")
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/healthprep.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }

    # Configure security headers and HTTPS enforcement
    from utils.security_headers import configure_security_middleware
    
    # Enable HTTPS enforcement in production only
    is_production = os.environ.get('FLASK_ENV') == 'production'
    configure_security_middleware(app, force_https=is_production)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore
    login_manager.login_message = 'Please log in to access this page.'
    csrf.init_app(app)
    configure_csrf_exemptions(app)
    migrate.init_app(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        try:
            user = User.query.get(int(user_id))
            if user and user.is_active_user:
                # Update last activity
                user.update_activity()
                db.session.commit()
                return user
            return None
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {e}")
            return None

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import flash, redirect, url_for, request
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    @app.before_request
    def check_user_role_redirect():
        from flask_login import current_user
        from flask import request, redirect, url_for

        # Skip for static files, auth routes, signup routes, password reset, and API routes
        if (request.endpoint and
            (request.endpoint.startswith('static') or
             request.endpoint.startswith('auth.') or
             request.endpoint.startswith('signup.') or
             request.endpoint.startswith('first_login.') or
             request.endpoint.startswith('password_reset.') or
             request.endpoint.startswith('api.'))):
            return

        # If user is authenticated, check first login requirements
        if current_user.is_authenticated:
            current_endpoint = request.endpoint
            
            # Force password change for users with temporary passwords
            if current_user.is_temp_password:
                if current_endpoint != 'first_login.change_password':
                    return redirect(url_for('first_login.change_password'))
            
            # Force security question setup if not completed (skip for root admins)
            elif not current_user.is_root_admin and (not current_user.security_answer_1_hash or not current_user.security_answer_2_hash):
                if current_endpoint != 'first_login.setup_security_questions':
                    return redirect(url_for('first_login.setup_security_questions'))

            # Root admin trying to access regular admin dashboard (but not root admin dashboard)
            if (current_user.is_root_admin_user() and
                current_endpoint and current_endpoint.startswith('admin.') and
                not current_endpoint.startswith('root_admin.')):
                return redirect(url_for('root_admin.dashboard'))

            # Regular admin trying to access root admin dashboard
            elif (current_user.is_admin_user() and not current_user.is_root_admin_user() and
                  current_endpoint and current_endpoint.startswith('root_admin.')):
                return redirect(url_for('admin.dashboard'))

            # Regular user trying to access admin areas
            elif (not current_user.is_admin_user() and not current_user.is_root_admin_user() and
                  current_endpoint and (current_endpoint.startswith('admin.') or current_endpoint.startswith('root_admin.'))):
                return redirect(url_for('ui.dashboard'))

    # Register blueprints
    register_blueprints(app)

    # Add static file serving for JWKS fallbacks
    from flask import send_from_directory
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """Serve static files including JWKS fallbacks"""
        return send_from_directory('static', filename)

    # Register error handlers
    register_error_handlers(app)

    # Template filters and context processors
    register_template_utilities(app)
    configure_jinja_filters(app)

    # Create tables
    with app.app_context():
        import models  # Import after app context
        db.create_all()
        logger.info("Database tables created successfully")
        
        # Process any existing unmatched documents on startup (disabled by default for performance)
        # Enable with environment variable: STARTUP_PROCESS_DOCS=true
        # Document processing should be triggered by EMR sync or screening list refresh instead
        if os.environ.get('STARTUP_PROCESS_DOCS', 'false').lower() == 'true':
            try:
                from core.engine import ScreeningEngine
                from models import Document, ScreeningDocumentMatch
                
                # Check if there are unmatched documents with OCR text
                unmatched_docs = db.session.query(Document).filter(
                    Document.ocr_text.isnot(None),
                    ~Document.id.in_(db.session.query(ScreeningDocumentMatch.document_id))
                ).all()
                
                if unmatched_docs:
                    logger.info(f"Processing {len(unmatched_docs)} unmatched documents on startup")
                    engine = ScreeningEngine()
                    
                    processed_count = 0
                    for doc in unmatched_docs:
                        try:
                            engine.process_new_document(doc.id)
                            processed_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to process document {doc.id} on startup: {str(e)}")
                    
                    logger.info(f"Startup document processing completed: {processed_count}/{len(unmatched_docs)} documents processed")
                else:
                    logger.info("No unmatched documents found on startup")
            
            except Exception as e:
                logger.warning(f"Startup document processing failed: {str(e)}")
                # Don't fail startup if document processing fails
        else:
            logger.info("Startup document processing disabled for faster boot times (set STARTUP_PROCESS_DOCS=true to enable)")

    # Root route
    @app.route('/')
    def index():
        from flask_login import current_user
        from flask import session

        if current_user.is_authenticated:
            # Clear any cached redirect to ensure proper role-based routing
            session.pop('_flashes', None)

            # Redirect based on user role with explicit priority
            if current_user.is_root_admin_user():
                return redirect(url_for('root_admin.dashboard'))
            elif current_user.is_admin_user():
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('ui.dashboard'))
        else:
            return redirect(url_for('auth.login'))

    return app

def register_blueprints(app):
    """Register all blueprints"""
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.root_admin_routes import root_admin_bp
    from routes.screening_routes import screening_bp
    from routes.prep_sheet_routes import prep_sheet_bp
    from routes.api_routes import api_bp
    from routes.emr_sync_routes import emr_sync_bp
    from routes.fuzzy_detection_routes import fuzzy_bp
    from routes.fhir_routes import fhir_bp
    from routes.oauth_routes import oauth_bp
    from routes.smart_auth import smart_auth_bp
    from routes.epic_admin_routes import epic_admin_bp
    from routes.epic_registration_routes import epic_registration_bp
    from routes.epic_public_routes import epic_public_bp
    from routes.phi_test_routes import phi_test_bp
    from routes.signup_routes import signup_bp
    from routes.first_login_routes import first_login_bp
    from routes.password_reset_routes import password_reset_bp
    from routes.org_approval_routes import org_approval_bp
    from routes.webhook_routes import webhook_bp
    from ui.routes import ui_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(signup_bp)  # Public signup at /signup
    app.register_blueprint(first_login_bp)  # First login flow at /first-login
    app.register_blueprint(password_reset_bp)  # Password reset at /forgot-password
    app.register_blueprint(org_approval_bp)  # Organization approval routes
    app.register_blueprint(webhook_bp)  # Webhook handlers at /webhooks
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(root_admin_bp, url_prefix='/root-admin')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep-sheet')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(emr_sync_bp, url_prefix='/emr')
    app.register_blueprint(fuzzy_bp, url_prefix='/fuzzy')
    app.register_blueprint(fhir_bp, url_prefix='/fhir')
    app.register_blueprint(oauth_bp, url_prefix='/oauth')
    app.register_blueprint(smart_auth_bp)  # SMART on FHIR auth routes with /smart prefix
    app.register_blueprint(epic_admin_bp)  # Epic admin routes with /admin/epic prefix
    app.register_blueprint(epic_registration_bp)
    app.register_blueprint(epic_public_bp)  # Epic registration routes
    app.register_blueprint(phi_test_bp)    # PHI testing routes with /admin/dashboard/phi prefix
    app.register_blueprint(ui_bp)

    # Exempt all API routes from CSRF
    csrf.exempt(api_bp)
    csrf.exempt(emr_sync_bp)  # Exempt EMR webhooks from CSRF
    csrf.exempt(fuzzy_bp)  # Exempt fuzzy detection API from CSRF
    csrf.exempt(smart_auth_bp)  # Exempt SMART auth from CSRF for OAuth callbacks
    csrf.exempt(webhook_bp)  # Exempt Stripe webhooks from CSRF

    # Configure additional CSRF exemptions
    configure_csrf_exemptions(app)

    # Configure custom Jinja2 filters
    configure_jinja_filters(app)

def register_error_handlers(app):
    """Register error handlers"""
    from flask import render_template
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
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=lambda: generate_csrf())
    
    @app.context_processor
    def inject_subscription_status():
        """Inject subscription status into all templates"""
        from middleware.subscription_check import get_subscription_context
        return get_subscription_context()

# Configure CSRF protection to exempt API routes
def configure_csrf_exemptions(app):
    """Configure CSRF exemptions for API routes"""
    # CSRF exemptions are handled at blueprint level in register_blueprints()
    # This function is kept for compatibility but exemptions are done via csrf.exempt()
    pass

def configure_jinja_filters(app):
    """Configure custom Jinja2 filters"""
    try:
        from markupsafe import Markup
    except ImportError:
        try:
            from jinja2 import Markup  # type: ignore
        except ImportError:
            # Fallback for older versions
            def Markup(object):
                return str(object)
    import json

    @app.template_filter('tojsonpretty')
    def tojsonpretty_filter(value):
        """Converts a Python object to a pretty-printed JSON string"""
        if not value:
            return ""
        try:
            # Use json.dumps for pretty printing and escape HTML characters
            pretty_json = json.dumps(value, indent=2, sort_keys=True)
            return Markup(f'<pre>{pretty_json}</pre>')
        except Exception as e:
            logger.error(f"Error formatting JSON for log data: {e}")
            return Markup(f'<pre>Error formatting data: {e}</pre>')