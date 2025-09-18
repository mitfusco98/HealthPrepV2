"""
EMR Sync Service - Dashboard Workflow
Responsible ONLY for:
1. Pulling NEW documents from Epic FHIR
2. OCR processing new documents 
3. Initial screening status updates for new data
4. Audit logging of sync operations
5. Early termination when no new data
"""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dateutil.relativedelta import relativedelta

from flask import session, has_request_context
from flask_login import current_user

from models import db, Patient, PatientCondition, FHIRDocument, Organization, ScreeningType, Screening, Document, AdminLog
from services.epic_fhir_service import EpicFHIRService, get_epic_fhir_service_background
from emr.fhir_client import FHIRClient
from ocr.document_processor import DocumentProcessor
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria

logger = logging.getLogger(__name__)


class EMRSyncService:
    """
    EMR Sync Service for Dashboard operations
    Handles pulling NEW data from Epic FHIR with OCR processing and initial screening updates
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.organization = Organization.query.get(organization_id)
        
        if not self.organization:
            raise ValueError(f"Organization {organization_id} not found")
        
        # Always use background/database tokens for EMR sync operations
        logger.info(f"EMRSyncService: Initializing for org {organization_id}")
        
        self.epic_service = get_epic_fhir_service_background(organization_id)
        
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
        
        # Initialize processing components
        self.document_processor = DocumentProcessor()
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        
        # Track sync progress
        self.sync_stats = {
            'patients_processed': 0,
            'new_documents_found': 0,
            'documents_processed': 0,
            'screenings_updated': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"EMRSyncService initialized for organization {organization_id}")
    
    def sync_new_data(self, patient_filter: Optional[Dict] = None, 
                     sync_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point for EMR sync - pulls NEW data only
        
        Args:
            patient_filter: Optional filter for specific patients
            sync_options: Configuration options for sync behavior
            
        Returns:
            Dict with sync results and statistics
        """
        if sync_options is None:
            sync_options = self._get_default_sync_options()
        
        self.sync_stats['start_time'] = datetime.utcnow()
        
        try:
            logger.info("Starting EMR sync for NEW data only")
            
            # Log sync start to admin logs
            self._log_sync_event('emr_sync_started', {
                'organization_id': self.organization_id,
                'patient_filter': patient_filter,
                'sync_options': sync_options
            })
            
            # Ensure we have valid authentication
            if not self.epic_service.ensure_authenticated():
                raise Exception("Epic FHIR authentication failed")
            
            # Get patients to sync (upcoming 2 weeks get priority)
            patients_to_sync = self._get_patients_for_sync(patient_filter, sync_options)
            
            if not patients_to_sync:
                logger.info("No patients found for sync - early termination")
                self._log_sync_event('emr_sync_completed_early', {
                    'reason': 'no_patients_found',
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No patients found for sync',
                    'stats': self.sync_stats
                }
            
            # Process each patient for new data
            for patient in patients_to_sync:
                try:
                    new_data_found = self._sync_patient_new_data(patient, sync_options)
                    if new_data_found:
                        self.sync_stats['patients_processed'] += 1
                        
                except Exception as e:
                    error_msg = f"Error syncing patient {patient.id}: {str(e)}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Early termination check
            if self.sync_stats['new_documents_found'] == 0:
                logger.info("No new documents found - early termination")
                self._log_sync_event('emr_sync_completed_early', {
                    'reason': 'no_new_documents',
                    'patients_checked': len(patients_to_sync),
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No new documents found',
                    'stats': self.sync_stats
                }
            
            db.session.commit()
            self.sync_stats['end_time'] = datetime.utcnow()
            
            # Log successful completion
            self._log_sync_event('emr_sync_completed', {
                'organization_id': self.organization_id,
                'stats': self.sync_stats,
                'duration_seconds': (self.sync_stats['end_time'] - self.sync_stats['start_time']).total_seconds()
            })
            
            logger.info(f"EMR sync completed successfully: {self.sync_stats}")
            
            return {
                'success': True,
                'message': f"Sync completed: {self.sync_stats['new_documents_found']} new documents, {self.sync_stats['screenings_updated']} screenings updated",
                'stats': self.sync_stats
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"EMR sync failed: {str(e)}"
            logger.error(error_msg)
            
            self.sync_stats['end_time'] = datetime.utcnow()
            self.sync_stats['errors'].append(error_msg)
            
            # Log error
            self._log_sync_event('emr_sync_error', {
                'organization_id': self.organization_id,
                'error': str(e),
                'stats': self.sync_stats
            })
            
            return {
                'success': False,
                'error': error_msg,
                'stats': self.sync_stats
            }
    
    def _get_patients_for_sync(self, patient_filter: Optional[Dict], 
                              sync_options: Dict) -> List[Patient]:
        """Get patients for sync with priority for next 2 weeks"""
        query = Patient.query.filter_by(org_id=self.organization_id, is_active=True)
        
        # Apply patient filter if provided
        if patient_filter:
            if patient_filter.get('patient_ids'):
                query = query.filter(Patient.id.in_(patient_filter['patient_ids']))
            if patient_filter.get('mrn_filter'):
                query = query.filter(Patient.mrn.ilike(f"%{patient_filter['mrn_filter']}%"))
        
        # Get all patients, then prioritize
        all_patients = query.all()
        
        if not all_patients:
            return []
        
        # Priority: patients with appointments in next 2 weeks
        # For now, return all patients but this could be enhanced with appointment data
        upcoming_window = date.today() + timedelta(days=14)
        
        # Sort by priority (this could be enhanced with actual appointment dates)
        # For now, just return patients ordered by ID
        return sorted(all_patients, key=lambda p: p.id)[:sync_options.get('max_patients', 1000)]
    
    def _sync_patient_new_data(self, patient: Patient, sync_options: Dict) -> bool:
        """Sync NEW data for a single patient"""
        new_data_found = False
        
        try:
            logger.info(f"Syncing new data for patient {patient.id} (MRN: {patient.mrn})")
            
            # Get last sync time for incremental sync
            last_sync = self._get_last_sync_time(patient)
            
            # Sync new documents only
            new_docs = self._sync_patient_new_documents(patient, last_sync, sync_options)
            if new_docs > 0:
                self.sync_stats['new_documents_found'] += new_docs
                self.sync_stats['documents_processed'] += new_docs
                new_data_found = True
                
                # Update screening statuses for this patient based on new documents
                screening_updates = self._update_patient_screenings_for_new_docs(patient)
                self.sync_stats['screenings_updated'] += screening_updates
            
            # Update last sync time
            patient.last_emr_sync_at = datetime.utcnow()
            db.session.add(patient)
            
        except Exception as e:
            logger.error(f"Error syncing patient {patient.id}: {str(e)}")
            self.sync_stats['errors'].append(f"Patient {patient.id}: {str(e)}")
        
        return new_data_found
    
    def _sync_patient_new_documents(self, patient: Patient, 
                                   since_date: Optional[datetime], 
                                   sync_options: Dict) -> int:
        """Sync only NEW documents for a patient"""
        new_docs_count = 0
        
        try:
            # Get Epic patient ID
            if not patient.mrn:
                logger.warning(f"Patient {patient.id} has no MRN, skipping document sync")
                return 0
            
            # Query Epic for new documents since last sync
            fhir_documents = self.epic_service.get_patient_documents(
                patient.mrn, 
                since_date=since_date,
                limit=sync_options.get('document_batch_size', 100)
            )
            
            if not fhir_documents:
                logger.debug(f"No new documents found for patient {patient.id}")
                return 0
            
            # Process each new document
            for fhir_doc in fhir_documents:
                try:
                    # Check if we already have this document
                    existing_doc = Document.query.filter_by(
                        patient_id=patient.id,
                        org_id=patient.org_id,
                        external_system='epic',
                        external_id=fhir_doc.get('id')
                    ).first()
                    
                    if existing_doc:
                        logger.debug(f"Document {fhir_doc.get('id')} already exists, skipping")
                        continue
                    
                    # Download and process new document
                    doc_content = self.epic_service.download_document_content(fhir_doc)
                    if doc_content:
                        # Create document record
                        document = self._create_document_from_fhir(patient, fhir_doc, doc_content)
                        if document:
                            new_docs_count += 1
                            logger.info(f"Processed new document: {document.filename}")
                    
                except Exception as e:
                    logger.error(f"Error processing document {fhir_doc.get('id')}: {str(e)}")
                    self.sync_stats['errors'].append(f"Document {fhir_doc.get('id')}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error syncing documents for patient {patient.id}: {str(e)}")
            raise
        
        return new_docs_count
    
    def _create_document_from_fhir(self, patient: Patient, fhir_doc: Dict, 
                                  doc_content: bytes) -> Optional[Document]:
        """Create and process a document from FHIR data"""
        try:
            # Extract document metadata
            document_title = self._extract_document_title(fhir_doc)
            document_date = self._extract_document_date(fhir_doc)
            
            # Process document with OCR
            ocr_text = None
            if doc_content:
                ocr_text = self.document_processor.process_document(doc_content, document_title)
            
            # Create document record
            document = Document(
                patient_id=patient.id,
                org_id=patient.org_id,
                filename=document_title or f"epic_doc_{fhir_doc.get('id')}",
                document_date=document_date,
                ocr_text=ocr_text,
                external_system='epic',
                external_id=fhir_doc.get('id'),
                ingested_at=datetime.utcnow(),
                processed_at=datetime.utcnow() if ocr_text else None,
                created_at=datetime.utcnow()
            )
            
            db.session.add(document)
            db.session.flush()  # Get the ID
            
            return document
            
        except Exception as e:
            logger.error(f"Error creating document from FHIR: {str(e)}")
            return None
    
    def _update_patient_screenings_for_new_docs(self, patient: Patient) -> int:
        """Update screening statuses based on newly added documents"""
        updates_count = 0
        
        try:
            # Get patient's screening types
            screening_types = ScreeningType.query.filter_by(
                org_id=patient.org_id,
                is_active=True
            ).all()
            
            for screening_type in screening_types:
                # Check if patient is eligible for this screening
                if self.criteria.is_patient_eligible(patient, screening_type):
                    # Get or create screening
                    screening = Screening.query.filter_by(
                        patient_id=patient.id,
                        screening_type_id=screening_type.id
                    ).first()
                    
                    if not screening:
                        screening = Screening(
                            patient_id=patient.id,
                            screening_type_id=screening_type.id,
                            org_id=patient.org_id,
                            status='due'
                        )
                        db.session.add(screening)
                        db.session.flush()
                    
                    # Update status based on any matching documents
                    if self._update_screening_status_from_documents(screening):
                        updates_count += 1
            
        except Exception as e:
            logger.error(f"Error updating screenings for patient {patient.id}: {str(e)}")
        
        return updates_count
    
    def _update_screening_status_from_documents(self, screening: Screening) -> bool:
        """Update a screening's status based on matching documents"""
        try:
            # Find matching documents
            matches = self.matcher.find_screening_matches(screening)
            
            if matches:
                # Get the most recent matching document
                def safe_date_key(match):
                    doc_date = match['document_date']
                    if doc_date is None:
                        return date.min
                    if hasattr(doc_date, 'date'):
                        return doc_date.date()
                    return doc_date
                
                latest_match = max(matches, key=safe_date_key)
                document_date = latest_match['document_date'] or latest_match['document'].created_at.date()
                
                if hasattr(document_date, 'date'):
                    document_date = document_date.date()
                
                # Calculate new status
                new_status = self.criteria.calculate_screening_status(
                    screening.screening_type,
                    document_date
                )
                
                # Update if status changed or we have a newer completion date
                status_changed = new_status != screening.status
                date_changed = (screening.last_completed is None or 
                              document_date > screening.last_completed)
                
                if status_changed or date_changed:
                    screening.status = new_status
                    screening.last_completed = document_date
                    screening.updated_at = datetime.utcnow()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating screening {screening.id}: {str(e)}")
            return False
    
    def _get_last_sync_time(self, patient: Patient) -> Optional[datetime]:
        """Get the last sync time for incremental updates"""
        if patient.last_emr_sync_at:
            return patient.last_emr_sync_at
        
        # Fallback: look for most recent document
        last_doc = Document.query.filter_by(
            patient_id=patient.id,
            external_system='epic'
        ).order_by(Document.ingested_at.desc()).first()
        
        if last_doc and last_doc.ingested_at:
            return last_doc.ingested_at
        
        # No previous sync - start from 30 days ago for initial sync
        return datetime.utcnow() - timedelta(days=30)
    
    def _extract_document_title(self, fhir_doc: Dict) -> str:
        """Extract document title from FHIR DocumentReference"""
        if fhir_doc.get('type', {}).get('text'):
            return fhir_doc['type']['text']
        
        if fhir_doc.get('description'):
            return fhir_doc['description']
        
        return f"Epic Document {fhir_doc.get('id', 'Unknown')}"
    
    def _extract_document_date(self, fhir_doc: Dict) -> Optional[date]:
        """Extract document date from FHIR DocumentReference"""
        try:
            # Try date field first
            if fhir_doc.get('date'):
                date_str = fhir_doc['date']
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                else:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Fallback to creation date
            if fhir_doc.get('created'):
                created_str = fhir_doc['created']
                if 'T' in created_str:
                    return datetime.fromisoformat(created_str.replace('Z', '+00:00')).date()
            
            return date.today()  # Fallback to today
            
        except Exception as e:
            logger.warning(f"Error parsing document date from FHIR: {str(e)}")
            return date.today()
    
    def _log_sync_event(self, event_type: str, details: Dict):
        """Log sync events to admin audit log"""
        try:
            # Get current user if available
            user_id = None
            username = None
            if has_request_context() and current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
            
            # Create admin log entry
            admin_log = AdminLog(
                user_id=user_id,
                username=username or 'system',
                action=event_type,
                target_type='emr_sync',
                target_id=self.organization_id,
                details=json.dumps(details),
                org_id=self.organization_id,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(admin_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging sync event: {str(e)}")
    
    def _get_default_sync_options(self) -> Dict:
        """Get default sync options"""
        return {
            'max_patients': 1000,
            'document_batch_size': 100,
            'enable_ocr': True,
            'update_screenings': True,
            'sync_conditions': True,
            'sync_observations': False  # Can be enabled later
        }