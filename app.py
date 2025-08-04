import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# CSRF Protection
csrf = CSRFProtect(app)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    'pool_pre_ping': True,
    "pool_recycle": 300,
}

# Initialize extensions
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    import models  # noqa: F401
    db.create_all()
    logging.info("Database tables created")

# Import routes after app initialization
import routes  # noqa: F401

# Register blueprints
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.patient_routes import patient_bp
from routes.screening_routes import screening_bp
from routes.document_routes import document_bp
from routes.api_routes import api_bp
from routes.main_routes import main_bp

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(patient_bp, url_prefix='/patients')
app.register_blueprint(screening_bp, url_prefix='/screening')
app.register_blueprint(document_bp, url_prefix='/documents')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(main_bp)  # No url_prefix so it handles root routes

# Error handlers
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

# Template globals
@app.template_global()
def cache_timestamp():
    import time
    return str(int(time.time()))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)