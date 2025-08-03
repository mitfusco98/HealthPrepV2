import os
import logging
from flask import Flask, render_template
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

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

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
    return render_template('error/500.html'), 500

# Add a root route
@app.route('/')
def index():
    return render_template('dashboard.html')

with app.app_context():
    # Import models to create tables
    import models
    db.create_all()
    
    # Import routes
    import routes
