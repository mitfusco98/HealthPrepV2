"""
SMART on FHIR API client for EMR integration
Handles authentication and data retrieval from FHIR endpoints
"""

import os
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import json

logger = logging.getLogger(__name__)

class FHIRClient:
    """SMART on FHIR client for EMR integration"""
    
    def __init__(self):
        self.base_url = os.getenv('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
        self.client_id = os.getenv('FHIR_CLIENT_ID', 'health_prep_client')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET', 'default_secret')
        self.access_token = None
        self.token_expires_at = None
        
    def authenticate(self, username: str = None, password: str = None) -> bool:
        """
        Authenticate with FHIR server using client credentials or user credentials
        """
        try:
            auth_url = f"{self.base_url}/oauth2/token"
            
            # Use client credentials flow for now
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'system/Patient.read system/DocumentReference.read system/Condition.read system/Observation.read'
            }
            
            response = requests.post(auth_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now().timestamp() + expires_in
                logger.info("FHIR authentication successful")
                return True
            else:
                logger.error(f"FHIR authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"FHIR authentication error: {str(e)}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for FHIR API requests"""
        if not self.access_token or (self.token_expires_at and datetime.now().timestamp() > self.token_expires_at):
            self.authenticate()
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get patient information by FHIR ID"""
        try:
            url = f"{self.base_url}/Patient/{patient_id}"
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get patient {patient_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, identifier: str = None, name: str = None) -> List[Dict[str, Any]]:
        """Search for patients by identifier or name"""
        try:
            url = f"{self.base_url}/Patient"
            params = {}
            
            if identifier:
                params['identifier'] = identifier
            if name:
                params['name'] = name
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logger.error(f"Failed to search patients: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            return []
    
    def get_patient_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient conditions"""
        try:
            url = f"{self.base_url}/Condition"
            params = {'patient': patient_id}
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logger.error(f"Failed to get conditions for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting conditions for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_documents(self, patient_id: str, document_type: str = None) -> List[Dict[str, Any]]:
        """Get patient documents (DocumentReference resources)"""
        try:
            url = f"{self.base_url}/DocumentReference"
            params = {'patient': patient_id}
            
            if document_type:
                params['type'] = document_type
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logger.error(f"Failed to get documents for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting documents for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_observations(self, patient_id: str, category: str = None) -> List[Dict[str, Any]]:
        """Get patient observations (lab results, vital signs, etc.)"""
        try:
            url = f"{self.base_url}/Observation"
            params = {'patient': patient_id}
            
            if category:
                params['category'] = category
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logger.error(f"Failed to get observations for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting observations for patient {patient_id}: {str(e)}")
            return []
    
    def get_document_content(self, document_url: str) -> Optional[bytes]:
        """Get document content from FHIR document URL"""
        try:
            response = requests.get(document_url, headers=self._get_headers())
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to get document content: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting document content: {str(e)}")
            return None
    
    def create_patient(self, patient_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new patient in FHIR system"""
        try:
            url = f"{self.base_url}/Patient"
            response = requests.post(url, headers=self._get_headers(), json=patient_data)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Failed to create patient: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating patient: {str(e)}")
            return None
    
    def update_patient(self, patient_id: str, patient_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update patient information in FHIR system"""
        try:
            url = f"{self.base_url}/Patient/{patient_id}"
            response = requests.put(url, headers=self._get_headers(), json=patient_data)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to update patient {patient_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating patient {patient_id}: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """Test FHIR server connection"""
        try:
            url = f"{self.base_url}/metadata"
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                logger.info("FHIR connection test successful")
                return True
            else:
                logger.error(f"FHIR connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"FHIR connection test error: {str(e)}")
            return False
