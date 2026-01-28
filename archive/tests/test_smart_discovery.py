#!/usr/bin/env python3
"""
Test SMART Discovery from ISS Endpoint
Confirms SMART configuration is discoverable from the issuer
"""

import requests
import json
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_smart_discovery(iss):
    """
    Test SMART discovery from ISS endpoint

    Args:
        iss: Issuer URL (e.g., https://fhir.epic.com/interconnect-fhir-oauth)
    """
    logger.info(f"Testing SMART discovery for ISS: {iss}")
    logger.info("=" * 60)

    try:
        # Construct well-known endpoint
        well_known_url = f"{iss.rstrip('/')}/.well-known/smart-configuration"
        logger.info(f"Fetching SMART configuration from: {well_known_url}")

        # Make request
        response = requests.get(well_known_url, timeout=10)
        response.raise_for_status()

        # Parse JSON
        config = response.json()

        # Extract required endpoints
        auth_endpoint = config.get('authorization_endpoint')
        token_endpoint = config.get('token_endpoint')

        # Display results
        logger.info("SMART Discovery Results:")
        logger.info(f"  Authorization Endpoint: {auth_endpoint}")
        logger.info(f"  Token Endpoint: {token_endpoint}")

        # Validate required fields
        if not auth_endpoint:
            logger.error("❌ Missing authorization_endpoint")
            return False

        if not token_endpoint:
            logger.error("❌ Missing token_endpoint")
            return False

        logger.info("✅ SMART discovery successful - required endpoints found")

        # Display additional configuration
        logger.info("\nAdditional SMART Configuration:")
        for key, value in config.items():
            if key not in ['authorization_endpoint', 'token_endpoint']:
                logger.info(f"  {key}: {value}")

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ HTTP request failed: {e}")
        logger.error("This indicates the ISS is unreachable or not serving SMART configuration")
        return False

    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON response: {e}")
        logger.error("The endpoint exists but is not returning valid SMART configuration")
        return False

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    # Epic's correct R4 FHIR ISS for sandbox/testing (must use R4 endpoint for proper discovery)
    epic_iss = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"

    logger.info("SMART Discovery Test")
    logger.info("Testing Epic's SMART on FHIR configuration")
    logger.info("=" * 60)

    # Test Epic ISS
    success = test_smart_discovery(epic_iss)

    if success:
        logger.info("\n🎉 SMART discovery validation passed!")
        logger.info("Epic's SMART configuration is properly discoverable")
    else:
        logger.error("\n💥 SMART discovery validation failed!")
        logger.error("Check ISS URL or Epic's service availability")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)