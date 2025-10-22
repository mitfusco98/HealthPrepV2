#!/usr/bin/env python3
"""
Test Epic Client Credentials Flow (Backend OAuth 2.0)
Based on Epic sanity checks for testing before EHR launch
"""

import os
import requests
import logging
from services.jwt_client_auth import JWTClientAuthService
from services.smart_discovery import smart_discovery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_client_credentials_flow():
    """
    Test Epic client credentials flow (backend OAuth 2.0)
    This helps verify JWT client assertion and token exchange work
    """
    
    # Configuration - replace with your actual values
    CLIENT_ID = os.environ.get('NONPROD_CLIENT_ID', 'your_nonprod_client_id_here')
    ISS = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4'
    ENVIRONMENT = "nonprod"
    
    logger.info("🧪 Epic Client Credentials Flow Test")
    logger.info("=" * 60)
    logger.info(f"Client ID: {CLIENT_ID}")
    logger.info(f"ISS: {ISS}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info("=" * 60)
    
    try:
        # Step 1: Discover token endpoint
        logger.info("Step 1: SMART Discovery")
        config = smart_discovery.fetch(ISS)
        token_endpoint = config['token_endpoint']
        logger.info(f"✅ Token Endpoint: {token_endpoint}")
        
        # Step 2: Create client assertion
        logger.info("\nStep 2: Creating JWT Client Assertion")
        client_assertion = JWTClientAuthService.create_client_assertion(
            client_id=CLIENT_ID,
            token_url=token_endpoint,
            environment=ENVIRONMENT
        )
        logger.info("✅ Client assertion created (see debug output above)")
        
        # Step 3: Make token request (client credentials)
        logger.info("\nStep 3: Token Request (Client Credentials)")
        token_data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': client_assertion
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'User-Agent': 'HealthPrep-SMART-Client/1.0'
        }
        
        logger.info(f"POST {token_endpoint}")
        logger.info("Request Headers:")
        for key, value in headers.items():
            logger.info(f"  {key}: {value}")
        logger.info("Request Data:")
        for key, value in token_data.items():
            if key == 'client_assertion':
                logger.info(f"  {key}: [JWT - {len(value)} chars]")
            else:
                logger.info(f"  {key}: {value}")
        
        # Make the request
        response = requests.post(token_endpoint, data=token_data, headers=headers, timeout=30)
        
        logger.info(f"\nResponse Status: {response.status_code}")
        logger.info("Response Headers:")
        for key, value in response.headers.items():
            logger.info(f"  {key}: {value}")
        
        if response.status_code == 200:
            token_response = response.json()
            logger.info("✅ SUCCESS: Token response received")
            logger.info("Token Response:")
            for key, value in token_response.items():
                if key == 'access_token':
                    logger.info(f"  {key}: [TOKEN - {len(value)} chars]")
                else:
                    logger.info(f"  {key}: {value}")
            return True
            
        else:
            logger.error(f"❌ FAILED: HTTP {response.status_code}")
            logger.error(f"Response Body: {response.text}")
            
            # Common Epic error interpretations
            if response.status_code == 401:
                logger.error("\n🔍 Common 401 Causes:")
                logger.error("  - Client ID mismatch (iss/sub in JWT)")
                logger.error("  - Audience mismatch (aud in JWT != token URL)")
                logger.error("  - Key ID (kid) not found in nonprod JWKS")
                logger.error("  - JWT exp/iat time window issues")
                logger.error("  - App not yet synced to Sandbox (wait 60 min after 'Ready for Sandbox')")
            
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        return False

def test_jwks_consistency():
    """Test that our JWT kid matches what's published in JWKS"""
    logger.info("\n🔑 Testing JWKS Key Consistency")
    logger.info("=" * 40)
    
    try:
        result = JWTClientAuthService.validate_key_consistency("nonprod")
        if result:
            logger.info("✅ JWT kid matches published JWKS")
        else:
            logger.error("❌ JWT kid NOT found in published JWKS")
            logger.error("This will cause 'invalid_client' errors")
        return result
    except Exception as e:
        logger.error(f"❌ JWKS validation failed: {e}")
        return False

def main():
    """Run all Epic integration tests"""
    logger.info("🚀 Epic Sandbox Integration Tests")
    logger.info("Based on Epic troubleshooting sanity checks")
    logger.info("=" * 60)
    
    # Test 1: JWKS consistency
    jwks_ok = test_jwks_consistency()
    
    # Test 2: Client credentials flow
    client_creds_ok = test_client_credentials_flow()
    
    # Summary
    logger.info("\n📋 Test Summary")
    logger.info("=" * 30)
    logger.info(f"JWKS Consistency: {'✅ PASS' if jwks_ok else '❌ FAIL'}")
    logger.info(f"Client Credentials: {'✅ PASS' if client_creds_ok else '❌ FAIL'}")
    
    if jwks_ok and client_creds_ok:
        logger.info("\n🎉 All tests passed! Epic integration looks ready.")
    else:
        logger.info("\n⚠️  Some tests failed. Check Epic app status and configuration.")
        logger.info("Remember: Wait 60 minutes after 'Ready for Sandbox' for Epic to sync.")

if __name__ == "__main__":
    main()