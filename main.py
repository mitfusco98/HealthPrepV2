"""
HealthPrep Medical Screening System
Main application entry point
"""
import os
import logging
from app import create_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask application (blueprints are registered in app.py)
app = create_app()

if __name__ == '__main__':
    logger.info("Starting HealthPrep Medical Screening System")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)