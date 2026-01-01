#!/usr/bin/env python3
"""
Smart Start Script - Hybrid Port Conflict Resolution
Combines environment-based port configuration with dynamic port cleanup
"""
import os
import sys
import time
import subprocess
import psutil
import logging
from app import create_app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_processes_on_port(port):
    """Kill any processes using the specified port"""
    try:
        # Find processes using the port
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        logger.info(f"Killing process {proc.info['pid']} ({proc.info['name']}) using port {port}")
                        proc.kill()
                        time.sleep(0.5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.warning(f"Error cleaning up port {port}: {e}")

def kill_related_processes():
    """Kill processes related to this application"""
    patterns = [
        "python.*main.py",
        "gunicorn.*main:app",
        "flask.*run"
    ]
    
    for pattern in patterns:
        try:
            result = subprocess.run(
                ['pkill', '-f', pattern],
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Cleaned up processes matching: {pattern}")
        except Exception as e:
            logger.warning(f"Error cleaning up pattern {pattern}: {e}")

def get_available_port(preferred_port):
    """Get an available port, preferring the specified one"""
    import socket
    
    # Try the preferred port first
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', preferred_port))
            return preferred_port
    except OSError:
        logger.warning(f"Port {preferred_port} is in use")
    
    # Find an alternative port
    for port in range(preferred_port + 1, preferred_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                logger.info(f"Using alternative port: {port}")
                return port
        except OSError:
            continue
    
    raise RuntimeError("No available ports found")

def smart_start(server_type='dev'):
    """
    Smart start with hybrid port conflict resolution
    
    Args:
        server_type: 'dev' for development server, 'prod' for gunicorn
    """
    # Get configuration
    preferred_port = int(os.environ.get('PORT', 5000))
    
    if server_type == 'prod':
        preferred_port = int(os.environ.get('PROD_PORT', 5001))
    
    logger.info(f"Starting HealthPrep Medical Screening System ({server_type} mode)")
    logger.info(f"Preferred port: {preferred_port}")
    
    # Step 1: Clean up existing processes
    logger.info("Cleaning up existing processes...")
    kill_related_processes()
    time.sleep(2)  # Allow processes to terminate
    
    # Step 2: Clean up port specifically  
    logger.info(f"Cleaning up port {preferred_port}...")
    kill_processes_on_port(preferred_port)
    time.sleep(1)
    
    # Step 3: Get available port
    try:
        available_port = get_available_port(preferred_port)
        os.environ['PORT'] = str(available_port)
        logger.info(f"Using port: {available_port}")
    except RuntimeError as e:
        logger.error(f"Cannot find available port: {e}")
        sys.exit(1)
    
    # Step 4: Start the appropriate server
    if server_type == 'dev':
        logger.info("Starting Flask development server...")
        app = create_app()
        app.run(host='0.0.0.0', port=available_port, debug=True)
    
    elif server_type == 'prod':
        logger.info("Starting Gunicorn production server...")
        cmd = [
            'gunicorn',
            '--bind', f'0.0.0.0:{available_port}',
            '--reload',
            '--worker-class', 'sync',
            '--workers', '1',
            'main:app'
        ]
        subprocess.run(cmd)
    
    else:
        logger.error(f"Unknown server type: {server_type}")
        sys.exit(1)

if __name__ == '__main__':
    # Parse command line arguments
    server_type = 'dev'
    if len(sys.argv) > 1:
        server_type = sys.argv[1]
    
    try:
        smart_start(server_type)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)