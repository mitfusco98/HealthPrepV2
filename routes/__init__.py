
"""
Routes package initialization
"""

def register_blueprints(app):
    """Register all blueprint routes with the Flask app"""
    
    # Import blueprints
    try:
        from .auth_routes import auth_bp
        app.register_blueprint(auth_bp)
    except ImportError:
        pass
    
    try:
        from .patient_routes import patient_bp
        app.register_blueprint(patient_bp)
    except ImportError:
        pass
    
    try:
        from .screening_routes import screening_bp
        app.register_blueprint(screening_bp)
    except ImportError:
        pass
    
    try:
        from .admin_routes import admin_bp
        app.register_blueprint(admin_bp)
    except ImportError:
        pass
    
    try:
        from .api_routes import api_bp
        app.register_blueprint(api_bp)
    except ImportError:
        pass
    
    try:
        from .document_routes import document_bp
        app.register_blueprint(document_bp)
    except ImportError:
        pass
    
    try:
        from .prep_sheet_routes import prep_sheet_bp
        app.register_blueprint(prep_sheet_bp)
    except ImportError:
        pass
    
    try:
        from .demo_routes import demo_bp
        app.register_blueprint(demo_bp)
    except ImportError:
        pass
    
    # Add a basic index route if no demo routes exist
    @app.route('/')
    def index():
        from flask import render_template
        try:
            return render_template('base.html')
        except:
            return '<h1>HealthPrep Medical Screening System</h1><p>Please log in to continue.</p>'
    
    # Add /home route that redirects to index
    @app.route('/home')
    def home():
        from flask import redirect, url_for
        return redirect(url_for('index'))
