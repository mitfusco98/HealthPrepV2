import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, session, g, redirect, url_for, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///healthprep.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

# Import models and routes after app initialization
with app.app_context():
    import models
    from ui.routes import ui_bp
    from admin.config import admin_bp
    
    # Register blueprints
    app.register_blueprint(ui_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Create all database tables
    db.create_all()
    
    # Create default admin user if it doesn't exist
    if not models.User.query.filter_by(username='admin').first():
        admin_user = models.User(
            username='admin',
            email='admin@healthprep.local',
            is_admin=True
        )
        admin_user.set_password('admin123')  # Default password - should be changed
        db.session.add(admin_user)
        db.session.commit()
        logging.info("Default admin user created: admin/admin123")

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

@app.before_request
def before_request():
    """Global request preprocessing"""
    g.start_time = datetime.utcnow()
    
    # Add cache timestamp for static files
    g.cache_timestamp = int(datetime.utcnow().timestamp())

@app.after_request
def after_request(response):
    """Global response postprocessing"""
    if hasattr(g, 'start_time'):
        duration = datetime.utcnow() - g.start_time
        logging.debug(f"Request {request.endpoint} took {duration.total_seconds():.3f}s")
    
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    return response

@app.context_processor
def inject_globals():
    """Inject global variables into templates"""
    return {
        'cache_timestamp': getattr(g, 'cache_timestamp', ''),
        'current_year': datetime.utcnow().year
    }

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
def page_not_found(error):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    return render_template('error/500.html'), 500

@app.route('/')
def index():
    """Redirect to appropriate dashboard based on user role"""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('ui.screening_list'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
