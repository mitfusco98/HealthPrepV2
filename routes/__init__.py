"""
Route initialization and blueprint registration
"""
import os
from flask import render_template, redirect, url_for

def init_routes(app):
    """Initialize all application routes"""

    # Import all blueprints
    from routes.auth_routes import auth_bp
    from routes.main_routes import main_bp
    from routes.demo_routes import demo_bp
    from routes.admin_routes import admin_bp
    from routes.patient_routes import patient_bp
    from routes.screening_routes import screening_bp
    from routes.document_routes import document_bp
    from routes.prep_sheet_routes import prep_sheet_bp
    from routes.api_routes import api_bp
    from routes.ocr_routes import ocr_bp

    # Register all blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(demo_bp, url_prefix='/demo')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(patient_bp, url_prefix='/patients')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(document_bp, url_prefix='/documents')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep-sheet')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ocr_bp, url_prefix='/ocr')

    # Add root route
    @app.route('/')
    def index():
        """Root route - redirect to main dashboard"""
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        else:
            return redirect(url_for('auth.login'))

    # Add additional helpful routes
    @app.route('/home')
    def home():
        """Home route - redirect to root"""
        return redirect(url_for('index'))

    @app.route('/test')
    def test():
        """Test route to verify app is working"""
        return '<h1>✅ HealthPrep Medical Screening System</h1><p>Flask is running successfully!</p><p><a href="/">Go to Home</a></p>'

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('error/403.html'), 403

    @app.errorhandler(400)
    def bad_request_error(error):
        return render_template('error/400.html'), 400