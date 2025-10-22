
#!/usr/bin/env python3
"""
Setup Epic Non-Production Credentials
Helper script to configure environment variables for testing
"""

import os
import sys

def setup_epic_nonprod():
    """Setup Epic non-production environment variables"""
    
    print("Epic Non-Production Setup")
    print("=" * 40)
    
    # Check current environment
    current_client_id = os.environ.get('EPIC_NONPROD_CLIENT_ID')
    if current_client_id:
        print(f"✅ EPIC_NONPROD_CLIENT_ID already set: {current_client_id}")
    else:
        print("❌ EPIC_NONPROD_CLIENT_ID not set")
    
    # Instructions
    print("\nTo set your Epic non-production client ID:")
    print("1. Go to Epic App Orchard: https://apporchard.epic.com/")
    print("2. Find your app in 'My Apps'")
    print("3. Copy the 'Non-Production Client ID'")
    print("4. Set it in Replit Secrets:")
    print("   - Key: EPIC_NONPROD_CLIENT_ID") 
    print("   - Value: <your-client-id>")
    
    # Check JWKS setup
    print(f"\nJWKS Configuration:")
    print(f"✅ Base URL: {os.environ.get('REPLIT_URL', 'Not set')}")
    
    # Check key setup
    nonprod_keys = [name for name in os.environ if name.startswith('NP_KEY')]
    if nonprod_keys:
        print(f"✅ Non-prod keys found: {len(nonprod_keys)}")
        for key in nonprod_keys:
            kid = key.replace('NP_KEY_', '')
            print(f"   - {kid}")
    else:
        print("⚠️  No NP_KEY_* environment variables found (using fallback)")
    
    print(f"\nNext steps:")
    print("1. Set EPIC_NONPROD_CLIENT_ID in Replit Secrets")
    print("2. Run: python test_epic_sandbox_readiness.py")

if __name__ == "__main__":
    setup_epic_nonprod()
