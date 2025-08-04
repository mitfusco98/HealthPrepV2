import os
import requests
import json
from datetime import datetime
import logging

class FHIRClient:
    """SMART on FHIR client for EMR integration"""
    
    def __init__(self):
        self.base_url = os.environ.get('FHIR_BASE_URL', 'https://api.logicahealth.org/demo/open')
        self.client_id = os.environ.get('FHIR_CLIENT_ID', 'demo_client')
        self.access_token = None
        self.headers = {
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def authenticate(self, username=None, password=None):
        """Authenticate with FHIR server"""
        # For demo purposes, we'll use a simple token approach
        # In production, this would implement OAuth2/SMART on FHIR
        auth_token = os.environ.get('FHIR_ACCESS_TOKEN', 'demo_token')
        if auth_token:
            self.access_token = auth_token
            self.headers['Authorization'] = f'Bearer {auth_token}'
            return True
        
        logging.warning("No FHIR access token configured")
        return False
    
    def get_patient(self, patient_id):
        """Get patient resource by ID"""
        try:
            url = f"{self.base_url}/Patient/{patient_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get patient {patient_id}: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logging.error(f"Error fetching patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, family_name=None, given_name=None, identifier=None):
        """Search for patients"""
        try:
            url = f"{self.base_url}/Patient"
            params = {}
            
            if family_name:
                params['family'] = family_name
            if given_name:
                params['given'] = given_name
            if identifier:
                params['identifier'] = identifier
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logging.error(f"Failed to search patients: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logging.error(f"Error searching patients: {str(e)}")
            return []
    
    def get_patient_documents(self, patient_id):
        """Get DocumentReference resources for patient"""
        try:
            url = f"{self.base_url}/DocumentReference"
            params = {'patient': patient_id}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logging.error(f"Failed to get documents for patient {patient_id}: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logging.error(f"Error fetching documents for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_observations(self, patient_id, category=None):
        """Get Observation resources for patient"""
        try:
            url = f"{self.base_url}/Observation"
            params = {'patient': patient_id}
            
            if category:
                params['category'] = category
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logging.error(f"Failed to get observations for patient {patient_id}: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logging.error(f"Error fetching observations for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_conditions(self, patient_id):
        """Get Condition resources for patient"""
        try:
            url = f"{self.base_url}/Condition"
            params = {'patient': patient_id}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                bundle = response.json()
                return bundle.get('entry', [])
            else:
                logging.error(f"Failed to get conditions for patient {patient_id}: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logging.error(f"Error fetching conditions for patient {patient_id}: {str(e)}")
            return []
    
    def download_document(self, document_url):
        """Download document content"""
        try:
            response = requests.get(document_url, headers=self.headers, timeout=60)
            
            if response.status_code == 200:
                return response.content
            else:
                logging.error(f"Failed to download document: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logging.error(f"Error downloading document: {str(e)}")
            return None
