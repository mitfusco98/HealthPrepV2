"""
SMART on FHIR API client for EMR integration.
Handles authentication and data retrieval from FHIR-compatible EMRs.
"""

import logging
import requests
from typing import Dict, List, Optional, Any
import os
from datetime import datetime, timedelta
import json

class FHIRClient:
    """FHIR client for EMR integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = os.getenv('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
        self.client_id = os.getenv('FHIR_CLIENT_ID', 'health-prep-client')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET', 'default-secret')
        self.access_token = None
        self.token_expires_at = None
        
        # Common FHIR endpoints
        self.endpoints = {
            'patients': '/Patient',
            'observations': '/Observation',
            'diagnostic_reports': '/DiagnosticReport',
            'document_references': '/DocumentReference',
            'conditions': '/Condition',
            'procedures': '/Procedure',
            'encounters': '/Encounter'
        }
    
    def authenticate(self) -> bool:
        """Authenticate with FHIR server using client credentials"""
        try:
            auth_url = f"{self.base_url}/oauth2/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'system/Patient.read system/Observation.read system/DiagnosticReport.read system/DocumentReference.read'
            }
            
            response = requests.post(auth_url, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)  # 1 minute buffer
            
            self.logger.info("Successfully authenticated with FHIR server")
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"FHIR authentication failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during FHIR authentication: {str(e)}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expires_at and datetime.utcnow() >= self.token_expires_at):
            return self.authenticate()
        return True
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to FHIR server"""
        if not self._ensure_authenticated():
            return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/fhir+json',
                'Content-Type': 'application/fhir+json'
            }
            
            response = requests.get(url, headers=headers, params=params or {}, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            self.logger.error(f"FHIR request failed for {endpoint}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during FHIR request: {str(e)}")
            return None
    
    def get_patient_by_mrn(self, mrn: str) -> Optional[Dict]:
        """Get patient by medical record number"""
        params = {
            'identifier': f'urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.0|{mrn}'
        }
        
        response = self._make_request(self.endpoints['patients'], params)
        if response and response.get('total', 0) > 0:
            entries = response.get('entry', [])
            if entries:
                return entries[0].get('resource')
        
        return None
    
    def get_patient_observations(self, patient_id: str, category: Optional[str] = None, 
                               date_range: Optional[tuple] = None) -> List[Dict]:
        """Get observations for a patient"""
        params = {
            'patient': patient_id,
            '_count': 1000
        }
        
        if category:
            params['category'] = category
        
        if date_range:
            start_date, end_date = date_range
            params['date'] = f'ge{start_date.isoformat()}'
            if end_date:
                params['date'] += f'&date=le{end_date.isoformat()}'
        
        response = self._make_request(self.endpoints['observations'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def get_patient_diagnostic_reports(self, patient_id: str, date_range: Optional[tuple] = None) -> List[Dict]:
        """Get diagnostic reports for a patient"""
        params = {
            'patient': patient_id,
            '_count': 1000
        }
        
        if date_range:
            start_date, end_date = date_range
            params['date'] = f'ge{start_date.isoformat()}'
            if end_date:
                params['date'] += f'&date=le{end_date.isoformat()}'
        
        response = self._make_request(self.endpoints['diagnostic_reports'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def get_patient_documents(self, patient_id: str, date_range: Optional[tuple] = None) -> List[Dict]:
        """Get document references for a patient"""
        params = {
            'patient': patient_id,
            '_count': 1000
        }
        
        if date_range:
            start_date, end_date = date_range
            params['date'] = f'ge{start_date.isoformat()}'
            if end_date:
                params['date'] += f'&date=le{end_date.isoformat()}'
        
        response = self._make_request(self.endpoints['document_references'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def get_patient_conditions(self, patient_id: str) -> List[Dict]:
        """Get active conditions for a patient"""
        params = {
            'patient': patient_id,
            'clinical-status': 'active',
            '_count': 1000
        }
        
        response = self._make_request(self.endpoints['conditions'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def get_patient_procedures(self, patient_id: str, date_range: Optional[tuple] = None) -> List[Dict]:
        """Get procedures for a patient"""
        params = {
            'patient': patient_id,
            '_count': 1000
        }
        
        if date_range:
            start_date, end_date = date_range
            params['date'] = f'ge{start_date.isoformat()}'
            if end_date:
                params['date'] += f'&date=le{end_date.isoformat()}'
        
        response = self._make_request(self.endpoints['procedures'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def download_document(self, document_url: str) -> Optional[bytes]:
        """Download document content"""
        if not self._ensure_authenticated():
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': '*/*'
            }
            
            response = requests.get(document_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            return response.content
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to download document from {document_url}: {str(e)}")
            return None
    
    def search_patients(self, search_params: Dict[str, str]) -> List[Dict]:
        """Search for patients with given parameters"""
        params = search_params.copy()
        params['_count'] = params.get('_count', 50)
        
        response = self._make_request(self.endpoints['patients'], params)
        if response:
            return [entry.get('resource') for entry in response.get('entry', [])]
        
        return []
    
    def get_capability_statement(self) -> Optional[Dict]:
        """Get server capability statement"""
        return self._make_request('/metadata')
    
    def test_connection(self) -> bool:
        """Test connection to FHIR server"""
        try:
            capability = self.get_capability_statement()
            return capability is not None
        except Exception as e:
            self.logger.error(f"FHIR connection test failed: {str(e)}")
            return False
