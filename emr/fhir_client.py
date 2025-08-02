"""
SMART on FHIR API client for EMR integration
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FHIRClient:
    """Client for connecting to FHIR-enabled EMR systems"""
    
    def __init__(self):
        self.base_url = os.environ.get("FHIR_BASE_URL", "")
        self.client_id = os.environ.get("FHIR_CLIENT_ID", "")
        self.client_secret = os.environ.get("FHIR_CLIENT_SECRET", "")
        self.access_token = None
        self.token_expiry = None
        
        # FHIR version
        self.fhir_version = "R4"
        
        # Request session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        })
    
    def authenticate(self) -> bool:
        """
        Authenticate with FHIR server using client credentials
        """
        if not self.base_url or not self.client_id:
            logger.warning("FHIR credentials not configured")
            return False
        
        try:
            auth_url = f"{self.base_url}/auth/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'patient/*.read'
            }
            
            response = requests.post(auth_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            
            self.token_expiry = datetime.utcnow().timestamp() + expires_in
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            logger.info("FHIR authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"FHIR authentication failed: {str(e)}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expiry and datetime.utcnow().timestamp() >= self.token_expiry):
            return self.authenticate()
        return True
    
    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get patient resource by ID
        """
        if not self._ensure_authenticated():
            return None
        
        try:
            url = f"{self.base_url}/Patient/{patient_id}"
            response = self.session.get(url)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, **params) -> List[Dict[str, Any]]:
        """
        Search for patients with given parameters
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/Patient"
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            bundle = response.json()
            patients = []
            
            if bundle.get('entry'):
                for entry in bundle['entry']:
                    if entry.get('resource', {}).get('resourceType') == 'Patient':
                        patients.append(entry['resource'])
            
            return patients
            
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            return []
    
    def get_patient_documents(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Get all documents for a patient (DocumentReference resources)
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/DocumentReference"
            params = {'patient': patient_id, '_count': 100}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            bundle = response.json()
            documents = []
            
            if bundle.get('entry'):
                for entry in bundle['entry']:
                    if entry.get('resource', {}).get('resourceType') == 'DocumentReference':
                        documents.append(entry['resource'])
            
            return documents
            
        except Exception as e:
            logger.error(f"Error fetching documents for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_conditions(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Get patient conditions
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/Condition"
            params = {'patient': patient_id, 'clinical-status': 'active'}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            bundle = response.json()
            conditions = []
            
            if bundle.get('entry'):
                for entry in bundle['entry']:
                    if entry.get('resource', {}).get('resourceType') == 'Condition':
                        conditions.append(entry['resource'])
            
            return conditions
            
        except Exception as e:
            logger.error(f"Error fetching conditions for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_observations(self, patient_id: str, category: str = None) -> List[Dict[str, Any]]:
        """
        Get patient observations (labs, vitals, etc.)
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/Observation"
            params = {'patient': patient_id, '_count': 100}
            
            if category:
                params['category'] = category
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            bundle = response.json()
            observations = []
            
            if bundle.get('entry'):
                for entry in bundle['entry']:
                    if entry.get('resource', {}).get('resourceType') == 'Observation':
                        observations.append(entry['resource'])
            
            return observations
            
        except Exception as e:
            logger.error(f"Error fetching observations for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Get patient appointments
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/Appointment"
            params = {'patient': patient_id, '_count': 50}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            bundle = response.json()
            appointments = []
            
            if bundle.get('entry'):
                for entry in bundle['entry']:
                    if entry.get('resource', {}).get('resourceType') == 'Appointment':
                        appointments.append(entry['resource'])
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error fetching appointments for patient {patient_id}: {str(e)}")
            return []
    
    def get_patient_bundle(self, patient_id: str) -> Dict[str, Any]:
        """
        Get comprehensive patient data bundle
        """
        if not self._ensure_authenticated():
            return {}
        
        try:
            # Get all resources for patient in one request
            url = f"{self.base_url}/Patient/{patient_id}/$everything"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching patient bundle for {patient_id}: {str(e)}")
            # Fallback to individual requests
            return self._get_patient_bundle_fallback(patient_id)
    
    def _get_patient_bundle_fallback(self, patient_id: str) -> Dict[str, Any]:
        """
        Fallback method to get patient data using individual requests
        """
        bundle = {
            'resourceType': 'Bundle',
            'id': f'patient-{patient_id}-bundle',
            'type': 'collection',
            'entry': []
        }
        
        # Get patient
        patient = self.get_patient(patient_id)
        if patient:
            bundle['entry'].append({'resource': patient})
        
        # Get conditions
        conditions = self.get_patient_conditions(patient_id)
        for condition in conditions:
            bundle['entry'].append({'resource': condition})
        
        # Get documents
        documents = self.get_patient_documents(patient_id)
        for document in documents:
            bundle['entry'].append({'resource': document})
        
        # Get observations
        observations = self.get_patient_observations(patient_id)
        for observation in observations:
            bundle['entry'].append({'resource': observation})
        
        # Get appointments
        appointments = self.get_patient_appointments(patient_id)
        for appointment in appointments:
            bundle['entry'].append({'resource': appointment})
        
        return bundle
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test FHIR server connection and return capability statement
        """
        try:
            url = f"{self.base_url}/metadata"
            response = self.session.get(url)
            response.raise_for_status()
            
            capability_statement = response.json()
            
            return {
                'success': True,
                'server_version': capability_statement.get('fhirVersion', 'Unknown'),
                'software': capability_statement.get('software', {}),
                'implementation': capability_statement.get('implementation', {})
            }
            
        except Exception as e:
            logger.error(f"FHIR connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
