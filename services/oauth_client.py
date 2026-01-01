"""
OAuth2 Client Service for SMART on FHIR Authentication
Handles authorization URL building, token exchange, and client assertion creation
"""

import os
import jwt
import secrets
import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
import requests

from services.smart_discovery import smart_discovery
from services.jwt_client_auth import JWTClientAuthService

logger = logging.getLogger(__name__)

class OAuthClientService:
    """Service for SMART on FHIR OAuth2 authentication flows"""
    
    def __init__(self, client_id: str = None, redirect_uri: str = None, environment: str = "nonprod"):
        """
        Initialize OAuth client
        
        Args:
            client_id: OAuth2 client ID
            redirect_uri: Redirect URI for authorization callback
            environment: "nonprod" or "prod"
        """
        self.client_id = client_id or os.environ.get('NONPROD_CLIENT_ID')
        self.redirect_uri = redirect_uri or os.environ.get('REDIRECT_URI')
        self.environment = environment
        
        if not self.client_id:
            logger.warning("No client_id provided for OAuth client")
            raise ValueError("client_id is required for OAuth client")
        if not self.redirect_uri:
            logger.warning("No redirect_uri provided for OAuth client")
            raise ValueError("redirect_uri is required for OAuth client")
    
    def build_authorization_url(self, iss: str, scopes: list = None, state: str = None, 
                               launch: str = None, aud: str = None) -> Tuple[str, str]:
        """
        Build SMART on FHIR authorization URL
        
        Args:
            iss: Issuer URL (FHIR server base URL)
            scopes: List of requested scopes
            state: OAuth2 state parameter (generated if not provided)
            launch: Launch context token (for EHR launch)
            aud: Audience parameter (FHIR server URL)
            
        Returns:
            Tuple of (authorization_url, state)
        """
        try:
            # Get authorization endpoint from SMART discovery
            config = smart_discovery.fetch(iss)
            auth_endpoint = config['authorization_endpoint']
            
            # Generate state if not provided
            if not state:
                state = secrets.token_urlsafe(32)
            
            # Default scopes for SMART on FHIR
            if not scopes:
                scopes = [
                    'openid', 'profile', 'fhirUser',
                    'patient/Patient.read',
                    'patient/Observation.read', 
                    'patient/DocumentReference.read',
                    'patient/Condition.read',
                    'patient/DiagnosticReport.read'
                ]
            
            # Build authorization parameters
            params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'scope': ' '.join(scopes),
                'state': state,
                'aud': aud or iss
            }
            
            # Add launch context if provided (EHR launch)
            if launch:
                params['launch'] = launch
            
            # Build authorization URL
            auth_url = f"{auth_endpoint}?{urlencode(params)}"
            
            logger.info(f"Built authorization URL for ISS: {iss}")
            logger.debug(f"Scopes requested: {scopes}")
            
            return auth_url, state
            
        except Exception as e:
            logger.error(f"Failed to build authorization URL: {e}")
            raise Exception(f"Authorization URL building failed: {e}")
    
    def exchange_code_for_token(self, iss: str, code: str, state: str = None) -> Dict:
        """
        Exchange authorization code for access token
        
        Args:
            iss: Issuer URL
            code: Authorization code from callback
            state: OAuth2 state parameter for validation
            
        Returns:
            Token response dictionary
        """
        try:
            # Get token endpoint from SMART discovery
            config = smart_discovery.fetch(iss)
            token_endpoint = config['token_endpoint']
            
            # Create client assertion for private_key_jwt authentication
            client_assertion = JWTClientAuthService.create_client_assertion(
                client_id=self.client_id,
                token_url=token_endpoint,
                environment=self.environment
            )
            
            # Prepare token request
            token_data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': client_assertion
            }
            
            # Make token request
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'User-Agent': 'HealthPrep-SMART-Client/1.0'
            }
            
            logger.info(f"Exchanging code for token at {token_endpoint}")
            response = requests.post(token_endpoint, data=token_data, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_response = response.json()
            
            # Validate token response
            if 'access_token' not in token_response:
                raise ValueError("No access_token in token response")
            
            logger.info("Successfully exchanged code for access token")
            
            # Parse additional token information
            token_info = {
                'access_token': token_response['access_token'],
                'token_type': token_response.get('token_type', 'Bearer'),
                'expires_in': token_response.get('expires_in'),
                'refresh_token': token_response.get('refresh_token'),
                'scope': token_response.get('scope'),
                'patient': token_response.get('patient'),
                'encounter': token_response.get('encounter'),
                'user': token_response.get('user'),
                'issued_at': datetime.utcnow()
            }
            
            return token_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange HTTP error: {e}")
            raise Exception(f"Token exchange failed: {e}")
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            raise Exception(f"Token exchange failed: {e}")
    
    def refresh_access_token(self, iss: str, refresh_token: str) -> Dict:
        """
        Refresh access token using refresh token
        
        Args:
            iss: Issuer URL
            refresh_token: Refresh token
            
        Returns:
            New token response dictionary
        """
        try:
            # Get token endpoint from SMART discovery
            config = smart_discovery.fetch(iss)
            token_endpoint = config['token_endpoint']
            
            # Create client assertion
            client_assertion = JWTClientAuthService.create_client_assertion(
                client_id=self.client_id,
                token_url=token_endpoint,
                environment=self.environment
            )
            
            # Prepare refresh request
            refresh_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': client_assertion
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            logger.info("Refreshing access token")
            response = requests.post(token_endpoint, data=refresh_data, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_response = response.json()
            
            if 'access_token' not in token_response:
                raise ValueError("No access_token in refresh response")
            
            logger.info("Successfully refreshed access token")
            
            # Parse refreshed token information
            token_info = {
                'access_token': token_response['access_token'],
                'token_type': token_response.get('token_type', 'Bearer'),
                'expires_in': token_response.get('expires_in'),
                'refresh_token': token_response.get('refresh_token', refresh_token),  # Keep old if new not provided
                'scope': token_response.get('scope'),
                'patient': token_response.get('patient'),
                'encounter': token_response.get('encounter'),
                'user': token_response.get('user'),
                'issued_at': datetime.utcnow()
            }
            
            return token_info
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise Exception(f"Token refresh failed: {e}")
    
    def validate_state(self, received_state: str, expected_state: str) -> bool:
        """
        Validate OAuth2 state parameter
        
        Args:
            received_state: State received in callback
            expected_state: Expected state value
            
        Returns:
            True if states match, False otherwise
        """
        if not received_state or not expected_state:
            logger.warning("Missing state parameter in OAuth callback")
            return False
        
        if received_state != expected_state:
            logger.error("OAuth state mismatch - possible CSRF attack")
            return False
        
        return True
    
    def _fetch_jwks(self, iss: str) -> Optional[Dict]:
        """
        Fetch JWKS from the OAuth provider's discovery document
        
        Args:
            iss: Issuer URL
            
        Returns:
            JWKS dictionary or None if unavailable
        """
        try:
            config = smart_discovery.fetch(iss)
            jwks_uri = config.get('jwks_uri')
            
            if not jwks_uri:
                logger.warning(f"No jwks_uri found in discovery for {iss}")
                return None
            
            response = requests.get(jwks_uri, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch JWKS from {iss}: {e}")
            return None
    
    def _decode_and_verify_id_token(self, id_token: str, iss: str = None) -> Optional[Dict]:
        """
        Decode and verify an ID token with signature validation
        
        Args:
            id_token: The JWT ID token string
            iss: Issuer URL for JWKS lookup
            
        Returns:
            Decoded token claims if valid, None otherwise
        """
        try:
            # First, decode header to get the key ID (kid)
            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get('kid')
            alg = unverified_header.get('alg', 'RS256')
            
            # Try to fetch JWKS and verify signature
            if iss:
                jwks = self._fetch_jwks(iss)
                if jwks and 'keys' in jwks:
                    # Find the matching key
                    for key_data in jwks['keys']:
                        if key_data.get('kid') == kid or kid is None:
                            try:
                                from jwt import PyJWK
                                public_key = PyJWK.from_dict(key_data).key
                                
                                # Decode with signature verification
                                claims = jwt.decode(
                                    id_token,
                                    public_key,
                                    algorithms=[alg],
                                    options={
                                        "verify_aud": False,  # Audience varies by provider
                                        "verify_iss": False,  # ISS format varies
                                    }
                                )
                                logger.info("ID token signature verified successfully")
                                return claims
                            except jwt.InvalidSignatureError:
                                logger.error("ID token signature verification failed - token may be tampered")
                                return None
                            except Exception as e:
                                logger.warning(f"Key verification attempt failed: {e}")
                                continue
            
            # If verification couldn't be performed, log security warning and reject
            logger.error(
                "SECURITY: Unable to verify ID token signature - "
                "JWKS unavailable or key not found. Token rejected for security."
            )
            return None
            
        except jwt.ExpiredSignatureError:
            logger.error("ID token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid ID token: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to decode/verify ID token: {e}")
            return None
    
    def parse_fhir_user(self, token_response: Dict) -> Optional[Dict]:
        """
        Parse FHIR user information from token response
        
        Args:
            token_response: Token response from OAuth server
            
        Returns:
            Parsed user information or None
        """
        try:
            # SMART on FHIR user information
            user_info = {}
            
            if 'user' in token_response:
                user_info['fhir_user'] = token_response['user']
            
            if 'patient' in token_response:
                user_info['patient_id'] = token_response['patient']
            
            if 'encounter' in token_response:
                user_info['encounter_id'] = token_response['encounter']
            
            # Parse ID token if present
            if 'id_token' in token_response:
                try:
                    id_token_claims = self._decode_and_verify_id_token(
                        token_response['id_token'],
                        token_response.get('iss')
                    )
                    if id_token_claims:
                        user_info['id_token_claims'] = id_token_claims
                except Exception as e:
                    logger.warning(f"Failed to parse ID token: {e}")
            
            return user_info if user_info else None
            
        except Exception as e:
            logger.error(f"Failed to parse FHIR user information: {e}")
            return None
    
    def create_fhir_headers(self, access_token: str) -> Dict[str, str]:
        """
        Create headers for FHIR API requests
        
        Args:
            access_token: Access token from OAuth flow
            
        Returns:
            Headers dictionary for FHIR requests
        """
        return {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json',
            'User-Agent': 'HealthPrep-SMART-Client/1.0'
        }

# Global OAuth client instance (will be initialized when needed with environment variables)
oauth_client = None

def get_oauth_client(client_id: str = None, redirect_uri: str = None, environment: str = "nonprod") -> OAuthClientService:
    """Get or create OAuth client instance with provided or environment variables"""
    global oauth_client
    if oauth_client is None:
        oauth_client = OAuthClientService(client_id, redirect_uri, environment)
    return oauth_client