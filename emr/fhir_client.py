"""
SMART on FHIR API client for EMR integration
"""
import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class FHIRClient:
    """SMART on FHIR client for connecting to EMR systems"""
    
    def __init__(self):
        self.base_url = os.getenv('FHIR_BASE_URL', 'https://api.example.com/fhir')
        self.client_id = os.getenv('FHIR_CLIENT_ID', 'health-prep-client')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET', 'default-secret')
        self.access_token = None
        self.token_expires_at = None
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        })
    
    def authenticate(self) -> bool:
        """Authenticate with FHIR server using client credentials"""
        try:
            auth_url = urljoin(self.base_url, 'auth/token')
            
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'system/Patient.read system/DocumentReference.read system/DiagnosticReport.read'
            }
            
            response = self.session.post(auth_url, data=auth_data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update session headers with token
                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_token}'
                })
                
                logger.info("Successfully authenticated with FHIR server")
                return True
            else:
                logger.error(f"FHIR authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error during FHIR authentication: {str(e)}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            return self.authenticate()
        return True
    
    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get patient by FHIR ID"""
        if not self._ensure_authenticated():
            return None
        
        try:
            url = urljoin(self.base_url, f'Patient/{patient_id}')
            response = self.session.get(url)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Patient {patient_id} not found")
                return None
            else:
                logger.error(f"Error fetching patient {patient_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, search_params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Search for patients using FHIR search parameters"""
        if not self._ensure_authenticated():
            return []
        
        try:
            url = urljoin(self.base_url, 'Patient')
            response = self.session.get(url, params=search_params)
            
            if response.status_code == 200:
                bundle = response.json()
                patients = []
                
                for entry in bundle.get('entry', []):
                    if entry.get('resource', {}).get('resourceType') == 'Patient':
                        patients.append(entry['resource'])
                
                return patients
            else:
                logger.error(f"Error searching patients: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            return []
    
    def get_patient_documents(self, patient_id: str, document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documents for a patient"""
        if not self._ensure_authenticated():
            return []
        
        try:
            search_params = {
                'patient': patient_id,
                '_sort': '-date'
            }
            
            if document_type:
                search_params['type'] = document_type
            
            url = urljoin(self.base_url, 'DocumentReference')
            response = self.session.get(url, params=search_params)
            
            if response.status_code == 200:
                bundle = response.json()
                documents = []
                
                for entry in bundle.get('entry', []):
                    if entry.get('resource', {}).get('resourceType') == 'DocumentReference':
                        documents.append(entry['resource'])
                
                return documents
            else:
                logger.error(f"Error fetching documents for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching documents for patient {patient_id}: {str(e)}")
            return []
    
    def get_diagnostic_reports(self, patient_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get diagnostic reports for a patient"""
        if not self._ensure_authenticated():
            return []
        
        try:
            search_params = {
                'patient': patient_id,
                '_sort': '-date'
            }
            
            if category:
                search_params['category'] = category
            
            url = urljoin(self.base_url, 'DiagnosticReport')
            response = self.session.get(url, params=search_params)
            
            if response.status_code == 200:
                bundle = response.json()
                reports = []
                
                for entry in bundle.get('entry', []):
                    if entry.get('resource', {}).get('resourceType') == 'DiagnosticReport':
                        reports.append(entry['resource'])
                
                return reports
            else:
                logger.error(f"Error fetching diagnostic reports for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching diagnostic reports for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get conditions for a patient"""
        if not self._ensure_authenticated():
            return []
        
        try:
            search_params = {
                'patient': patient_id,
                'clinical-status': 'active'
            }
            
            url = urljoin(self.base_url, 'Condition')
            response = self.session.get(url, params=search_params)
            
            if response.status_code == 200:
                bundle = response.json()
                conditions = []
                
                for entry in bundle.get('entry', []):
                    if entry.get('resource', {}).get('resourceType') == 'Condition':
                        conditions.append(entry['resource'])
                
                return conditions
            else:
                logger.error(f"Error fetching conditions for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching conditions for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_observations(self, patient_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get observations for a patient"""
        if not self._ensure_authenticated():
            return []
        
        try:
            search_params = {
                'patient': patient_id,
                '_sort': '-date',
                '_count': '100'
            }
            
            if category:
                search_params['category'] = category
            
            url = urljoin(self.base_url, 'Observation')
            response = self.session.get(url, params=search_params)
            
            if response.status_code == 200:
                bundle = response.json()
                observations = []
                
                for entry in bundle.get('entry', []):
                    if entry.get('resource', {}).get('resourceType') == 'Observation':
                        observations.append(entry['resource'])
                
                return observations
            else:
                logger.error(f"Error fetching observations for patient {patient_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching observations for patient {patient_id}: {str(e)}")
            return []
    
    def download_document_content(self, document_reference: Dict[str, Any]) -> Optional[bytes]:
        """Download the actual content of a document"""
        if not self._ensure_authenticated():
            return None
        
        try:
            content = document_reference.get('content', [])
            if not content:
                return None
            
            attachment = content[0].get('attachment', {})
            url = attachment.get('url')
            
            if not url:
                return None
            
            response = self.session.get(url)
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Error downloading document content: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading document content: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to FHIR server"""
        try:
            if not self._ensure_authenticated():
                return False
            
            url = urljoin(self.base_url, 'metadata')
            response = self.session.get(url)
            
            if response.status_code == 200:
                logger.info("FHIR server connection test successful")
                return True
            else:
                logger.error(f"FHIR server connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"FHIR server connection test error: {str(e)}")
            return False

# Global FHIR client instance
fhir_client = FHIRClient()
