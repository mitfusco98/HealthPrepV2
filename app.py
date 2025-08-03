import os
import logging
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

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
login_manager.init_app(app)
csrf.init_app(app)

# Configure Flask-Login
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Import models to ensure tables are created
with app.app_context():
    import models
    db.create_all()

# Register blueprints
from routes.auth_routes import auth_bp
from routes.screening_routes import screening_bp
from routes.admin_routes import admin_bp
from routes.prep_sheet_routes import prep_sheet_bp

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(screening_bp, url_prefix='/screening')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(prep_sheet_bp, url_prefix='/prep')

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

# Template context processors
@app.context_processor
def utility_processor():
    import time
    return dict(cache_timestamp=int(time.time()))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
