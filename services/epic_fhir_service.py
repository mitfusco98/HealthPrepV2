"""
Epic FHIR Service Layer
Handles FHIR API operations, token management, and Epic integration
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from flask import session, current_app
from flask_login import current_user

from emr.fhir_client import FHIRClient
from emr.epic_integration import EpicScreeningIntegration
from models import db, Patient, FHIRDocument, Organization, ScreeningType, Provider
from routes.oauth_routes import get_epic_fhir_client, get_epic_fhir_client_background

logger = logging.getLogger(__name__)


class EpicFHIRService:
    """
    Service layer for Epic FHIR operations with enhanced token management.
    
    Supports two modes:
    1. Organization-level (legacy): Uses EpicCredentials for org-wide access
    2. Provider-level (v2.1): Uses Provider model for provider-specific access
    
    Provider-level mode is preferred and provides:
    - Per-provider OAuth tokens
    - Practitioner ID filtering for FHIR queries
    - Provider-scoped patient rosters
    """
    
    def __init__(self, organization_id: int = None, provider_id: int = None, background_context: bool = False):
        """
        Initialize Epic FHIR service.
        
        Args:
            organization_id: Organization ID (required for org-level or if provider not specified)
            provider_id: Provider ID for provider-specific access (preferred for v2.1)
            background_context: True for background jobs (uses database tokens)
        """
        self.provider_id = provider_id
        self.provider = None
        self.practitioner_id = None
        
        # Determine organization ID and context
        if background_context:
            # Background context: organization_id is required (or derived from provider)
            if provider_id:
                self.provider = Provider.query.get(provider_id)
                if self.provider:
                    self.organization_id = self.provider.org_id
                    self.practitioner_id = self.provider.epic_practitioner_id
                else:
                    raise ValueError(f"Provider {provider_id} not found")
            elif not organization_id:
                raise ValueError("organization_id or provider_id is required for background context")
            else:
                self.organization_id = organization_id
            self.is_background = True
        else:
            # Interactive context: try to get from current_user or provider
            if provider_id:
                self.provider = Provider.query.get(provider_id)
                if self.provider:
                    self.organization_id = self.provider.org_id
                    self.practitioner_id = self.provider.epic_practitioner_id
            else:
                self.organization_id = organization_id or (current_user.org_id if current_user and current_user.is_authenticated else None)
            self.is_background = False
        
        self.fhir_client = None
        self.organization = None
        
        if self.organization_id:
            self.organization = Organization.query.get(self.organization_id)
            
            if self.provider_id and self.provider:
                # Provider-specific mode: ONLY use provider's tokens (no org fallback for provider-scoped operations)
                if self.provider.is_epic_connected and self.provider.access_token:
                    self._init_fhir_client_from_provider()
                else:
                    # Provider not connected - do NOT fall back to org credentials
                    # This prevents PHI exposure across provider boundaries
                    logger.warning(f"Provider {self.provider_id} not Epic-connected, no FHIR client available")
                    self.fhir_client = None
            elif self.is_background:
                # Background context: use stored credentials from database
                logger.info(f"Creating background Epic FHIR client for organization {self.organization_id}")
                self.fhir_client = get_epic_fhir_client_background(self.organization_id)
                
                # If background client failed, create basic client for potential re-auth
                if not self.fhir_client and self.organization and self.organization.epic_client_id:
                    logger.warning(f"Background client failed, creating basic client for org {self.organization_id}")
                    epic_config = {
                        'epic_client_id': self.organization.epic_client_id,
                        'epic_client_secret': self.organization.epic_client_secret,
                        'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
                    }
                    self.fhir_client = FHIRClient(epic_config, organization=self.organization)
            else:
                # Interactive context: try session-based client first
                self.fhir_client = get_epic_fhir_client()
                
                # If no session-based client, create basic client with org config
                if not self.fhir_client and self.organization and self.organization.epic_client_id:
                    epic_config = {
                        'epic_client_id': self.organization.epic_client_id,
                        'epic_client_secret': self.organization.epic_client_secret,
                        'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
                    }
                    self.fhir_client = FHIRClient(epic_config, organization=self.organization)
    
    def _init_fhir_client_from_provider(self):
        """Initialize FHIR client using provider-specific tokens"""
        if not self.provider or not self.organization:
            return
        
        epic_config = {
            'epic_client_id': self.organization.epic_client_id,
            'epic_client_secret': self.organization.epic_client_secret,
            'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        self.fhir_client = FHIRClient(epic_config, organization=self.organization)
        
        # Load tokens from provider model
        self.fhir_client.access_token = self.provider.access_token
        self.fhir_client.refresh_token = self.provider.refresh_token
        self.fhir_client.token_expires = self.provider.token_expires_at
        if self.provider.token_scope:
            self.fhir_client.token_scopes = self.provider.token_scope.split()
        
        logger.info(f"Initialized FHIR client from provider {self.provider.id} ({self.provider.name})")
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure FHIR client is authenticated and tokens are valid.
        
        Supports both organization-level and provider-level authentication.
        Provider-level is preferred for v2.1 architecture.
        """
        context_label = f"provider {self.provider_id}" if self.provider_id else f"org {self.organization_id}"
        
        if not self.fhir_client:
            # Try to initialize from database credentials if available
            if self.provider_id:
                logger.info(f"No FHIR client available, attempting to load from provider {self.provider_id}")
                if self._load_tokens_from_provider():
                    logger.info(f"Successfully loaded tokens from provider {self.provider_id}")
                else:
                    logger.error(f"No FHIR client and no provider credentials available for {context_label}")
                    return False
            elif self.organization_id:
                logger.info(f"No FHIR client available, attempting to load from database for org {self.organization_id}")
                if self._load_tokens_from_database():
                    logger.info(f"Successfully loaded tokens from database for org {self.organization_id}")
                else:
                    logger.error(f"No FHIR client and no database credentials available for org {self.organization_id}")
                    return False
            else:
                logger.error("No FHIR client available and no organization/provider context - OAuth2 authentication required")
                return False
        
        if not self.fhir_client.access_token:
            # Try to load tokens from database if in background mode
            if self.provider_id:
                logger.info(f"No access token in client, attempting to load from provider {self.provider_id}")
                if self._load_tokens_from_provider():
                    logger.info(f"Successfully loaded tokens from provider {self.provider_id}")
                else:
                    logger.error(f"No access token available for {context_label}")
                    return False
            elif self.is_background and self.organization_id:
                logger.info(f"No access token in client, attempting to load from database for org {self.organization_id}")
                if self._load_tokens_from_database():
                    logger.info(f"Successfully loaded tokens from database for org {self.organization_id}")
                else:
                    logger.error(f"No access token available and no database credentials for org {self.organization_id}")
                    return False
            else:
                logger.error("No access token available - OAuth2 authentication required")
                return False
        
        # Check if token is expired
        if self.fhir_client.token_expires and datetime.now() >= self.fhir_client.token_expires:
            logger.info(f"Access token expired for {context_label}, attempting refresh")
            if not self.fhir_client.refresh_access_token():
                logger.error(f"Failed to refresh access token for {context_label}")
                # If refresh fails, try to reload from database (in case tokens were updated elsewhere)
                if self.provider_id:
                    logger.info("Attempting to reload tokens from provider after refresh failure")
                    if self._load_tokens_from_provider():
                        logger.info("Reloaded tokens from provider, retrying authentication")
                        return self.ensure_authenticated()  # Recursive retry with fresh tokens
                elif self.is_background and self.organization_id:
                    logger.info("Attempting to reload tokens from database after refresh failure")
                    if self._load_tokens_from_database():
                        logger.info("Reloaded tokens from database, retrying authentication")
                        return self.ensure_authenticated()  # Recursive retry with fresh tokens
                return False
            
            # Update tokens based on context - always prefer database storage
            if self.provider_id:
                # Provider-specific: update provider model
                self._update_provider_tokens()
                logger.info(f"Updated tokens for provider {self.provider_id}")
            elif self.is_background or self.organization_id:
                # Background context or any context with org: update database storage
                self._update_database_tokens()
                logger.info(f"Updated tokens in database for org {self.organization_id}")
            else:
                # Interactive context without org: update session
                try:
                    session['epic_access_token'] = self.fhir_client.access_token
                    if self.fhir_client.refresh_token:
                        session['epic_refresh_token'] = self.fhir_client.refresh_token
                    expires_in = int((self.fhir_client.token_expires - datetime.now()).total_seconds())
                    session['epic_token_expires'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                    logger.info("Updated tokens in session")
                except RuntimeError:
                    # No session available (e.g., background context detected late)
                    logger.warning("No session available to update tokens, updating database instead")
                    if self.organization_id:
                        self._update_database_tokens()
        
        logger.info(f"Authentication verified for {context_label}")
        return True
    
    def _load_tokens_from_provider(self) -> bool:
        """Load Epic tokens from Provider model"""
        try:
            if not self.provider:
                self.provider = Provider.query.get(self.provider_id)
            
            if not self.provider:
                logger.error(f"Provider {self.provider_id} not found")
                return False
            
            if not self.provider.access_token:
                logger.info(f"No access token stored for provider {self.provider_id}")
                return False
            
            # Create FHIR client if needed
            if not self.fhir_client and self.organization:
                epic_config = {
                    'epic_client_id': self.organization.epic_client_id,
                    'epic_client_secret': self.organization.epic_client_secret,
                    'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
                }
                self.fhir_client = FHIRClient(epic_config, organization=self.organization)
                logger.info(f"Created FHIR client for provider {self.provider_id}")
            
            if self.fhir_client:
                # Load tokens into FHIR client
                self.fhir_client.access_token = self.provider.access_token
                self.fhir_client.refresh_token = self.provider.refresh_token
                self.fhir_client.token_expires = self.provider.token_expires_at
                if self.provider.token_scope:
                    self.fhir_client.token_scopes = self.provider.token_scope.split()
                
                # Store practitioner ID for filtering
                self.practitioner_id = self.provider.epic_practitioner_id
                
                logger.info(f"Successfully loaded tokens from provider {self.provider_id}")
                logger.info(f"Token expires at: {self.provider.token_expires_at}")
                return True
            else:
                logger.error(f"Cannot load tokens: no FHIR client available for provider {self.provider_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading tokens from provider {self.provider_id}: {str(e)}")
            return False
    
    def _update_provider_tokens(self):
        """Update Epic tokens in Provider model (after token refresh)"""
        try:
            if not self.provider:
                self.provider = Provider.query.get(self.provider_id)
            
            if self.provider and self.fhir_client:
                self.provider.access_token = self.fhir_client.access_token
                if self.fhir_client.refresh_token:
                    self.provider.refresh_token = self.fhir_client.refresh_token
                self.provider.token_expires_at = self.fhir_client.token_expires
                if self.fhir_client.token_scopes:
                    self.provider.token_scope = ' '.join(self.fhir_client.token_scopes)
                self.provider.last_epic_sync = datetime.now()
                
                db.session.commit()
                logger.info(f"Updated Epic tokens for provider {self.provider_id}")
            else:
                logger.error(f"Cannot update provider tokens: provider or client not available")
        except Exception as e:
            logger.error(f"Error updating provider tokens: {str(e)}")
            db.session.rollback()
    
    def _load_tokens_from_database(self) -> bool:
        """Load Epic tokens from database storage"""
        try:
            from models import EpicCredentials
            
            epic_creds = EpicCredentials.query.filter_by(org_id=self.organization_id).first()
            if epic_creds and epic_creds.access_token:
                # Check if we have a valid client to load tokens into
                if not self.fhir_client and self.organization:
                    # Create FHIR client if needed
                    epic_config = {
                        'epic_client_id': self.organization.epic_client_id,
                        'epic_client_secret': self.organization.epic_client_secret,
                        'epic_fhir_url': self.organization.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
                    }
                    self.fhir_client = FHIRClient(epic_config, organization=self.organization)
                    logger.info(f"Created FHIR client for token loading for org {self.organization_id}")
                
                if self.fhir_client:
                    # Load tokens into FHIR client
                    self.fhir_client.access_token = epic_creds.access_token
                    self.fhir_client.refresh_token = epic_creds.refresh_token
                    self.fhir_client.token_expires = epic_creds.token_expires_at
                    if epic_creds.token_scope:
                        self.fhir_client.token_scopes = epic_creds.token_scope.split()
                    
                    logger.info(f"Successfully loaded tokens from database for org {self.organization_id}")
                    logger.info(f"Token expires at: {epic_creds.token_expires_at}")
                    return True
                else:
                    logger.error(f"Cannot load tokens: no FHIR client available for org {self.organization_id}")
                    return False
            else:
                logger.info(f"No database credentials found for organization {self.organization_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading tokens from database for org {self.organization_id}: {str(e)}")
            return False
    
    def _update_database_tokens(self):
        """Update Epic tokens in database storage (for background context or session failures)"""
        try:
            from models import EpicCredentials
            
            epic_creds = EpicCredentials.query.filter_by(org_id=self.organization_id).first()
            if epic_creds:
                # Update existing credentials
                epic_creds.access_token = self.fhir_client.access_token
                if self.fhir_client.refresh_token:
                    epic_creds.refresh_token = self.fhir_client.refresh_token
                epic_creds.token_expires_at = self.fhir_client.token_expires
                if self.fhir_client.token_scopes:
                    epic_creds.token_scope = ' '.join(self.fhir_client.token_scopes)
                epic_creds.updated_at = datetime.now()
                
                db.session.commit()
                logger.info(f"Updated Epic tokens in database for organization {self.organization_id}")
            else:
                logger.error(f"No Epic credentials record found for organization {self.organization_id}")
        except Exception as e:
            logger.error(f"Error updating database tokens: {str(e)}")
            db.session.rollback()
    
    def sync_patient_from_epic(self, epic_patient_id: str) -> Optional[Patient]:
        """
        Sync patient data from Epic FHIR and create/update local record.
        
        If service was initialized with provider_id, the patient will be
        assigned to that provider.
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Fetch patient from Epic
            fhir_patient = self.fhir_client.get_patient(epic_patient_id)
            if not fhir_patient:
                logger.error(f"Patient not found in Epic: {epic_patient_id}")
                return None
            
            # Find existing patient or create new one
            # If provider_id is set, check for patient in provider's roster
            if self.provider_id:
                patient = Patient.query.filter_by(
                    epic_patient_id=epic_patient_id,
                    org_id=self.organization_id,
                    provider_id=self.provider_id
                ).first()
            else:
                patient = Patient.query.filter_by(
                    epic_patient_id=epic_patient_id,
                    org_id=self.organization_id
                ).first()
            
            if not patient:
                # Create new patient from FHIR data
                patient = self._create_patient_from_fhir(fhir_patient)
            else:
                # Update existing patient
                patient.update_from_fhir(fhir_patient)
            
            db.session.add(patient)
            db.session.commit()
            
            context_label = f"provider {self.provider_id}" if self.provider_id else f"org {self.organization_id}"
            logger.info(f"Successfully synced patient {epic_patient_id} from Epic for {context_label}")
            return patient
            
        except Exception as e:
            logger.error(f"Error syncing patient from Epic: {str(e)}")
            db.session.rollback()
            raise
    
    def _create_patient_from_fhir(self, fhir_patient: dict) -> Patient:
        """
        Create new Patient record from FHIR Patient resource.
        
        If service was initialized with provider_id, the patient will be
        assigned to that provider's roster.
        """
        patient = Patient()
        patient.org_id = self.organization_id
        patient.epic_patient_id = fhir_patient.get('id')
        
        # Assign to provider if in provider context
        if self.provider_id:
            patient.provider_id = self.provider_id
        
        # Extract MRN from identifiers
        if 'identifier' in fhir_patient:
            for identifier in fhir_patient['identifier']:
                if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                    patient.mrn = identifier.get('value')
                    break
        
        if not patient.mrn:
            patient.mrn = f"EPIC_{fhir_patient.get('id')}"
        
        # Update from FHIR data
        patient.update_from_fhir(fhir_patient)
        
        return patient
    
    def get_provider_appointments(self, days_ahead: int = 14) -> List[dict]:
        """
        Get appointments for this provider from Epic FHIR.
        
        Filters by Practitioner ID if available (from fhirUser claim).
        This implements the 2-week appointment prioritization window.
        
        Args:
            days_ahead: Number of days to look ahead (default 14 days)
            
        Returns:
            List of FHIR Appointment resources for this provider
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        if not self.practitioner_id:
            logger.warning("No Practitioner ID available for provider-filtered appointments")
            return []
        
        try:
            from datetime import date, timedelta
            
            start_date = date.today()
            end_date = start_date + timedelta(days=days_ahead)
            
            # Query appointments filtered by practitioner
            appointments = self.fhir_client.search_appointments(
                practitioner=f"Practitioner/{self.practitioner_id}",
                date_from=start_date.isoformat(),
                date_to=end_date.isoformat()
            )
            
            logger.info(f"Retrieved {len(appointments)} appointments for practitioner {self.practitioner_id}")
            return appointments
            
        except Exception as e:
            logger.error(f"Error fetching provider appointments: {str(e)}")
            return []
    
    def sync_provider_patient_roster(self, days_ahead: int = 14) -> List[Patient]:
        """
        Sync patients from upcoming appointments for this provider.
        
        This creates/updates Patient records for all patients with
        appointments in the specified window, assigning them to this provider.
        
        Args:
            days_ahead: Number of days to look ahead (default 14 days)
            
        Returns:
            List of synced Patient records
        """
        if not self.provider_id:
            raise ValueError("Provider ID required for roster sync")
        
        appointments = self.get_provider_appointments(days_ahead)
        synced_patients = []
        
        for appt in appointments:
            # Extract patient reference from appointment
            patient_refs = [
                p.get('actor', {}).get('reference', '')
                for p in appt.get('participant', [])
                if 'Patient/' in p.get('actor', {}).get('reference', '')
            ]
            
            for patient_ref in patient_refs:
                epic_patient_id = patient_ref.split('Patient/')[-1].split('/')[0]
                if epic_patient_id:
                    try:
                        patient = self.sync_patient_from_epic(epic_patient_id)
                        if patient:
                            synced_patients.append(patient)
                    except Exception as e:
                        logger.error(f"Error syncing patient {epic_patient_id}: {str(e)}")
        
        logger.info(f"Synced {len(synced_patients)} patients for provider {self.provider_id}")
        return synced_patients
    
    def check_patient_immunization_screening(self, patient: Patient, screening_type: ScreeningType) -> dict:
        """
        Check immunization status for a patient based on a screening type.
        
        This is used for immunization-based screening types (where is_immunization_based=True)
        instead of the normal document scanning approach.
        
        SECURITY: This enforces provider scope - if initialized with provider_id, only
        patients belonging to that provider can be checked.
        
        Args:
            patient: Patient record to check
            screening_type: ScreeningType with immunization in name and vaccine_codes
            
        Returns:
            dict with:
                - status: 'complete', 'due_soon', or 'due'
                - last_completed: date or None
                - next_due: date or None
                - immunization_records: list of FHIR Immunization resources
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        # SECURITY: Enforce provider scope if in provider context
        if self.provider_id and patient.provider_id and patient.provider_id != self.provider_id:
            logger.error(f"SECURITY: Attempted cross-provider immunization check. "
                        f"Service provider: {self.provider_id}, Patient provider: {patient.provider_id}")
            raise ValueError("Access denied: Patient belongs to a different provider")
        
        if not patient.epic_patient_id:
            logger.warning(f"Patient {patient.id} has no Epic patient ID for immunization check")
            return {
                'status': 'due',
                'last_completed': None,
                'next_due': None,
                'immunization_records': []
            }
        
        if not screening_type.is_immunization_based:
            logger.warning(f"Screening type {screening_type.name} is not immunization-based")
            return {
                'status': 'due',
                'last_completed': None,
                'next_due': None,
                'immunization_records': []
            }
        
        try:
            from datetime import date
            from core.criteria import EligibilityCriteria
            
            vaccine_codes = screening_type.vaccine_codes_list
            
            if not vaccine_codes:
                # Return unknown status when vaccine codes not configured
                # This allows the screening to be displayed but not auto-determined
                logger.info(f"No vaccine codes defined for {screening_type.name} - returning unknown status")
                return {
                    'status': 'unknown',  # Special status indicating manual review needed
                    'last_completed': None,
                    'next_due': None,
                    'immunization_records': [],
                    'requires_vaccine_codes': True
                }
            
            # Fetch immunization records from FHIR
            immunizations = self.fhir_client.get_patient_immunizations(
                patient.epic_patient_id,
                vaccine_codes
            )
            
            # Extract the most recent immunization date as last_completed
            last_completed = None
            if immunizations:
                # Parse dates from immunization records and find the most recent
                for imm in immunizations:
                    occurrence_date = imm.get('occurrenceDateTime') or imm.get('occurrenceString')
                    if occurrence_date:
                        try:
                            # Parse FHIR date format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
                            if 'T' in str(occurrence_date):
                                imm_date = date.fromisoformat(str(occurrence_date).split('T')[0])
                            else:
                                imm_date = date.fromisoformat(str(occurrence_date))
                            
                            if last_completed is None or imm_date > last_completed:
                                last_completed = imm_date
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not parse immunization date {occurrence_date}: {e}")
            
            # Use the shared criteria engine for consistent status calculation
            # This ensures immunization screenings follow the same rules as document-based screenings
            criteria = EligibilityCriteria()
            status = criteria.calculate_screening_status(screening_type, last_completed)
            
            # Calculate next due date for response
            next_due = None
            if last_completed and screening_type.frequency_value and screening_type.frequency_unit:
                next_due = criteria._calculate_next_due_date(
                    last_completed,
                    screening_type.frequency_value,
                    screening_type.frequency_unit
                )
            
            return {
                'status': status,
                'last_completed': last_completed,
                'next_due': next_due,
                'immunization_records': immunizations or []
            }
            
        except Exception as e:
            logger.error(f"Error checking immunization for patient {patient.id}: {str(e)}")
            return {
                'status': 'due',
                'last_completed': None,
                'next_due': None,
                'immunization_records': []
            }
    
    def update_immunization_screening(self, patient: Patient, screening_type: ScreeningType) -> Optional['Screening']:
        """
        Update or create a Screening record based on immunization data.
        
        This replaces document-based screening detection for immunization types.
        
        Args:
            patient: Patient to update screening for
            screening_type: Immunization-based ScreeningType
            
        Returns:
            Updated or created Screening record
        """
        from models import Screening
        
        immunization_result = self.check_patient_immunization_screening(patient, screening_type)
        
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id,
            org_id=self.organization_id
        ).first()
        
        if not screening:
            screening = Screening()
            screening.patient_id = patient.id
            screening.screening_type_id = screening_type.id
            screening.org_id = self.organization_id
            if self.provider_id:
                screening.provider_id = self.provider_id
        
        screening.status = immunization_result['status']
        screening.last_completed = immunization_result['last_completed']
        screening.next_due = immunization_result['next_due']
        
        db.session.add(screening)
        db.session.commit()
        
        logger.info(f"Updated immunization screening {screening_type.name} for patient {patient.id}: {screening.status}")
        
        # Store immunization records as FHIRDocument entries for admin documents view
        self._sync_immunization_records(patient, screening_type, immunization_result.get('immunization_records', []))
        
        return screening
    
    def _sync_immunization_records(self, patient: Patient, screening_type: 'ScreeningType', immunization_records: List[dict]) -> List[FHIRDocument]:
        """
        Sync immunization records as FHIRDocument entries.
        
        This allows immunization records to appear in /admin/documents view
        and be matched by the screening engine based on title keywords.
        
        Args:
            patient: Patient the immunizations belong to
            screening_type: ScreeningType for context (vaccine name)
            immunization_records: List of FHIR Immunization resources
            
        Returns:
            List of created/updated FHIRDocument records
        """
        import json
        from datetime import datetime as dt
        
        synced_docs = []
        
        for imm_record in immunization_records:
            try:
                imm_id = imm_record.get('id')
                if not imm_id:
                    continue
                
                epic_doc_id = f"immunization-{imm_id}"
                
                fhir_doc = FHIRDocument.query.filter_by(
                    epic_document_id=epic_doc_id,
                    org_id=self.organization_id
                ).first()
                
                is_new = fhir_doc is None
                if is_new:
                    fhir_doc = FHIRDocument()
                    fhir_doc.patient_id = patient.id
                    fhir_doc.org_id = self.organization_id
                    fhir_doc.epic_document_id = epic_doc_id
                    fhir_doc.created_at = dt.utcnow()
                
                vaccine_code = imm_record.get('vaccineCode', {})
                vaccine_display = ''
                if vaccine_code.get('text'):
                    vaccine_display = vaccine_code['text']
                elif vaccine_code.get('coding'):
                    for coding in vaccine_code['coding']:
                        if coding.get('display'):
                            vaccine_display = coding['display']
                            break
                
                if not vaccine_display:
                    vaccine_display = screening_type.name if screening_type else "Unknown Vaccine"
                
                occurrence_date = None
                occurrence_datetime = None
                if imm_record.get('occurrenceDateTime'):
                    try:
                        date_str = imm_record['occurrenceDateTime'][:10]
                        occurrence_date = dt.strptime(date_str, '%Y-%m-%d').date()
                        occurrence_datetime = dt.strptime(date_str, '%Y-%m-%d')
                    except (ValueError, TypeError):
                        pass
                
                # HIPAA COMPLIANCE: Use structured code-derived title, not free text with vaccine name
                # The vaccine name may be PHI-safe, but we enforce consistency with the deterministic approach
                fhir_doc.title = "Immunization Record"
                fhir_doc.document_type_display = "Immunization Record"
                fhir_doc.document_type_code = "11369-6"
                # Description redacted - vaccine_display may contain PHI
                fhir_doc.description = None
                fhir_doc.document_date = occurrence_date
                
                if is_new:
                    fhir_doc.creation_date = occurrence_datetime or dt.utcnow()
                
                # HIPAA COMPLIANCE: Sanitize FHIR resource before storage
                from ocr.phi_filter import PHIFilter
                phi_filter = PHIFilter()
                fhir_doc.fhir_document_reference = phi_filter.sanitize_fhir_resource(json.dumps(imm_record))
                fhir_doc.content_type = "application/fhir+json"
                fhir_doc.is_processed = True
                fhir_doc.processing_status = "completed"
                
                # HIPAA COMPLIANCE: Use generic searchable terms, not patient-specific data
                fhir_doc.set_ocr_text("immunization vaccine vaccination record")
                
                db.session.add(fhir_doc)
                synced_docs.append(fhir_doc)
                
            except Exception as e:
                logger.warning(f"Error syncing immunization record: {str(e)}")
                continue
        
        if synced_docs:
            try:
                db.session.commit()
                logger.info(f"Synced {len(synced_docs)} immunization records as FHIRDocuments for patient {patient.id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error committing immunization FHIRDocuments: {str(e)}")
                return []
        
        return synced_docs
    
    def sync_patient_documents(self, patient: Patient) -> List[FHIRDocument]:
        """
        Sync patient documents from Epic DocumentReference resources.
        
        SECURITY: Enforces provider scope when initialized with provider_id.
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        # SECURITY: Enforce provider scope if in provider context
        if self.provider_id and patient.provider_id and patient.provider_id != self.provider_id:
            logger.error(f"SECURITY: Attempted cross-provider document sync. "
                        f"Service provider: {self.provider_id}, Patient provider: {patient.provider_id}")
            raise ValueError("Access denied: Patient belongs to a different provider")
        
        if not patient.epic_patient_id:
            logger.warning(f"Patient {patient.id} has no Epic patient ID")
            return []
        
        try:
            # Fetch documents from Epic
            document_references = self.fhir_client.get_patient_documents(patient.epic_patient_id)
            synced_documents = []
            
            for doc_ref in document_references:
                fhir_doc = self._sync_document_reference(patient, doc_ref)
                if fhir_doc:
                    synced_documents.append(fhir_doc)
            
            db.session.commit()
            logger.info(f"Synced {len(synced_documents)} documents for patient {patient.id}")
            return synced_documents
            
        except Exception as e:
            logger.error(f"Error syncing documents for patient {patient.id}: {str(e)}")
            db.session.rollback()
            raise
    
    def _sync_document_reference(self, patient: Patient, doc_ref: dict) -> Optional[FHIRDocument]:
        """Sync individual DocumentReference to FHIRDocument"""
        epic_doc_id = doc_ref.get('id')
        if not epic_doc_id:
            return None
        
        # Find existing document or create new one
        fhir_doc = FHIRDocument.query.filter_by(
            epic_document_id=epic_doc_id,
            org_id=self.organization_id
        ).first()
        
        if not fhir_doc:
            fhir_doc = FHIRDocument()
            fhir_doc.patient_id = patient.id
            fhir_doc.org_id = self.organization_id
            fhir_doc.epic_document_id = epic_doc_id
        
        # Update from FHIR data
        fhir_doc.update_from_fhir(doc_ref)
        
        db.session.add(fhir_doc)
        return fhir_doc
    
    def write_prep_sheet_to_epic(self, patient: Patient, prep_sheet_content: str, 
                                screening_types: List[ScreeningType]) -> Optional[str]:
        """
        Write preparation sheet back to Epic as DocumentReference
        Returns Epic DocumentReference ID if successful
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Create FHIR DocumentReference for prep sheet
            document_reference = self._create_prep_sheet_document_reference(
                patient, prep_sheet_content, screening_types
            )
            
            # Post to Epic FHIR server
            result = self.fhir_client.create_document_reference(document_reference)
            
            if result and 'id' in result:
                epic_doc_id = result['id']
                
                # Create local FHIRDocument record
                fhir_doc = FHIRDocument()
                fhir_doc.patient_id = patient.id
                fhir_doc.org_id = self.organization_id
                fhir_doc.epic_document_id = epic_doc_id
                fhir_doc.update_from_fhir(result)
                fhir_doc.mark_processed('completed', ocr_text=prep_sheet_content)
                
                db.session.add(fhir_doc)
                db.session.commit()
                
                logger.info(f"Successfully wrote prep sheet to Epic for patient {patient.id}: {epic_doc_id}")
                return epic_doc_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error writing prep sheet to Epic: {str(e)}")
            db.session.rollback()
            raise
    
    def _create_prep_sheet_document_reference(self, patient: Patient, content: str, 
                                           screening_types: List[ScreeningType]) -> dict:
        """Create FHIR DocumentReference resource for prep sheet"""
        import base64
        
        # Generate screening type summary
        screening_names = [st.name for st in screening_types]
        title = f"Medical Screening Preparation Sheet - {', '.join(screening_names[:3])}"
        if len(screening_names) > 3:
            title += f" (+{len(screening_names) - 3} more)"
        
        document_reference = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Provider-unspecified progress note"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "LP173421-1",
                            "display": "Clinical note"
                        }
                    ]
                }
            ],
            "subject": {
                "reference": f"Patient/{patient.epic_patient_id}"
            },
            "date": datetime.utcnow().isoformat() + "Z",
            "author": [
                {
                    "display": f"HealthPrep System - {self.organization.name}"
                }
            ],
            "description": title,
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": base64.b64encode(content.encode('utf-8')).decode('ascii'),
                        "title": title,
                        "creation": datetime.utcnow().isoformat() + "Z"
                    }
                }
            ]
        }
        
        return document_reference
    
    def process_fhir_documents_for_screening(self, patient: Patient, 
                                           screening_types: List[ScreeningType]) -> List[FHIRDocument]:
        """
        Process FHIR documents for screening relevance using OCR and keyword matching
        """
        if not patient.fhir_documents:
            return []
        
        relevant_documents = []
        
        for fhir_doc in patient.fhir_documents:
            try:
                # Skip HealthPrep-generated documents (no need for OCR processing)
                if fhir_doc.is_healthprep_generated:
                    fhir_doc.mark_processed('skipped_healthprep_generated')
                    continue
                
                # Download and process document content if not already processed
                if not fhir_doc.is_processed and fhir_doc.content_url:
                    self._download_and_process_document(fhir_doc)
                
                # Check relevance for screening types
                for screening_type in screening_types:
                    if fhir_doc.is_relevant_for_screening(screening_type):
                        # Calculate relevance score based on keyword matching
                        relevance_score = self._calculate_relevance_score(fhir_doc, screening_type)
                        
                        if relevance_score > 0.3:  # Threshold for relevance
                            fhir_doc.relevance_score = relevance_score
                            relevant_documents.append(fhir_doc)
                
            except Exception as e:
                logger.error(f"Error processing FHIR document {fhir_doc.id}: {str(e)}")
                fhir_doc.mark_processed('failed', error=str(e))
        
        db.session.commit()
        return relevant_documents
    
    def _download_and_process_document(self, fhir_doc: FHIRDocument):
        """Download document content from Epic and extract text"""
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        try:
            # Download document content
            content = self.fhir_client.get_document_content(fhir_doc.content_url)
            
            if content and fhir_doc.is_pdf:
                # Use OCR to extract text from PDF
                from ocr.pdf_processor import PDFProcessor
                processor = PDFProcessor()
                ocr_result = processor.process_pdf_content(content)
                extracted_text = ocr_result.get('text', '')
            elif content:
                extracted_text = content.decode('utf-8', errors='ignore')
            else:
                extracted_text = None
            
            # mark_processed applies PHI filtering automatically
            fhir_doc.mark_processed('completed', ocr_text=extracted_text)
            fhir_doc.last_accessed = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error downloading document {fhir_doc.epic_document_id}: {str(e)}")
            fhir_doc.mark_processed('failed', error=str(e))
    
    def _calculate_relevance_score(self, fhir_doc: FHIRDocument, screening_type: ScreeningType) -> float:
        """Calculate relevance score based on keyword matching"""
        if not fhir_doc.ocr_text or not screening_type.keywords_list:
            return 0.0
        
        from utils.fuzzy_matching import FuzzyMatcher
        matcher = FuzzyMatcher()
        
        text_lower = fhir_doc.ocr_text.lower()
        total_keywords = len(screening_type.keywords_list)
        matched_keywords = 0
        
        for keyword in screening_type.keywords_list:
            if matcher.fuzzy_match(keyword.lower(), text_lower, threshold=0.8):
                matched_keywords += 1
        
        return matched_keywords / total_keywords if total_keywords > 0 else 0.0
    
    def get_patient_screening_data(self, patient: Patient, 
                                 screening_types: List[ScreeningType]) -> Dict[str, Any]:
        """
        Get comprehensive screening data for patient from Epic FHIR
        Implements Epic's blueprint data retrieval sequence
        """
        if not self.ensure_authenticated():
            raise Exception("Epic FHIR authentication required")
        
        if not patient.epic_patient_id:
            raise Exception(f"Patient {patient.id} has no Epic patient ID")
        
        try:
            # Use Epic integration for comprehensive data retrieval
            epic_integration = EpicScreeningIntegration(self.organization_id)
            epic_integration.fhir_client = self.fhir_client
            
            screening_type_names = [st.name for st in screening_types]
            screening_data = epic_integration.get_screening_data_for_patient(
                patient.mrn, screening_type_names
            )
            
            return screening_data
            
        except Exception as e:
            logger.error(f"Error getting screening data for patient {patient.id}: {str(e)}")
            raise
    
    def get_fhir_client(self):
        """
        Get the FHIR client instance for this service
        Returns the authenticated FHIR client or None if not available
        """
        return self.fhir_client


def get_epic_fhir_service(organization_id: int = None, background_context: bool = False) -> EpicFHIRService:
    """Factory function to get Epic FHIR service instance"""
    return EpicFHIRService(organization_id, background_context)


def get_epic_fhir_service_background(organization_id: int) -> EpicFHIRService:
    """Factory function to get Epic FHIR service instance for background processes"""
    return EpicFHIRService(organization_id, background_context=True)