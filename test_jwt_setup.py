#!/usr/bin/env python3
"""
Test script to verify JWT setup and demonstrate usage
"""

import sys
import os
sys.path.append('.')

from utils.jwt_utils import get_epic_client_assertion, setup_instructions
import requests

def test_jwks_endpoints():
    """Test the JWKS endpoints"""
    print("Testing JWKS Endpoints...")
    print("=" * 50)
    
    base_url = "https://55ab1b06-006d-47ec-9b73-b827f4e0f641-00-1fje9legmrd1y.riker.replit.dev"
    
    # Test non-production endpoint
    try:
        response = requests.get(f"{base_url}/nonprod/.well-known/jwks.json")
        if response.status_code == 200:
            jwks = response.json()
            print(f"✅ Non-prod JWKS: {len(jwks['keys'])} keys found")
            for key in jwks['keys']:
                print(f"   Key ID: {key['kid']}, Algorithm: {key['alg']}")
        else:
            print(f"❌ Non-prod JWKS failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Non-prod JWKS error: {e}")
    
    # Test production endpoint
    try:
        response = requests.get(f"{base_url}/.well-known/jwks.json")
        if response.status_code == 200:
            jwks = response.json()
            print(f"✅ Production JWKS: {len(jwks['keys'])} keys found")
            for key in jwks['keys']:
                print(f"   Key ID: {key['kid']}, Algorithm: {key['alg']}")
        else:
            print(f"❌ Production JWKS failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Production JWKS error: {e}")

def test_client_assertion():
    """Test client assertion generation"""
    print("\nTesting Client Assertion Generation...")
    print("=" * 50)
    
    try:
        # Test with dummy client ID
        client_id = "test-client-id"
        
        # Generate assertions for both environments
        nonprod_assertion = get_epic_client_assertion(client_id, "nonprod")
        prod_assertion = get_epic_client_assertion(client_id, "prod")
        
        print(f"✅ Non-prod assertion generated: {len(nonprod_assertion)} characters")
        print(f"✅ Production assertion generated: {len(prod_assertion)} characters")
        
        # Decode headers to show kid values (without verification)
        import jwt
        nonprod_header = jwt.get_unverified_header(nonprod_assertion)
        prod_header = jwt.get_unverified_header(prod_assertion)
        
        print(f"   Non-prod Key ID: {nonprod_header.get('kid')}")
        print(f"   Production Key ID: {prod_header.get('kid')}")
        
    except Exception as e:
        print(f"❌ Client assertion error: {e}")

def show_current_keys():
    """Show what keys are currently configured"""
    print("\nCurrent Key Configuration...")
    print("=" * 50)
    
    nonprod_keys = []
    prod_keys = []
    
    for name, val in os.environ.items():
        if name.startswith("NP_KEY") and val.strip():
            nonprod_keys.append(name)
        elif name.startswith("P_KEY") and val.strip():
            prod_keys.append(name)
    
    if nonprod_keys:
        print(f"✅ Non-production keys found: {', '.join(nonprod_keys)}")
    else:
        print("⚠️  No non-production keys found in environment (using fallback)")
    
    if prod_keys:
        print(f"✅ Production keys found: {', '.join(prod_keys)}")
    else:
        print("⚠️  No production keys found in environment (using fallback)")

if __name__ == "__main__":
    print("HealthPrep JWT Setup Test")
    print("=" * 50)
    
    # Show current configuration
    show_current_keys()
    
    # Test endpoints
    test_jwks_endpoints()
    
    # Test assertion generation
    test_client_assertion()
    
    # Show setup instructions
    print("\n")
    setup_instructions()