"""
SMART Discovery Service
Provides cached discovery configuration for SMART on FHIR endpoints
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from functools import lru_cache
import time
import urllib.parse

logger = logging.getLogger(__name__)

class SMARTDiscoveryService:
    """Service for fetching and caching SMART configuration metadata"""
    
    def __init__(self):
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes default cache
        
        # Epic fallback endpoints (when discovery fails)
        self._epic_fallbacks = {
            'https://fhir.epic.com/interconnect-fhir-oauth': {
                'authorization_endpoint': 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize',
                'token_endpoint': 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token',
                'scopes_supported': ['patient/Patient.read', 'patient/Observation.read', 'patient/DocumentReference.read']
            }
        }
    
    def fetch(self, iss: str, cache_timeout: int = 300) -> Dict:
        """
        Fetch SMART configuration from issuer's .well-known endpoint
        
        Args:
            iss: Issuer URL (e.g., https://fhir.epic.com/interconnect-fhir-oauth)
            cache_timeout: Cache timeout in seconds (default 5 minutes)
            
        Returns:
            SMART configuration dictionary
        """
        cache_key = f"smart_config_{iss}"
        current_time = time.time()
        
        # Check cache first
        if cache_key in self._cache:
            config, timestamp = self._cache[cache_key]
            if current_time - timestamp < cache_timeout:
                logger.debug(f"Using cached SMART config for {iss}")
                return config
        
        # Fetch fresh configuration
        try:
            # Try multiple discovery endpoints
            discovery_urls = [
                f"{iss.rstrip('/')}/.well-known/smart-configuration",
                f"{iss.rstrip('/')}/.well-known/openid_configuration",
                f"{iss.rstrip('/')}/metadata/.well-known/smart-configuration"
            ]
            
            config = None
            last_error = None
            
            for url in discovery_urls:
                try:
                    logger.info(f"Trying SMART discovery at {url}")
                    response = requests.get(url, timeout=10, headers={
                        'Accept': 'application/json',
                        'User-Agent': 'HealthPrep-SMART-Client/1.0'
                    })
                    response.raise_for_status()
                    config = response.json()
                    logger.info(f"Successfully discovered SMART config at {url}")
                    break
                except Exception as e:
                    last_error = e
                    logger.debug(f"Discovery failed at {url}: {e}")
                    continue
            
            # If all discovery methods fail, try fallback for known ISS
            if not config:
                config = self._get_fallback_config(iss)
                if config:
                    logger.warning(f"Using fallback SMART config for {iss}")
                else:
                    raise last_error or Exception("All discovery methods failed")
            
            # Validate required fields
            required_fields = ['authorization_endpoint', 'token_endpoint']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field '{field}' in SMART configuration")
            
            # Cache the configuration
            self._cache[cache_key] = (config, current_time)
            logger.info(f"Successfully cached SMART config for {iss}")
            
            return config
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch SMART configuration from {iss}: {e}")
            raise Exception(f"SMART discovery failed for {iss}: {e}")
        except Exception as e:
            logger.error(f"Error processing SMART configuration: {e}")
            raise

    def get_authorization_endpoint(self, iss: str) -> str:
        """Get authorization endpoint from SMART configuration"""
        config = self.fetch(iss)
        return config['authorization_endpoint']
    
    def get_token_endpoint(self, iss: str) -> str:
        """Get token endpoint from SMART configuration"""
        config = self.fetch(iss)
        return config['token_endpoint']
    
    def get_scopes_supported(self, iss: str) -> list:
        """Get supported scopes from SMART configuration"""
        config = self.fetch(iss)
        return config.get('scopes_supported', [])
    
    def _get_fallback_config(self, iss: str) -> Optional[Dict]:
        """Get fallback configuration for known Epic ISS endpoints"""
        # Normalize ISS URL
        normalized_iss = iss.rstrip('/')
        
        # Check exact match first
        if normalized_iss in self._epic_fallbacks:
            return self._epic_fallbacks[normalized_iss].copy()
        
        # Check if it's an Epic URL pattern
        if 'epic.com' in normalized_iss.lower():
            # Use generic Epic fallback
            base_url = normalized_iss
            return {
                'authorization_endpoint': f"{base_url}/oauth2/authorize",
                'token_endpoint': f"{base_url}/oauth2/token",
                'scopes_supported': ['patient/Patient.read', 'patient/Observation.read', 'patient/DocumentReference.read'],
                'fallback': True
            }
        
        return None
    
    def add_fallback_config(self, iss: str, config: Dict):
        """Add custom fallback configuration for an ISS"""
        self._epic_fallbacks[iss.rstrip('/')] = config
        logger.info(f"Added fallback config for {iss}")
    
    def test_endpoints(self, iss: str) -> Dict[str, bool]:
        """Test reachability of discovered endpoints"""
        try:
            config = self.fetch(iss)
            results = {}
            
            # Test authorization endpoint
            try:
                auth_response = requests.head(config['authorization_endpoint'], timeout=5)
                results['authorization_endpoint'] = auth_response.status_code < 500
            except:
                results['authorization_endpoint'] = False
            
            # Test token endpoint
            try:
                token_response = requests.head(config['token_endpoint'], timeout=5)
                results['token_endpoint'] = token_response.status_code < 500
            except:
                results['token_endpoint'] = False
                
            return results
        except Exception as e:
            logger.error(f"Failed to test endpoints for {iss}: {e}")
            return {'authorization_endpoint': False, 'token_endpoint': False}
    
    def clear_cache(self, iss: Optional[str] = None):
        """Clear cache for specific issuer or all cache"""
        if iss:
            cache_key = f"smart_config_{iss}"
            self._cache.pop(cache_key, None)
            logger.info(f"Cleared SMART config cache for {iss}")
        else:
            self._cache.clear()
            logger.info("Cleared all SMART config cache")

# Global instance
smart_discovery = SMARTDiscoveryService()