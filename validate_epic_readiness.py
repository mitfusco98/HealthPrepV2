
#!/usr/bin/env python3
"""
Simplified Epic Sandbox Readiness Validator
Focuses on the key requirements for Epic integration
"""

import os
import sys
import requests
import logging
from services.jwt_client_auth import JWTClientAuthService
from services.smart_discovery import smart_discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run focused Epic readiness checks"""
    logger.info("🚀 Epic Sandbox Readiness Check")
    logger.info("=" * 50)
    
    # Check 1: Environment variables
    client_id = os.environ.get('NONPROD_CLIENT_ID')
    if not client_id:
        logger.error("❌ NONPROD_CLIENT_ID environment variable not set")
        return False
    
    logger.info(f"✅ Client ID found: {client_id}")
    
    # Check 2: JWKS endpoint accessibility
    jwks_url = "https://epic-sandbox-link-mitchfusillo.replit.app/nonprod/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks_data = response.json()
        kids = [key.get('kid') for key in jwks_data.get('keys', [])]
        logger.info(f"✅ JWKS accessible with kids: {kids}")
    except Exception as e:
        logger.error(f"❌ JWKS endpoint error: {e}")
        return False
    
    # Check 3: JWT client assertion creation
    try:
        token_url = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
        client_assertion = JWTClientAuthService.create_client_assertion(
            client_id=client_id,
            token_url=token_url,
            environment="nonprod"
        )
        logger.info("✅ JWT client assertion created successfully")
    except Exception as e:
        logger.error(f"❌ JWT creation failed: {e}")
        return False
    
    # Check 4: Key consistency
    try:
        key_consistent = JWTClientAuthService.validate_key_consistency("nonprod")
        if key_consistent:
            logger.info("✅ JWT kid matches JWKS")
        else:
            logger.error("❌ JWT kid not found in JWKS")
            return False
    except Exception as e:
        logger.error(f"❌ Key consistency check failed: {e}")
        return False
    
    # Check 5: Epic token endpoint test (will fail until app is active)
    logger.info("\n🔑 Testing Epic Token Endpoint...")
    try:
        token_data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': client_assertion
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        response = requests.post(token_url, data=token_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info("🎉 SUCCESS: Epic token endpoint working!")
            return True
        elif response.status_code == 400:
            error_data = response.json()
            if error_data.get('error') == 'invalid_client':
                logger.warning("⚠️  Expected 'invalid_client' - app likely not synced yet")
                logger.info("📋 Next steps:")
                logger.info("   1. Verify app is 'Ready for Sandbox' in Epic App Orchard")
                logger.info("   2. Wait 60+ minutes for Epic to sync your app")
                logger.info("   3. Ensure JWKS URL is correct in Epic registration")
                logger.info(f"   4. Your JWKS URL: {jwks_url}")
                return False
        else:
            logger.error(f"❌ Unexpected response: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Token endpoint test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        logger.info("\n🎉 Epic Sandbox is READY!")
    else:
        logger.info("\n⚠️  Epic Sandbox not ready yet - check steps above")
    sys.exit(0 if success else 1)
