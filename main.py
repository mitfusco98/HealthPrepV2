"""
HealthPrep Medical Screening System
Main application entry point
"""
import os
import logging
from app import create_app

# Register blueprints
from routes.screening_routes import screening_bp
app = create_app()
app.register_blueprint(screening_bp, url_prefix='/screening')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Database tables created successfully")

    logger.info("Starting HealthPrep Medical Screening System")
    app.run(host='0.0.0.0', port=5000, debug=True)