"""
SMART on FHIR API client for EMR integration
"""
import requests
import json
import os
from datetime import datetime, timedelta
import logging

class FHIRClient:
    """Client for connecting to FHIR-based EMR systems"""
    
    def __init__(self):
        self.base_url = os.environ.get('FHIR_BASE_URL', 'https://sandbox.epic.com/interconnect-fhir-oauth/api/FHIR/R4/')
        self.client_id = os.environ.get('FHIR_CLIENT_ID', 'default_client_id')
        self.client_secret = os.environ.get('FHIR_CLIENT_SECRET', 'default_secret')
        self.access_token = None
        self.token_expires = None
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self):
        """Authenticate with FHIR server using client credentials"""
        try:
            auth_url = f"{self.base_url.rstrip('/')}/oauth2/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'system/Patient.read system/DocumentReference.read system/DiagnosticReport.read'
            }
            
            response = requests.post(auth_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            self.logger.info("Successfully authenticated with FHIR server")
            return True
            
        except Exception as e:
            self.logger.error(f"FHIR authentication failed: {str(e)}")
            return False
    
    def _get_headers(self):
        """Get headers for FHIR API requests"""
        if not self.access_token or (self.token_expires and datetime.now() >= self.token_expires):
            if not self.authenticate():
                raise Exception("Failed to authenticate with FHIR server")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def get_patient(self, patient_id):
        """Retrieve patient information from FHIR server"""
        try:
            url = f"{self.base_url}Patient/{patient_id}"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, given_name=None, family_name=None, identifier=None):
        """Search for patients using FHIR search parameters"""
        try:
            url = f"{self.base_url}Patient"
            params = {}
            
            if given_name:
                params['given'] = given_name
            if family_name:
                params['family'] = family_name
            if identifier:
                params['identifier'] = identifier
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error searching patients: {str(e)}")
            return None
    
    def get_document_references(self, patient_id, date_from=None, date_to=None):
        """Get document references for a patient"""
        try:
            url = f"{self.base_url}DocumentReference"
            params = {
                'patient': patient_id,
                '_sort': '-date'
            }
            
            if date_from:
                params['date'] = f"ge{date_from.isoformat()}"
            if date_to:
                if 'date' in params:
                    params['date'] += f"&date=le{date_to.isoformat()}"
                else:
                    params['date'] = f"le{date_to.isoformat()}"
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error retrieving documents for patient {patient_id}: {str(e)}")
            return None
    
    def get_diagnostic_reports(self, patient_id, category=None, date_from=None):
        """Get diagnostic reports for a patient"""
        try:
            url = f"{self.base_url}DiagnosticReport"
            params = {
                'patient': patient_id,
                '_sort': '-date'
            }
            
            if category:
                params['category'] = category
            if date_from:
                params['date'] = f"ge{date_from.isoformat()}"
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error retrieving diagnostic reports for patient {patient_id}: {str(e)}")
            return None
    
    def get_observations(self, patient_id, code=None, category=None, date_from=None):
        """Get observations (lab results) for a patient"""
        try:
            url = f"{self.base_url}Observation"
            params = {
                'patient': patient_id,
                '_sort': '-date'
            }
            
            if code:
                params['code'] = code
            if category:
                params['category'] = category
            if date_from:
                params['date'] = f"ge{date_from.isoformat()}"
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error retrieving observations for patient {patient_id}: {str(e)}")
            return None
    
    def get_conditions(self, patient_id):
        """Get active conditions for a patient"""
        try:
            url = f"{self.base_url}Condition"
            params = {
                'patient': patient_id,
                'clinical-status': 'active'
            }
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error retrieving conditions for patient {patient_id}: {str(e)}")
            return None
    
    def download_document_content(self, document_url):
        """Download the actual content of a document"""
        try:
            response = requests.get(document_url, headers=self._get_headers())
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error downloading document content: {str(e)}")
            return None
    
    def sync_patient_data(self, patient_mrn):
        """Sync all patient data from FHIR server"""
        # Search for patient by MRN
        patient_bundle = self.search_patients(identifier=patient_mrn)
        
        if not patient_bundle or not patient_bundle.get('entry'):
            self.logger.warning(f"Patient not found with MRN: {patient_mrn}")
            return None
        
        patient_resource = patient_bundle['entry'][0]['resource']
        patient_id = patient_resource['id']
        
        # Sync patient data
        sync_data = {
            'patient': patient_resource,
            'documents': self.get_document_references(patient_id),
            'diagnostic_reports': self.get_diagnostic_reports(patient_id),
            'lab_results': self.get_observations(patient_id, category='laboratory'),
            'conditions': self.get_conditions(patient_id)
        }
        
        return sync_data
