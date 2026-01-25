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
        
        # NO DEFAULT CREDENTIALS - must be provided via organization config or environment
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = redirect_uri or 'http://localhost:5000/oauth/epic-callback'
        
        # Store organization reference for connection status updates (per blueprint)
        self.organization = organization
        
        # Override with organization-specific config if provided
        if organization_config:
            self.base_url = organization_config.get('epic_fhir_url', self.base_url)
            self.client_id = organization_config.get('epic_client_id')
            self.client_secret = organization_config.get('epic_client_secret')
            
            # Derive auth and token URLs from base URL
            base_oauth = self.base_url.replace('/api/FHIR/R4/', '/')
            self.auth_url = f"{base_oauth}oauth2/authorize"
            self.token_url = f"{base_oauth}oauth2/token"
        
        # Use environment variables as fallback (only if org config didn't provide them)
        if not self.client_id:
            self.client_id = os.environ.get('FHIR_CLIENT_ID')
        if not self.client_secret:
            self.client_secret = os.environ.get('FHIR_CLIENT_SECRET')
        if 'FHIR_BASE_URL' in os.environ:
            self.base_url = os.environ.get('FHIR_BASE_URL')
        
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
        # Validate credentials are configured
        if not self.client_id:
            raise ValueError(
                "Epic client_id is not configured. Please configure Epic credentials "
                "via organization settings or environment variables."
            )
        
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
        
        # Debug logging for Epic OAuth parameters (avoid logging sensitive values)
        self.logger.info("Epic OAuth Parameters:")
        safe_params = {
            'response_type': params.get('response_type'),
            'scope_count': len(scopes) if scopes else 0,
            'aud': params.get('aud'),
        }
        for key, value in safe_params.items():
            self.logger.info(f"  {key}: {value}")
        self.logger.info("Generated Epic authorization URL")
        
        return auth_url, state
    
    def exchange_code_for_token(self, authorization_code, state=None):
        """
        Exchange authorization code for access token
        Called from OAuth callback endpoint after user authorizes
        """
        # Validate credentials are configured
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Epic credentials are not configured. Please configure Epic client_id "
                "and client_secret via organization settings or environment variables."
            )
        
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            # Debug logging for token exchange (avoid logging sensitive values)
            self.logger.info("Token exchange request:")
            self.logger.info(f"  - URL: {self.token_url}")
            self.logger.info("  - client_id: [REDACTED]")
            self.logger.info("  - redirect_uri: [REDACTED]")
            self.logger.info("  - grant_type: authorization_code")
            self.logger.info(f"  - code_present: {bool(authorization_code)}")
            
            response = requests.post(self.token_url, data=data)
            
            # Log response details for debugging (without sensitive body content)
            self.logger.info("Token exchange response:")
            self.logger.info(f"  - status_code: {response.status_code}")
            self.logger.info(f"  - headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                self.logger.error(f"Token exchange failed with status {response.status_code}")
                self.logger.error("Response body: [REDACTED]")
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
                # Avoid logging full response content, which may contain sensitive data
                self.logger.error("Response content: [REDACTED]")
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
        
        # Validate credentials are configured
        if not self.client_id or not self.client_secret:
            error_msg = "Epic credentials not configured - cannot refresh token"
            self.logger.error(error_msg)
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
    
    def search_appointments(self, practitioner=None, patient=None, date_from=None, date_to=None, status=None):
        """
        Search for appointments with optional filters.
        
        Supports provider-centric filtering by practitioner reference (from fhirUser claim).
        
        Args:
            practitioner: Practitioner reference (e.g., "Practitioner/eOPiqtxdD35SmjVN0xkGLtg3")
            patient: Patient reference (e.g., "Patient/abc123")
            date_from: Start date for appointment date range (ISO format)
            date_to: End date for appointment date range (ISO format)
            status: Appointment status filter (e.g., "booked", "arrived", "fulfilled")
            
        Returns:
            List of FHIR Appointment resources
        """
        if not self.access_token:
            self.logger.error("No access token available")
            return []
        
        try:
            url = f"{self.base_url}Appointment"
            params = {}
            
            if practitioner:
                params['actor'] = practitioner
            if patient:
                params['patient'] = patient
            if date_from and date_to:
                params['date'] = [f'ge{date_from}', f'le{date_to}']
            elif date_from:
                params['date'] = f'ge{date_from}'
            elif date_to:
                params['date'] = f'le{date_to}'
            if status:
                params['status'] = status
            
            params['_count'] = 100
            
            headers = self._get_headers()
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 401:
                self.logger.warning("Token expired, attempting refresh...")
                if self.refresh_access_token():
                    headers = self._get_headers()
                    response = requests.get(url, headers=headers, params=params)
            
            response.raise_for_status()
            data = response.json()
            
            appointments = []
            if data.get('resourceType') == 'Bundle' and 'entry' in data:
                for entry in data['entry']:
                    if 'resource' in entry:
                        appointments.append(entry['resource'])
            
            self.logger.info(f"Retrieved {len(appointments)} appointments")
            return appointments
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error searching appointments: {str(e)}")
            return []
    
    def get_patient_appointments(self, patient_id, date_from=None, date_to=None):
        """
        Get appointments for a specific patient.
        
        Args:
            patient_id: Epic patient ID
            date_from: Optional start date (ISO format)
            date_to: Optional end date (ISO format)
            
        Returns:
            List of FHIR Appointment resources
        """
        return self.search_appointments(
            patient=f"Patient/{patient_id}",
            date_from=date_from,
            date_to=date_to
        )
    
    def get_patient_immunizations(self, patient_id, vaccine_codes=None, date_from=None):
        """
        Get immunization records for a patient.
        
        Used by immunization-based screening types to check vaccine compliance
        instead of document scanning.
        
        Args:
            patient_id: Epic patient ID
            vaccine_codes: Optional list of CVX codes to filter by (e.g., ["140", "03"])
            date_from: Optional start date filter (ISO format)
            
        Returns:
            List of FHIR Immunization resources
        """
        if not self.access_token:
            self.logger.error("No access token available")
            return []
        
        try:
            url = f"{self.base_url}Immunization"
            params = {
                'patient': patient_id,
                '_count': 100
            }
            
            if vaccine_codes:
                cvx_codes = ','.join([f'http://hl7.org/fhir/sid/cvx|{code}' for code in vaccine_codes])
                params['vaccine-code'] = cvx_codes
            
            if date_from:
                params['date'] = f'ge{date_from}'
            
            headers = self._get_headers()
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 401:
                self.logger.warning("Token expired, attempting refresh...")
                if self.refresh_access_token():
                    headers = self._get_headers()
                    response = requests.get(url, headers=headers, params=params)
            
            response.raise_for_status()
            data = response.json()
            
            immunizations = []
            if data.get('resourceType') == 'Bundle' and 'entry' in data:
                for entry in data['entry']:
                    if 'resource' in entry:
                        immunizations.append(entry['resource'])
            
            self.logger.info(f"Retrieved {len(immunizations)} immunizations for patient {patient_id}")
            return immunizations
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching immunizations for patient {patient_id}: {str(e)}")
            return []
    
    def check_immunization_status(self, patient_id, vaccine_codes, screening_frequency_years=1):
        """
        Check if a patient has a valid (not expired) immunization for specified vaccines.
        
        Args:
            patient_id: Epic patient ID
            vaccine_codes: List of CVX codes to check (e.g., ["140"] for Influenza)
            screening_frequency_years: How often the immunization is required (for due date calc)
            
        Returns:
            dict with:
                - is_current: bool - True if immunization is within frequency period
                - last_immunization_date: date or None
                - next_due_date: date or None
                - immunization_records: list of relevant FHIR Immunization resources
        """
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        result = {
            'is_current': False,
            'last_immunization_date': None,
            'next_due_date': None,
            'immunization_records': []
        }
        
        try:
            immunizations = self.get_patient_immunizations(patient_id, vaccine_codes)
            
            if not immunizations:
                result['next_due_date'] = date.today()
                return result
            
            result['immunization_records'] = immunizations
            
            most_recent_date = None
            for imm in immunizations:
                occurrence = imm.get('occurrenceDateTime')
                if occurrence:
                    try:
                        imm_date = datetime.fromisoformat(occurrence.replace('Z', '+00:00')).date()
                        if most_recent_date is None or imm_date > most_recent_date:
                            most_recent_date = imm_date
                    except ValueError:
                        continue
            
            if most_recent_date:
                result['last_immunization_date'] = most_recent_date
                next_due = most_recent_date + relativedelta(years=screening_frequency_years)
                result['next_due_date'] = next_due
                result['is_current'] = date.today() < next_due
            else:
                result['next_due_date'] = date.today()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking immunization status: {str(e)}")
            result['next_due_date'] = date.today()
            return result
    
    def download_binary(self, binary_url):
        """
        Download binary content from Epic FHIR Binary resource
        Epic returns Binary resources as JSON with base64-encoded data field
        
        Returns:
            tuple: (content: bytes or None, error_info: dict or None)
            - On success: (content_bytes, None)
            - On failure: (None, {'error_type': str, 'status_code': int, 'message': str})
        """
        try:
            # Reject internal file:// URLs that point to Epic's internal file server
            # Epic sandbox sometimes returns paths like file:////172.16.61.84/q/data/...
            # which are internal and cannot be accessed externally
            if binary_url and binary_url.startswith('file://'):
                error_info = {
                    'error_type': 'internal_file_path',
                    'status_code': None,
                    'message': 'Epic internal file path not accessible - document content unavailable'
                }
                self.logger.warning(f"Skipping internal file path URL: {binary_url[:100]}...")
                return None, error_info
            
            # Handle relative URLs by prepending base URL if needed
            if binary_url.startswith('/'):
                url = f"{self.base_url.rstrip('/')}{binary_url}"
            elif binary_url.startswith('http'):
                url = binary_url
            else:
                # Extract just the ID from Binary/xxx format if present
                if binary_url.startswith('Binary/'):
                    binary_id = binary_url.replace('Binary/', '', 1)
                else:
                    binary_id = binary_url
                url = f"{self.base_url}Binary/{binary_id}"
            
            # Request JSON response to get Binary resource with base64 data
            headers = self._get_headers()
            headers['Accept'] = 'application/fhir+json'
            
            response = requests.get(url, headers=headers)
            
            # Categorize HTTP errors
            if response.status_code in (401, 403):
                error_info = {
                    'error_type': 'token_expired',
                    'status_code': response.status_code,
                    'message': 'Access token expired or unauthorized'
                }
                self.logger.warning(f"Token expired/unauthorized downloading binary from {binary_url}: HTTP {response.status_code}")
                return None, error_info
            elif response.status_code == 404:
                error_info = {
                    'error_type': 'not_found',
                    'status_code': 404,
                    'message': 'Document not found in Epic'
                }
                self.logger.warning(f"Document not found at {binary_url}: HTTP 404")
                return None, error_info
            elif response.status_code == 429:
                error_info = {
                    'error_type': 'rate_limited',
                    'status_code': 429,
                    'message': 'Epic rate limit exceeded'
                }
                self.logger.warning(f"Rate limited downloading binary from {binary_url}")
                return None, error_info
            elif response.status_code >= 500:
                error_info = {
                    'error_type': 'epic_server_error',
                    'status_code': response.status_code,
                    'message': f'Epic server error: HTTP {response.status_code}'
                }
                self.logger.error(f"Epic server error downloading binary from {binary_url}: HTTP {response.status_code}")
                return None, error_info
            elif response.status_code >= 400:
                error_info = {
                    'error_type': 'request_error',
                    'status_code': response.status_code,
                    'message': f'Request error: HTTP {response.status_code}'
                }
                self.logger.warning(f"Request error downloading binary from {binary_url}: HTTP {response.status_code}")
                return None, error_info
            
            # Epic returns Binary as JSON: {"resourceType":"Binary","data":"base64...","contentType":"..."}
            try:
                binary_resource = response.json()
                if binary_resource.get('resourceType') == 'Binary' and 'data' in binary_resource:
                    # Decode base64 data field
                    import base64
                    decoded_content = base64.b64decode(binary_resource['data'])
                    self.logger.debug(f"Successfully decoded Binary resource, content type: {binary_resource.get('contentType')}")
                    return decoded_content, None
                else:
                    # Fallback: return raw content if not a proper Binary resource
                    self.logger.warning(f"Binary response is not in expected format: {binary_resource.get('resourceType')}")
                    return response.content, None
            except ValueError:
                # Not JSON, return raw bytes
                self.logger.debug("Binary response is not JSON, returning raw content")
                return response.content, None
            
        except requests.exceptions.Timeout:
            error_info = {
                'error_type': 'timeout',
                'status_code': None,
                'message': 'Request timed out connecting to Epic'
            }
            self.logger.error(f"Timeout downloading binary from {binary_url}")
            return None, error_info
        except requests.exceptions.ConnectionError:
            error_info = {
                'error_type': 'network_error',
                'status_code': None,
                'message': 'Network error connecting to Epic'
            }
            self.logger.error(f"Network error downloading binary from {binary_url}")
            return None, error_info
        except Exception as e:
            error_info = {
                'error_type': 'unknown',
                'status_code': None,
                'message': str(e)
            }
            self.logger.error(f"Error downloading binary from {binary_url}: {str(e)}")
            return None, error_info
    
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
        """Create a new DocumentReference in Epic (write prep sheet back)
        
        Returns:
            dict: On success, the created DocumentReference resource
            dict: On failure, {'error': str, 'details': dict, 'is_sandbox_limitation': bool}
        """
        try:
            url = f"{self.base_url}DocumentReference"
            
            headers = self._get_headers()
            headers['Content-Type'] = 'application/fhir+json'
            
            # Log request details for debugging (without the full PDF data)
            # Build a separate summary dict to avoid mutating original payload
            debug_summary = {
                'resourceType': document_reference_data.get('resourceType'),
                'status': document_reference_data.get('status'),
                'type': document_reference_data.get('type'),
                'category': document_reference_data.get('category'),
                'subject': document_reference_data.get('subject'),
                'date': document_reference_data.get('date'),
                'author': document_reference_data.get('author'),
                'description': document_reference_data.get('description'),
            }
            # Summarize content without including actual base64 data
            if 'content' in document_reference_data:
                content_summary = []
                for content_item in document_reference_data.get('content', []):
                    attachment = content_item.get('attachment', {})
                    data_len = len(attachment.get('data', '')) if attachment.get('data') else 0
                    content_summary.append({
                        'contentType': attachment.get('contentType'),
                        'title': attachment.get('title'),
                        'creation': attachment.get('creation'),
                        'data': f"<base64: {data_len} chars>"
                    })
                debug_summary['content'] = content_summary
            
            self.logger.info(f"Creating DocumentReference at {url}")
            self.logger.debug(f"DocumentReference payload summary: {debug_summary}")
            
            response = requests.post(url, headers=headers, json=document_reference_data)
            
            # Check status manually to ensure we have access to response object
            if response.status_code >= 400:
                # Parse error details directly from the response object
                error_details = self._parse_epic_error_response(response)
                
                is_sandbox = 'fhir.epic.com' in self.base_url or 'sandbox' in self.base_url.lower()
                is_write_not_supported = self._is_sandbox_write_limitation(error_details)
                
                if is_sandbox and is_write_not_supported:
                    self.logger.warning(
                        f"Epic sandbox may not support DocumentReference writes. "
                        f"Error: {error_details.get('message', 'Unknown')}. "
                        f"This is a known limitation of Epic's public sandbox environment."
                    )
                else:
                    self.logger.error(
                        f"Error creating DocumentReference: HTTP {response.status_code}. "
                        f"OperationOutcome: {error_details}"
                    )
                
                return {
                    'error': error_details.get('message', f'HTTP {response.status_code}'),
                    'details': error_details,
                    'is_sandbox_limitation': is_sandbox and is_write_not_supported,
                    'status_code': response.status_code
                }
            
            # Handle successful response (2xx)
            # Epic may return:
            # - 201 Created with JSON body containing the resource
            # - 201 Created with empty body but Location header
            # - 200 OK with JSON body
            
            # Log response details for debugging
            self.logger.debug(f"Response status: {response.status_code}, Content-Length: {response.headers.get('Content-Length', 'not set')}")
            
            # Check for Location header (common for 201 Created)
            # Location format: https://fhir.epic.com/.../DocumentReference/{id}/_history/{version}
            # or: https://fhir.epic.com/.../DocumentReference/{id}
            location = response.headers.get('Location', '')
            location_doc_id = None
            if location:
                self.logger.info(f"DocumentReference created, Location: {location}")
                # Parse Location URL to extract resource ID
                # Remove trailing slash if present
                location_path = location.rstrip('/')
                path_parts = location_path.split('/')
                
                # Find DocumentReference in path and take the next segment as ID
                for i, part in enumerate(path_parts):
                    if part == 'DocumentReference' and i + 1 < len(path_parts):
                        location_doc_id = path_parts[i + 1]
                        # Stop at _history marker
                        if location_doc_id == '_history':
                            location_doc_id = None
                        break
                
                if location_doc_id:
                    self.logger.info(f"Extracted DocumentReference ID from Location: {location_doc_id}")
            
            # Try to parse JSON response body
            if response.text and response.text.strip():
                try:
                    result = response.json()
                    doc_id = result.get('id') or location_doc_id
                    self.logger.info(f"Successfully created DocumentReference: {doc_id}")
                    return result
                except json.JSONDecodeError as e:
                    # Epic returned non-JSON content (possibly HTML error page or success message)
                    self.logger.warning(f"Could not parse response as JSON: {e}")
                    self.logger.debug(f"Response content (first 500 chars): {response.text[:500]}")
                    
                    # If we have a valid ID from Location header, consider it a success
                    if location_doc_id:
                        self.logger.info(f"DocumentReference created (from Location header): {location_doc_id}")
                        return {
                            'resourceType': 'DocumentReference',
                            'id': location_doc_id,
                            'location': location,
                            'status': 'current'
                        }
                    
                    # Otherwise return error with response details
                    return {
                        'error': f'Epic returned non-JSON response: {response.text[:200]}',
                        'details': {'raw_response': response.text[:1000]},
                        'is_sandbox_limitation': False,
                        'status_code': response.status_code
                    }
            else:
                # Empty response body - check for Location header
                if location_doc_id:
                    self.logger.info(f"DocumentReference created (from Location header, empty body): {location_doc_id}")
                    return {
                        'resourceType': 'DocumentReference',
                        'id': location_doc_id,
                        'location': location,
                        'status': 'current'
                    }
                
                # No body and no location - unexpected but may be success
                self.logger.warning(f"Empty response body with status {response.status_code} and no Location header")
                return {
                    'error': f'Epic returned empty response with status {response.status_code}',
                    'details': {},
                    'is_sandbox_limitation': False,
                    'status_code': response.status_code
                }
            
        except requests.exceptions.RequestException as e:
            # Network errors, timeouts, etc.
            self.logger.error(f"Request error creating DocumentReference: {str(e)}")
            return {
                'error': str(e),
                'details': {},
                'is_sandbox_limitation': False,
                'status_code': None
            }
            
        except json.JSONDecodeError as e:
            # Catch any JSON decode errors that slip through
            self.logger.error(f"JSON decode error creating DocumentReference: {str(e)}")
            return {
                'error': f'Failed to parse Epic response: {str(e)}',
                'details': {},
                'is_sandbox_limitation': False,
                'status_code': None
            }
            
        except Exception as e:
            self.logger.error(f"Error creating DocumentReference: {str(e)}")
            return {
                'error': str(e),
                'details': {},
                'is_sandbox_limitation': False
            }
    
    def _parse_epic_error_response(self, response):
        """Parse Epic FHIR OperationOutcome from error response
        
        Epic returns OperationOutcome resources with detailed error information
        including issue severity, code, and diagnostics.
        """
        error_info = {
            'status_code': None,
            'message': 'Unknown error',
            'issues': [],
            'raw_response': None
        }
        
        # Note: Use 'is None' check because requests.Response evaluates to False
        # for status codes >= 400, but the object still exists and has data
        if response is None:
            self.logger.warning("No response object available for error parsing")
            return error_info
        
        # Safely get status code
        try:
            error_info['status_code'] = response.status_code
        except Exception as e:
            self.logger.debug(f"Could not get status_code: {e}")
        
        # Safely capture raw response text first (critical for debugging)
        response_text = None
        try:
            response_text = response.text
            error_info['raw_response'] = response_text[:2000] if response_text else None
        except Exception as e:
            self.logger.debug(f"Could not read response text: {e}")
            
        # Try to parse as JSON
        try:
            if response_text:
                data = response.json()
                
                if data.get('resourceType') == 'OperationOutcome':
                    issues = data.get('issue', [])
                    error_info['issues'] = issues
                    
                    if issues:
                        # Collect all issue messages for comprehensive error
                        all_messages = []
                        for issue in issues:
                            diagnostics = issue.get('diagnostics', '')
                            details_text = issue.get('details', {}).get('text', '')
                            code = issue.get('code', '')
                            severity = issue.get('severity', 'error')
                            
                            msg = diagnostics or details_text or f"{severity}: {code}"
                            if msg:
                                all_messages.append(msg)
                        
                        first_issue = issues[0]
                        error_info['message'] = all_messages[0] if all_messages else 'OperationOutcome error'
                        error_info['all_messages'] = all_messages
                        error_info['severity'] = first_issue.get('severity', 'error')
                        error_info['code'] = first_issue.get('code', 'unknown')
                        
                        # Log all issues for debugging
                        self.logger.debug(f"OperationOutcome issues: {issues}")
                else:
                    # Non-OperationOutcome JSON response
                    error_info['message'] = data.get('error', data.get('message', str(data)[:500]))
        except ValueError as json_error:
            # Not valid JSON - use raw text
            if response_text:
                error_info['message'] = f"HTTP {error_info['status_code']}: {response_text[:500]}"
            self.logger.debug(f"Could not parse error response as JSON: {json_error}")
        except Exception as e:
            self.logger.debug(f"Error parsing response: {e}")
            if response_text:
                error_info['message'] = f"HTTP {error_info['status_code']}: {response_text[:500]}"
        
        # Log the full parsed error for debugging
        self.logger.info(f"Parsed Epic error: status={error_info['status_code']}, "
                        f"message={error_info['message'][:200]}, "
                        f"issues_count={len(error_info['issues'])}")
            
        return error_info
    
    def _is_sandbox_write_limitation(self, error_details):
        """Detect if error indicates Epic sandbox write limitations
        
        Epic's public sandbox (fhir.epic.com) often restricts or disables
        write operations like DocumentReference.create().
        """
        message = error_details.get('message', '').lower()
        raw = (error_details.get('raw_response') or '').lower()
        code = error_details.get('code', '').lower()
        
        sandbox_indicators = [
            'not supported',
            'read-only',
            'readonly',
            'write not allowed',
            'operation not permitted',
            'method not allowed',
            'not implemented',
            'sandbox does not support',
            'test environment',
            'unauthorized',
            'insufficient scope',
            'not-supported',  # FHIR issue code
            'business-rule',  # FHIR issue code for validation rules
            'processing',     # FHIR issue code for processing failures
        ]
        
        # Also check the issue code
        if code in ['not-supported', 'forbidden', 'security']:
            return True
        
        return any(indicator in message or indicator in raw for indicator in sandbox_indicators)
    
    def update_document_reference(self, document_id, document_reference_data):
        """Update an existing DocumentReference in Epic
        
        Returns:
            dict: On success, the updated DocumentReference resource
            dict: On failure, {'error': str, 'details': dict, 'is_sandbox_limitation': bool}
        """
        try:
            url = f"{self.base_url}DocumentReference/{document_id}"
            
            headers = self._get_headers()
            headers['Content-Type'] = 'application/fhir+json'
            
            self.logger.info(f"Updating DocumentReference at {url}")
            
            response = requests.put(url, headers=headers, json=document_reference_data)
            
            # Check status manually to ensure we have access to response object
            if response.status_code >= 400:
                error_details = self._parse_epic_error_response(response)
                
                is_sandbox = 'fhir.epic.com' in self.base_url or 'sandbox' in self.base_url.lower()
                is_write_not_supported = self._is_sandbox_write_limitation(error_details)
                
                self.logger.error(
                    f"Error updating DocumentReference {document_id}: HTTP {response.status_code}. "
                    f"OperationOutcome: {error_details}"
                )
                
                return {
                    'error': error_details.get('message', f'HTTP {response.status_code}'),
                    'details': error_details,
                    'is_sandbox_limitation': is_sandbox and is_write_not_supported,
                    'status_code': response.status_code
                }
            
            result = response.json()
            self.logger.info(f"Successfully updated DocumentReference: {document_id}")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error updating DocumentReference {document_id}: {str(e)}")
            return {
                'error': str(e),
                'details': {},
                'is_sandbox_limitation': False,
                'status_code': None
            }
            
        except Exception as e:
            self.logger.error(f"Error updating DocumentReference {document_id}: {str(e)}")
            return {
                'error': str(e),
                'details': {},
                'is_sandbox_limitation': False
            }
