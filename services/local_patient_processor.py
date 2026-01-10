"""
Local Patient Document Processor

Processes existing patient documents against current screening criteria without
requiring Epic FHIR integration. Used for manual patients who were not synced
from Epic EMR.

This module shares the same screening logic as ComprehensiveEMRSync but:
- Does NOT require Epic OAuth credentials
- Does NOT fetch data from Epic FHIR API  
- Processes only existing local documents (Document and FHIRDocument tables)
- Uses the same screening engine for eligibility and document matching
- Logs the same audit events for HITRUST CSF compliance
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from models import db, Patient, Document, FHIRDocument, ScreeningType, Screening, ScreeningDocumentMatch
from core.engine import ScreeningEngine
from ocr.phi_filter import PHIFilter
from utils.admin_audit_log import log_admin_event

logger = logging.getLogger(__name__)


class LocalPatientProcessor:
    """
    Process patient documents locally without Epic integration.
    
    This processor re-evaluates existing documents against current active
    screening criteria, updating screening statuses and due dates.
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.screening_engine = ScreeningEngine()
        self.phi_filter = PHIFilter()
        
        self.processing_stats = {
            'documents_evaluated': 0,
            'screenings_updated': 0,
            'matches_created': 0,
            'errors': []
        }
        
        logger.info(f"Initialized LocalPatientProcessor for organization {organization_id}")
    
    def process_patient_documents(self, patient: Patient, 
                                   options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process existing documents for a patient using current screening criteria.
        
        This is the local-only equivalent of ComprehensiveEMRSync.sync_patient_comprehensive()
        but without any Epic FHIR API calls.
        
        Args:
            patient: Patient to process
            options: Processing options (force_refresh, etc.)
        
        Returns:
            Dict with processing results and statistics
        """
        if options is None:
            options = {'force_refresh': True}
        
        try:
            logger.info(f"Starting local document processing for patient {patient.name} (ID: {patient.id})")
            
            processing_start = datetime.now()
            
            log_admin_event(
                event_type='local_patient_reprocess_started',
                user_id=None,
                org_id=self.organization_id,
                ip=None,
                patient_id=patient.id,
                resource_type='patient',
                resource_id=patient.id,
                action_details=f'Local reprocessing started for {patient.name}',
                data={
                    'patient_name': patient.name,
                    'force_refresh': options.get('force_refresh', False),
                    'started_at': processing_start.isoformat()
                }
            )
            
            manual_docs = Document.query.filter_by(patient_id=patient.id).all()
            fhir_docs = FHIRDocument.query.filter_by(patient_id=patient.id).all()
            total_docs = len(manual_docs) + len(fhir_docs)
            
            logger.info(f"Found {len(manual_docs)} manual docs and {len(fhir_docs)} FHIR docs for patient {patient.name}")
            
            screenings_updated = self._process_screening_eligibility(patient)
            
            patient.mark_documents_evaluated()
            
            now = datetime.utcnow()
            for screening in patient.screenings:
                screening.last_processed = now
                screening.updated_at = now
                screening.is_dormant = False
            
            db.session.commit()
            
            processing_duration = (datetime.now() - processing_start).total_seconds()
            
            log_admin_event(
                event_type='local_patient_reprocess_complete',
                user_id=None,
                org_id=self.organization_id,
                ip=None,
                patient_id=patient.id,
                resource_type='patient',
                resource_id=patient.id,
                action_details=f'Local reprocessing completed for {patient.name}',
                data={
                    'patient_name': patient.name,
                    'documents_evaluated': total_docs,
                    'screenings_updated': screenings_updated,
                    'processing_duration_seconds': round(processing_duration, 2),
                    'completed_at': datetime.now().isoformat()
                }
            )
            
            result = {
                'success': True,
                'patient_id': patient.id,
                'patient_name': patient.name,
                'documents_evaluated': total_docs,
                'screenings_updated': screenings_updated,
                'processing_duration_seconds': round(processing_duration, 2),
                'local_only': True
            }
            
            logger.info(f"Local processing completed for {patient.name}: {total_docs} docs evaluated, {screenings_updated} screenings updated")
            
            return result
            
        except Exception as e:
            error_msg = f"Error in local patient processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.processing_stats['errors'].append(error_msg)
            
            try:
                log_admin_event(
                    event_type='local_patient_reprocess_failed',
                    user_id=None,
                    org_id=self.organization_id,
                    ip=None,
                    patient_id=patient.id,
                    resource_type='patient',
                    resource_id=patient.id,
                    action_details=f'Local reprocessing failed: {str(e)[:100]}',
                    data={
                        'patient_name': patient.name,
                        'error': str(e),
                        'failed_at': datetime.now().isoformat()
                    }
                )
            except Exception as log_error:
                logger.warning(f"Failed to log processing error: {log_error}")
            
            db.session.rollback()
            
            return {
                'success': False,
                'patient_id': patient.id,
                'error': error_msg,
                'local_only': True
            }
    
    def _process_screening_eligibility(self, patient: Patient) -> int:
        """
        Process screening eligibility using current active criteria.
        
        This mirrors ComprehensiveEMRSync._process_screening_eligibility() but
        works without Epic integration.
        """
        logger.info(f"Processing screening eligibility for patient {patient.name}")
        
        try:
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id, 
                is_active=True
            ).all()
            
            screenings_updated = 0
            
            for screening_type in screening_types:
                is_eligible = self.screening_engine.criteria.is_patient_eligible(patient, screening_type)
                
                if is_eligible:
                    completion_status = self._check_screening_completion(patient, screening_type)
                    
                    self._update_screening_status(patient, screening_type, completion_status)
                    screenings_updated += 1
            
            logger.info(f"Updated {screenings_updated} screening statuses for {patient.name}")
            return screenings_updated
            
        except Exception as e:
            logger.error(f"Error processing screening eligibility: {str(e)}")
            return 0
    
    def _check_screening_completion(self, patient: Patient, screening_type: ScreeningType) -> Dict[str, Any]:
        """
        Check if screening has been completed based on BOTH manual and FHIR documents.
        
        This mirrors ComprehensiveEMRSync._check_screening_completion().
        """
        try:
            keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
            if not keywords:
                return {
                    'completed': False,
                    'last_completed_date': None,
                    'source': None,
                    'matched_manual_docs': [],
                    'matched_fhir_docs': []
                }
            
            cutoff_date = datetime.now() - timedelta(days=int(screening_type.frequency_years * 365))
            
            matched_manual_docs = []
            matched_fhir_docs = []
            most_recent_completion_date = None
            
            manual_documents = Document.query.filter_by(
                patient_id=patient.id
            ).filter(
                Document.created_at >= cutoff_date
            ).all()
            
            for doc in manual_documents:
                if self._document_contains_screening_evidence(doc.ocr_text, keywords):
                    completion_date = doc.created_at or datetime.now()
                    matched_manual_docs.append({
                        'id': doc.id,
                        'date': completion_date,
                        'title': doc.filename
                    })
                    if not most_recent_completion_date or completion_date > most_recent_completion_date:
                        most_recent_completion_date = completion_date
            
            fhir_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id
            ).filter(
                FHIRDocument.document_date >= cutoff_date
            ).all()
            
            for doc in fhir_documents:
                search_text = doc.search_title or doc.title or ''
                ocr_text = doc.ocr_text or ''
                combined_text = f"{search_text} {ocr_text}"
                
                if self._document_contains_screening_evidence(combined_text, keywords):
                    completion_date = doc.document_date or doc.created_at or datetime.now()
                    matched_fhir_docs.append({
                        'id': doc.id,
                        'date': completion_date,
                        'title': doc.title
                    })
                    if not most_recent_completion_date or completion_date > most_recent_completion_date:
                        most_recent_completion_date = completion_date
            
            is_completed = len(matched_manual_docs) > 0 or len(matched_fhir_docs) > 0
            source = None
            if matched_fhir_docs:
                source = 'FHIR'
            elif matched_manual_docs:
                source = 'manual'
            
            return {
                'completed': is_completed,
                'last_completed_date': most_recent_completion_date,
                'source': source,
                'matched_manual_docs': matched_manual_docs,
                'matched_fhir_docs': matched_fhir_docs
            }
            
        except Exception as e:
            logger.error(f"Error checking screening completion: {str(e)}")
            return {
                'completed': False,
                'last_completed_date': None,
                'source': None,
                'matched_manual_docs': [],
                'matched_fhir_docs': []
            }
    
    def _document_contains_screening_evidence(self, text: str, keywords: List[str]) -> bool:
        """
        Check if document text contains evidence of screening completion.
        Uses fuzzy matching for keyword detection.
        """
        if not text or not keywords:
            return False
        
        text_lower = text.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            if not keyword_lower:
                continue
                
            keyword_normalized = keyword_lower.replace('_', ' ').replace('-', ' ').replace('.', ' ')
            
            if keyword_lower in text_lower:
                return True
            if keyword_normalized in text_lower:
                return True
            
            keyword_words = keyword_normalized.split()
            if len(keyword_words) > 1:
                if all(word in text_lower for word in keyword_words):
                    return True
        
        return False
    
    def _update_screening_status(self, patient: Patient, screening_type: ScreeningType, 
                                  completion_status: Dict[str, Any]):
        """
        Update or create screening record based on completion status.
        """
        try:
            screening = Screening.query.filter_by(
                patient_id=patient.id,
                screening_type_id=screening_type.id
            ).first()
            
            if not screening:
                screening = Screening()
                screening.patient_id = patient.id
                screening.screening_type_id = screening_type.id
                screening.created_at = datetime.now()
                db.session.add(screening)
            
            if completion_status['completed']:
                screening.status = 'completed'
                screening.last_completed = completion_status['last_completed_date']
                
                if screening_type.frequency_years and screening.last_completed:
                    screening.next_due = screening.last_completed + timedelta(
                        days=int(screening_type.frequency_years * 365)
                    )
            else:
                screening.status = 'due'
                if not screening.next_due:
                    screening.next_due = datetime.now()
            
            screening.updated_at = datetime.now()
            
            self._update_document_matches(screening, completion_status)
            
        except Exception as e:
            logger.error(f"Error updating screening status: {str(e)}")
    
    def _update_document_matches(self, screening: Screening, completion_status: Dict[str, Any]):
        """
        Update ScreeningDocumentMatch associations for matched documents.
        """
        try:
            ScreeningDocumentMatch.query.filter_by(screening_id=screening.id).delete()
            
            for manual_doc in completion_status.get('matched_manual_docs', []):
                match = ScreeningDocumentMatch()
                match.screening_id = screening.id
                match.document_id = manual_doc['id']
                match.document_type = 'manual'
                match.matched_at = datetime.now()
                db.session.add(match)
                self.processing_stats['matches_created'] += 1
            
            for fhir_doc in completion_status.get('matched_fhir_docs', []):
                match = ScreeningDocumentMatch()
                match.screening_id = screening.id
                match.fhir_document_id = fhir_doc['id']
                match.document_type = 'fhir'
                match.matched_at = datetime.now()
                db.session.add(match)
                self.processing_stats['matches_created'] += 1
                
        except Exception as e:
            logger.error(f"Error updating document matches: {str(e)}")
