"""
SMART on FHIR API client
Handles FHIR data retrieval and authentication
"""

import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin
import logging

class FHIRClient:
    """FHIR client for EMR integration"""
    
    def __init__(self, base_url=None, client_id=None, client_secret=None):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires = None
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self, username=None, password=None):
        """Authenticate with FHIR server"""
        try:
            # For demo purposes, simulate authentication
            # In production, this would use OAuth2 flow
            self.access_token = "demo_access_token"
            self.token_expires = datetime.now() + timedelta(hours=1)
            
            self.logger.info("FHIR authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"FHIR authentication failed: {str(e)}")
            return False
    
    def get_patient(self, patient_id):
        """Get patient resource by ID"""
        try:
            if not self._is_authenticated():
                if not self.authenticate():
                    return None
            
            url = urljoin(self.base_url, f"Patient/{patient_id}")
            headers = self._get_headers()
            
            # For demo purposes, return mock data
            # In production, this would make actual FHIR API call
            response = self._mock_patient_response(patient_id)
            
            self.logger.info(f"Retrieved patient {patient_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
            return None
    
    def search_patients(self, search_params):
        """Search for patients based on parameters"""
        try:
            if not self._is_authenticated():
                if not self.authenticate():
                    return None
            
            url = urljoin(self.base_url, "Patient")
            headers = self._get_headers()
            
            # For demo purposes, return mock data
            response = self._mock_patient_search_response(search_params)
            
            self.logger.info(f"Patient search completed with {len(response.get('entry', []))} results")
            return response
            
        except Exception as e:
            self.logger.error(f"Error searching patients: {str(e)}")
            return None
    
    def get_documents(self, patient_id):
        """Get DocumentReference resources for a patient"""
        try:
            if not self._is_authenticated():
                if not self.authenticate():
                    return None
            
            url = urljoin(self.base_url, "DocumentReference")
            headers = self._get_headers()
            params = {"patient": patient_id}
            
            # For demo purposes, return mock data
            response = self._mock_documents_response(patient_id)
            
            self.logger.info(f"Retrieved documents for patient {patient_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error retrieving documents for patient {patient_id}: {str(e)}")
            return None
    
    def get_observations(self, patient_id, category=None):
        """Get Observation resources for a patient"""
        try:
            if not self._is_authenticated():
                if not self.authenticate():
                    return None
            
            url = urljoin(self.base_url, "Observation")
            headers = self._get_headers()
            params = {"patient": patient_id}
            
            if category:
                params["category"] = category
            
            # For demo purposes, return mock data
            response = self._mock_observations_response(patient_id, category)
            
            self.logger.info(f"Retrieved observations for patient {patient_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error retrieving observations for patient {patient_id}: {str(e)}")
            return None
    
    def get_conditions(self, patient_id):
        """Get Condition resources for a patient"""
        try:
            if not self._is_authenticated():
                if not self.authenticate():
                    return None
            
            url = urljoin(self.base_url, "Condition")
            headers = self._get_headers()
            params = {"patient": patient_id}
            
            # For demo purposes, return mock data
            response = self._mock_conditions_response(patient_id)
            
            self.logger.info(f"Retrieved conditions for patient {patient_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error retrieving conditions for patient {patient_id}: {str(e)}")
            return None
    
    def _is_authenticated(self):
        """Check if client is authenticated and token is valid"""
        if not self.access_token:
            return False
        
        if self.token_expires and datetime.now() >= self.token_expires:
            return False
        
        return True
    
    def _get_headers(self):
        """Get HTTP headers for FHIR requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def _mock_patient_response(self, patient_id):
        """Mock patient response for demo purposes"""
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [
                {
                    "use": "usual",
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "MR"
                            }
                        ]
                    },
                    "value": f"MRN-{patient_id}"
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": "Demo",
                    "given": ["Patient"]
                }
            ],
            "gender": "male",
            "birthDate": "1980-01-01",
            "telecom": [
                {
                    "system": "phone",
                    "value": "555-1234",
                    "use": "home"
                }
            ]
        }
    
    def _mock_patient_search_response(self, search_params):
        """Mock patient search response"""
        return {
            "resourceType": "Bundle",
            "id": "search-results",
            "type": "searchset",
            "total": 1,
            "entry": [
                {
                    "resource": self._mock_patient_response("demo-patient-1")
                }
            ]
        }
    
    def _mock_documents_response(self, patient_id):
        """Mock documents response"""
        return {
            "resourceType": "Bundle",
            "id": "documents-bundle",
            "type": "searchset",
            "total": 2,
            "entry": [
                {
                    "resource": {
                        "resourceType": "DocumentReference",
                        "id": "doc-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "type": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "11502-2",
                                    "display": "Laboratory report"
                                }
                            ]
                        },
                        "date": "2024-01-15T10:30:00Z",
                        "description": "Lab Results - Lipid Panel"
                    }
                },
                {
                    "resource": {
                        "resourceType": "DocumentReference",
                        "id": "doc-2",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "type": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "18748-4",
                                    "display": "Diagnostic imaging study"
                                }
                            ]
                        },
                        "date": "2024-02-20T14:15:00Z",
                        "description": "Chest X-Ray"
                    }
                }
            ]
        }
    
    def _mock_observations_response(self, patient_id, category):
        """Mock observations response"""
        return {
            "resourceType": "Bundle",
            "id": "observations-bundle",
            "type": "searchset",
            "total": 1,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": "33747-0",
                                    "display": "Cholesterol"
                                }
                            ]
                        },
                        "valueQuantity": {
                            "value": 180,
                            "unit": "mg/dL"
                        },
                        "effectiveDateTime": "2024-01-15T10:30:00Z"
                    }
                }
            ]
        }
    
    def _mock_conditions_response(self, patient_id):
        """Mock conditions response"""
        return {
            "resourceType": "Bundle",
            "id": "conditions-bundle",
            "type": "searchset",
            "total": 1,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Condition",
                        "id": "cond-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "code": {
                            "coding": [
                                {
                                    "system": "http://snomed.info/sct",
                                    "code": "73211009",
                                    "display": "Diabetes mellitus"
                                }
                            ]
                        },
                        "clinicalStatus": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                    "code": "active"
                                }
                            ]
                        },
                        "onsetDateTime": "2020-01-15"
                    }
                }
            ]
        }
