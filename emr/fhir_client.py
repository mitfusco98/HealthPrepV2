"""
SMART on FHIR API client for EMR integration
Handles authentication and data retrieval from FHIR-compliant EMRs
"""
import requests
import json
import logging
from datetime import datetime
from config.settings import FHIR_BASE_URL, FHIR_CLIENT_ID, FHIR_CLIENT_SECRET

logger = logging.getLogger(__name__)

class FHIRClient:
    """Client for connecting to FHIR-compliant EMR systems"""
    
    def __init__(self, base_url=None, client_id=None, client_secret=None):
        self.base_url = base_url or FHIR_BASE_URL
        self.client_id = client_id or FHIR_CLIENT_ID
        self.client_secret = client_secret or FHIR_CLIENT_SECRET
        self.access_token = None
        self.token_expires = None
        
    def authenticate(self):
        """Authenticate with the FHIR server using OAuth2"""
        auth_url = f"{self.base_url}/auth/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'patient/*.read'
        }
        
        try:
            response = requests.post(auth_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires = datetime.utcnow().timestamp() + token_data.get('expires_in', 3600)
            
            logger.info("Successfully authenticated with FHIR server")
            return True
            
        except requests.RequestException as e:
            logger.error(f"FHIR authentication failed: {e}")
            return False
    
    def is_token_valid(self):
        """Check if the current access token is still valid"""
        if not self.access_token or not self.token_expires:
            return False
        
        return datetime.utcnow().timestamp() < self.token_expires
    
    def ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.is_token_valid():
            return self.authenticate()
        return True
    
    def get_headers(self):
        """Get HTTP headers for FHIR requests"""
        if not self.ensure_authenticated():
            raise Exception("Failed to authenticate with FHIR server")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def get_patient(self, patient_id):
        """Get patient resource by ID"""
        url = f"{self.base_url}/Patient/{patient_id}"
        
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch patient {patient_id}: {e}")
            return None
    
    def search_patients(self, family_name=None, given_name=None, identifier=None):
        """Search for patients"""
        url = f"{self.base_url}/Patient"
        params = {}
        
        if family_name:
            params['family'] = family_name
        if given_name:
            params['given'] = given_name
        if identifier:
            params['identifier'] = identifier
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Patient search failed: {e}")
            return None
    
    def get_patient_documents(self, patient_id):
        """Get all DocumentReference resources for a patient"""
        url = f"{self.base_url}/DocumentReference"
        params = {'patient': patient_id}
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch documents for patient {patient_id}: {e}")
            return None
    
    def get_patient_observations(self, patient_id, category=None):
        """Get Observation resources for a patient"""
        url = f"{self.base_url}/Observation"
        params = {'patient': patient_id}
        
        if category:
            params['category'] = category
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch observations for patient {patient_id}: {e}")
            return None
    
    def get_patient_conditions(self, patient_id):
        """Get Condition resources for a patient"""
        url = f"{self.base_url}/Condition"
        params = {'patient': patient_id}
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch conditions for patient {patient_id}: {e}")
            return None
    
    def get_patient_encounters(self, patient_id):
        """Get Encounter resources for a patient"""
        url = f"{self.base_url}/Encounter"
        params = {'patient': patient_id}
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch encounters for patient {patient_id}: {e}")
            return None
    
    def download_document(self, document_url):
        """Download a document from a FHIR DocumentReference"""
        try:
            response = requests.get(document_url, headers=self.get_headers())
            response.raise_for_status()
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"Failed to download document from {document_url}: {e}")
            return None
    
    def create_document_reference(self, patient_id, document_data):
        """Create a new DocumentReference resource"""
        url = f"{self.base_url}/DocumentReference"
        
        fhir_document = {
            "resourceType": "DocumentReference",
            "status": "current",
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "content": [{
                "attachment": {
                    "contentType": document_data.get('content_type', 'application/pdf'),
                    "title": document_data.get('title', 'Uploaded Document'),
                    "creation": document_data.get('creation_date', datetime.utcnow().isoformat())
                }
            }]
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(), json=fhir_document)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Failed to create document reference: {e}")
            return None
