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

from flask import session
from flask_login import current_user

from models import db, Patient, PatientCondition, FHIRDocument, Organization, ScreeningType
from services.epic_fhir_service import EpicFHIRService
from emr.fhir_client import FHIRClient
from core.engine import ScreeningEngine
from ocr.document_processor import DocumentProcessor

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
        
        # Initialize services
        self.epic_service = EpicFHIRService(organization_id)
        self.screening_engine = ScreeningEngine()
        self.document_processor = DocumentProcessor()
        
        # Track sync progress
        self.sync_stats = {
            'patients_processed': 0,
            'conditions_synced': 0,
            'observations_synced': 0,
            'documents_processed': 0,
            'encounters_synced': 0,
            'screenings_updated': 0,
            'errors': []
        }
        
        logger.info(f"Initialized ComprehensiveEMRSync for organization {organization_id}")
    
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
            
            # Get the last encounter date for data cutoff calculations
            last_encounter_date = self._get_last_encounter_date(patient)
            
            # Step 2: Retrieve Conditions (Problem List)
            conditions_synced = self._sync_patient_conditions(patient, last_encounter_date, sync_options)
            
            # Step 3: Retrieve Observations (Lab Results, Vitals)
            observations_synced = self._sync_patient_observations(patient, last_encounter_date, sync_options)
            
            # Step 4: Retrieve Documents (Clinical Notes, Reports)  
            documents_processed = self._sync_patient_documents(patient, last_encounter_date, sync_options)
            
            # Step 5: Retrieve Encounters (Appointments, Visits)
            encounters_synced = self._sync_patient_encounters(patient, sync_options)
            
            # Step 6: Process data for screening engine
            screening_updates = self._process_screening_eligibility(patient, sync_options)
            
            # Update sync statistics
            self.sync_stats.update({
                'patients_processed': self.sync_stats['patients_processed'] + 1,
                'conditions_synced': self.sync_stats['conditions_synced'] + conditions_synced,
                'observations_synced': self.sync_stats['observations_synced'] + observations_synced,
                'documents_processed': self.sync_stats['documents_processed'] + documents_processed,
                'encounters_synced': self.sync_stats['encounters_synced'] + encounters_synced,
                'screenings_updated': self.sync_stats['screenings_updated'] + screening_updates
            })
            
            # Update patient's last sync timestamp
            patient.last_fhir_sync = datetime.now()
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
        """Step 3: Retrieve Observations (Lab Results, Vitals)"""
        logger.info(f"Syncing observations for patient {patient.epic_patient_id}")
        
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
            
            logger.info(f"Processed {observations_synced} screening-relevant observations")
            return observations_synced
            
        except Exception as e:
            logger.error(f"Error syncing patient observations: {str(e)}")
            return 0
    
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
            
            # Process each document reference
            for fhir_document in documents_data.get('entry', []):
                document_resource = fhir_document.get('resource', {})
                
                # Extract document metadata
                doc_id = document_resource.get('id')
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
                        # Download and process document content
                        content_processed = self._process_document_content(
                            patient, document_resource, doc_title, doc_date, doc_type
                        )
                        
                        if content_processed:
                            documents_processed += 1
            
            logger.info(f"Processed {documents_processed} documents for screening analysis")
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
        """Extract document date"""
        try:
            date_str = document_resource.get('date') or document_resource.get('created')
            if date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            pass
        return None
    
    def _extract_document_type(self, document_resource: Dict) -> Optional[str]:
        """Extract document type"""
        try:
            type_coding = document_resource.get('type', {}).get('coding', [])
            if type_coding:
                return type_coding[0].get('display') or type_coding[0].get('code')
        except Exception:
            pass
        return None
    
    def _is_potentially_screening_document(self, title: Optional[str], doc_type: Optional[str]) -> bool:
        """Check if document might contain screening information"""
        if not title and not doc_type:
            return False
        
        # Screening-related keywords
        screening_keywords = [
            'mammogram', 'colonoscopy', 'pap smear', 'pap test', 'cervical',
            'bone density', 'dexa', 'dxa', 'osteoporosis',
            'skin cancer', 'dermatology', 'mole', 'lesion',
            'prostate', 'psa', 'digital rectal',
            'breast', 'clinical breast exam',
            'lung', 'chest ct', 'ldct',
            'vision', 'eye exam', 'glaucoma',
            'hearing', 'audiometry'
        ]
        
        text_to_check = f"{title or ''} {doc_type or ''}".lower()
        
        return any(keyword in text_to_check for keyword in screening_keywords)
    
    def _process_document_content(self, patient: Patient, document_resource: Dict,
                                title: str, doc_date: datetime, doc_type: str) -> bool:
        """Download and process document content for screening keywords"""
        try:
            # Download document content
            doc_content = self._download_document_content(document_resource)
            
            if doc_content:
                # Use OCR if needed and extract text
                extracted_text = self.document_processor.process_document(doc_content, title)
                
                if extracted_text:
                    # Create FHIRDocument record
                    fhir_doc = FHIRDocument(
                        patient_id=patient.id,
                        epic_document_id=document_resource.get('id'),
                        document_type=doc_type or 'Unknown',
                        title=title or 'Untitled',
                        document_date=doc_date,
                        extracted_text=extracted_text[:5000],  # Limit text length
                        fhir_resource=json.dumps(document_resource),
                        org_id=self.organization_id
                    )
                    
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
    
    def _check_screening_completion(self, patient: Patient, screening_type: ScreeningType) -> Dict[str, Any]:
        """Check if screening has been completed based on documents and observations"""
        try:
            # Get screening keywords
            keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
            
            # Search patient's documents for screening keywords
            recent_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id
            ).filter(
                FHIRDocument.creation_date >= datetime.now() - timedelta(days=int(screening_type.frequency_years * 365))
            ).all()
            
            for doc in recent_documents:
                if self._document_contains_screening_evidence(doc, keywords):
                    return {
                        'completed': True,
                        'last_completed_date': doc.creation_date,
                        'source': 'document',
                        'document_id': doc.id
                    }
            
            return {
                'completed': False,
                'last_completed_date': None,
                'source': None
            }
            
        except Exception as e:
            logger.error(f"Error checking screening completion: {str(e)}")
            return {'completed': False, 'last_completed_date': None, 'source': None}
    
    def _document_contains_screening_evidence(self, document: FHIRDocument, keywords: List[str]) -> bool:
        """Check if document contains evidence of completed screening"""
        if not document.extracted_text or not keywords:
            return False
        
        text_lower = document.extracted_text.lower()
        
        # Use fuzzy matching for keywords
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    def _update_screening_status(self, patient: Patient, screening_type: ScreeningType, 
                               completion_status: Dict[str, Any]):
        """Update screening status for patient"""
        try:
            from models import Screening, db
            
            # Check if screening already exists
            existing_screening = Screening.query.filter_by(
                patient_id=patient.id,
                screening_type_id=screening_type.id
            ).first()
            
            status = 'complete' if completion_status['completed'] else 'due'
            
            if existing_screening:
                # Update existing screening
                existing_screening.status = status
                existing_screening.last_completed = completion_status['last_completed_date']
                existing_screening.updated_at = datetime.now()
            else:
                # Create new screening record
                new_screening = Screening(
                    patient_id=patient.id,
                    screening_type_id=screening_type.id,
                    org_id=patient.org_id,
                    status=status,
                    last_completed=completion_status['last_completed_date'],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(new_screening)
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"Updating screening status for {patient.epic_patient_id}: "
                       f"{screening_type.name} - {'Completed' if completion_status['completed'] else 'Due'}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating screening status: {str(e)}")
    
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