import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
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

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Import models and create tables
with app.app_context():
    import models  # noqa: F401
    db.create_all()
    logging.info("Database tables created successfully")

# Register error handlers
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

# Template filters
@app.template_filter('datetime')
def datetime_filter(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ""
    return value.strftime(format)

# Cache timestamp for static files
@app.context_processor
def inject_cache_timestamp():
    import time
    return dict(cache_timestamp=int(time.time()))

# CSRF token generation
@app.context_processor
def inject_csrf_token():
    from secrets import token_urlsafe
    return dict(csrf_token=lambda: token_urlsafe(32))
