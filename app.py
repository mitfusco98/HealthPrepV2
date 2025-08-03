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
    
    # Import and register all route blueprints
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.patient_routes import patient_bp
    from routes.screening_routes import screening_bp
    from routes.document_routes import document_bp
    from routes.api_routes import api_bp
    from routes.demo_routes import demo_bp
    from routes.prep_sheet_routes import prep_sheet_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(patient_bp, url_prefix='/patients')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(document_bp, url_prefix='/documents')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(demo_bp, url_prefix='/demo')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep-sheet')
    
    # Import legacy routes
    import routes
