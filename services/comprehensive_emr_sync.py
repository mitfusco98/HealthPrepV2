"""
Comprehensive EMR Synchronization Service
Implements Epic's recommended FHIR data retrieval sequence:
Patient → Conditions → Observations → Documents → Encounters
"""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dateutil.relativedelta import relativedelta

from flask import session, has_request_context
from flask_login import current_user

from models import db, Patient, PatientCondition, FHIRDocument, Document, Organization, ScreeningType, Appointment, ScreeningDocumentMatch
from services.epic_fhir_service import EpicFHIRService, get_epic_fhir_service_background
from emr.fhir_client import FHIRClient
from core.engine import ScreeningEngine
from ocr.document_processor import DocumentProcessor
from ocr.phi_filter import PHIFilter

logger = logging.getLogger(__name__)


class ComprehensiveEMRSync:
    """
    Comprehensive EMR synchronization service following Epic's recommended sequence.
    Retrieves Patient → Conditions → Observations → Documents → Encounters
    and processes data for screening engine integration.
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.organization = Organization.query.get(organization_id)
        
        # EMR sync operations should ALWAYS use database-stored tokens for stability
        # Session tokens are volatile and expire quickly - not suitable for long-running sync operations
        logger.info(f"ComprehensiveEMRSync: forcing database/background token usage for org {organization_id}")
        
        # Always use background service for EMR sync operations
        self.epic_service = get_epic_fhir_service_background(organization_id)
        
        # If background service fails, ensure we have database credentials to work with
        if not self.epic_service or not hasattr(self.epic_service, 'fhir_client') or not self.epic_service.fhir_client:
            logger.warning(f"Background Epic FHIR service unavailable for org {organization_id}")
            
            # Check if we have database credentials
            from models import EpicCredentials
            epic_creds = EpicCredentials.query.filter_by(org_id=organization_id).first()
            if epic_creds and epic_creds.access_token:
                logger.info(f"Found database credentials for org {organization_id}, creating service manually")
                self.epic_service = EpicFHIRService(organization_id, background_context=True)
            else:
                logger.error(f"No database credentials available for org {organization_id} - OAuth2 authentication required")
                raise ValueError(f"Epic FHIR authentication required for organization {organization_id}")
        
        logger.info(f"ComprehensiveEMRSync: using database-stored tokens for stable sync operations")
            
        self.screening_engine = ScreeningEngine()
        self.document_processor = DocumentProcessor()
        self.phi_filter = PHIFilter()
        
        # Track sync progress
        self.sync_stats = {
            'patients_processed': 0,
            'conditions_synced': 0,
            'observations_synced': 0,
            'documents_processed': 0,
            'encounters_synced': 0,
            'appointments_synced': 0,
            'screenings_updated': 0,
            'errors': []
        }
        
        logger.info(f"Initialized ComprehensiveEMRSync for organization {organization_id}")
    
    def _should_skip_patient_sync(self, patient: Patient, sync_options: Dict[str, Any]) -> bool:
        """
        Pre-flight check to determine if patient sync can be skipped.
        Uses deterministic change detection based on:
        - criteria_last_changed_at on ScreeningType (SHA-256 based signature changes)
        - documents_last_evaluated_at on Patient
        
        Skips if:
        - Patient has been evaluated since the last criteria change
        - No new documents since last evaluation
        - force_refresh not enabled
        
        Returns:
            True if sync can be safely skipped, False otherwise
        """
        from models import Document, FHIRDocument, ScreeningType, Screening
        
        # Never skip if force refresh is requested
        if sync_options.get('force_refresh', False):
            logger.debug(f"Force refresh enabled for {patient.epic_patient_id}, cannot skip")
            return False
        
        # If never synced before, don't skip
        if not patient.last_fhir_sync:
            logger.debug(f"Patient {patient.epic_patient_id} never synced before, cannot skip")
            return False
        
        # If patient has never had documents evaluated, don't skip
        if not patient.documents_last_evaluated_at:
            logger.debug(f"Patient {patient.epic_patient_id} never had documents evaluated, cannot skip")
            return False
        
        # If patient has no screenings, they've never been fully processed - don't skip
        screening_count = Screening.query.filter_by(patient_id=patient.id).count()
        if screening_count == 0:
            logger.debug(f"Patient {patient.epic_patient_id} has no screenings, cannot skip first full sync")
            return False
        
        try:
            # Get all active screening types for this organization
            active_screening_types = ScreeningType.query.filter_by(
                org_id=patient.org_id,
                is_active=True
            ).all()
            
            # Find the most recent criteria change across all screening types
            # This uses the deterministic criteria_last_changed_at field that's updated
            # only when criteria_signature (SHA-256 of keywords/eligibility/frequency) changes
            latest_criteria_change = None
            for st in active_screening_types:
                if st.criteria_last_changed_at:
                    if latest_criteria_change is None or st.criteria_last_changed_at > latest_criteria_change:
                        latest_criteria_change = st.criteria_last_changed_at
            
            # Check if patient needs re-evaluation based on criteria changes
            # This uses the deterministic method on Patient model
            if latest_criteria_change and patient.needs_document_evaluation(latest_criteria_change):
                logger.info(f"Screening criteria changed since last evaluation for {patient.epic_patient_id} "
                          f"(last eval: {patient.documents_last_evaluated_at}, criteria changed: {latest_criteria_change}), cannot skip")
                return False
            
            # Check for new documents since last evaluation
            # This counts documents added after the patient's documents were last evaluated
            new_manual_docs = Document.query.filter(
                Document.patient_id == patient.id,
                Document.created_at > patient.documents_last_evaluated_at
            ).count()
            
            new_fhir_docs = FHIRDocument.query.filter(
                FHIRDocument.patient_id == patient.id,
                FHIRDocument.created_at > patient.documents_last_evaluated_at
            ).count()
            
            total_new_docs = new_manual_docs + new_fhir_docs
            
            if total_new_docs > 0:
                logger.info(f"Found {total_new_docs} new documents for {patient.epic_patient_id} since last evaluation, cannot skip")
                return False
            
            # All checks passed - safe to skip
            logger.info(f"No changes detected for {patient.epic_patient_id} since last evaluation "
                      f"(evaluated: {patient.documents_last_evaluated_at}), skipping reprocessing")
            return True
            
        except Exception as e:
            logger.error(f"Error in skip check for {patient.epic_patient_id}: {str(e)}, will not skip")
            return False
    
    def sync_patient_comprehensive(self, epic_patient_id: str, 
                                 sync_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform comprehensive patient synchronization following Epic's sequence:
        Patient → Conditions → Observations → Documents → Encounters
        
        Args:
            epic_patient_id: Patient identifier in Epic
            sync_options: Configuration options for sync behavior
        
        Returns:
            Dict with sync results and statistics
        """
        if sync_options is None:
            sync_options = self._get_default_sync_options()
        
        try:
            logger.info(f"Starting comprehensive sync for patient {epic_patient_id}")
            
            # Ensure we have valid authentication
            if not self.epic_service.ensure_authenticated():
                raise Exception("Epic FHIR authentication failed")
            
            # Step 1: Retrieve Patient Demographics
            patient = self._sync_patient_demographics(epic_patient_id)
            if not patient:
                raise Exception(f"Failed to retrieve patient {epic_patient_id}")
            
            # PRE-FLIGHT CHECK: Selective sync optimization
            # Skip reprocessing if no new documents and eligibility unchanged
            if self._should_skip_patient_sync(patient, sync_options):
                logger.info(f"Skipped reprocessing for {patient.epic_patient_id} - no changes detected")
                return {
                    'success': True,
                    'patient_id': patient.id,
                    'epic_patient_id': epic_patient_id,
                    'skipped': True,
                    'reason': 'No new documents and eligibility unchanged',
                    'conditions_synced': 0,
                    'observations_synced': 0,
                    'documents_processed': 0,
                    'encounters_synced': 0,
                    'appointments_synced': 0,
                    'screenings_updated': 0
                }
            
            # Get the last encounter date for data cutoff calculations
            last_encounter_date = self._get_last_encounter_date(patient)
            
            # Step 2: Retrieve Conditions (Problem List)
            conditions_synced = self._sync_patient_conditions(patient, last_encounter_date, sync_options)
            
            # Step 3: Retrieve Observations (Lab Results, Vitals)
            observations_synced = self._sync_patient_observations(patient, last_encounter_date, sync_options)
            
            # Step 3a: Retrieve Imaging Studies (DiagnosticReport resources)
            imaging_synced = self._sync_patient_imaging(patient, last_encounter_date, sync_options)
            
            # Step 4: Retrieve Documents (Clinical Notes, Reports) with keyword filtering for consults/hospital  
            documents_processed = self._sync_patient_documents(patient, last_encounter_date, sync_options)
            
            # Step 5: Retrieve Encounters (Appointments, Visits)
            encounters_synced = self._sync_patient_encounters(patient, sync_options)
            
            # Step 5a: Retrieve Appointments (Scheduled Visits)
            appointments_synced = self._sync_patient_appointments(patient, sync_options)
            
            # Step 6: Process data for screening engine
            screening_updates = self._process_screening_eligibility(patient, sync_options)
            
            # Update sync statistics
            self.sync_stats.update({
                'patients_processed': self.sync_stats['patients_processed'] + 1,
                'conditions_synced': self.sync_stats['conditions_synced'] + conditions_synced,
                'observations_synced': self.sync_stats['observations_synced'] + observations_synced,
                'imaging_synced': self.sync_stats.get('imaging_synced', 0) + imaging_synced,
                'documents_processed': self.sync_stats['documents_processed'] + documents_processed,
                'encounters_synced': self.sync_stats['encounters_synced'] + encounters_synced,
                'appointments_synced': self.sync_stats['appointments_synced'] + appointments_synced,
                'screenings_updated': self.sync_stats['screenings_updated'] + screening_updates
            })
            
            # Update patient's last sync timestamp and document count for selective sync
            from models import Document as ManualDocument, FHIRDocument
            manual_doc_count = ManualDocument.query.filter_by(patient_id=patient.id).count()
            fhir_doc_count = FHIRDocument.query.filter_by(patient_id=patient.id).count()
            total_docs = manual_doc_count + fhir_doc_count
            
            patient.last_fhir_sync = datetime.now()
            patient.fhir_version_id = str(total_docs)  # Store document count for next sync comparison
            db.session.commit()
            
            logger.info(f"Successfully completed comprehensive sync for patient {epic_patient_id}")
            
            return {
                'success': True,
                'patient_id': patient.id,
                'epic_patient_id': epic_patient_id,
                'conditions_synced': conditions_synced,
                'observations_synced': observations_synced, 
                'documents_processed': documents_processed,
                'encounters_synced': encounters_synced,
                'appointments_synced': appointments_synced,
                'screenings_updated': screening_updates,
                'last_encounter_date': last_encounter_date.isoformat() if last_encounter_date else None
            }
            
        except Exception as e:
            error_msg = f"Error in comprehensive patient sync: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.sync_stats['errors'].append(error_msg)
            db.session.rollback()
            
            return {
                'success': False,
                'error': error_msg,
                'epic_patient_id': epic_patient_id
            }
    
    def _sync_patient_demographics(self, epic_patient_id: str) -> Optional[Patient]:
        """Step 1: Retrieve Patient Demographics and Identifiers"""
        logger.info(f"Syncing patient demographics for {epic_patient_id}")
        
        try:
            # Use existing patient sync from EpicFHIRService
            patient = self.epic_service.sync_patient_from_epic(epic_patient_id)
            
            if patient:
                # Assign to organization's default provider if no provider_id set
                if not patient.provider_id:
                    from models import Provider
                    default_provider = Provider.query.filter_by(
                        org_id=self.organization_id,
                        is_active=True
                    ).first()
                    if default_provider:
                        # Re-query patient to ensure we have a fresh session object
                        fresh_patient = Patient.query.get(patient.id)
                        if fresh_patient and not fresh_patient.provider_id:
                            fresh_patient.provider_id = default_provider.id
                            db.session.commit()
                            patient.provider_id = default_provider.id  # Update local reference
                            logger.info(f"Assigned patient {patient.name} to default provider: {default_provider.name}")
                    else:
                        logger.warning(f"No default provider found for org {self.organization_id}")
                
                logger.info(f"Successfully synced patient demographics: {patient.name}")
                return patient
            else:
                logger.error(f"Failed to sync patient demographics for {epic_patient_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error syncing patient demographics: {str(e)}")
            return None
    
    def _sync_patient_conditions(self, patient: Patient, last_encounter_date: Optional[datetime], 
                               sync_options: Dict[str, Any]) -> int:
        """Step 2: Retrieve Conditions (Problem List)"""
        logger.info(f"Syncing conditions for patient {patient.epic_patient_id}")
        
        try:
            # Retrieve conditions from Epic FHIR
            conditions_data = self.epic_service.fhir_client.get_patient_conditions(patient.epic_patient_id)
            
            if not conditions_data:
                logger.info(f"No conditions found for patient {patient.epic_patient_id}")
                return 0
            
            conditions_synced = 0
            
            # Process each condition
            for fhir_condition in conditions_data.get('entry', []):
                condition_resource = fhir_condition.get('resource', {})
                
                # Extract condition information
                condition_name = self._extract_condition_name(condition_resource)
                diagnosis_date = self._extract_condition_date(condition_resource)
                is_active = self._is_condition_active(condition_resource)
                
                if condition_name:
                    # Check if condition already exists
                    existing_condition = PatientCondition.query.filter_by(
                        patient_id=patient.id,
                        condition_name=condition_name
                    ).first()
                    
                    if not existing_condition:
                        # Create new condition record
                        new_condition = PatientCondition()
                        new_condition.patient_id = patient.id
                        new_condition.condition_name = condition_name
                        new_condition.diagnosis_date = diagnosis_date
                        new_condition.is_active = is_active
                        db.session.add(new_condition)
                        conditions_synced += 1
                        
                        logger.info(f"Added new condition: {condition_name}")
                    else:
                        # Update existing condition if needed
                        if existing_condition.is_active != is_active:
                            existing_condition.is_active = is_active
                            conditions_synced += 1
            
            return conditions_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient conditions: {str(e)}")
            return 0
    
    def _sync_patient_observations(self, patient: Patient, last_encounter_date: Optional[datetime],
                                 sync_options: Dict[str, Any]) -> int:
        """Step 3: Retrieve Observations (Lab Results, Vitals) using FHIR Observation resource"""
        logger.info(f"Syncing observations (labs) for patient {patient.epic_patient_id}")
        
        try:
            # Calculate data cutoff based on sync options
            cutoff_date = self._calculate_observation_cutoff(last_encounter_date, sync_options)
            
            # Retrieve observations from Epic FHIR with date filter
            observations_data = self.epic_service.fhir_client.get_patient_observations(
                patient.epic_patient_id,
                date_filter=cutoff_date.isoformat() if cutoff_date else None
            )
            
            if not observations_data:
                logger.info(f"No observations found for patient {patient.epic_patient_id}")
                return 0
            
            observations_synced = 0
            
            # Process observation entries - focus on screening-relevant data
            for fhir_observation in observations_data.get('entry', []):
                observation_resource = fhir_observation.get('resource', {})
                
                # Extract observation details
                obs_code = self._extract_observation_code(observation_resource)
                obs_value = self._extract_observation_value(observation_resource)
                obs_date = self._extract_observation_date(observation_resource)
                
                # Check if observation is relevant to screening criteria
                if self._is_screening_relevant_observation(obs_code, obs_value):
                    # Store observation data for screening engine
                    self._store_screening_observation(patient, obs_code, obs_value, obs_date)
                    observations_synced += 1
            
            logger.info(f"Processed {observations_synced} screening-relevant observations (labs)")
            return observations_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient observations: {str(e)}")
            return 0
    
    def _sync_patient_imaging(self, patient: Patient, last_encounter_date: Optional[datetime],
                             sync_options: Dict[str, Any]) -> int:
        """Step 3a: Retrieve Imaging Studies using FHIR DiagnosticReport resource"""
        logger.info(f"Syncing imaging studies (DiagnosticReport) for patient {patient.epic_patient_id}")
        
        try:
            # Calculate data cutoff based on sync options
            cutoff_date = self._calculate_observation_cutoff(last_encounter_date, sync_options)
            
            # Retrieve DiagnosticReports with imaging category from Epic FHIR
            imaging_data = self.epic_service.fhir_client.get_diagnostic_reports(
                patient.epic_patient_id,
                category='imaging',
                date_from=cutoff_date
            )
            
            if not imaging_data or not imaging_data.get('entry'):
                logger.info(f"No imaging DiagnosticReports found for patient {patient.epic_patient_id}")
                return 0
            
            imaging_synced = 0
            
            # Process each DiagnosticReport entry
            for fhir_report in imaging_data.get('entry', []):
                report_resource = fhir_report.get('resource', {})
                
                report_id = report_resource.get('id')
                report_status = report_resource.get('status')
                report_date = self._extract_diagnostic_report_date(report_resource)
                report_title = self._extract_diagnostic_report_title(report_resource)
                report_conclusion = self._extract_diagnostic_report_conclusion(report_resource)
                
                if report_id:
                    # Check if we already have this imaging report
                    existing_doc = FHIRDocument.query.filter_by(
                        epic_document_id=report_id,
                        patient_id=patient.id
                    ).first()
                    
                    if not existing_doc:
                        # HIPAA COMPLIANCE: Extract structured codes for PHI-safe title
                        # Never use free-text title from Epic - use LOINC codes only
                        from utils.document_types import get_safe_document_type, get_document_type_code
                        
                        code = report_resource.get('code', {})
                        type_coding = code.get('coding', [])
                        category = report_resource.get('category', [])
                        
                        # Get PHI-safe title from structured codes
                        safe_title = get_safe_document_type(type_coding, category, fallback_code='imaging')
                        type_code = get_document_type_code(type_coding, category)
                        
                        # Sanitize FHIR resource JSON to remove PHI
                        sanitized_resource = self.phi_filter.sanitize_fhir_resource(json.dumps(report_resource))
                        fhir_doc = FHIRDocument(
                            patient_id=patient.id,
                            epic_document_id=report_id,
                            document_type_code=type_code or None,
                            document_type_display=safe_title,
                            title=safe_title,  # Use structured code-derived title
                            document_date=report_date,
                            fhir_document_reference=sanitized_resource,
                            org_id=self.organization_id
                        )
                        # Apply PHI filtering to any text content
                        if report_conclusion:
                            fhir_doc.set_ocr_text(report_conclusion[:5000])
                        
                        db.session.add(fhir_doc)
                        imaging_synced += 1
                        
                        logger.debug(f"Added imaging DiagnosticReport: {report_title}")
            
            db.session.commit()
            logger.info(f"Processed {imaging_synced} imaging studies (DiagnosticReports)")
            return imaging_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient imaging: {str(e)}")
            return 0
    
    def _extract_diagnostic_report_date(self, report_resource: Dict) -> Optional[datetime]:
        """Extract date from DiagnosticReport resource"""
        try:
            date_str = report_resource.get('effectiveDateTime') or report_resource.get('issued')
            if date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            pass
        return datetime.now()
    
    def _extract_diagnostic_report_title(self, report_resource: Dict) -> Optional[str]:
        """Extract title/display name from DiagnosticReport resource"""
        try:
            code = report_resource.get('code', {})
            coding = code.get('coding', [])
            if coding:
                return coding[0].get('display') or coding[0].get('code')
            return code.get('text')
        except Exception:
            return None
    
    def _extract_diagnostic_report_conclusion(self, report_resource: Dict) -> Optional[str]:
        """Extract conclusion/interpretation from DiagnosticReport resource"""
        try:
            return report_resource.get('conclusion') or report_resource.get('text', {}).get('div')
        except Exception:
            return None
    
    def _sync_patient_documents(self, patient: Patient, last_encounter_date: Optional[datetime],
                              sync_options: Dict[str, Any]) -> int:
        """Step 4: Retrieve Documents (Clinical Notes, Reports)"""
        logger.info(f"Syncing documents for patient {patient.epic_patient_id}")
        
        try:
            # Calculate document cutoff based on screening frequencies
            cutoff_date = self._calculate_document_cutoff(last_encounter_date, sync_options)
            
            # Retrieve document references from Epic FHIR
            documents_data = self.epic_service.fhir_client.get_patient_documents(
                patient.epic_patient_id,
                date_filter=cutoff_date.isoformat() if cutoff_date else None
            )
            
            if not documents_data:
                logger.info(f"No documents found for patient {patient.epic_patient_id}")
                return 0
            
            documents_processed = 0
            documents_skipped = 0
            total_documents_from_epic = len(documents_data.get('entry', []))
            doc_ids_from_epic = []
            
            logger.info(f"Epic returned {total_documents_from_epic} documents for patient {patient.epic_patient_id}")
            
            # Process each document reference
            for fhir_document in documents_data.get('entry', []):
                document_resource = fhir_document.get('resource', {})
                
                # Extract document metadata
                doc_id = document_resource.get('id')
                # CRITICAL FIX: Handle None document IDs for logging
                if doc_id:
                    doc_ids_from_epic.append(doc_id)
                doc_title = self._extract_document_title(document_resource)
                doc_date = self._extract_document_date(document_resource)
                doc_type = self._extract_document_type(document_resource)
                
                # Check if document is potentially relevant to screenings
                if self._is_potentially_screening_document(doc_title, doc_type):
                    # Check if we already have this document
                    existing_doc = FHIRDocument.query.filter_by(
                        epic_document_id=doc_id,
                        patient_id=patient.id
                    ).first()
                    
                    if not existing_doc:
                        logger.debug(f"Processing new document: ID={doc_id}, Title='{doc_title}', Type='{doc_type}'")
                        # Download and process document content
                        content_processed = self._process_document_content(
                            patient, document_resource, doc_title, doc_date, doc_type
                        )
                        
                        if content_processed:
                            documents_processed += 1
                    else:
                        logger.debug(f"Skipping duplicate document: ID={doc_id}, Title='{doc_title}'")
                        documents_skipped += 1
            
            # Log document IDs for deduplication verification
            logger.info(f"Epic document IDs: {', '.join(doc_ids_from_epic[:5])}{'...' if len(doc_ids_from_epic) > 5 else ''}")
            logger.info(f"Document sync summary - Total: {total_documents_from_epic}, New: {documents_processed}, Skipped: {documents_skipped}")
            return documents_processed
            
        except Exception as e:
            logger.error(f"Error syncing patient documents: {str(e)}")
            return 0
    
    def _sync_patient_encounters(self, patient: Patient, sync_options: Dict[str, Any]) -> int:
        """Step 5: Retrieve Encounters (Appointments, Visits)"""
        logger.info(f"Syncing encounters for patient {patient.epic_patient_id}")
        
        try:
            # Retrieve encounters from Epic FHIR
            encounters_data = self.epic_service.fhir_client.get_patient_encounters(patient.epic_patient_id)
            
            if not encounters_data:
                logger.info(f"No encounters found for patient {patient.epic_patient_id}")
                return 0
            
            encounters_synced = 0
            
            # Process encounters to find last visit and upcoming appointments
            for fhir_encounter in encounters_data.get('entry', []):
                encounter_resource = fhir_encounter.get('resource', {})
                
                encounter_date = self._extract_encounter_date(encounter_resource)
                encounter_status = self._extract_encounter_status(encounter_resource)
                encounter_type = self._extract_encounter_type(encounter_resource)
                
                # Update patient's visit history for screening calculations
                if encounter_status in ['finished', 'completed'] and encounter_date:
                    # This is a completed visit - useful for screening frequency calculations
                    self._update_patient_visit_history(patient, encounter_date, encounter_type)
                    encounters_synced += 1
            
            logger.info(f"Processed {encounters_synced} encounters")
            return encounters_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient encounters: {str(e)}")
            return 0
    
    def _sync_patient_appointments(self, patient: Patient, sync_options: Dict[str, Any]) -> int:
        """Step 5a: Retrieve Appointments (Scheduled Future Visits)"""
        logger.info(f"Syncing appointments for patient {patient.epic_patient_id}")
        
        try:
            # Get appointment window from organization settings or use default (14 days)
            window_days = self.organization.prioritization_window_days or 14
            today = datetime.now().date()
            date_from = today
            date_to = today + timedelta(days=window_days)
            
            # Retrieve appointments from Epic FHIR (booked/pending appointments only)
            appointments_data = self.epic_service.fhir_client.get_appointments(
                patient_id=patient.epic_patient_id,
                status='booked',
                date_from=date_from,
                date_to=date_to
            )
            
            if not appointments_data or not appointments_data.get('entry'):
                logger.info(f"No upcoming appointments found for patient {patient.epic_patient_id}")
                return 0
            
            appointments_synced = 0
            
            # Process each appointment
            for fhir_appointment in appointments_data.get('entry', []):
                appointment_resource = fhir_appointment.get('resource', {})
                
                epic_appointment_id = appointment_resource.get('id')
                appointment_date = self._extract_appointment_date(appointment_resource)
                appointment_status = appointment_resource.get('status', 'scheduled')
                appointment_type = self._extract_appointment_type(appointment_resource)
                provider = self._extract_appointment_provider(appointment_resource)
                
                if epic_appointment_id and appointment_date:
                    # Check if appointment already exists
                    existing_appointment = Appointment.query.filter_by(
                        epic_appointment_id=epic_appointment_id,
                        org_id=self.organization_id
                    ).first()
                    
                    if not existing_appointment:
                        # Create new appointment record
                        new_appointment = Appointment()
                        new_appointment.patient_id = patient.id
                        new_appointment.org_id = self.organization_id
                        new_appointment.epic_appointment_id = epic_appointment_id
                        new_appointment.appointment_date = appointment_date
                        new_appointment.appointment_type = appointment_type
                        new_appointment.provider = provider
                        new_appointment.status = appointment_status
                        new_appointment.fhir_appointment_resource = json.dumps(appointment_resource)
                        new_appointment.last_fhir_sync = datetime.now()
                        
                        # Assign provider_id from patient or org's default provider
                        if patient.provider_id:
                            new_appointment.provider_id = patient.provider_id
                        else:
                            from models import Provider
                            default_provider = Provider.query.filter_by(
                                org_id=self.organization_id,
                                is_active=True
                            ).first()
                            if default_provider:
                                new_appointment.provider_id = default_provider.id
                        
                        db.session.add(new_appointment)
                        appointments_synced += 1
                        
                        logger.info(f"Added new appointment: {appointment_date} for patient {patient.name}")
                    else:
                        # Update existing appointment if status/date changed
                        if (existing_appointment.status != appointment_status or 
                            existing_appointment.appointment_date != appointment_date):
                            existing_appointment.appointment_date = appointment_date
                            existing_appointment.status = appointment_status
                            existing_appointment.appointment_type = appointment_type
                            existing_appointment.provider = provider
                            existing_appointment.fhir_appointment_resource = json.dumps(appointment_resource)
                            existing_appointment.last_fhir_sync = datetime.now()
                            
                            logger.info(f"Updated appointment: {epic_appointment_id}")
            
            # Update organization's last appointment sync timestamp
            self.organization.last_appointment_sync = datetime.now()
            db.session.commit()
            
            logger.info(f"Processed {appointments_synced} appointments")
            return appointments_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient appointments: {str(e)}")
            return 0
    
    def _process_screening_eligibility(self, patient: Patient, sync_options: Dict[str, Any]) -> int:
        """Step 6: Process synchronized data for screening engine"""
        logger.info(f"Processing screening eligibility for patient {patient.epic_patient_id}")
        
        try:
            # Get all screening types for the organization
            screening_types = ScreeningType.query.filter_by(org_id=self.organization_id).all()
            
            screenings_updated = 0
            
            for screening_type in screening_types:
                # Check eligibility based on demographics and conditions
                is_eligible = self.screening_engine.criteria.is_patient_eligible(patient, screening_type)
                
                if is_eligible:
                    # Check completion status based on documents and observations
                    completion_status = self._check_screening_completion(patient, screening_type)
                    
                    # Update screening status
                    self._update_screening_status(patient, screening_type, completion_status)
                    screenings_updated += 1
            
            # Mark that documents have been evaluated for this patient
            # This enables deterministic selective refresh - skip patients whose
            # documents_last_evaluated_at is after all criteria_last_changed_at timestamps
            patient.mark_documents_evaluated()
            db.session.commit()
            
            logger.info(f"Updated {screenings_updated} screening statuses")
            return screenings_updated
            
        except Exception as e:
            logger.error(f"Error processing screening eligibility: {str(e)}")
            return 0
    
    def _get_last_encounter_date(self, patient: Patient) -> Optional[datetime]:
        """Get patient's last encounter date for data cutoff calculations"""
        try:
            # This would query the patient's encounter history
            # For now, return a sensible default based on last sync
            if patient.last_fhir_sync:
                return patient.last_fhir_sync
            else:
                # Default to 2 years ago for initial sync
                return datetime.now() - timedelta(days=730)
        except Exception as e:
            logger.error(f"Error getting last encounter date: {str(e)}")
            return None
    
    def _calculate_document_cutoff(self, last_encounter_date: Optional[datetime], 
                                 sync_options: Dict[str, Any]) -> Optional[datetime]:
        """Calculate how far back to retrieve documents based on screening frequencies"""
        try:
            # Use the maximum screening frequency to determine cutoff
            max_lookback_years = sync_options.get('max_document_lookback_years', 5)
            
            cutoff_date = datetime.now() - timedelta(days=max_lookback_years * 365)
            
            # If last encounter is more recent, use that as a reference point
            if last_encounter_date and last_encounter_date > cutoff_date:
                # Extend lookback from last encounter
                cutoff_date = last_encounter_date - timedelta(days=730)  # 2 years before last encounter
            
            return cutoff_date
            
        except Exception as e:
            logger.error(f"Error calculating document cutoff: {str(e)}")
            return datetime.now() - timedelta(days=1825)  # Default 5 years
    
    def _calculate_observation_cutoff(self, last_encounter_date: Optional[datetime],
                                    sync_options: Dict[str, Any]) -> Optional[datetime]:
        """Calculate how far back to retrieve observations"""
        try:
            # Observations (labs, vitals) are usually relevant for shorter periods
            lookback_years = sync_options.get('observation_lookback_years', 3)
            return datetime.now() - timedelta(days=lookback_years * 365)
        except Exception as e:
            logger.error(f"Error calculating observation cutoff: {str(e)}")
            return datetime.now() - timedelta(days=1095)  # Default 3 years
    
    def _get_default_sync_options(self) -> Dict[str, Any]:
        """Get default synchronization options"""
        return {
            'max_document_lookback_years': 5,
            'observation_lookback_years': 3,
            'process_all_documents': False,  # Only process screening-relevant documents
            'include_inactive_conditions': False,
            'skip_low_priority_observations': True
        }
    
    # Helper methods for FHIR data extraction
    def _extract_condition_name(self, condition_resource: Dict) -> Optional[str]:
        """Extract condition name from FHIR Condition resource"""
        try:
            coding = condition_resource.get('code', {}).get('coding', [])
            if coding:
                return coding[0].get('display') or coding[0].get('code')
            return condition_resource.get('code', {}).get('text')
        except Exception:
            return None
    
    def _extract_condition_date(self, condition_resource: Dict) -> Optional[date]:
        """Extract condition diagnosis date"""
        try:
            onset_str = condition_resource.get('onsetDateTime') or condition_resource.get('recordedDate')
            if onset_str:
                return datetime.fromisoformat(onset_str.replace('Z', '+00:00')).date()
        except Exception:
            pass
        return None
    
    def _is_condition_active(self, condition_resource: Dict) -> bool:
        """Check if condition is active"""
        try:
            clinical_status = condition_resource.get('clinicalStatus', {}).get('coding', [])
            if clinical_status:
                return clinical_status[0].get('code') == 'active'
            return True  # Default to active
        except Exception:
            return True
    
    def _extract_observation_code(self, observation_resource: Dict) -> Optional[str]:
        """Extract observation code (LOINC, SNOMED, etc.)"""
        try:
            coding = observation_resource.get('code', {}).get('coding', [])
            if coding:
                return coding[0].get('code')
        except Exception:
            pass
        return None
    
    def _extract_observation_value(self, observation_resource: Dict) -> Optional[str]:
        """Extract observation value"""
        try:
            # Handle different value types
            if 'valueQuantity' in observation_resource:
                quantity = observation_resource['valueQuantity']
                value = quantity.get('value')
                unit = quantity.get('unit', '')
                return f"{value} {unit}".strip()
            elif 'valueString' in observation_resource:
                return observation_resource['valueString']
            elif 'valueBoolean' in observation_resource:
                return str(observation_resource['valueBoolean'])
        except Exception:
            pass
        return None
    
    def _extract_observation_date(self, observation_resource: Dict) -> Optional[datetime]:
        """Extract observation date"""
        try:
            effective_date = observation_resource.get('effectiveDateTime')
            if effective_date:
                return datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
        except Exception:
            pass
        return None
    
    def _is_screening_relevant_observation(self, code: Optional[str], value: Optional[str]) -> bool:
        """Check if observation is relevant to screening criteria"""
        if not code:
            return False
        
        # Define screening-relevant observation codes (LOINC codes)
        screening_relevant_codes = {
            '33747-0',  # PSA
            '2093-3',   # Cholesterol Total
            '17861-6',  # Calcium
            '33743-9',  # Hemoglobin A1c
            # Add more as needed
        }
        
        return code in screening_relevant_codes
    
    def _store_screening_observation(self, patient: Patient, code: str, value: str, obs_date: datetime):
        """Store screening-relevant observation for later analysis"""
        # This could be implemented as a separate model or stored in patient's FHIR data
        # For now, we'll log it for the screening engine to process
        logger.info(f"Screening observation for {patient.epic_patient_id}: {code} = {value} on {obs_date}")
    
    def _extract_document_title(self, document_resource: Dict) -> Optional[str]:
        """Extract document title from DocumentReference"""
        try:
            return document_resource.get('description') or document_resource.get('type', {}).get('text')
        except Exception:
            return None
    
    def _extract_document_date(self, document_resource: Dict) -> Optional[datetime]:
        """Extract document date with current date fallback for sandbox documents"""
        try:
            date_str = document_resource.get('date') or document_resource.get('created')
            if date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            pass
        
        # Fallback to current date for sandbox documents without dates
        # This ensures sandbox documents can be recognized as having completion dates
        logger.info("Document has no date from Epic FHIR, using current date as fallback for sandbox testing")
        return datetime.utcnow()
    
    def _extract_document_type(self, document_resource: Dict) -> Optional[str]:
        """Extract document type"""
        try:
            type_coding = document_resource.get('type', {}).get('coding', [])
            if type_coding:
                return type_coding[0].get('display') or type_coding[0].get('code')
        except Exception:
            pass
        return None
    
    def _extract_content_type(self, document_resource: Dict) -> Optional[str]:
        """Extract content type (MIME type) from document attachment"""
        try:
            content = document_resource.get('content', [])
            for content_item in content:
                attachment = content_item.get('attachment', {})
                content_type = attachment.get('contentType')
                if content_type:
                    logger.debug(f"Extracted content type: {content_type}")
                    return content_type
        except Exception as e:
            logger.debug(f"Could not extract content type: {str(e)}")
        return None
    
    def _is_potentially_screening_document(self, title: Optional[str], doc_type: Optional[str]) -> bool:
        """Check if document might contain screening information
        
        CRITICAL FIX: Process ALL documents instead of filtering by title.
        Epic documents often have generic titles like "Progress Note" that don't contain
        screening keywords, but their content does. Keyword matching should happen on 
        the extracted text, not the title.
        """
        # Process all documents - let the keyword matching happen on extracted text
        return True
    
    def _process_document_content(self, patient: Patient, document_resource: Dict,
                                title: str, doc_date: datetime, doc_type: str) -> bool:
        """Download and process document content for screening keywords
        
        HIPAA COMPLIANCE: Document titles are derived ONLY from structured FHIR
        type codes, never from free-text fields that could contain patient names.
        This ensures deterministic PHI protection regardless of input data.
        """
        from utils.document_types import get_safe_document_type, get_document_type_code
        
        try:
            # Extract content type from document metadata
            content_type = self._extract_content_type(document_resource)
            
            # Download document content
            doc_content = self._download_document_content(document_resource)
            
            if doc_content:
                # Use OCR if needed and extract text (pass content_type for proper file type detection)
                extracted_text = self.document_processor.process_document(doc_content, title, content_type)
                
                if extracted_text:
                    # HIPAA COMPLIANCE: Extract structured codes for PHI-safe title
                    # NEVER use free-text 'description' or 'title' fields from Epic
                    type_coding = document_resource.get('type', {}).get('coding', [])
                    category = document_resource.get('category', [])
                    
                    # Get PHI-safe title from structured codes only
                    safe_title = get_safe_document_type(type_coding, category)
                    
                    # Get document type code for database storage
                    type_code = get_document_type_code(type_coding, category)
                    
                    # Sanitize FHIR resource JSON to remove PHI
                    sanitized_resource = self.phi_filter.sanitize_fhir_resource(json.dumps(document_resource))
                    fhir_doc = FHIRDocument(
                        patient_id=patient.id,
                        epic_document_id=document_resource.get('id'),
                        document_type_code=type_code or None,
                        document_type_display=safe_title,
                        title=safe_title,  # Use structured code-derived title, not free text
                        document_date=doc_date,
                        fhir_document_reference=sanitized_resource,
                        org_id=self.organization_id
                    )
                    # Apply PHI filtering to extracted text
                    fhir_doc.set_ocr_text(extracted_text[:5000])
                    
                    db.session.add(fhir_doc)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing document content: {str(e)}")
            return False
    
    def _download_document_content(self, document_resource: Dict) -> Optional[bytes]:
        """Download document content from Epic FHIR API"""
        try:
            # Get document content URL or attachment
            content = document_resource.get('content', [])
            
            for content_item in content:
                attachment = content_item.get('attachment', {})
                
                # Check for direct data
                if 'data' in attachment:
                    import base64
                    return base64.b64decode(attachment['data'])
                
                # Check for URL
                elif 'url' in attachment:
                    # Download from URL using FHIR client
                    return self.epic_service.fhir_client.download_binary(attachment['url'])
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading document content: {str(e)}")
            return None
    
    def _extract_encounter_date(self, encounter_resource: Dict) -> Optional[datetime]:
        """Extract encounter date"""
        try:
            period = encounter_resource.get('period', {})
            start_date = period.get('start')
            if start_date:
                return datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except Exception:
            pass
        return None
    
    def _extract_encounter_status(self, encounter_resource: Dict) -> Optional[str]:
        """Extract encounter status"""
        return encounter_resource.get('status')
    
    def _extract_encounter_type(self, encounter_resource: Dict) -> Optional[str]:
        """Extract encounter type"""
        try:
            type_coding = encounter_resource.get('type', [{}])[0].get('coding', [])
            if type_coding:
                return type_coding[0].get('display') or type_coding[0].get('code')
        except Exception:
            pass
        return None
    
    def _update_patient_visit_history(self, patient: Patient, encounter_date: datetime, encounter_type: str):
        """Update patient's visit history for screening calculations"""
        # This would update a separate patient visit history model
        # For now, we'll log it
        logger.info(f"Patient {patient.epic_patient_id} visit: {encounter_type} on {encounter_date}")
    
    def _extract_appointment_date(self, appointment_resource: Dict) -> Optional[datetime]:
        """Extract appointment date from FHIR Appointment resource"""
        try:
            start_date = appointment_resource.get('start')
            if start_date:
                return datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except Exception:
            pass
        return None
    
    def _extract_appointment_type(self, appointment_resource: Dict) -> Optional[str]:
        """Extract appointment type from FHIR Appointment resource"""
        try:
            appointment_type = appointment_resource.get('appointmentType', {})
            coding = appointment_type.get('coding', [])
            if coding:
                return coding[0].get('display') or coding[0].get('code')
        except Exception:
            pass
        return 'General'
    
    def _extract_appointment_provider(self, appointment_resource: Dict) -> Optional[str]:
        """Extract appointment provider from FHIR Appointment resource"""
        try:
            participants = appointment_resource.get('participant', [])
            for participant in participants:
                actor = participant.get('actor', {})
                if actor.get('display'):
                    return actor.get('display')
        except Exception:
            pass
        return None
    
    def _check_screening_completion(self, patient: Patient, screening_type: ScreeningType) -> Dict[str, Any]:
        """Check if screening has been completed based on BOTH manual and FHIR documents
        
        CRITICAL FIX: Query both Document (manual) and FHIRDocument (FHIR) tables
        to ensure manual test documents are included in screening match detection.
        Returns all matched documents for proper association management.
        """
        try:
            # Get screening keywords
            keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
            if not keywords:
                return {
                    'completed': False,
                    'last_completed_date': None,
                    'source': None,
                    'matched_manual_docs': [],
                    'matched_fhir_docs': []
                }
            
            # Calculate date cutoff (same for both manual and FHIR documents)
            cutoff_date = datetime.now() - timedelta(days=int(screening_type.frequency_years * 365))
            
            matched_manual_docs = []
            matched_fhir_docs = []
            most_recent_completion_date = None
            
            # Query manual documents (Document table)
            logger.debug(f"Checking manual documents for patient {patient.id}, screening {screening_type.name}")
            manual_documents = Document.query.filter_by(
                patient_id=patient.id
            ).filter(
                Document.created_at >= cutoff_date
            ).all()
            
            for doc in manual_documents:
                if self._document_contains_screening_evidence_generic(doc.ocr_text, keywords):
                    completion_date = doc.created_at
                    if not completion_date:
                        completion_date = datetime.now()
                        logger.warning(f"Manual document {doc.id} has no date - using current date")
                    
                    matched_manual_docs.append({
                        'id': doc.id,
                        'date': completion_date,
                        'title': doc.filename
                    })
                    
                    if not most_recent_completion_date or completion_date > most_recent_completion_date:
                        most_recent_completion_date = completion_date
                    
                    logger.info(f"Manual document match: {doc.filename} (ID: {doc.id}) for {screening_type.name}")
            
            # Query FHIR documents (FHIRDocument table)
            logger.debug(f"Checking FHIR documents for patient {patient.id}, screening {screening_type.name}")
            fhir_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id
            ).filter(
                FHIRDocument.document_date >= cutoff_date
            ).all()
            
            for doc in fhir_documents:
                if self._document_contains_screening_evidence_generic(doc.ocr_text, keywords):
                    completion_date = doc.document_date or doc.creation_date
                    if not completion_date:
                        completion_date = datetime.now()
                        logger.warning(f"FHIR document {doc.id} has no date - using current date")
                    
                    matched_fhir_docs.append({
                        'id': doc.id,
                        'date': completion_date,
                        'title': doc.title
                    })
                    
                    if not most_recent_completion_date or completion_date > most_recent_completion_date:
                        most_recent_completion_date = completion_date
                    
                    logger.info(f"FHIR document match: {doc.title} (ID: {doc.id}, Epic: {doc.epic_document_id}) for {screening_type.name}")
            
            # Return results with all matched documents
            has_matches = len(matched_manual_docs) > 0 or len(matched_fhir_docs) > 0
            
            return {
                'completed': has_matches,
                'last_completed_date': most_recent_completion_date,
                'source': 'document' if has_matches else None,
                'matched_manual_docs': matched_manual_docs,
                'matched_fhir_docs': matched_fhir_docs
            }
            
        except Exception as e:
            logger.error(f"Error checking screening completion: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'completed': False,
                'last_completed_date': None,
                'source': None,
                'matched_manual_docs': [],
                'matched_fhir_docs': []
            }
    
    def _document_contains_screening_evidence_generic(self, ocr_text: Optional[str], keywords: List[str]) -> bool:
        """Generic keyword matching for both manual and FHIR documents using word boundary regex
        
        This method applies the same word boundary matching logic to OCR text from any source.
        """
        import re
        
        if not ocr_text or not keywords:
            return False
        
        # Use word boundary regex matching to prevent false positives
        for keyword in keywords:
            # Handle multi-word keywords: require sequential word matching
            if ' ' in keyword:
                # Multi-word: escape each word and require sequential matching with whitespace
                escaped_words = [re.escape(word) for word in keyword.split()]
                pattern = r'\b' + r'\s+'.join(escaped_words) + r'\b'
            else:
                # Single word: exact word boundary matching
                pattern = r'\b' + re.escape(keyword) + r'\b'
            
            # Check for match with case-insensitive search
            if re.search(pattern, ocr_text, re.IGNORECASE):
                logger.debug(f"Keyword match found: '{keyword}'")
                return True
        
        return False
    
    def _document_contains_screening_evidence(self, document: FHIRDocument, keywords: List[str]) -> bool:
        """Check if FHIR document contains evidence of completed screening (legacy method)
        
        Kept for backwards compatibility. New code should use _document_contains_screening_evidence_generic.
        """
        return self._document_contains_screening_evidence_generic(document.ocr_text, keywords)
    
    def _update_screening_status(self, patient: Patient, screening_type: ScreeningType, 
                               completion_status: Dict[str, Any]):
        """Update screening status with unified document matching and stale association cleanup
        
        CRITICAL FIX: This method now:
        1. Clears OLD associations not re-confirmed in current sync
        2. Creates NEW associations to correct junction tables
        3. Updates screening status based ONLY on current validated matches
        """
        try:
            from models import Screening, FHIRDocument, Document, db
            
            # Check if screening already exists
            existing_screening = Screening.query.filter_by(
                patient_id=patient.id,
                screening_type_id=screening_type.id
            ).first()
            
            # Calculate proper status including 'due_soon'
            next_due = None
            if completion_status['completed'] and completion_status['last_completed_date']:
                from utils.date_helpers import calculate_due_date
                from datetime import date as date_class, timedelta
                
                # Calculate next due date
                next_due = calculate_due_date(
                    completion_status['last_completed_date'],
                    screening_type.frequency_value,
                    screening_type.frequency_unit
                )
                
                # Calculate status based on next_due date
                today = date_class.today()
                due_soon_threshold = next_due - timedelta(days=30)
                
                if today >= next_due:
                    status = 'due'
                elif today >= due_soon_threshold:
                    status = 'due_soon'
                else:
                    status = 'complete'
            else:
                status = 'due'
            
            if existing_screening:
                # Update existing screening
                existing_screening.status = status
                existing_screening.last_completed = completion_status['last_completed_date']
                existing_screening.next_due = next_due if completion_status['completed'] and completion_status['last_completed_date'] else None
                existing_screening.updated_at = datetime.now()
                screening = existing_screening
            else:
                # Create new screening record
                new_screening = Screening(
                    patient_id=patient.id,
                    screening_type_id=screening_type.id,
                    org_id=patient.org_id,
                    status=status,
                    last_completed=completion_status['last_completed_date'],
                    next_due=next_due if completion_status['completed'] and completion_status['last_completed_date'] else None,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(new_screening)
                screening = new_screening
                db.session.flush()  # Get screening ID for associations
            
            # SCOPED INVALIDATION: Clear stale associations before creating new ones
            # This ensures screening status reflects ONLY current, validated matches
            
            # Get current match IDs from this sync
            current_manual_ids = set(doc['id'] for doc in completion_status.get('matched_manual_docs', []))
            current_fhir_ids = set(doc['id'] for doc in completion_status.get('matched_fhir_docs', []))
            
            # Remove stale manual document associations
            if existing_screening:
                stale_manual_matches = ScreeningDocumentMatch.query.filter_by(
                    screening_id=screening.id
                ).all()
                
                for match in stale_manual_matches:
                    if match.document_id not in current_manual_ids:
                        logger.info(f"Removing stale manual document association: "
                                  f"screening {screening.id} <-> document {match.document_id}")
                        db.session.delete(match)
            
            # Remove stale FHIR document associations
            if existing_screening:
                # Clear FHIR associations not in current match set
                existing_fhir_ids = set(doc.id for doc in screening.fhir_documents)
                for fhir_id in existing_fhir_ids:
                    if fhir_id not in current_fhir_ids:
                        fhir_doc = FHIRDocument.query.get(fhir_id)
                        if fhir_doc and fhir_doc in screening.fhir_documents:
                            screening.fhir_documents.remove(fhir_doc)
                            logger.info(f"Removing stale FHIR document association: "
                                      f"screening {screening.id} <-> FHIR doc {fhir_id}")
            
            # CREATE NEW ASSOCIATIONS: Add matched documents to correct junction tables
            
            # Add manual document matches to screening_document_match table
            for doc_info in completion_status.get('matched_manual_docs', []):
                doc_id = doc_info['id']
                
                # Check if association already exists
                existing_match = ScreeningDocumentMatch.query.filter_by(
                    screening_id=screening.id,
                    document_id=doc_id
                ).first()
                
                if not existing_match:
                    new_match = ScreeningDocumentMatch(
                        screening_id=screening.id,
                        document_id=doc_id,
                        match_confidence=1.0,
                        matched_keywords=json.dumps([]),  # Could track which keywords matched
                        created_at=datetime.now()
                    )
                    db.session.add(new_match)
                    logger.info(f"Created manual document association: "
                              f"{doc_info['title']} (ID: {doc_id}) -> {screening_type.name}")
            
            # Add FHIR document matches to screening_fhir_documents table
            for doc_info in completion_status.get('matched_fhir_docs', []):
                doc_id = doc_info['id']
                fhir_doc = FHIRDocument.query.get(doc_id)
                
                if fhir_doc and fhir_doc not in screening.fhir_documents:
                    screening.fhir_documents.append(fhir_doc)
                    logger.info(f"Created FHIR document association: "
                              f"{doc_info['title']} (ID: {doc_id}) -> {screening_type.name}")
            
            # Commit all changes atomically
            db.session.commit()
            
            logger.info(f"Updated screening status for {patient.epic_patient_id}: "
                       f"{screening_type.name} - {status} "
                       f"({len(current_manual_ids)} manual + {len(current_fhir_ids)} FHIR docs matched)")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating screening status: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def discover_and_sync_patients(self, sync_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Discover patients from Epic FHIR and perform comprehensive sync.
        This is the main entry point for testing with Epic sandbox patients.
        
        Returns:
            Dict with discovery and sync results
        """
        if not sync_options:
            sync_options = self._get_default_sync_options()
        
        try:
            logger.info("Starting patient discovery from Epic FHIR")
            
            # Ensure we have valid authentication
            if not self.epic_service.ensure_authenticated():
                raise Exception("Epic FHIR authentication failed")
            
            # Step 1: Discover patients from Epic
            discovered_patients = self._discover_patients_from_epic()
            
            if not discovered_patients:
                return {
                    'success': False,
                    'error': 'No patients discovered from Epic FHIR',
                    'discovered_patients': 0,
                    'synced_patients': 0
                }
            
            logger.info(f"Discovered {len(discovered_patients)} patients from Epic")
            
            # Step 2: Import/update local patient records
            imported_patients = []
            for epic_patient_data in discovered_patients:
                try:
                    patient = self._import_or_update_patient(epic_patient_data)
                    if patient:
                        imported_patients.append(patient)
                except Exception as e:
                    logger.error(f"Error importing patient {epic_patient_data.get('id', 'unknown')}: {str(e)}")
                    self.sync_stats['errors'].append(f"Import failed for {epic_patient_data.get('id', 'unknown')}: {str(e)}")
            
            # Step 3: Run comprehensive sync for imported patients
            synced_patients = 0
            total_updated_screenings = 0
            
            # Check if appointment-based prioritization is enabled
            from services.appointment_prioritization import AppointmentBasedPrioritization
            
            organization = Organization.query.get(self.organization_id)
            
            if organization and organization.appointment_based_prioritization:
                logger.info("Appointment-Based Screening Prioritization is ENABLED")
                
                # Get priority patients with upcoming appointments
                prioritization_service = AppointmentBasedPrioritization(self.organization_id)
                priority_patient_ids = prioritization_service.get_priority_patients()
                
                if priority_patient_ids:
                    logger.info(f"Processing {len(priority_patient_ids)} priority patients with upcoming appointments")
                    
                    # Process priority patients first
                    priority_patients = [p for p in imported_patients if p.id in priority_patient_ids]
                    for patient in priority_patients:
                        try:
                            sync_result = self.sync_patient_comprehensive(patient.epic_patient_id, sync_options)
                            if sync_result.get('success'):
                                synced_patients += 1
                                total_updated_screenings += sync_result.get('screenings_updated', 0)
                            else:
                                self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {sync_result.get('error', 'Unknown error')}")
                        except Exception as e:
                            logger.error(f"Error syncing priority patient {patient.epic_patient_id}: {str(e)}")
                            self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {str(e)}")
                    
                    # Process non-priority patients if configured
                    if organization.process_non_scheduled_patients:
                        logger.info("Processing non-scheduled patients (process_non_scheduled_patients is enabled)")
                        non_priority_patients = [p for p in imported_patients if p.id not in priority_patient_ids]
                        
                        for patient in non_priority_patients:
                            try:
                                sync_result = self.sync_patient_comprehensive(patient.epic_patient_id, sync_options)
                                if sync_result.get('success'):
                                    synced_patients += 1
                                    total_updated_screenings += sync_result.get('screenings_updated', 0)
                                else:
                                    self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {sync_result.get('error', 'Unknown error')}")
                            except Exception as e:
                                logger.error(f"Error syncing non-priority patient {patient.epic_patient_id}: {str(e)}")
                                self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {str(e)}")
                    else:
                        logger.info(f"Skipping {len([p for p in imported_patients if p.id not in priority_patient_ids])} non-scheduled patients (process_non_scheduled_patients is disabled)")
                else:
                    # No priority patients found - fallback to standard sync
                    logger.info("No patients eligible for Appointment-Based Screening Prioritization, continuing general EMR sync")
                    
                    for patient in imported_patients:
                        try:
                            sync_result = self.sync_patient_comprehensive(patient.epic_patient_id, sync_options)
                            if sync_result.get('success'):
                                synced_patients += 1
                                total_updated_screenings += sync_result.get('screenings_updated', 0)
                            else:
                                self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {sync_result.get('error', 'Unknown error')}")
                        except Exception as e:
                            logger.error(f"Error syncing patient {patient.epic_patient_id}: {str(e)}")
                            self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {str(e)}")
            else:
                # Appointment prioritization disabled - process all patients
                logger.info("Appointment-Based Screening Prioritization is DISABLED - processing all patients")
                
                for patient in imported_patients:
                    try:
                        sync_result = self.sync_patient_comprehensive(patient.epic_patient_id, sync_options)
                        if sync_result.get('success'):
                            synced_patients += 1
                            total_updated_screenings += sync_result.get('screenings_updated', 0)
                        else:
                            self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {sync_result.get('error', 'Unknown error')}")
                    except Exception as e:
                        logger.error(f"Error syncing patient {patient.epic_patient_id}: {str(e)}")
                        self.sync_stats['errors'].append(f"Sync failed for {patient.name}: {str(e)}")
            
            logger.info(f"Discovery and sync completed: {synced_patients} patients synced, {total_updated_screenings} screenings updated")
            
            return {
                'success': True,
                'discovered_patients': len(discovered_patients),
                'imported_patients': len(imported_patients),
                'synced_patients': synced_patients,
                'updated_screenings': total_updated_screenings,
                'errors': self.sync_stats['errors']
            }
            
        except Exception as e:
            logger.error(f"Error in patient discovery and sync: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'discovered_patients': 0,
                'synced_patients': 0
            }
    
    def _discover_patients_from_epic(self) -> List[Dict[str, Any]]:
        """
        Retrieve known Epic sandbox test patients.
        Epic FHIR doesn't allow broad patient queries, so we use known test patient IDs.
        """
        try:
            # Get FHIR client instance
            fhir_client = self.epic_service.get_fhir_client()
            
            # Known Epic sandbox test patient IDs
            known_patient_ids = [
                'erXuFYUfucBZaryVksYEcMg3',  # Camila Lopez
                'eq081-VQEgP8drUUqCWzHfw3',  # Derrick Lin
                'eAB3mDIBBcyUKviyzrxsnAw3',  # Desiree Powell
                'egqBHVfQlt4Bw3XGXoxVxHg3',  # Elijah Davis (MRN: 203709)
                'eIXesllypH3M9tAA5WdJftQ3',  # Linda Ross (MRN: 203712)
                'eh2xYHuzl9nkSFVvV3osUHg3',  # Olivia Roberts (MRN: 203715)
                'e0w0LEDCYtfckT6N.CkJKCw3',  # Warren McGinnis (MRN: 203710)
            ]
            
            patients = []
            
            for patient_id in known_patient_ids:
                try:
                    logger.info(f"Retrieving patient {patient_id} from Epic")
                    patient_data = fhir_client.get_patient(patient_id)
                    
                    if patient_data:
                        patients.append(patient_data)
                        logger.info(f"Successfully retrieved patient {patient_id}")
                    else:
                        logger.warning(f"Could not retrieve patient {patient_id}")
                        
                except Exception as e:
                    logger.warning(f"Error retrieving patient {patient_id}: {str(e)}")
                    continue
            
            logger.info(f"Retrieved {len(patients)} Epic sandbox patients")
            return patients
            
        except Exception as e:
            logger.error(f"Error discovering patients from Epic: {str(e)}")
            return []
    
    def _import_or_update_patient(self, epic_patient_data: Dict[str, Any]) -> Optional[Patient]:
        """
        Create or update local Patient record from Epic FHIR data.
        
        Args:
            epic_patient_data: Patient FHIR resource from Epic
            
        Returns:
            Patient instance or None if failed
        """
        try:
            epic_patient_id = epic_patient_data.get('id')
            if not epic_patient_id:
                logger.error("Patient data missing ID")
                return None
            
            # Check if patient already exists
            patient = Patient.query.filter_by(
                epic_patient_id=epic_patient_id,
                org_id=self.organization_id
            ).first()
            
            # Extract patient demographics
            name_data = epic_patient_data.get('name', [{}])[0]
            given_names = name_data.get('given', ['Unknown'])
            family_name = name_data.get('family', 'Unknown')
            
            full_name = f"{' '.join(given_names)} {family_name}"
            
            # Extract other demographic data
            gender = epic_patient_data.get('gender', 'unknown')
            birth_date = None
            if epic_patient_data.get('birthDate'):
                try:
                    birth_date = datetime.strptime(epic_patient_data['birthDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            # Extract identifiers (MRN, etc.) with Epic fallback logic
            identifiers = epic_patient_data.get('identifier', [])
            mrn = None
            
            # Try to find MRN-type identifier first
            for identifier in identifiers:
                type_info = identifier.get('type', {})
                coding = type_info.get('coding', [{}])
                if coding and coding[0].get('code') == 'MR':
                    mrn = identifier.get('value')
                    break
            
            # Fallback to any identifier if no MRN found
            if not mrn and identifiers:
                for identifier in identifiers:
                    if identifier.get('value'):
                        mrn = identifier.get('value')
                        break
            
            # Generate fallback MRN for Epic sandbox patients if still no MRN
            if not mrn:
                if epic_patient_id:
                    mrn = f"EPIC-{epic_patient_id}"
                else:
                    mrn = f"EPIC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            if patient:
                # Update existing patient
                patient.name = full_name
                patient.date_of_birth = birth_date
                patient.gender = gender
                patient.mrn = mrn
                patient.last_fhir_sync = datetime.now()
                logger.info(f"Updated existing patient: {full_name}")
            else:
                # Create new patient
                patient = Patient(
                    name=full_name,
                    epic_patient_id=epic_patient_id,
                    org_id=self.organization_id,
                    date_of_birth=birth_date,
                    gender=gender,
                    mrn=mrn,
                    last_fhir_sync=datetime.now()
                )
                db.session.add(patient)
                logger.info(f"Created new patient: {full_name}")
            
            db.session.commit()
            return patient
            
        except Exception as e:
            logger.error(f"Error importing/updating patient: {str(e)}")
            db.session.rollback()
            return None

    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            **self.sync_stats,
            'organization_id': self.organization_id,
            'timestamp': datetime.now().isoformat()
        }