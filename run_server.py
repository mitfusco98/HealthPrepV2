#!/usr/bin/env python3
"""
Production-ready server startup script for workflow compatibility
"""
import os
import sys
import logging
from app import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Start the Flask application"""
    try:
        # Create the app
        app = create_app()
        logger.info("Flask application created successfully")
        
        # Start the server
        logger.info("Starting HealthPrep Medical Screening System on 0.0.0.0:5000")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Disable debug mode for workflow compatibility
            threaded=True,
            use_reloader=False  # Disable auto-reloader for workflow compatibility
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()