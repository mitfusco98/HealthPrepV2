"""
SMART on FHIR API client for EMR integration
Implements Epic's OAuth2 authentication flow as per SMART on FHIR specification
"""
import requests
import json
import os
import secrets
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse, quote
from typing import Dict, Optional, Any
import logging

class FHIRClient:
    """Client for connecting to Epic FHIR API following Epic's query patterns"""
    
    def __init__(self, organization_config=None, redirect_uri=None, organization=None):
        # Epic FHIR endpoints as per SMART on FHIR specification
        self.base_url = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        self.auth_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize'
        self.token_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
        
        self.client_id = 'default_client_id'
        self.client_secret = 'default_secret'
        self.redirect_uri = redirect_uri or 'http://localhost:5000/oauth/epic-callback'
        
        # Store organization reference for connection status updates (per blueprint)
        self.organization = organization
        
        # Override with organization-specific config if provided
        if organization_config:
            self.base_url = organization_config.get('epic_fhir_url', self.base_url)
            self.client_id = organization_config.get('epic_client_id', self.client_id)
            self.client_secret = organization_config.get('epic_client_secret', self.client_secret)
            
            # Derive auth and token URLs from base URL
            base_oauth = self.base_url.replace('/api/FHIR/R4/', '/')
            self.auth_url = f"{base_oauth}oauth2/authorize"
            self.token_url = f"{base_oauth}oauth2/token"
        
        # Use environment variables as fallback
        self.base_url = os.environ.get('FHIR_BASE_URL', self.base_url)
        self.client_id = os.environ.get('FHIR_CLIENT_ID', self.client_id)
        self.client_secret = os.environ.get('FHIR_CLIENT_SECRET', self.client_secret)
        
        # Token management
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.token_scopes = None
        
        # SMART on FHIR scopes for Epic integration
        self.default_scopes = [
            'openid',
            'fhirUser',
            'patient/Patient.read',
            'patient/Condition.read', 
            'patient/Observation.read',
            'patient/DocumentReference.read',
            'patient/Encounter.read',
            'patient/Appointment.read',
            'user/Patient.read',
            'user/Condition.read',
            'user/Observation.read',
            'user/DocumentReference.read',
            'user/Encounter.read'
        ]
        
        self.logger = logging.getLogger(__name__)
    
    def get_authorization_url(self, state=None, scopes=None):
        """
        Generate Epic's authorization URL for SMART on FHIR OAuth2 flow
        User's browser should be directed to this URL to start authentication
        """
        if not state:
            state = secrets.token_urlsafe(32)
        
        if not scopes:
            scopes = self.default_scopes
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes),
            'aud': self.base_url,  # Epic requires audience parameter
            'state': state
        }
        
        # Epic is very strict about parameter encoding
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        
        # Debug logging for Epic OAuth parameters
        self.logger.info(f"Epic OAuth Parameters:")
        for key, value in params.items():
            self.logger.info(f"  {key}: {value}")
        self.logger.info(f"Generated Epic authorization URL: {auth_url}")
        
        return auth_url, state
    
    def exchange_code_for_token(self, authorization_code, state=None):
        """
        Exchange authorization code for access token
        Called from OAuth callback endpoint after user authorizes
        """
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            # Debug logging for token exchange
            self.logger.info(f"Token exchange request:")
            self.logger.info(f"  - URL: {self.token_url}")
            self.logger.info(f"  - client_id: {self.client_id}")
            self.logger.info(f"  - redirect_uri: {self.redirect_uri}")
            self.logger.info(f"  - grant_type: authorization_code")
            self.logger.info(f"  - code: {'<present>' if authorization_code else 'None'}")
            
            response = requests.post(self.token_url, data=data)
            
            # Log response details for debugging
            self.logger.info(f"Token exchange response:")
            self.logger.info(f"  - status_code: {response.status_code}")
            self.logger.info(f"  - headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                self.logger.error(f"Token exchange failed with status {response.status_code}")
                self.logger.error(f"Response body: {response.text}")
                return None
            
            response.raise_for_status()
            
            token_data = response.json()
            
            # Store tokens and metadata
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            self.token_scopes = token_data.get('scope', '').split()
            
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            self.logger.info("Successfully exchanged authorization code for Epic access token")
            return token_data
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error during token exchange: {str(e)}")
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"Token exchange failed: {str(e)}")
            return None
    
    def refresh_access_token(self):
        """
        Use refresh token to get new access token (Enhanced per blueprint)
        Called when access token expires with comprehensive error handling
        """
        if not self.refresh_token:
            error_msg = "No refresh token available for token refresh"
            self.logger.warning(error_msg)
            self._update_organization_status(False, error_msg)
            return False
        
        try:
            self.logger.info(f"Attempting token refresh for organization {getattr(self.organization, 'name', 'unknown')}")
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update tokens
            self.access_token = token_data.get('access_token')
            if token_data.get('refresh_token'):
                self.refresh_token = token_data.get('refresh_token')
            
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            # Update organization connection status (success)
            self._update_organization_status(True, None, self.token_expires)
            
            # Persist refreshed tokens in database for background access
            self._persist_tokens_to_database()
            
            self.logger.info(f"Successfully refreshed Epic access token, expires in {expires_in} seconds")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                error_msg = "Refresh token expired or invalid - full re-authentication required"
            else:
                error_msg = f"HTTP {e.response.status_code} error during token refresh: {str(e)}"
            self.logger.error(error_msg)
            self._update_organization_status(False, error_msg)
            return False
            
        except Exception as e:
            error_msg = f"Token refresh failed: {str(e)}"
            self.logger.error(error_msg)
            self._update_organization_status(False, error_msg)
            return False
    
    def _update_organization_status(self, is_connected: bool, error_message: str = None, token_expiry: datetime = None):
        """Update organization Epic connection status (per blueprint)"""
        if self.organization:
            try:
                self.organization.update_epic_connection_status(
                    is_connected=is_connected,
                    error_message=error_message,
                    token_expiry=token_expiry
                )
            except Exception as e:
                self.logger.error(f"Failed to update organization connection status: {str(e)}")
    
    def _persist_tokens_to_database(self):
        """Persist current tokens to EpicCredentials table for background access"""
        if not self.organization:
            self.logger.warning("No organization available for token persistence")
            return
        
        try:
            # Import here to avoid circular imports
            from models import EpicCredentials, db
            
            # Find or create Epic credentials record
            epic_creds = EpicCredentials.query.filter_by(org_id=self.organization.id).first()
            if not epic_creds:
                epic_creds = EpicCredentials(org_id=self.organization.id)
                db.session.add(epic_creds)
            
            # Update tokens
            epic_creds.access_token = self.access_token
            if self.refresh_token:
                epic_creds.refresh_token = self.refresh_token
            epic_creds.token_expires_at = self.token_expires
            if self.token_scopes:
                epic_creds.token_scope = ' '.join(self.token_scopes)
            epic_creds.updated_at = datetime.now()
            
            db.session.commit()
            self.logger.info(f"Persisted Epic tokens to database for organization {self.organization.id}")
            
        except Exception as e:
            self.logger.error(f"Error persisting tokens to database: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
    
    def authenticate(self):
        """
        Legacy method for backward compatibility
        For SMART on FHIR, use get_authorization_url() and exchange_code_for_token()
        """
        self.logger.warning("Direct authentication not supported in SMART on FHIR flow")
        self.logger.info("Use get_authorization_url() to start OAuth2 flow")
        return False
    
    def set_tokens(self, access_token, refresh_token=None, expires_in=3600, scopes=None):
        """
        Manually set tokens (e.g., from session storage)
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_scopes = scopes or []
        self.token_expires = datetime.now() + timedelta(seconds=expires_in)
        
        self.logger.info("Epic FHIR tokens set successfully")
    
    def _get_headers(self):
        """
        Get headers for FHIR API requests with OAuth2 bearer token
        Automatically refreshes token if expired
        """
        # Check if token is expired and refresh if possible
        if not self.access_token or (self.token_expires and datetime.now() >= self.token_expires):
            if not self.refresh_access_token():
                raise Exception("No valid Epic FHIR token available. Please re-authenticate.")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
    
    def _api_get_with_retry(self, url: str, params: Dict = None, max_retries: int = 1) -> Optional[Dict]:
        """
        Enhanced API GET with comprehensive error handling (per blueprint)
        Implements blueprint suggestion for connection status tracking
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Check token before request
                if not self.access_token or (self.token_expires and datetime.now() >= self.token_expires):
                    if not self.refresh_access_token():
                        error_msg = "No valid Epic FHIR token available. Please re-authenticate."
                        self._update_organization_status(False, error_msg)
                        return None
                
                headers = self._get_headers()
                
                self.logger.debug(f"Making Epic API request to {url} (attempt {attempt + 1})")
                response = requests.get(url, headers=headers, params=params or {})
                
                # Handle 401 Unauthorized specifically (Epic blueprint pattern)
                if response.status_code == 401:
                    if attempt < max_retries:
                        self.logger.info(f"Received 401 Unauthorized, attempting token refresh (attempt {attempt + 1})")
                        
                        # Attempt token refresh
                        if self.refresh_access_token():
                            # Headers will be updated in next iteration
                            continue
                        else:
                            error_msg = "Token refresh failed after 401 error"
                            self.logger.error(error_msg)
                            self._update_organization_status(False, error_msg)
                            return None
                    else:
                        error_msg = "Max retries reached for 401 error - re-authentication required"
                        self.logger.error(error_msg)
                        self._update_organization_status(False, error_msg)
                        return None
                
                response.raise_for_status()
                
                # Success - update organization status
                self._update_organization_status(True, None, self.token_expires)
                
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP {e.response.status_code} error: {str(e)}"
                if e.response.status_code >= 500:  # Server errors - retry
                    if attempt < max_retries:
                        self.logger.warning(f"Server error, retrying (attempt {attempt + 1}): {last_error}")
                        continue
                else:  # Client errors - don't retry
                    self.logger.error(f"Client error, not retrying: {last_error}")
                    break
                    
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {str(e)}"
                if attempt < max_retries:
                    self.logger.warning(f"Connection failed, retrying (attempt {attempt + 1}): {last_error}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                if attempt < max_retries:
                    self.logger.warning(f"Request failed, retrying (attempt {attempt + 1}): {last_error}")
                    continue
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                self.logger.error(f"Unexpected error during Epic API call: {last_error}")
                break
        
        # All attempts failed - update organization status
        self._update_organization_status(False, last_error)
        return None
    
    def get_patient(self, patient_id):
        """Retrieve patient information from FHIR server"""
        try:
            url = f"{self.base_url}Patient/{patient_id}"
            
            # Use enhanced retry logic for 401 handling
            return self._api_get_with_retry(url)
            
        except Exception as e:
            self.logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
            return None
    
    def get_patients(self, count=50):
        """
        Note: Epic FHIR doesn't allow broad patient queries without specific search parameters.
        This method is deprecated in favor of using known patient IDs.
        Use get_patient(patient_id) for specific patients instead.
        """
        self.logger.warning("get_patients() is deprecated - Epic FHIR requires specific patient identifiers")
        return {
            'success': False,
            'error': 'Epic FHIR requires specific patient identifiers - use known patient IDs instead'
        }

    def search_patients(self, given_name=None, family_name=None, birthdate=None, identifier=None):
        """
        Search for patients using Epic FHIR search patterns
        Example: GET [base]/Patient?family=Lin&given=Derrick&birthdate=1973-06-03
        Epic requires minimal set of identifiers (name + DOB, MRN, or SSN)
        """
        try:
            url = f"{self.base_url}Patient"
            params = {}
            
            if given_name:
                params['given'] = given_name
            if family_name:
                params['family'] = family_name
            if birthdate:
                params['birthdate'] = birthdate
            if identifier:
                params['identifier'] = identifier
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error searching patients: {str(e)}")
            return None
    
    def get_patient_by_name_and_dob(self, family_name, given_name, birthdate):
        """
        Get patient using Epic's recommended search pattern with name and DOB
        Example: Derrick Lin, born 1973-06-03 (Epic sandbox test patient)
        """
        return self.search_patients(
            given_name=given_name,
            family_name=family_name, 
            birthdate=birthdate
        )
    
    def get_document_references(self, patient_id, document_type=None, date_from=None, date_to=None):
        """
        Get clinical documents using Epic FHIR DocumentReference
        Query: GET [base]/DocumentReference?patient={patient_id}
        Returns: PDFs, consult notes, colonoscopy reports, DXA scans, etc.
        Implements "minimum necessary" principle with filtering
        """
        try:
            url = f"{self.base_url}DocumentReference"
            params = {
                'patient': patient_id,
                '_sort': '-date',  # Most recent first
                '_count': '50'     # Limit results for "minimum necessary"
            }
            
            if document_type:
                params['type'] = document_type
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
    
    # Comprehensive EMR Sync Methods
    def get_patient_conditions(self, patient_id, date_filter=None):
        """
        Get patient conditions for comprehensive EMR sync
        Wrapper around get_conditions with additional filtering
        """
        try:
            return self.get_conditions(patient_id)
        except Exception as e:
            self.logger.error(f"Error retrieving patient conditions: {str(e)}")
            return None
    
    def get_patient_observations(self, patient_id, date_filter=None):
        """
        Get patient observations for comprehensive EMR sync
        Wrapper around get_observations with date filtering
        """
        try:
            if date_filter:
                from datetime import datetime
                date_obj = datetime.fromisoformat(date_filter.replace('Z', '+00:00'))
                return self.get_observations(patient_id, date_from=date_obj)
            else:
                return self.get_observations(patient_id)
        except Exception as e:
            self.logger.error(f"Error retrieving patient observations: {str(e)}")
            return None
    
    def get_patient_documents(self, patient_id, date_filter=None):
        """
        Get patient documents for comprehensive EMR sync
        Wrapper around get_document_references with date filtering
        """
        try:
            if date_filter:
                from datetime import datetime
                date_obj = datetime.fromisoformat(date_filter.replace('Z', '+00:00'))
                return self.get_document_references(patient_id, date_from=date_obj)
            else:
                return self.get_document_references(patient_id)
        except Exception as e:
            self.logger.error(f"Error retrieving patient documents: {str(e)}")
            return None
    
    def get_patient_encounters(self, patient_id, date_filter=None):
        """
        Get patient encounters for comprehensive EMR sync
        Wrapper around get_encounters with date filtering
        """
        try:
            if date_filter:
                from datetime import datetime
                date_obj = datetime.fromisoformat(date_filter.replace('Z', '+00:00'))
                return self.get_encounters(patient_id, date_from=date_obj)
            else:
                return self.get_encounters(patient_id)
        except Exception as e:
            self.logger.error(f"Error retrieving patient encounters: {str(e)}")
            return None
    
    def download_binary(self, binary_url):
        """
        Download binary content from Epic FHIR Binary resource
        Used for downloading document attachments
        """
        try:
            # Handle relative URLs by prepending base URL if needed
            if binary_url.startswith('/'):
                url = f"{self.base_url.rstrip('/')}{binary_url}"
            elif binary_url.startswith('http'):
                url = binary_url
            else:
                url = f"{self.base_url}Binary/{binary_url}"
            
            # Use retry logic for binary downloads
            headers = self._get_headers()
            headers['Accept'] = 'application/octet-stream'  # Request binary content
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error downloading binary from {binary_url}: {str(e)}")
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
    
    def get_observations(self, patient_id, code=None, category='laboratory', date_from=None):
        """
        Get lab results and observations using Epic FHIR
        Query: GET [base]/Observation?patient={patient_id}&category=laboratory
        Returns: Lab test results (HbA1c, lipid panel, etc.) with LOINC codes, values, dates
        Used to check if results are within required timeframe for screening
        """
        try:
            url = f"{self.base_url}Observation"
            params = {
                'patient': patient_id,
                '_sort': '-date',
                '_count': '100'  # Reasonable limit for observations
            }
            
            if code:
                params['code'] = code
            if category:
                params['category'] = category  # Default to 'laboratory' per Epic pattern
            if date_from:
                params['date'] = f"ge{date_from.isoformat()}"
            
            # Use enhanced retry logic for 401 handling
            return self._api_get_with_retry(url, params)
            
        except Exception as e:
            self.logger.error(f"Error retrieving observations for patient {patient_id}: {str(e)}")
            return None
    
    def get_conditions(self, patient_id, clinical_status=None, code=None):
        """
        Get patient's conditions (problem list) using Epic FHIR
        Query: GET [base]/Condition?patient={patient_id}
        Returns: Active/past conditions like Diabetes, Hyperlipidemia
        Used for identifying trigger conditions that affect screening criteria
        """
        try:
            url = f"{self.base_url}Condition"
            params = {
                'patient': patient_id,
                '_sort': '-onset-date',
                '_count': '100'  # Reasonable limit for conditions
            }
            
            if clinical_status:
                params['clinical-status'] = clinical_status
            if code:
                params['code'] = code
            
            # Use enhanced retry logic for 401 handling
            return self._api_get_with_retry(url, params)
            
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
    
    def get_encounters(self, patient_id, status=None, date_from=None, date_to=None):
        """
        Get patient encounters (visits/appointments) using Epic FHIR
        Query: GET [base]/Encounter?patient={patient_id}
        Returns: Clinic visits, hospital admissions with dates and types
        Used to identify upcoming encounters for prep sheet context
        """
        try:
            url = f"{self.base_url}Encounter"
            params = {
                'patient': patient_id,
                '_sort': '-date',
                '_count': '50'  # Recent encounters only
            }
            
            if status:
                params['status'] = status
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
            self.logger.error(f"Error retrieving encounters for patient {patient_id}: {str(e)}")
            return None
    
    def get_appointments(self, patient_id=None, status=None, date_from=None, date_to=None):
        """
        Get patient appointments using Epic FHIR
        Query: GET [base]/Appointment?patient={patient_id}
        Returns: Scheduled appointments for screening prioritization
        
        Args:
            patient_id: Epic patient ID to filter appointments
            status: Appointment status (booked, pending, arrived, fulfilled, cancelled, noshow)
            date_from: Start date for appointment range
            date_to: End date for appointment range
        """
        try:
            url = f"{self.base_url}Appointment"
            params = {
                '_sort': 'date',
                '_count': '100'
            }
            
            if patient_id:
                params['patient'] = patient_id
            
            if status:
                params['status'] = status
            
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
            self.logger.error(f"Error retrieving appointments for patient {patient_id}: {str(e)}")
            return None
    
    def get_epic_screening_data_sequence(self, patient_id):
        """
        Execute Epic's recommended data retrieval sequence for screening
        As per blueprint: Patient → Condition → Observation → DocumentReference → Encounter
        Implements "minimum necessary" principle with focused queries
        """
        try:
            screening_data = {}
            
            # 1. Get Patient record (demographics)
            self.logger.info(f"Fetching patient demographics for {patient_id}")
            screening_data['patient'] = self.get_patient(patient_id)
            
            # 2. Get Conditions (problem list for trigger conditions)
            self.logger.info(f"Fetching conditions for {patient_id}")
            screening_data['conditions'] = self.get_conditions(patient_id)
            
            # 3. Get Observations (lab results for screening status)
            self.logger.info(f"Fetching lab observations for {patient_id}")
            screening_data['lab_results'] = self.get_observations(patient_id, category='laboratory')
            
            # 4. Get DocumentReference (clinical documents)
            self.logger.info(f"Fetching clinical documents for {patient_id}")
            screening_data['documents'] = self.get_document_references(patient_id)
            
            # 5. Get Encounters (visit context)
            self.logger.info(f"Fetching encounters for {patient_id}")
            screening_data['encounters'] = self.get_encounters(patient_id)
            
            return screening_data
            
        except Exception as e:
            self.logger.error(f"Error in Epic screening data sequence: {str(e)}")
            return None
    
    def sync_patient_data_epic_sequence(self, patient_mrn):
        """
        Sync patient data using Epic FHIR patterns with MRN lookup
        Implements Epic's recommended query sequence for comprehensive data retrieval
        """
        try:
            # Search for patient by MRN (Epic requires minimal identifiers)
            patient_bundle = self.search_patients(identifier=patient_mrn)
            
            if not patient_bundle or not patient_bundle.get('entry'):
                self.logger.warning(f"Patient not found with MRN: {patient_mrn}")
                return None
            
            # Get patient ID from search results
            patient_resource = patient_bundle['entry'][0]['resource']
            patient_id = patient_resource['id']
            
            # Execute Epic's screening data sequence
            return self.get_epic_screening_data_sequence(patient_id)
            
        except Exception as e:
            self.logger.error(f"Error syncing patient data: {str(e)}")
            return None
    
    def get_document_content(self, content_url):
        """Download document content from Epic Binary resource"""
        try:
            # Handle both absolute URLs and relative URLs
            if not content_url.startswith('http'):
                content_url = f"{self.base_url.rstrip('/')}/{content_url.lstrip('/')}"
            
            response = requests.get(content_url, headers=self._get_headers())
            response.raise_for_status()
            
            self.logger.info(f"Downloaded document content from {content_url}")
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error downloading document content from {content_url}: {str(e)}")
            return None
    
    def create_document_reference(self, document_reference_data):
        """Create a new DocumentReference in Epic (write prep sheet back)"""
        try:
            url = f"{self.base_url}DocumentReference"
            
            headers = self._get_headers()
            headers['Content-Type'] = 'application/fhir+json'
            
            response = requests.post(url, headers=headers, json=document_reference_data)
            response.raise_for_status()
            
            result = response.json()
            self.logger.info(f"Successfully created DocumentReference: {result.get('id')}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error creating DocumentReference: {str(e)}")
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"Response content: {e.response.text}")
            return None
    
    def update_document_reference(self, document_id, document_reference_data):
        """Update an existing DocumentReference in Epic"""
        try:
            url = f"{self.base_url}DocumentReference/{document_id}"
            
            headers = self._get_headers()
            headers['Content-Type'] = 'application/fhir+json'
            
            response = requests.put(url, headers=headers, json=document_reference_data)
            response.raise_for_status()
            
            result = response.json()
            self.logger.info(f"Successfully updated DocumentReference: {document_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error updating DocumentReference {document_id}: {str(e)}")
            return None
