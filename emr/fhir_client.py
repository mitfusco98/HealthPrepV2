"""
SMART on FHIR API client for EMR integration
"""
import requests
import json
import logging
from datetime import datetime
import os

class FHIRClient:
    def __init__(self):
        self.base_url = os.getenv('FHIR_BASE_URL', 'http://hapi.fhir.org/baseR4')
        self.client_id = os.getenv('FHIR_CLIENT_ID', 'health-prep-client')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET', 'default_secret')
        self.access_token = None
        
    def authenticate(self):
        """Authenticate with FHIR server using client credentials"""
        try:
            auth_url = f"{self.base_url}/oauth/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'system/Patient.read system/Observation.read system/DiagnosticReport.read'
            }
            
            response = requests.post(auth_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                logging.info("Successfully authenticated with FHIR server")
                return True
            else:
                logging.error(f"FHIR authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"Error during FHIR authentication: {e}")
            return False
    
    def _make_request(self, endpoint, params=None):
        """Make authenticated request to FHIR server"""
        if not self.access_token:
            if not self.authenticate():
                return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json'
        }
        
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token expired, try to re-authenticate
                if self.authenticate():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        return response.json()
            
            logging.error(f"FHIR request failed: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            logging.error(f"Error making FHIR request: {e}")
            return None
    
    def get_patient(self, patient_id):
        """Get patient resource by ID"""
        return self._make_request(f"Patient/{patient_id}")
    
    def search_patients(self, family_name=None, given_name=None, identifier=None):
        """Search for patients"""
        params = {}
        if family_name:
            params['family'] = family_name
        if given_name:
            params['given'] = given_name
        if identifier:
            params['identifier'] = identifier
        
        return self._make_request("Patient", params)
    
    def get_patient_observations(self, patient_id, code=None, date_from=None):
        """Get observations for a patient"""
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if code:
            params['code'] = code
        if date_from:
            params['date'] = f'ge{date_from.isoformat()}'
        
        return self._make_request("Observation", params)
    
    def get_diagnostic_reports(self, patient_id, category=None, date_from=None):
        """Get diagnostic reports for a patient"""
        params = {
            'patient': patient_id,
            '_sort': '-date'
        }
        
        if category:
            params['category'] = category
        if date_from:
            params['date'] = f'ge{date_from.isoformat()}'
        
        return self._make_request("DiagnosticReport", params)
    
    def get_conditions(self, patient_id):
        """Get conditions for a patient"""
        params = {
            'patient': patient_id,
            'clinical-status': 'active'
        }
        
        return self._make_request("Condition", params)
    
    def get_medications(self, patient_id):
        """Get medications for a patient"""
        params = {
            'patient': patient_id,
            'status': 'active'
        }
        
        return self._make_request("MedicationRequest", params)
    
    def sync_patient_data(self, fhir_patient_id, local_patient_id):
        """Sync patient data from FHIR server to local database"""
        try:
            # Get patient demographics
            patient_data = self.get_patient(fhir_patient_id)
            if not patient_data:
                return False
            
            # Get recent observations (last 2 years)
            from datetime import timedelta
            date_from = datetime.now() - timedelta(days=730)
            observations = self.get_patient_observations(fhir_patient_id, date_from=date_from)
            
            # Get diagnostic reports
            reports = self.get_diagnostic_reports(fhir_patient_id, date_from=date_from)
            
            # Get conditions
            conditions = self.get_conditions(fhir_patient_id)
            
            # Process and store data
            from emr.parser import FHIRParser
            parser = FHIRParser()
            
            parser.process_patient_data(local_patient_id, {
                'patient': patient_data,
                'observations': observations,
                'reports': reports,
                'conditions': conditions
            })
            
            logging.info(f"Successfully synced FHIR data for patient {local_patient_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error syncing patient data: {e}")
            return False
