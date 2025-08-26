#!/usr/bin/env python3
"""
Keep-alive script to ensure server stays active during Epic approval process
Run this in a separate terminal/workflow to prevent Replit shutdown
"""

import requests
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Use your deployment URL instead of development URL
BASE_URL = "https://health-prep-v-201-mitchfusillo.replit.app"

ENDPOINTS_TO_PING = [
    "/health",
    "/nonprod/.well-known/jwks.json",
    "/.well-known/jwks.json"
]

def ping_endpoints():
    """Ping critical endpoints to keep server active"""
    for endpoint in ENDPOINTS_TO_PING:
        try:
            url = f"{BASE_URL}{endpoint}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ {endpoint} - Status: {response.status_code}")
            else:
                logger.warning(f"⚠️  {endpoint} - Status: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {endpoint} - Error: {e}")

        time.sleep(2)  # Small delay between requests

def main():
    """Run keep-alive loop"""
    logger.info("🚀 Starting Epic approval keep-alive service")
    logger.info("This will ping your JWKS endpoints every 5 minutes")
    logger.info("Keep this running during Epic App Orchard registration")

    try:
        while True:
            logger.info("🔄 Pinging endpoints to keep server active...")
            ping_endpoints()

            logger.info("✅ All endpoints pinged - sleeping for 5 minutes")
            time.sleep(300)  # Wait 5 minutes between ping cycles

    except KeyboardInterrupt:
        logger.info("🛑 Keep-alive service stopped by user")
    except Exception as e:
        logger.error(f"💥 Keep-alive service error: {e}")

if __name__ == "__main__":
    main()