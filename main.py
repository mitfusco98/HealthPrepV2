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

# Create Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting HealthPrep Medical Screening System")
    # Use production-compatible settings for workflow stability
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=False,  # Disable debug mode for workflow compatibility
        threaded=True,
        use_reloader=False  # Disable auto-reloader for workflow compatibility
    )