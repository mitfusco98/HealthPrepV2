"""
JWT Client Authentication Service
Handles JWT client assertion creation with proper key ID matching
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

class JWTClientAuthService:
    """Service for creating JWT client assertions with consistent key management"""
    
    @staticmethod
    def get_private_key_and_kid(environment: str = "nonprod"):
        """
        Get private key and matching kid for environment
        
        Args:
            environment: "nonprod" or "prod"
            
        Returns:
            Tuple of (private_key_pem, kid)
        """
        prefix = "NP_KEY" if environment == "nonprod" else "P_KEY"
        
        # Find first available key in environment
        for env_var in os.environ:
            if env_var.startswith(prefix + "_"):
                private_key_pem = os.environ[env_var]
                # Handle potential newline issues in PEM (sanity check from Epic troubleshooting)
                # Replace \n with actual newlines if stored as single-line env var
                if '\\n' in private_key_pem and '\n' not in private_key_pem:
                    private_key_pem = private_key_pem.replace('\\n', '\n')
                
                # Extract kid from environment variable name
                # e.g., NP_KEY_2025_08_A -> kid: "2025_08_A"
                kid = env_var.replace(prefix + "_", "")
                return private_key_pem, kid
        
        # Generate fallback if no environment keys found
        from routes.epic_public_routes import generate_fallback_key
        fallback_key = generate_fallback_key()
        fallback_kid = f"{environment}-fallback"
        
        logger.warning(f"No {environment} keys found in environment, using fallback key")
        return fallback_key, fallback_kid
    
    @staticmethod
    def create_client_assertion(client_id: str, token_url: str, environment: str = "nonprod") -> str:
        """
        Create JWT client assertion for Epic OAuth2 authentication
        
        Args:
            client_id: Epic client ID
            token_url: Epic token endpoint URL  
            environment: "nonprod" or "prod"
            
        Returns:
            Signed JWT client assertion
        """
        try:
            # Get private key and kid for environment
            private_key_pem, kid = JWTClientAuthService.get_private_key_and_kid(environment)
            
            # Use private key PEM directly for JWT encoding
            private_key = private_key_pem
            
            # Create JWT claims
            now = datetime.utcnow()
            claims = {
                "iss": client_id,  # Issuer (client ID)
                "sub": client_id,  # Subject (client ID)
                "aud": token_url,  # Audience (Epic token endpoint)
                "jti": f"{client_id}-{int(now.timestamp())}-{os.urandom(8).hex()}",
                "exp": int((now + timedelta(minutes=5)).timestamp()),
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp())
            }
            
            # Create JWT header with matching kid
            headers = {
                "alg": "RS256",
                "typ": "JWT", 
                "kid": kid  # Must match kid in JWKS endpoint
            }
            
            # Debug output for sanity checking (as recommended in Epic troubleshooting)
            import json
            logger.info(f"JWT Client Assertion Debug for {client_id}:")
            logger.info(f"Header:  {json.dumps(headers, separators=(',', ':'))}")
            logger.info(f"Payload: {json.dumps(claims, separators=(',', ':'))}")
            logger.info(f"Token URL (aud): {token_url}")
            logger.info(f"Environment: {environment}")
            logger.info(f"Key ID (kid): {kid}")
            
            # Sign JWT
            token = jwt.encode(
                claims,
                private_key,
                algorithm="RS256",
                headers=headers
            )
            
            logger.info(f"✅ Created JWT client assertion for {client_id} with kid={kid}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create client assertion: {e}")
            raise ValueError(f"JWT client assertion creation failed: {e}")
    
    @staticmethod
    def validate_key_consistency(environment: str = "nonprod") -> bool:
        """
        Validate that JWT kid matches what's published in JWKS
        
        Args:
            environment: "nonprod" or "prod"
            
        Returns:
            True if keys are consistent
        """
        try:
            # Get current key ID
            _, kid = JWTClientAuthService.get_private_key_and_kid(environment)
            
            # Check if this kid exists in JWKS endpoint
            import requests
            base_url = os.environ.get('REPLIT_URL', 'https://localhost:5000')
            
            if environment == "nonprod":
                jwks_url = f"{base_url}/nonprod/.well-known/jwks.json"
            else:
                jwks_url = f"{base_url}/.well-known/jwks.json"
            
            response = requests.get(jwks_url, timeout=5)
            jwks = response.json()
            
            # Check if kid exists in JWKS
            kids_in_jwks = [key.get('kid') for key in jwks.get('keys', [])]
            
            if kid in kids_in_jwks:
                logger.info(f"Key consistency validated: kid={kid} found in JWKS")
                return True
            else:
                logger.error(f"Key inconsistency: kid={kid} not found in JWKS: {kids_in_jwks}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to validate key consistency: {e}")
            return False

# Convenience function for backward compatibility
def create_client_assertion(client_id: str, token_url: str, environment: str = "nonprod") -> str:
    """Create JWT client assertion (backward compatible wrapper)"""
    return JWTClientAuthService.create_client_assertion(client_id, token_url, environment)