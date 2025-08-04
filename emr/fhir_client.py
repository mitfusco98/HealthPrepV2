"""
SMART on FHIR client for EMR integration.
Handles authentication and data retrieval from FHIR-enabled EMR systems.
"""

import os
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

class FHIRClient:
    """Client for SMART on FHIR integration with EMR systems."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # FHIR server configuration from environment
        self.fhir_base_url = os.getenv('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth/api/v4')
        self.client_id = os.getenv('FHIR_CLIENT_ID', '')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET', '')
        self.redirect_uri = os.getenv('FHIR_REDIRECT_URI', 'http://localhost:5000/fhir/callback')
        
        # OAuth endpoints
        self.auth_url = f"{self.fhir_base_url}/oauth2/authorize"
        self.token_url = f"{self.fhir_base_url}/oauth2/token"
        
        # Current session tokens
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Request session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        })
    
    def get_authorization_url(self, state: str = None) -> str:
        """Get OAuth2 authorization URL for SMART on FHIR launch."""
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'patient/*.read',
            'state': state or 'health-prep-auth'
        }
        
        url = f"{self.auth_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        self.logger.info(f"Generated FHIR authorization URL: {url}")
        
        return url
    
    def exchange_code_for_token(self, code: str, state: str = None) -> Dict:
        """Exchange authorization code for access token."""
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            # Calculate expiration time
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            self.logger.info("Successfully obtained FHIR access token")
            return token_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error exchanging code for token: {e}")
            raise Exception(f"FHIR token exchange failed: {e}")
    
    def refresh_access_token(self) -> Dict:
        """Refresh the access token using refresh token."""
        
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            self.access_token = token_data.get('access_token')
            if 'refresh_token' in token_data:
                self.refresh_token = token_data.get('refresh_token')
            
            # Calculate expiration time
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            self.logger.info("Successfully refreshed FHIR access token")
            return token_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error refreshing token: {e}")
            raise Exception(f"FHIR token refresh failed: {e}")
    
    def ensure_valid_token(self):
        """Ensure we have a valid access token, refreshing if necessary."""
        
        if not self.access_token:
            raise Exception("No access token available. Please authenticate first.")
        
        if self.token_expires_at and datetime.now() >= self.token_expires_at:
            self.logger.info("Access token expired, refreshing...")
            self.refresh_access_token()
    
    def make_fhir_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated FHIR API request."""
        
        self.ensure_valid_token()
        
        url = f"{self.fhir_base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"FHIR request failed: {e}")
            raise Exception(f"FHIR API request failed: {e}")
    
    def get_patient(self, patient_id: str) -> Dict:
        """Get patient resource by ID."""
        
        endpoint = f"Patient/{patient_id}"
        return self.make_fhir_request(endpoint)
    
    def search_patients(self, family_name: str = None, given_name: str = None, 
                       birthdate: str = None, identifier: str = None) -> Dict:
        """Search for patients with given criteria."""
        
        params = {}
        
        if family_name:
            params['family'] = family_name
        if given_name:
            params['given'] = given_name
        if birthdate:
            params['birthdate'] = birthdate
        if identifier:
            params['identifier'] = identifier
        
        return self.make_fhir_request("Patient", params)
    
    def get_patient_documents(self, patient_id: str, category: str = None, 
                            date_from: str = None, date_to: str = None) -> Dict:
        """Get DocumentReference resources for a patient."""
        
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if category:
            params['category'] = category
        if date_from:
            params['date'] = f"ge{date_from}"
        if date_to:
            if 'date' in params:
                params['date'] += f"&date=le{date_to}"
            else:
                params['date'] = f"le{date_to}"
        
        return self.make_fhir_request("DocumentReference", params)
    
    def get_diagnostic_reports(self, patient_id: str, category: str = None,
                             date_from: str = None, date_to: str = None) -> Dict:
        """Get DiagnosticReport resources for a patient."""
        
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if category:
            params['category'] = category
        if date_from:
            params['date'] = f"ge{date_from}"
        if date_to:
            if 'date' in params:
                params['date'] += f"&date=le{date_to}"
            else:
                params['date'] = f"le{date_to}"
        
        return self.make_fhir_request("DiagnosticReport", params)
    
    def get_observations(self, patient_id: str, code: str = None,
                        date_from: str = None, date_to: str = None) -> Dict:
        """Get Observation resources for a patient."""
        
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if code:
            params['code'] = code
        if date_from:
            params['date'] = f"ge{date_from}"
        if date_to:
            if 'date' in params:
                params['date'] += f"&date=le{date_to}"
            else:
                params['date'] = f"le{date_to}"
        
        return self.make_fhir_request("Observation", params)
    
    def get_conditions(self, patient_id: str, clinical_status: str = 'active') -> Dict:
        """Get Condition resources for a patient."""
        
        params = {
            'patient': patient_id,
            'clinical-status': clinical_status
        }
        
        return self.make_fhir_request("Condition", params)
    
    def get_encounters(self, patient_id: str, status: str = None,
                      date_from: str = None, date_to: str = None) -> Dict:
        """Get Encounter resources for a patient."""
        
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if status:
            params['status'] = status
        if date_from:
            params['date'] = f"ge{date_from}"
        if date_to:
            if 'date' in params:
                params['date'] += f"&date=le{date_to}"
            else:
                params['date'] = f"le{date_to}"
        
        return self.make_fhir_request("Encounter", params)
    
    def get_document_content(self, document_reference: Dict) -> Optional[bytes]:
        """Download actual document content from DocumentReference."""
        
        if 'content' not in document_reference:
            return None
        
        for content in document_reference['content']:
            if 'attachment' in content and 'url' in content['attachment']:
                url = content['attachment']['url']
                
                try:
                    self.ensure_valid_token()
                    response = self.session.get(url)
                    response.raise_for_status()
                    
                    return response.content
                    
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error downloading document content: {e}")
                    continue
        
        return None
    
    def test_connection(self) -> Dict:
        """Test FHIR server connection and capabilities."""
        
        try:
            # Test basic connectivity with capability statement
            response = self.session.get(f"{self.fhir_base_url}/metadata")
            response.raise_for_status()
            
            capability_statement = response.json()
            
            return {
                'success': True,
                'server_url': self.fhir_base_url,
                'fhir_version': capability_statement.get('fhirVersion', 'Unknown'),
                'software': capability_statement.get('software', {}),
                'supported_resources': [r['type'] for r in capability_statement.get('rest', [{}])[0].get('resource', [])]
            }
            
        except Exception as e:
            self.logger.error(f"FHIR connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'server_url': self.fhir_base_url
            }
