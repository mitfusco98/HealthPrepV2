
#!/usr/bin/env python3
"""
Epic Sandbox Readiness Validation
Final sanity checks to prove Sandbox readiness before testing
"""

import os
import sys
import json
import time
import uuid
import base64
import hashlib
import hmac
import logging
import requests
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from services.jwt_client_auth import JWTClientAuthService

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

class EpicSandboxValidator:
    """Validates Epic Sandbox readiness with final sanity checks"""
    
    def __init__(self):
        # Use the correct externally hosted JWKS URL
        self.jwks_base_url = "https://epic-sandbox-link-mitchfusillo.replit.app"
        self.iss = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
        self.results = []
    
    def log_result(self, test_name: str, passed: bool, message: str, details: dict = None):
        """Log validation result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'details': details or {}
        }
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name} - {message}")
        if details:
            for key, value in details.items():
                logger.info(f"    {key}: {value}")
    
    def test_smart_discovery(self) -> tuple:
        """Step 1: Re-confirm SMART discovery (fresh, right before testing)"""
        logger.info("\n🔍 Step 1: SMART Discovery Validation")
        logger.info("=" * 50)
        
        try:
            url = f"{self.iss}/.well-known/smart-configuration"
            logger.info(f"Fetching SMART config from: {url}")
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.log_result("SMART Discovery", False, 
                              f"HTTP {response.status_code}")
                return None, None
            
            config = response.json()
            auth_endpoint = config.get('authorization_endpoint')
            token_endpoint = config.get('token_endpoint')
            
            if not auth_endpoint or not token_endpoint:
                self.log_result("SMART Discovery", False, 
                              "Missing required endpoints")
                return None, None
            
            self.log_result("SMART Discovery", True, 
                          "Successfully retrieved endpoints", {
                'authorization_endpoint': auth_endpoint,
                'token_endpoint': token_endpoint
            })
            
            return auth_endpoint, token_endpoint
            
        except Exception as e:
            self.log_result("SMART Discovery", False, f"Exception: {e}")
            return None, None
    
    def get_nonprod_credentials(self) -> tuple:
        """Get non-prod client credentials and key info"""
        try:
            # Get private key and kid
            private_key_pem, kid = JWTClientAuthService.get_private_key_and_kid("nonprod")
            
            # Get client ID from EPIC_NONPROD_CLIENT_ID environment variable
            client_id = os.environ.get('EPIC_NONPROD_CLIENT_ID')
            if not client_id:
                logger.error("❌ EPIC_NONPROD_CLIENT_ID environment variable not set")
                logger.error("   Please set this to your Epic nonprod client ID")
                return None, None, None
            
            logger.info(f"Using client ID: {client_id}")
            logger.info(f"Using key ID: {kid}")
            
            return client_id, private_key_pem, kid
            
        except Exception as e:
            logger.error(f"Failed to get nonprod credentials: {e}")
            return None, None, None
    
    def build_client_assertion_manual(self, client_id: str, token_url: str, 
                                    private_key_pem: str, kid: str) -> str:
        """Step 2: Build client assertion with manual verification"""
        logger.info(f"\n🔑 Step 2: Building Client Assertion")
        logger.info("=" * 50)
        
        try:
            # Create JWT header
            now = int(time.time())
            header = {
                "alg": "RS256",
                "typ": "JWT", 
                "kid": kid
            }
            
            # Create JWT payload
            payload = {
                "iss": client_id,
                "sub": client_id,
                "aud": token_url,
                "jti": str(uuid.uuid4()),
                "iat": now,
                "exp": now + 300  # 5 minutes
            }
            
            logger.info("JWT Construction Details:")
            logger.info(f"  Header:  {json.dumps(header, separators=(',', ':'))}")
            logger.info(f"  Payload: {json.dumps(payload, separators=(',', ':'))}")
            logger.info(f"  Client ID (iss/sub): {client_id}")
            logger.info(f"  Token URL (aud): {token_url}")
            logger.info(f"  Key ID: {kid}")
            logger.info(f"  Expires in: {(payload['exp'] - payload['iat']) / 60:.1f} minutes")
            
            # Base64url encode without padding
            def b64u(data):
                if isinstance(data, str):
                    data = data.encode('utf-8')
                return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
            
            # Encode header and payload
            header_b64 = b64u(json.dumps(header, separators=(',', ':')))
            payload_b64 = b64u(json.dumps(payload, separators=(',', ':')))
            
            # Create signing input
            signing_input = f"{header_b64}.{payload_b64}"
            
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )
            
            # Sign the JWT
            signature = private_key.sign(
                signing_input.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            signature_b64 = b64u(signature)
            jwt_token = f"{signing_input}.{signature_b64}"
            
            # Validation checks
            checks = {
                "iss equals client_id": payload["iss"] == client_id,
                "sub equals client_id": payload["sub"] == client_id, 
                "aud equals token_url": payload["aud"] == token_url,
                "kid matches expected": header["kid"] == kid,
                "exp within 5 min": (payload["exp"] - payload["iat"]) <= 300,
                "iat not in future": payload["iat"] <= int(time.time()) + 60
            }
            
            all_checks_passed = all(checks.values())
            
            self.log_result("JWT Client Assertion", all_checks_passed,
                          f"Built {'successfully' if all_checks_passed else 'with issues'}", {
                **checks,
                'jwt_length': len(jwt_token)
            })
            
            return jwt_token if all_checks_passed else None
            
        except Exception as e:
            self.log_result("JWT Client Assertion", False, f"Exception: {e}")
            return None
    
    def test_jwks_consistency(self, kid: str) -> bool:
        """Verify kid exists in published JWKS using correct URL"""
        logger.info(f"\n🔗 JWKS Consistency Check")
        logger.info("=" * 50)
        
        try:
            # Use the correct externally hosted JWKS URL
            jwks_url = f"{self.jwks_base_url}/nonprod/.well-known/jwks.json"
            logger.info(f"Checking JWKS at: {jwks_url}")
            
            response = requests.get(jwks_url, timeout=10)
            if response.status_code != 200:
                self.log_result("JWKS Consistency", False,
                              f"JWKS unavailable: HTTP {response.status_code}")
                return False
            
            jwks = response.json()
            kids_in_jwks = [key.get('kid') for key in jwks.get('keys', [])]
            
            kid_found = kid in kids_in_jwks
            
            self.log_result("JWKS Consistency", kid_found,
                          f"Kid {kid} {'found' if kid_found else 'NOT found'}", {
                'target_kid': kid,
                'available_kids': kids_in_jwks,
                'jwks_url': jwks_url
            })
            
            return kid_found
            
        except Exception as e:
            self.log_result("JWKS Consistency", False, f"Exception: {e}")
            return False
    
    def test_client_credentials_flow(self, token_url: str, client_assertion: str) -> bool:
        """Step 3a: Test backend service / client_credentials flow"""
        logger.info(f"\n🔒 Step 3a: Client Credentials Flow")
        logger.info("=" * 50)
        
        try:
            logger.info(f"Token endpoint: {token_url}")
            
            # Prepare request
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion
            }
            
            logger.info("Sending client_credentials request...")
            response = requests.post(token_url, headers=headers, data=data, timeout=30)
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.log_result("Client Credentials Flow", True,
                              "Successfully obtained access token", {
                    'access_token': f"{token_data.get('access_token', '')[:20]}...",
                    'token_type': token_data.get('token_type'),
                    'expires_in': token_data.get('expires_in'),
                    'scope': token_data.get('scope')
                })
                return True
            else:
                error_body = response.text
                logger.error(f"Token request failed: {error_body}")
                
                # Parse common errors
                error_analysis = self.analyze_token_error(response.status_code, error_body)
                
                self.log_result("Client Credentials Flow", False,
                              f"HTTP {response.status_code}", {
                    'error_response': error_body,
                    'analysis': error_analysis
                })
                return False
                
        except Exception as e:
            self.log_result("Client Credentials Flow", False, f"Exception: {e}")
            return False
    
    def analyze_token_error(self, status_code: int, response_body: str) -> str:
        """Analyze token request errors and provide guidance"""
        if status_code == 401:
            if "invalid_client" in response_body.lower():
                return """
                🔍 invalid_client - Common causes:
                • aud doesn't equal token URL byte-for-byte
                • iss/sub not the nonprod client_id  
                • kid not found in nonprod JWKS
                • JWT exp/iat time window issues
                • App not synced to Sandbox yet (wait ~60 min after 'Ready for Sandbox')
                """
            elif "invalid_assertion" in response_body.lower():
                return "JWT signature validation failed - check private key and JWKS"
        elif status_code == 400:
            if "unsupported_grant_type" in response_body.lower():
                return "Grant type not supported - check Epic app configuration"
        
        return f"HTTP {status_code} - Check Epic documentation for details"
    
    def run_full_validation(self) -> bool:
        """Run complete Epic Sandbox readiness validation"""
        logger.info("🚀 Epic Sandbox Readiness Validation")
        logger.info("=" * 60)
        
        # Step 1: SMART Discovery
        auth_endpoint, token_endpoint = self.test_smart_discovery()
        if not token_endpoint:
            logger.error("❌ Cannot proceed without token endpoint")
            return False
        
        # Get credentials
        client_id, private_key_pem, kid = self.get_nonprod_credentials()
        if not client_id:
            logger.error("❌ Cannot proceed without client credentials")
            return False
        
        # Step 2: Build client assertion
        client_assertion = self.build_client_assertion_manual(
            client_id, token_endpoint, private_key_pem, kid
        )
        if not client_assertion:
            logger.error("❌ Cannot proceed without valid client assertion")
            return False
        
        # JWKS consistency check
        jwks_ok = self.test_jwks_consistency(kid)
        if not jwks_ok:
            logger.warning("⚠️ JWKS consistency issues detected")
        
        # Step 3: Test token flows
        client_creds_ok = self.test_client_credentials_flow(token_endpoint, client_assertion)
        
        # Final summary
        logger.info("\n" + "=" * 60)
        passed_count = sum(1 for r in self.results if r['passed'])
        total_count = len(self.results)
        
        if client_creds_ok and jwks_ok:
            logger.info(f"🎉 SANDBOX READY! ({passed_count}/{total_count} checks passed)")
            logger.info("✅ Your app is ready for Epic Sandbox testing!")
            return True
        else:
            logger.info(f"❌ NOT READY ({passed_count}/{total_count} checks passed)")
            logger.info("❌ Fix issues before Epic Sandbox testing")
            
            # Additional troubleshooting info
            logger.info("\n📋 Troubleshooting Checklist:")
            logger.info("   1. Verify EPIC_NONPROD_CLIENT_ID is set correctly")
            logger.info("   2. Check Epic app status at https://fhir.epic.com")
            logger.info("   3. Ensure app is 'Ready for Sandbox'")
            logger.info("   4. Wait 60+ minutes for Epic sync after status change")
            logger.info(f"   5. Verify Epic has your JWKS URL: {self.jwks_base_url}/nonprod/.well-known/jwks.json")
            
            return False

def main():
    """Main validation entry point"""
    validator = EpicSandboxValidator()
    
    # Check if nonprod client ID is set
    client_id = os.environ.get('EPIC_NONPROD_CLIENT_ID')
    if not client_id:
        logger.error("❌ Please set EPIC_NONPROD_CLIENT_ID environment variable")
        logger.error("   This should be your Epic nonprod client ID from https://fhir.epic.com")
        return False
    
    # Show current configuration
    logger.info(f"Using client ID: {client_id[:12]}...")
    logger.info(f"Using JWKS URL: {validator.jwks_base_url}/nonprod/.well-known/jwks.json")
    
    return validator.run_full_validation()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
