import os
import logging
from datetime import datetime

from flask import Flask, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///health_prep.db")
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
login_manager.login_message_category = 'info'

# Import models and routes after app initialization
with app.app_context():
    import models
    from routes.auth_routes import auth_bp
    from routes.screening_routes import screening_bp
    from routes.admin_routes import admin_bp
    from routes.prep_sheet_routes import prep_sheet_bp
    from routes.document_routes import document_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep')
    app.register_blueprint(document_bp, url_prefix='/documents')
    
    # Create all database tables
    db.create_all()
    
    # Create default admin user if it doesn't exist
    if not models.User.query.filter_by(username='admin').first():
        from werkzeug.security import generate_password_hash
        admin_user = models.User(
            username='admin',
            email='admin@healthprep.com',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
        logging.info("Created default admin user (username: admin, password: admin123)")

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

# Template context processors
@app.context_processor
def inject_template_vars():
    return {
        'cache_timestamp': int(datetime.now().timestamp()),
        'current_year': datetime.now().year
    }

# Main route
@app.route('/')
def index():
    return render_template('screening/screening_list.html')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
