"""
HealthPrep Medical Screening System
Main application entry point
"""
import logging
from app import create_app

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app = create_app()
    logger.info("Starting HealthPrep Medical Screening System")
    app.run(host='0.0.0.0', port=5000, debug=True)