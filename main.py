"""
HealthPrep Medical Screening System
Main application entry point
"""
import os
import sys
import logging
from app import create_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask application (blueprints are registered in app.py)
app = create_app()

if __name__ == '__main__':
    logger.info("Starting HealthPrep Medical Screening System")
    
    # Enhanced port configuration with conflict resolution
    port = int(os.environ.get('PORT', 5000))
    
    # Check if smart_start.py should be used for better conflict resolution
    use_smart_start = os.environ.get('USE_SMART_START', 'false').lower() == 'true'
    
    if use_smart_start:
        logger.info("Delegating to smart_start.py for enhanced conflict resolution")
        import subprocess
        subprocess.run([sys.executable, 'smart_start.py', 'dev'])
    else:
        # Standard startup with basic port handling
        try:
            app.run(host='0.0.0.0', port=port, debug=True)
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(f"Port {port} is busy, trying alternative ports...")
                for alt_port in range(port + 1, port + 10):
                    try:
                        logger.info(f"Trying port {alt_port}...")
                        app.run(host='0.0.0.0', port=alt_port, debug=True)
                        break
                    except OSError:
                        continue
                else:
                    logger.error("No available ports found!")
                    raise
            else:
                raise