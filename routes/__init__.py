"""
Route initialization and blueprint registration
"""
from flask import render_template, redirect, url_for
from flask_login import current_user

def init_routes(app):
    """Initialize core application routes only"""

    # Import core blueprints only
    from routes.auth_routes import auth_bp
    from routes.demo_routes import demo_bp
    from routes.admin_routes import admin_bp
    from routes.screening_routes import screening_bp
    from routes.prep_sheet_routes import prep_sheet_bp

    # Register core blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(demo_bp, url_prefix='/demo')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(screening_bp, url_prefix='/screening')
    app.register_blueprint(prep_sheet_bp, url_prefix='/prep-sheet')

    # Root route - redirect to main functionality
    @app.route('/')
    def index():
        """Root route - redirect to core functionality"""
        if current_user.is_authenticated:
            return redirect(url_for('demo.index'))
        else:
            return redirect(url_for('auth.login'))

    # Simple test route
    @app.route('/test')
    def test():
        """Test route to verify app is working"""
        return '<h1>✅ HealthPrep Medical Screening System</h1><p>Flask is running successfully!</p><p><a href="/">Go to Dashboard</a></p>'

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