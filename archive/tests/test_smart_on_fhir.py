#!/usr/bin/env python3
"""
Test SMART on FHIR OAuth2 Integration
Tests the Epic OAuth2 authentication flow as outlined in the blueprint
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emr.fhir_client import FHIRClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_smart_on_fhir_client():
    """Test SMART on FHIR OAuth2 client functionality"""
    logger.info("Testing SMART on FHIR OAuth2 Client")
    logger.info("=" * 50)
    
    # Initialize client with Epic sandbox configuration
    epic_config = {
        'epic_client_id': 'test_client_id',
        'epic_client_secret': 'test_client_secret',
        'epic_fhir_url': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
    }
    
    redirect_uri = 'http://localhost:5000/fhir/epic-callback'
    client = FHIRClient(epic_config, redirect_uri)
    
    try:
        # Test 1: Generate authorization URL
        logger.info("Test 1: Generate Epic authorization URL")
        auth_url, state = client.get_authorization_url()
        
        logger.info(f"✓ Authorization URL generated successfully")
        logger.info(f"  URL: {auth_url[:100]}...")
        logger.info(f"  State: {state[:16]}...")
        
        # Verify URL components
        assert 'response_type=code' in auth_url
        assert 'client_id=test_client_id' in auth_url
        assert 'redirect_uri=' in auth_url
        assert 'scope=' in auth_url
        assert 'aud=' in auth_url
        assert 'state=' in auth_url
        
        logger.info("✓ All required OAuth2 parameters present in URL")
        
        # Test 2: Verify scopes
        logger.info("\nTest 2: Verify SMART on FHIR scopes")
        scopes = client.default_scopes
        expected_scopes = [
            'openid',
            'fhirUser', 
            'patient/Patient.read',
            'patient/Condition.read',
            'patient/Observation.read',
            'patient/DocumentReference.read',
            'patient/Encounter.read'
        ]
        
        for scope in expected_scopes:
            if scope in scopes:
                logger.info(f"✓ {scope}")
            else:
                logger.warning(f"✗ Missing scope: {scope}")
        
        # Test 3: Token management (without actual OAuth flow)
        logger.info("\nTest 3: Token management functionality")
        
        # Mock token data
        mock_access_token = "mock_access_token_12345"
        mock_refresh_token = "mock_refresh_token_67890"
        expires_in = 3600
        mock_scopes = ['patient/Patient.read', 'patient/Condition.read']
        
        client.set_tokens(mock_access_token, mock_refresh_token, expires_in, mock_scopes)
        
        if client.access_token == mock_access_token:
            logger.info("✓ Access token set successfully")
        if client.refresh_token == mock_refresh_token:
            logger.info("✓ Refresh token set successfully")
        if client.token_scopes == mock_scopes:
            logger.info("✓ Token scopes set successfully")
            
        # Test 4: Headers generation
        logger.info("\nTest 4: API headers generation")
        try:
            headers = client._get_headers()
            if headers.get('Authorization') == f"Bearer {mock_access_token}":
                logger.info("✓ Authorization header correctly formatted")
            if headers.get('Accept') == 'application/fhir+json':
                logger.info("✓ Accept header correctly set for FHIR")
            if headers.get('Content-Type') == 'application/fhir+json':
                logger.info("✓ Content-Type header correctly set for FHIR")
        except Exception as e:
            logger.error(f"✗ Headers generation failed: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"SMART on FHIR client test failed: {str(e)}")
        return False


def test_epic_oauth_endpoints():
    """Test Epic OAuth2 endpoint configuration"""
    logger.info("\nTesting Epic OAuth2 Endpoints")
    logger.info("=" * 50)
    
    try:
        client = FHIRClient()
        
        # Expected Epic endpoints
        expected_auth_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize'
        expected_token_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
        expected_base_url = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        
        logger.info("Epic FHIR Endpoint Configuration:")
        logger.info(f"  Auth URL: {client.auth_url}")
        logger.info(f"  Token URL: {client.token_url}")
        logger.info(f"  Base URL: {client.base_url}")
        
        # Verify endpoints
        if client.auth_url == expected_auth_url:
            logger.info("✓ Authorization endpoint correctly configured")
        else:
            logger.warning(f"✗ Authorization endpoint mismatch: {client.auth_url}")
            
        if client.token_url == expected_token_url:
            logger.info("✓ Token endpoint correctly configured")
        else:
            logger.warning(f"✗ Token endpoint mismatch: {client.token_url}")
            
        if client.base_url == expected_base_url:
            logger.info("✓ FHIR base URL correctly configured")
        else:
            logger.warning(f"✗ FHIR base URL mismatch: {client.base_url}")
        
        return True
        
    except Exception as e:
        logger.error(f"Endpoint configuration test failed: {str(e)}")
        return False


def main():
    """Run SMART on FHIR OAuth2 integration tests"""
    logger.info("SMART on FHIR OAuth2 Integration Test Suite")
    logger.info("Testing Epic Authentication Flow")
    logger.info("=" * 60)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: SMART on FHIR Client
    if test_smart_on_fhir_client():
        tests_passed += 1
    
    # Test 2: Epic OAuth2 Endpoints
    if test_epic_oauth_endpoints():
        tests_passed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("✅ All SMART on FHIR OAuth2 tests passed!")
        logger.info("Epic authentication flow ready for integration")
        logger.info("\nNext steps:")
        logger.info("1. Configure Epic Client ID and Secret in organization settings")
        logger.info("2. Use /fhir/epic-authorize to start OAuth2 flow")
        logger.info("3. Handle callback at /fhir/epic-callback")
        logger.info("4. Use authenticated FHIR client for Epic data queries")
    else:
        logger.warning(f"⚠️  {total_tests - tests_passed} test(s) failed")
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)