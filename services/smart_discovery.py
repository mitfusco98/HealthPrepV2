"""
SMART Discovery Service
Provides cached discovery configuration for SMART on FHIR endpoints
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class SMARTDiscoveryService:
    """Service for fetching and caching SMART configuration metadata"""
    
    def __init__(self):
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes default cache
    
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
            well_known_url = f"{iss.rstrip('/')}/.well-known/smart-configuration"
            logger.info(f"Fetching SMART configuration from {well_known_url}")
            
            response = requests.get(well_known_url, timeout=10)
            response.raise_for_status()
            
            config = response.json()
            
            # Validate required fields
            required_fields = ['authorization_endpoint', 'token_endpoint']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field '{field}' in SMART configuration")
            
            # Cache the configuration
            self._cache[cache_key] = (config, current_time)
            logger.info(f"Successfully fetched and cached SMART config for {iss}")
            
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