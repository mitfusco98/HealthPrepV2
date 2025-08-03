
#!/usr/bin/env python3

"""
Main application entry point
"""

import os
import sys
import logging
from app import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main application entry point"""
    try:
        # Ensure database is initialized
        with app.app_context():
            from app import db
            db.create_all()
            logger.info("Database tables created/verified")
        
        # Start the application
        host = '0.0.0.0'
        port = int(os.environ.get('PORT', 5000))
        
        logger.info(f"Starting Flask application on {host}:{port}")
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
