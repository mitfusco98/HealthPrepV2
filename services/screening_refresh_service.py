"""
Screening Refresh Service - Screening List Workflow
Responsible ONLY for:
1. Processing EXISTING documents in database
2. Applying updated screening type criteria/keywords
3. Recomputing screening statuses based on current rules
4. NO Epic FHIR calls - pure local processing
5. Early termination when no changes needed
"""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set, Any
from sqlalchemy import and_, or_

from flask import has_request_context
from flask_login import current_user

from models import (
    db, Patient, Screening, ScreeningType, Document, FHIRDocument, AdminLog,
    PatientCondition, PrepSheetSettings, ScreeningDocumentMatch
)
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria

logger = logging.getLogger(__name__)


class ScreeningRefreshService:
    """
    Screening Refresh Service for Screening List operations
    Handles reprocessing EXISTING documents with updated criteria - NO Epic calls
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        
        # Initialize local processing components only
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        
        # Track refresh progress
        self.refresh_stats = {
            'patients_processed': 0,
            'screenings_updated': 0,
            'documents_reprocessed': 0,
            'criteria_changes_detected': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"ScreeningRefreshService initialized for organization {organization_id} - LOCAL PROCESSING ONLY")
    
    def refresh_screenings(self, refresh_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point for screening refresh - processes EXISTING data only
        
        Args:
            refresh_options: Configuration options for refresh behavior
            
        Returns:
            Dict with refresh results and statistics
        """
        if refresh_options is None:
            refresh_options = self._get_default_refresh_options()
        
        self.refresh_stats['start_time'] = datetime.utcnow()
        
        try:
            logger.info("Starting screening refresh for EXISTING data only - NO Epic calls")
            
            # Log refresh start to admin logs
            self._log_refresh_event('screening_refresh_started', {
                'organization_id': self.organization_id,
                'refresh_options': refresh_options
            })
            
            # Detect what needs refreshing
            changes_detected = self._detect_refresh_needs(refresh_options)
            
            # Early termination if no changes needed
            if not changes_detected['needs_refresh']:
                logger.info("No changes detected - early termination")
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_changes_detected',
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No changes detected - screenings are up to date',
                    'stats': self.refresh_stats
                }
            
            # Process affected screenings
            affected_patients = self._get_affected_patients(changes_detected, refresh_options)
            
            if not affected_patients:
                logger.info("No affected patients found - early termination")
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_affected_patients',
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No patients affected by changes',
                    'stats': self.refresh_stats
                }
            
            # Process each affected patient
            for patient in affected_patients:
                try:
                    updated_count = self._refresh_patient_screenings(patient, changes_detected, refresh_options)
                    if updated_count > 0:
                        self.refresh_stats['patients_processed'] += 1
                        self.refresh_stats['screenings_updated'] += updated_count
                        
                except Exception as e:
                    error_msg = f"Error refreshing patient {patient.id}: {str(e)}"
                    logger.error(error_msg)
                    self.refresh_stats['errors'].append(error_msg)
            
            # Early termination if no actual updates occurred
            if self.refresh_stats['screenings_updated'] == 0:
                logger.info("No screening updates needed - early termination")
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_updates_needed',
                    'patients_processed': len(affected_patients),
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No screening updates needed',
                    'stats': self.refresh_stats
                }
            
            db.session.commit()
            self.refresh_stats['end_time'] = datetime.utcnow()
            
            # Log successful completion
            self._log_refresh_event('screening_refresh_completed', {
                'organization_id': self.organization_id,
                'stats': self.refresh_stats,
                'duration_seconds': (self.refresh_stats['end_time'] - self.refresh_stats['start_time']).total_seconds()
            })
            
            logger.info(f"Screening refresh completed successfully: {self.refresh_stats}")
            
            return {
                'success': True,
                'message': f"Refresh completed: {self.refresh_stats['screenings_updated']} screenings updated across {self.refresh_stats['patients_processed']} patients",
                'stats': self.refresh_stats
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Screening refresh failed: {str(e)}"
            logger.error(error_msg)
            
            self.refresh_stats['end_time'] = datetime.utcnow()
            self.refresh_stats['errors'].append(error_msg)
            
            # Log error
            self._log_refresh_event('screening_refresh_error', {
                'organization_id': self.organization_id,
                'error': str(e),
                'stats': self.refresh_stats
            })
            
            return {
                'success': False,
                'error': error_msg,
                'stats': self.refresh_stats
            }
    
    def _detect_refresh_needs(self, refresh_options: Dict) -> Dict[str, Any]:
        """
        Detect what needs refreshing based on recent changes
        NO Epic calls - only analyzes local database state
        """
        changes = {
            'needs_refresh': False,
            'screening_types_modified': [],
            'active_screening_types': [],
            'inactive_screening_types': [],
            'criteria_changes': [],
            'keyword_changes': [],
            'documents_modified': [],
            'last_refresh_check': datetime.utcnow()
        }
        
        try:
            # Check for recent screening type modifications
            # Look for screening types updated since last refresh (BOTH active and inactive)
            cutoff_time = refresh_options.get('since_time') or (datetime.utcnow() - timedelta(hours=24))
            
            modified_screening_types = ScreeningType.query.filter(
                ScreeningType.org_id == self.organization_id,
                ScreeningType.updated_at >= cutoff_time
            ).all()
            
            if modified_screening_types:
                changes['screening_types_modified'] = [st.id for st in modified_screening_types]
                # Track which ones are active vs inactive for proper handling
                changes['active_screening_types'] = [st.id for st in modified_screening_types if st.is_active]
                changes['inactive_screening_types'] = [st.id for st in modified_screening_types if not st.is_active]
                changes['needs_refresh'] = True
                logger.info(f"Found {len(modified_screening_types)} modified screening types (active: {len(changes['active_screening_types'])}, inactive: {len(changes['inactive_screening_types'])})")
            
            # Check for recent document additions/modifications (both local and Epic FHIR)
            modified_documents = Document.query.filter(
                Document.org_id == self.organization_id,
                Document.created_at >= cutoff_time
            ).all()
            
            modified_fhir_documents = FHIRDocument.query.filter(
                FHIRDocument.creation_date >= cutoff_time
            ).all()
            
            total_modified_docs = len(modified_documents) + len(modified_fhir_documents)
            
            if modified_documents or modified_fhir_documents:
                changes['documents_modified'] = [doc.id for doc in modified_documents]
                changes['fhir_documents_modified'] = [doc.id for doc in modified_fhir_documents]
                changes['needs_refresh'] = True
                logger.info(f"Found {total_modified_docs} new/modified documents (local: {len(modified_documents)}, FHIR: {len(modified_fhir_documents)})")
            
            # Always check if force refresh is requested
            if refresh_options.get('force_refresh', False):
                changes['needs_refresh'] = True
                logger.info("Force refresh requested")
            
        except Exception as e:
            logger.error(f"Error detecting refresh needs: {str(e)}")
            # Default to refresh on error to be safe
            changes['needs_refresh'] = True
        
        return changes
    
    def _get_affected_patients(self, changes_detected: Dict, refresh_options: Dict) -> List[Patient]:
        """Get patients affected by the detected changes"""
        affected_patient_ids = set()
        
        # If screening types were modified, get ALL patients (eligibility may have changed)
        # This includes both patients losing eligibility AND newly eligible patients
        if changes_detected['screening_types_modified']:
            all_patient_ids = db.session.query(Patient.id).filter(
                Patient.org_id == self.organization_id
            ).all()
            
            affected_patient_ids.update([pid[0] for pid in all_patient_ids])
            logger.info(f"Screening type criteria changed - checking ALL {len(all_patient_ids)} patients for eligibility")
        
        # If documents were modified, get their patients (local documents)
        if changes_detected.get('documents_modified'):
            doc_patient_ids = db.session.query(Document.patient_id).filter(
                Document.id.in_(changes_detected['documents_modified']),
                Document.org_id == self.organization_id
            ).distinct().all()
            
            affected_patient_ids.update([pid[0] for pid in doc_patient_ids])
        
        # If FHIR documents were modified, get their patients
        if changes_detected.get('fhir_documents_modified'):
            fhir_doc_patient_ids = db.session.query(FHIRDocument.patient_id).filter(
                FHIRDocument.id.in_(changes_detected['fhir_documents_modified'])
            ).distinct().all()
            
            affected_patient_ids.update([pid[0] for pid in fhir_doc_patient_ids])
        
        # If force refresh, get all patients
        if refresh_options.get('force_refresh', False):
            all_patient_ids = db.session.query(Patient.id).filter(
                Patient.org_id == self.organization_id
            ).all()
            
            affected_patient_ids.update([pid[0] for pid in all_patient_ids])
        
        # Apply patient filters if specified
        if refresh_options.get('patient_filter'):
            patient_filter = refresh_options['patient_filter']
            if patient_filter.get('patient_ids'):
                # Intersect with specified patient IDs
                affected_patient_ids = affected_patient_ids.intersection(set(patient_filter['patient_ids']))
        
        # Get actual patient objects
        if not affected_patient_ids:
            return []
        
        patients = Patient.query.filter(
            Patient.id.in_(affected_patient_ids),
            Patient.org_id == self.organization_id
        ).limit(refresh_options.get('max_patients', 1000)).all()
        
        return patients
    
    def _refresh_patient_screenings(self, patient: Patient, changes_detected: Dict, 
                                   refresh_options: Dict) -> int:
        """Refresh screenings for a single patient - NO Epic calls"""
        updates_count = 0
        
        try:
            logger.debug(f"Refreshing screenings for patient {patient.id} (LOCAL PROCESSING ONLY)")
            
            # Get all screening types for the organization
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            for screening_type in screening_types:
                try:
                    # Check if this SPECIFIC screening type was modified (not just force refresh)
                    screening_type_modified = (
                        changes_detected['screening_types_modified'] and 
                        screening_type.id in changes_detected['screening_types_modified']
                    )
                    
                    # Check if screening type is affected by changes OR force refresh
                    screening_affected = screening_type_modified or refresh_options.get('force_refresh', False)
                    
                    if not screening_affected:
                        # Check if any of the patient's documents were modified (local or FHIR)
                        patient_doc_ids = [doc.id for doc in patient.documents]
                        doc_affected = bool(set(patient_doc_ids).intersection(
                            set(changes_detected.get('documents_modified', []))
                        ))
                        
                        # Also check FHIR documents
                        patient_fhir_doc_ids = [doc.id for doc in patient.fhir_documents]
                        fhir_doc_affected = bool(set(patient_fhir_doc_ids).intersection(
                            set(changes_detected.get('fhir_documents_modified', []))
                        ))
                        
                        if not (doc_affected or fhir_doc_affected):
                            continue  # Skip this screening type
                    
                    # Check eligibility (this may have changed due to criteria updates)
                    if self.criteria.is_patient_eligible(patient, screening_type):
                        # Get or create screening
                        screening = Screening.query.filter_by(
                            patient_id=patient.id,
                            screening_type_id=screening_type.id
                        ).first()
                        
                        screening_created = False
                        if not screening:
                            screening = Screening(
                                patient_id=patient.id,
                                screening_type_id=screening_type.id,
                                org_id=self.organization_id,
                                status='due'
                            )
                            db.session.add(screening)
                            db.session.flush()
                            screening_created = True
                            logger.info(f"Created NEW screening {screening.id} for patient {patient.id}, type {screening_type.name}")
                        
                        # Update status based on existing documents with current criteria
                        status_changed = self._update_screening_status_with_current_criteria(screening)
                        
                        # Count as update if screening was created OR status changed
                        if screening_created or status_changed:
                            updates_count += 1
                            if status_changed and not screening_created:
                                logger.debug(f"Updated screening {screening.id} status for type {screening_type.name}")
                    else:
                        # ONLY delete screening if this specific screening type was modified
                        # Don't delete due to eligibility during force refresh of unmodified types
                        if screening_type_modified:
                            existing_screening = Screening.query.filter_by(
                                patient_id=patient.id,
                                screening_type_id=screening_type.id
                            ).first()
                            
                            if existing_screening:
                                logger.info(f"Patient {patient.id} no longer eligible for {screening_type.name} (criteria changed) - removing screening {existing_screening.id}")
                                
                                # Disable autoflush to prevent cascade update before we delete match records
                                with db.session.no_autoflush:
                                    # Delete related match records first to avoid FK constraint violation
                                    ScreeningDocumentMatch.query.filter_by(screening_id=existing_screening.id).delete(synchronize_session='fetch')
                                
                                # Now safe to delete the screening
                                db.session.delete(existing_screening)
                                updates_count += 1
                        else:
                            # Screening type not modified - just skip (don't delete)
                            logger.debug(f"Patient {patient.id} not eligible for {screening_type.name}, but criteria unchanged - skipping")
                    
                except Exception as e:
                    logger.error(f"Error processing screening type {screening_type.id} for patient {patient.id}: {str(e)}")
                    self.refresh_stats['errors'].append(f"Patient {patient.id}, Screening Type {screening_type.id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error refreshing patient {patient.id}: {str(e)}")
            raise
        
        return updates_count
    
    def _find_fhir_document_matches(self, screening: Screening) -> List[Dict]:
        """
        Find FHIR documents that match this screening's keywords
        Similar to DocumentMatcher but for Epic FHIR documents
        """
        matches = []
        
        try:
            # Get screening keywords
            keywords = json.loads(screening.screening_type.keywords) if screening.screening_type.keywords else []
            if not keywords:
                return matches
            
            # Get patient's FHIR documents
            fhir_documents = FHIRDocument.query.filter_by(
                patient_id=screening.patient_id
            ).all()
            
            for doc in fhir_documents:
                if not doc.ocr_text:
                    continue
                
                # Check if document text contains screening keywords
                text_lower = doc.ocr_text.lower()
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        # Use document_date with fallback to creation_date
                        doc_date = doc.document_date or doc.creation_date
                        if doc_date and hasattr(doc_date, 'date'):
                            doc_date = doc_date.date()
                        
                        matches.append({
                            'document': doc,
                            'document_date': doc_date,
                            'confidence': 0.9,  # High confidence for keyword match
                            'source': 'fhir'
                        })
                        break  # Found a match, no need to check other keywords
            
            logger.debug(f"Found {len(matches)} FHIR document matches for screening {screening.id}")
            return matches
            
        except Exception as e:
            logger.error(f"Error finding FHIR document matches: {str(e)}")
            return matches
    
    def _find_fhir_document_matches_filtered(self, screening: Screening) -> List[Dict]:
        """
        Find FHIR documents that match this screening - with dismissal filtering (batched query)
        """
        from models import DismissedDocumentMatch
        
        # Get all FHIR matches
        all_matches = self._find_fhir_document_matches(screening)
        
        if not all_matches:
            return []
        
        # Batch query: Get all dismissed FHIR document IDs for this screening in one query
        fhir_doc_ids = [match['document'].id for match in all_matches]
        dismissed_ids = set(
            row[0] for row in db.session.query(DismissedDocumentMatch.fhir_document_id).filter(
                DismissedDocumentMatch.fhir_document_id.in_(fhir_doc_ids),
                DismissedDocumentMatch.screening_id == screening.id,
                DismissedDocumentMatch.is_active == True
            ).all()
        )
        
        # Filter out dismissed matches using the batched set
        filtered_matches = []
        for match in all_matches:
            if match['document'].id not in dismissed_ids:
                filtered_matches.append(match)
            else:
                logger.debug(f"Skipping dismissed FHIR match: Doc {match['document'].id} -> Screening {screening.id}")
        
        return filtered_matches
    
    def _update_screening_status_with_current_criteria(self, screening: Screening) -> bool:
        """
        Update screening status based on existing documents with current criteria
        NO Epic calls - processes existing local documents AND FHIR documents
        Automatically excludes dismissed matches via DocumentMatcher
        """
        try:
            # Find matching LOCAL documents (already excludes dismissed matches)
            matches = self.matcher.find_screening_matches(screening, exclude_dismissed=True)
            
            # ALSO find matching FHIR documents (from Epic) and filter dismissed
            fhir_matches = self._find_fhir_document_matches_filtered(screening)
            
            # Link FHIR documents to screening for UI display (many-to-many relationship)
            for fhir_match in fhir_matches:
                fhir_doc = fhir_match['document']
                if fhir_doc not in screening.fhir_documents:
                    screening.fhir_documents.append(fhir_doc)
            
            # Combine both match lists (both already filtered)
            all_matches = matches + fhir_matches
            
            if all_matches:
                # Get the most recent matching document
                def safe_date_key(match):
                    doc_date = match['document_date']
                    if doc_date is None:
                        return date.min
                    if hasattr(doc_date, 'date'):
                        return doc_date.date()
                    return doc_date
                
                latest_match = max(all_matches, key=safe_date_key)
                document_date = latest_match['document_date'] or latest_match['document'].created_at.date()
                
                if hasattr(document_date, 'date'):
                    document_date = document_date.date()
                
                # Calculate new status using current criteria
                new_status = self.criteria.calculate_screening_status(
                    screening.screening_type,
                    document_date
                )
                
                # Update if status changed or we have a newer completion date
                status_changed = new_status != screening.status
                date_changed = (screening.last_completed is None or 
                              document_date > screening.last_completed)
                
                if status_changed or date_changed:
                    old_status = screening.status
                    screening.status = new_status
                    screening.last_completed = document_date
                    screening.updated_at = datetime.utcnow()
                    
                    logger.debug(f"Screening {screening.id}: {old_status} -> {new_status}, completed: {document_date}")
                    return True
            
            else:
                # No matching documents found - should be 'due'
                if screening.status != 'due':
                    old_status = screening.status
                    screening.status = 'due'
                    screening.last_completed = None
                    screening.updated_at = datetime.utcnow()
                    
                    logger.debug(f"Screening {screening.id}: {old_status} -> due (no matches)")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating screening {screening.id}: {str(e)}")
            return False
    
    def refresh_specific_screenings(self, screening_ids: List[int]) -> Dict[str, Any]:
        """
        Refresh specific screenings by ID
        Useful for targeted updates after criteria changes
        """
        self.refresh_stats = {
            'patients_processed': 0,
            'screenings_updated': 0,
            'documents_reprocessed': 0,
            'errors': [],
            'start_time': datetime.utcnow(),
            'end_time': None
        }
        
        try:
            logger.info(f"Refreshing {len(screening_ids)} specific screenings")
            
            # Get screenings
            screenings = Screening.query.filter(
                Screening.id.in_(screening_ids),
                Screening.org_id == self.organization_id
            ).all()
            
            if not screenings:
                return {
                    'success': True,
                    'message': 'No screenings found to refresh',
                    'stats': self.refresh_stats
                }
            
            # Process each screening
            patient_ids_processed = set()
            for screening in screenings:
                try:
                    if self._update_screening_status_with_current_criteria(screening):
                        self.refresh_stats['screenings_updated'] += 1
                        patient_ids_processed.add(screening.patient_id)
                        
                except Exception as e:
                    error_msg = f"Error refreshing screening {screening.id}: {str(e)}"
                    logger.error(error_msg)
                    self.refresh_stats['errors'].append(error_msg)
            
            self.refresh_stats['patients_processed'] = len(patient_ids_processed)
            
            db.session.commit()
            self.refresh_stats['end_time'] = datetime.utcnow()
            
            return {
                'success': True,
                'message': f"Refreshed {self.refresh_stats['screenings_updated']} screenings",
                'stats': self.refresh_stats
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Specific screenings refresh failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'stats': self.refresh_stats
            }
    
    def _log_refresh_event(self, event_type: str, details: Dict):
        """Log refresh events to admin audit log"""
        try:
            # Get current user if available
            user_id = None
            username = 'system'
            if has_request_context() and current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
            
            # Convert datetime objects to strings for JSON serialization
            serializable_details = {}
            for key, value in details.items():
                if isinstance(value, datetime):
                    serializable_details[key] = value.isoformat()
                elif isinstance(value, dict):
                    # Handle nested datetime objects
                    serializable_details[key] = {
                        k: v.isoformat() if isinstance(v, datetime) else v
                        for k, v in value.items()
                    }
                else:
                    serializable_details[key] = value
            
            # Create admin log entry matching AdminLog model structure
            admin_log = AdminLog(
                user_id=user_id,
                org_id=self.organization_id,
                event_type=event_type,
                resource_type='screening_refresh',
                action_details=f"Screening refresh: {event_type} (User: {username})",
                data=serializable_details
            )
            
            db.session.add(admin_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging refresh event: {str(e)}")
    
    def _get_default_refresh_options(self) -> Dict:
        """Get default refresh options"""
        return {
            'max_patients': 10000,  # Higher limit since no network calls
            'force_refresh': False,
            'check_eligibility': True,
            'update_statuses': True
        }