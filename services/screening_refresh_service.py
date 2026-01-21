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
    PatientCondition, PrepSheetSettings, ScreeningDocumentMatch, FHIRImmunization,
    Organization
)
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria
from core.variants import ScreeningVariants

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
            
            # Track manually refreshed patient IDs to exempt from dormancy marking
            # This allows manually refreshed patients to remain active for the day
            manually_refreshed_patient_ids: Set[int] = set()
            if refresh_options.get('patient_filter', {}).get('patient_ids'):
                manually_refreshed_patient_ids = set(refresh_options['patient_filter']['patient_ids'])
                logger.info(f"Manual refresh requested for {len(manually_refreshed_patient_ids)} patient(s) - will exempt from dormancy marking")
            
            # Early termination if no changes needed
            if not changes_detected['needs_refresh']:
                logger.info("No changes detected - applying dormancy check only")
                # Still apply dormancy logic even if no document/criteria changes
                dormancy_result = self._apply_appointment_prioritization_dormancy(manually_refreshed_patient_ids)
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_changes_detected',
                    'organization_id': self.organization_id,
                    'dormancy_applied': dormancy_result
                })
                # Commit with rollback on failure to ensure clean session state
                try:
                    db.session.commit()
                    return {
                        'success': True,
                        'message': 'No changes detected - dormancy updated based on appointments',
                        'stats': self.refresh_stats,
                        'dormancy_applied': dormancy_result
                    }
                except Exception as commit_error:
                    logger.error(f"Commit failed in early-return: {commit_error}")
                    db.session.rollback()
                    return {
                        'success': False,
                        'error': f"Commit failed: {str(commit_error)}",
                        'stats': self.refresh_stats
                    }
            
            # Process affected screenings
            affected_patients = self._get_affected_patients(changes_detected, refresh_options)
            
            if not affected_patients:
                logger.info("No affected patients found - applying dormancy check only")
                # Still apply dormancy logic even if no affected patients
                dormancy_result = self._apply_appointment_prioritization_dormancy(manually_refreshed_patient_ids)
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_affected_patients',
                    'organization_id': self.organization_id,
                    'dormancy_applied': dormancy_result
                })
                # Commit with rollback on failure to ensure clean session state
                try:
                    db.session.commit()
                    return {
                        'success': True,
                        'message': 'No patients affected - dormancy updated based on appointments',
                        'stats': self.refresh_stats,
                        'dormancy_applied': dormancy_result
                    }
                except Exception as commit_error:
                    logger.error(f"Commit failed in early-return: {commit_error}")
                    db.session.rollback()
                    return {
                        'success': False,
                        'error': f"Commit failed: {str(commit_error)}",
                        'stats': self.refresh_stats
                    }
            
            # For manual patient refresh, explicitly clear dormancy for ALL screenings
            # of the targeted patients BEFORE eligibility checks. This guarantees
            # the "active for the day" semantic even for ineligible screening types.
            if manually_refreshed_patient_ids:
                now_utc = datetime.utcnow()
                reactivated_count = Screening.query.filter(
                    Screening.org_id == self.organization_id,
                    Screening.patient_id.in_(manually_refreshed_patient_ids),
                    Screening.is_dormant == True
                ).update({
                    'is_dormant': False, 
                    'last_processed': now_utc
                }, synchronize_session=False)
                
                if reactivated_count > 0:
                    logger.info(f"Manual refresh: reactivated {reactivated_count} dormant screenings for {len(manually_refreshed_patient_ids)} patient(s)")
                    self.refresh_stats['dormant_screenings_reactivated'] = reactivated_count
            
            # Pre-fetch screening types once for all patients (avoid per-patient query)
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            # Process each affected patient
            for patient in affected_patients:
                try:
                    updated_count = self._refresh_patient_screenings(
                        patient, changes_detected, refresh_options, 
                        screening_types=screening_types
                    )
                    if updated_count > 0:
                        self.refresh_stats['patients_processed'] += 1
                        self.refresh_stats['screenings_updated'] += updated_count
                        
                except Exception as e:
                    error_msg = f"Error refreshing patient {patient.id}: {str(e)}"
                    logger.error(error_msg)
                    self.refresh_stats['errors'].append(error_msg)
            
            # Early termination if no actual updates occurred
            if self.refresh_stats['screenings_updated'] == 0:
                logger.info("No screening updates needed - applying dormancy check")
                # Still apply dormancy logic even if no screening updates
                dormancy_result = self._apply_appointment_prioritization_dormancy(manually_refreshed_patient_ids)
                self._log_refresh_event('screening_refresh_completed_early', {
                    'reason': 'no_updates_needed',
                    'patients_processed': len(affected_patients),
                    'organization_id': self.organization_id,
                    'dormancy_applied': dormancy_result
                })
                # Commit with rollback on failure to ensure clean session state
                try:
                    db.session.commit()
                    return {
                        'success': True,
                        'message': 'No screening updates needed',
                        'stats': self.refresh_stats,
                        'dormancy_applied': dormancy_result
                    }
                except Exception as commit_error:
                    logger.error(f"Commit failed in early-return: {commit_error}")
                    db.session.rollback()
                    return {
                        'success': False,
                        'error': f"Commit failed: {str(commit_error)}",
                        'stats': self.refresh_stats
                    }
            
            # Apply appointment prioritization dormancy after processing
            dormancy_result = self._apply_appointment_prioritization_dormancy(manually_refreshed_patient_ids)
            self.refresh_stats['dormancy_result'] = dormancy_result
            self.refresh_stats['end_time'] = datetime.utcnow()
            
            # Log successful completion before commit so it's included in the transaction
            self._log_refresh_event('screening_refresh_completed', {
                'organization_id': self.organization_id,
                'stats': self.refresh_stats,
                'duration_seconds': (self.refresh_stats['end_time'] - self.refresh_stats['start_time']).total_seconds()
            })
            
            # Commit with rollback on failure to ensure clean session state
            try:
                db.session.commit()
            except Exception as commit_error:
                logger.error(f"Commit failed in success path: {commit_error}")
                db.session.rollback()
                raise  # Re-raise to trigger error handling
            
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
            
            # Log error in a new transaction after rollback
            try:
                self._log_refresh_event('screening_refresh_error', {
                    'organization_id': self.organization_id,
                    'error': str(e),
                    'stats': self.refresh_stats
                })
                db.session.commit()  # Commit the error log
            except Exception as log_error:
                logger.error(f"Failed to log refresh error: {log_error}")
                db.session.rollback()  # Ensure clean session state
            
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
            
            # Manual patient refresh always needs to run to update is_dormant and last_processed
            # This ensures manually refreshed patients become active for the day
            if refresh_options.get('patient_filter', {}).get('patient_ids'):
                changes['needs_refresh'] = True
                changes['manual_patient_refresh'] = True
                logger.info(f"Manual patient refresh requested for {len(refresh_options['patient_filter']['patient_ids'])} patient(s)")
            
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
        
        # If force refresh, check for specific screening types first
        if refresh_options.get('force_refresh', False):
            specific_types = refresh_options.get('specific_screening_types', [])
            
            if specific_types:
                # OPTIMIZATION: When specific_screening_types is set, only get patients 
                # who might be affected by those types (have existing screenings OR are potentially eligible)
                # This avoids checking ALL patients for a single toggle-status operation
                
                # Get patients with existing screenings for these types
                existing_patient_ids = db.session.query(Screening.patient_id).filter(
                    Screening.org_id == self.organization_id,
                    Screening.screening_type_id.in_(specific_types)
                ).distinct().all()
                affected_patient_ids.update([pid[0] for pid in existing_patient_ids])
                
                # Also get patients who could be eligible based on screening type criteria
                # This is a heuristic: check patients matching gender/age range
                screening_types = ScreeningType.query.filter(
                    ScreeningType.id.in_(specific_types),
                    ScreeningType.org_id == self.organization_id
                ).all()
                
                for st in screening_types:
                    eligible_query = db.session.query(Patient.id).filter(
                        Patient.org_id == self.organization_id
                    )
                    
                    # Apply gender filter if specified (eligible_genders: 'M', 'F', or 'both')
                    if st.eligible_genders and st.eligible_genders.upper() not in ['BOTH', 'ALL', 'ANY', '']:
                        eligible_query = eligible_query.filter(
                            Patient.gender.ilike(st.eligible_genders[:1])  # 'M' or 'F'
                        )
                    
                    # Apply age range filter if specified (use date_of_birth field)
                    from datetime import date
                    today = date.today()
                    if st.min_age:
                        max_dob = date(today.year - st.min_age, today.month, today.day)
                        eligible_query = eligible_query.filter(Patient.date_of_birth <= max_dob)
                    if st.max_age:
                        min_dob = date(today.year - st.max_age - 1, today.month, today.day)
                        eligible_query = eligible_query.filter(Patient.date_of_birth >= min_dob)
                    
                    eligible_ids = eligible_query.distinct().all()
                    affected_patient_ids.update([pid[0] for pid in eligible_ids])
                
                logger.info(f"Force refresh with specific_screening_types: {len(affected_patient_ids)} potentially affected patients")
            else:
                # No specific types - get all patients for full refresh
                all_patient_ids = db.session.query(Patient.id).filter(
                    Patient.org_id == self.organization_id
                ).all()
                
                affected_patient_ids.update([pid[0] for pid in all_patient_ids])
        
        # Handle patient filter - behavior depends on whether this is a manual refresh
        if refresh_options.get('patient_filter'):
            patient_filter = refresh_options['patient_filter']
            if patient_filter.get('patient_ids'):
                specified_patient_ids = set(patient_filter['patient_ids'])
                
                if changes_detected.get('manual_patient_refresh'):
                    # For manual patient refresh, INCLUDE the specified patients
                    # (they may have no other detected changes but still need reactivation)
                    affected_patient_ids.update(specified_patient_ids)
                    logger.info(f"Manual refresh: including {len(specified_patient_ids)} specified patient(s)")
                elif affected_patient_ids:
                    # For filtered refresh, intersect with specified patient IDs
                    affected_patient_ids = affected_patient_ids.intersection(specified_patient_ids)
        
        # Get actual patient objects with eager loading to prevent N+1 queries
        if not affected_patient_ids:
            return []
        
        from sqlalchemy.orm import selectinload
        
        patients = Patient.query.filter(
            Patient.id.in_(affected_patient_ids),
            Patient.org_id == self.organization_id
        ).options(
            selectinload(Patient.documents),
            selectinload(Patient.fhir_documents),
            selectinload(Patient.conditions)
        ).limit(refresh_options.get('max_patients', 1000)).all()
        
        return patients
    
    def _refresh_patient_screenings(self, patient: Patient, changes_detected: Dict, 
                                   refresh_options: Dict, screening_types: List[ScreeningType] = None) -> int:
        """Refresh screenings for a single patient - NO Epic calls
        
        Args:
            patient: Patient to refresh
            changes_detected: Dict of detected changes
            refresh_options: Refresh configuration options
            screening_types: Pre-fetched screening types (avoids per-patient query)
        """
        updates_count = 0
        
        try:
            logger.debug(f"Refreshing screenings for patient {patient.id} (LOCAL PROCESSING ONLY)")
            
            # Use pre-fetched screening types if provided, otherwise query
            if screening_types is None:
                screening_types = ScreeningType.query.filter_by(
                    org_id=self.organization_id,
                    is_active=True
                ).all()
            
            # OPTIMIZATION: Filter to specific screening types if specified
            specific_types = refresh_options.get('specific_screening_types', [])
            if specific_types:
                screening_types = [st for st in screening_types if st.id in specific_types]
            
            for screening_type in screening_types:
                try:
                    # Check if this SPECIFIC screening type was modified (not just force refresh)
                    screening_type_modified = (
                        changes_detected['screening_types_modified'] and 
                        screening_type.id in changes_detected['screening_types_modified']
                    )
                    
                    # Manual patient refresh processes ALL screenings to update is_dormant and last_processed
                    is_manual_patient_refresh = changes_detected.get('manual_patient_refresh', False)
                    
                    # Check if screening type is affected by changes OR force refresh OR manual patient refresh
                    screening_affected = (
                        screening_type_modified or 
                        refresh_options.get('force_refresh', False) or
                        is_manual_patient_refresh
                    )
                    
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
                            now_utc = datetime.utcnow()
                            screening = Screening(
                                patient_id=patient.id,
                                screening_type_id=screening_type.id,
                                org_id=self.organization_id,
                                status='due',
                                last_processed=now_utc,  # Set initial processed timestamp
                                created_at=now_utc,
                                updated_at=now_utc
                            )
                            db.session.add(screening)
                            db.session.flush()
                            screening_created = True
                            logger.info(f"Created NEW screening {screening.id} for patient {patient.id}, type {screening_type.name}")
                            
                            # DETERMINISTIC VARIANT SELECTION: Archive other variant screenings for this family
                            # When a more specific variant is created, remove screenings for other variants
                            base_name = screening_type.base_name
                            self._archive_other_variant_screenings(patient.id, screening_type.id, base_name)
                        
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
                                
                                # Comprehensive cleanup of all related records
                                from models import DismissedDocumentMatch
                                
                                # Disable autoflush to prevent cascade update before we delete related records
                                with db.session.no_autoflush:
                                    # 1. Delete ScreeningDocumentMatch records (local documents)
                                    ScreeningDocumentMatch.query.filter_by(screening_id=existing_screening.id).delete(synchronize_session='fetch')
                                    
                                    # 2. Delete DismissedDocumentMatch records (both local and FHIR)
                                    DismissedDocumentMatch.query.filter_by(screening_id=existing_screening.id).delete(synchronize_session='fetch')
                                    
                                    # 3. Remove FHIR document associations (many-to-many)
                                    existing_screening.fhir_documents.clear()
                                
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
    
    def _archive_other_variant_screenings(self, patient_id: int, current_type_id: int, base_name: str) -> int:
        """Archive screenings for other variants when a more specific variant is selected
        
        This ensures deterministic variant selection: only ONE screening per variant family per patient.
        When a new/more specific variant screening is created, this removes screenings for other variants.
        
        Args:
            patient_id: The patient ID
            current_type_id: The screening type ID of the newly created/selected screening
            base_name: The base name of the screening type family
            
        Returns:
            Number of screenings archived
        """
        from models import DismissedDocumentMatch
        
        archived_count = 0
        
        try:
            # Find all screening types in this variant family (excluding current)
            variant_types = ScreeningType.query.filter(
                ScreeningType.org_id == self.organization_id,
                ScreeningType.id != current_type_id
            ).all()
            
            # Filter to only types that share the same base_name
            sibling_type_ids = [
                st.id for st in variant_types 
                if st.base_name == base_name
            ]
            
            if not sibling_type_ids:
                return 0
            
            # Find and archive screenings for sibling variants
            # IMPORTANT: Only archive non-completed screenings to preserve historical records
            sibling_screenings = Screening.query.filter(
                Screening.patient_id == patient_id,
                Screening.screening_type_id.in_(sibling_type_ids),
                Screening.status != 'complete'  # Preserve completed/historical screenings
            ).all()
            
            for sibling in sibling_screenings:
                sibling_type = sibling.screening_type
                
                # Log audit trail for archiving
                logger.info(
                    f"VARIANT ARCHIVE: Screening {sibling.id} ({sibling_type.name}, status={sibling.status}) "
                    f"for patient {patient_id} superseded by variant type {current_type_id} "
                    f"(base_name='{base_name}', org_id={self.organization_id})"
                )
                
                # Comprehensive cleanup of all related records
                with db.session.no_autoflush:
                    # 1. Delete ScreeningDocumentMatch records (local documents)
                    ScreeningDocumentMatch.query.filter_by(screening_id=sibling.id).delete(synchronize_session='fetch')
                    
                    # 2. Delete DismissedDocumentMatch records (both local and FHIR)
                    DismissedDocumentMatch.query.filter_by(screening_id=sibling.id).delete(synchronize_session='fetch')
                    
                    # 3. Remove FHIR document associations (many-to-many)
                    sibling.fhir_documents.clear()
                
                # Delete the superseded screening
                db.session.delete(sibling)
                archived_count += 1
            
            if archived_count > 0:
                db.session.flush()
                logger.info(f"Archived {archived_count} superseded variant screening(s) for patient {patient_id}, base_name '{base_name}'")
                
        except Exception as e:
            logger.error(f"Error archiving variant screenings for patient {patient_id}: {str(e)}")
            
        return archived_count
    
    def _find_fhir_document_matches(self, screening: Screening) -> List[Dict]:
        """
        Find FHIR documents that match this screening's keywords
        Similar to DocumentMatcher but for Epic FHIR documents
        
        CRITICAL FIX: Uses word boundary regex matching to prevent false positives
        (e.g., "flu" won't match "fluent" or "influence")
        """
        import re
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
                
                # Check if document text contains screening keywords using word boundary matching
                # This prevents false positives like "flu" matching "fluent"
                matched = False
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
                    if re.search(pattern, doc.ocr_text, re.IGNORECASE):
                        logger.debug(f"FHIR document {doc.id} matched keyword: '{keyword}'")
                        matched = True
                        break
                
                if matched:
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
        Update screening status based on existing documents/immunizations with current criteria
        NO Epic calls - processes existing local documents, FHIR documents, AND immunizations
        Automatically excludes dismissed matches via DocumentMatcher
        
        Returns True if:
        - Status changed
        - Completion date changed
        - Document matches were added or removed (even if status unchanged)
        """
        try:
            screening_type = screening.screening_type
            
            # Check if this is an immunization-based screening type
            if screening_type.is_immunization_based:
                return self._update_immunization_based_screening(screening)
            
            # Track if any matches changed (for force_refresh to report work done)
            matches_changed = False
            
            # Standard document-based screening matching
            # Find matching LOCAL documents (already excludes dismissed matches)
            matches = self.matcher.find_screening_matches(screening, exclude_dismissed=True)
            
            # Clean up stale matches and save current matches to database for UI display
            from models import ScreeningDocumentMatch
            import json
            
            # Get current matching document IDs
            current_match_doc_ids = {match['document'].id for match in matches}
            
            # Delete stale ScreeningDocumentMatch records (documents that no longer match)
            stale_matches = ScreeningDocumentMatch.query.filter(
                ScreeningDocumentMatch.screening_id == screening.id,
                ~ScreeningDocumentMatch.document_id.in_(current_match_doc_ids) if current_match_doc_ids else True
            ).all()
            
            if stale_matches:
                for stale_match in stale_matches:
                    logger.debug(f"Removing stale ScreeningDocumentMatch: Screening {screening.id} -> Doc {stale_match.document_id}")
                    db.session.delete(stale_match)
                matches_changed = True
            
            # Create or update current matches
            for match in matches:
                # Check if match already exists
                existing_match = ScreeningDocumentMatch.query.filter_by(
                    screening_id=screening.id,
                    document_id=match['document'].id
                ).first()
                
                if not existing_match:
                    # Create new match record
                    new_match = ScreeningDocumentMatch(
                        screening_id=screening.id,
                        document_id=match['document'].id,
                        match_confidence=match.get('confidence', 1.0),
                        matched_keywords=json.dumps(match.get('matched_keywords', []))
                    )
                    db.session.add(new_match)
                    logger.debug(f"Created ScreeningDocumentMatch: Screening {screening.id} -> Doc {match['document'].id}")
                    matches_changed = True
                else:
                    # Update existing match if confidence changed
                    if existing_match.match_confidence != match.get('confidence', 1.0):
                        existing_match.match_confidence = match.get('confidence', 1.0)
                        existing_match.matched_keywords = json.dumps(match.get('matched_keywords', []))
                        matches_changed = True
            
            # ALSO find matching FHIR documents (from Epic) and filter dismissed
            fhir_matches = self._find_fhir_document_matches_filtered(screening)
            
            # Clean up stale FHIR document associations and link current matches
            current_fhir_doc_ids = {fhir_match['document'].id for fhir_match in fhir_matches}
            
            # Remove FHIR documents that no longer match
            stale_fhir_docs = [doc for doc in screening.fhir_documents if doc.id not in current_fhir_doc_ids]
            for stale_doc in stale_fhir_docs:
                logger.debug(f"Removing stale FHIR document link: Screening {screening.id} -> FHIRDoc {stale_doc.id}")
                screening.fhir_documents.remove(stale_doc)
                matches_changed = True
            
            # Link current FHIR documents to screening for UI display (many-to-many relationship)
            for fhir_match in fhir_matches:
                fhir_doc = fhir_match['document']
                if fhir_doc not in screening.fhir_documents:
                    screening.fhir_documents.append(fhir_doc)
                    matches_changed = True
            
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
                
                now_utc = datetime.utcnow()
                
                if status_changed or date_changed:
                    old_status = screening.status
                    screening.status = new_status
                    screening.last_completed = document_date
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    
                    logger.debug(f"Screening {screening.id}: {old_status} -> {new_status}, completed: {document_date}")
                    return True
                
                # Even if status unchanged, report update if matches were modified
                # This ensures force_refresh reports work done when re-evaluating matches
                if matches_changed:
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    logger.debug(f"Screening {screening.id}: matches updated (status unchanged: {screening.status})")
                    return True
            
            else:
                # No matching documents found - should be 'due'
                now_utc = datetime.utcnow()
                
                if screening.status != 'due':
                    old_status = screening.status
                    screening.status = 'due'
                    screening.last_completed = None
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    
                    logger.debug(f"Screening {screening.id}: {old_status} -> due (no matches)")
                    return True
                
                # Report update if matches were removed (now showing as 'due')
                if matches_changed:
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    logger.debug(f"Screening {screening.id}: matches removed (status remains due)")
                    return True
            
            # Even if nothing changed, update last_processed to indicate screening was evaluated
            # This clears the stale indicator and reactivates the screening for today's processing
            screening.last_processed = datetime.utcnow()
            screening.is_dormant = False
            return False
            
        except Exception as e:
            logger.error(f"Error updating screening {screening.id}: {str(e)}")
            return False
    
    def _update_immunization_based_screening(self, screening: Screening) -> bool:
        """
        Update immunization-based screening status using FHIRImmunization records
        Links matching immunizations to the screening for UI display
        
        Returns True if status changed OR immunization matches were added/removed
        """
        try:
            screening_type = screening.screening_type
            matches_changed = False
            
            # Query FHIRImmunization records for the patient
            patient_immunizations = FHIRImmunization.query.filter_by(
                patient_id=screening.patient_id,
                status='completed'
            ).order_by(FHIRImmunization.administration_date.desc()).all()
            
            # Find immunizations that match the screening type's criteria
            matching_immunizations = []
            for imm in patient_immunizations:
                if imm.matches_screening_type(screening_type):
                    matching_immunizations.append(imm)
                    logger.debug(f"Matched immunization {imm.vaccine_name} (CVX:{imm.cvx_code}) dated {imm.administration_date} for screening {screening_type.name}")
            
            # Clean up stale immunization links and add current matches
            current_imm_ids = {imm.id for imm in matching_immunizations}
            
            # Remove immunizations that no longer match
            stale_immunizations = [imm for imm in screening.immunizations if imm.id not in current_imm_ids]
            for stale_imm in stale_immunizations:
                logger.debug(f"Removing stale immunization link: Screening {screening.id} -> Imm {stale_imm.id}")
                screening.immunizations.remove(stale_imm)
                matches_changed = True
            
            # Link current immunizations to screening for UI display
            for imm in matching_immunizations:
                if imm not in screening.immunizations:
                    screening.immunizations.append(imm)
                    logger.debug(f"Linked immunization {imm.id} ({imm.vaccine_name}) to screening {screening.id}")
                    matches_changed = True
            
            if matching_immunizations:
                # Get the most recent matching immunization
                latest_imm = matching_immunizations[0]  # Already sorted by date desc
                imm_date = latest_imm.administration_date
                
                # Ensure we're using a date object
                if imm_date and hasattr(imm_date, 'date'):
                    imm_date = imm_date.date()
                
                # Calculate new status using current criteria
                new_status = self.criteria.calculate_screening_status(
                    screening_type,
                    imm_date
                )
                
                # Update if status changed or we have a newer completion date
                status_changed = new_status != screening.status
                date_changed = (screening.last_completed is None or 
                              (imm_date and imm_date > screening.last_completed))
                
                now_utc = datetime.utcnow()
                
                if status_changed or date_changed:
                    old_status = screening.status
                    screening.status = new_status
                    screening.last_completed = imm_date
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    
                    logger.info(f"Immunization screening {screening.id} ({screening_type.name}): {old_status} -> {new_status}, completed: {imm_date}, matched {len(matching_immunizations)} immunization(s)")
                    return True
                
                # Even if status unchanged, report update if matches were modified
                if matches_changed:
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    logger.debug(f"Immunization screening {screening.id}: matches updated (status unchanged: {screening.status})")
                    return True
            else:
                # No matching immunizations found - should be 'due'
                # Also clear any stale immunization links
                if screening.immunizations:
                    screening.immunizations.clear()
                    matches_changed = True
                
                now_utc = datetime.utcnow()
                
                if screening.status != 'due':
                    old_status = screening.status
                    screening.status = 'due'
                    screening.last_completed = None
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    
                    logger.debug(f"Immunization screening {screening.id}: {old_status} -> due (no matching immunizations)")
                    return True
                
                # Report update if matches were removed
                if matches_changed:
                    screening.updated_at = now_utc
                    screening.last_processed = now_utc  # Clear stale indicator
                    screening.is_dormant = False  # Reactivate for day's processing
                    logger.debug(f"Immunization screening {screening.id}: immunization links cleared (status remains due)")
                    return True
            
            # Even if nothing changed, update last_processed to indicate screening was evaluated
            # This clears the stale indicator and reactivates the screening for today's processing
            screening.last_processed = datetime.utcnow()
            screening.is_dormant = False
            return False
            
        except Exception as e:
            logger.error(f"Error updating immunization screening {screening.id}: {str(e)}")
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
            # Don't commit or flush here - let the caller's commit include this log entry
            # This ensures atomic transaction handling across all paths
            
        except Exception as e:
            logger.error(f"Error logging refresh event: {str(e)}")
    
    def _apply_appointment_prioritization_dormancy(self, manually_refreshed_patient_ids: Optional[Set[int]] = None) -> Dict[str, Any]:
        """
        Apply appointment prioritization dormancy rules to screenings.
        
        This method checks the organization's appointment prioritization settings
        and marks screenings as dormant/active based on whether patients have
        upcoming appointments.
        
        Args:
            manually_refreshed_patient_ids: Optional set of patient IDs that were manually
                refreshed in this cycle. These patients will be exempted from dormancy
                marking so they remain active for the rest of the day.
        
        Returns:
            Dict with dormancy application results
        """
        result = {
            'applied': False,
            'priority_patients_activated': 0,
            'non_scheduled_marked_dormant': 0,
            'stale_patients_reactivated': 0,
            'setting_enabled': False,
            'process_non_scheduled': False,
            'manually_refreshed_exempted': 0
        }
        
        if manually_refreshed_patient_ids is None:
            manually_refreshed_patient_ids = set()
        
        try:
            # Get organization settings
            organization = Organization.query.get(self.organization_id)
            if not organization:
                logger.warning(f"Organization {self.organization_id} not found for dormancy check")
                return result
            
            # Check if appointment prioritization is enabled
            if not organization.appointment_based_prioritization:
                logger.info("Appointment prioritization is disabled - skipping dormancy logic")
                return result
            
            result['setting_enabled'] = True
            result['process_non_scheduled'] = organization.process_non_scheduled_patients
            
            # Get priority patients (those with upcoming appointments)
            from services.appointment_prioritization import AppointmentBasedPrioritization
            prioritization_service = AppointmentBasedPrioritization(self.organization_id)
            priority_patient_ids = set(prioritization_service.get_priority_patients())
            
            logger.info(f"Found {len(priority_patient_ids)} priority patients with upcoming appointments")
            
            # Mark priority patients as NOT dormant (active)
            if priority_patient_ids:
                active_count = Screening.query.filter(
                    Screening.org_id == self.organization_id,
                    Screening.patient_id.in_(priority_patient_ids),
                    Screening.is_dormant == True
                ).update({'is_dormant': False, 'last_processed': datetime.utcnow()}, synchronize_session=False)
                
                result['priority_patients_activated'] = active_count
                if active_count > 0:
                    logger.info(f"Reactivated {active_count} screenings for priority patients")
            
            # Get non-scheduled patients
            non_scheduled_ids = prioritization_service.get_non_scheduled_patients(
                exclude_patient_ids=list(priority_patient_ids)
            )
            
            if organization.process_non_scheduled_patients:
                # When enabled, keep ALL non-scheduled patients active (not dormant)
                # This ensures their screenings continue to be processed
                logger.info("Processing non-scheduled patients (process_non_scheduled_patients is enabled)")
                
                if non_scheduled_ids:
                    # Reactivate any dormant non-scheduled patients
                    reactivate_count = Screening.query.filter(
                        Screening.org_id == self.organization_id,
                        Screening.patient_id.in_(non_scheduled_ids),
                        Screening.is_dormant == True
                    ).update({'is_dormant': False, 'last_processed': datetime.utcnow()}, synchronize_session=False)
                    
                    if reactivate_count > 0:
                        result['non_scheduled_reactivated'] = reactivate_count
                        logger.info(f"Reactivated {reactivate_count} screenings for non-scheduled patients (setting enabled)")
                    else:
                        logger.info(f"All {len(non_scheduled_ids)} non-scheduled patients already active")
                
                # Do NOT mark any non-scheduled patients as dormant when setting is enabled
                result['non_scheduled_marked_dormant'] = 0
            else:
                # Mark non-scheduled patients as dormant when disabled,
                # EXCEPT for:
                # 1. Manually refreshed patients in this cycle (via manually_refreshed_patient_ids)
                # 2. Patients whose screenings were refreshed today (via last_processed check)
                patients_to_mark_dormant = set(non_scheduled_ids) - manually_refreshed_patient_ids
                
                if manually_refreshed_patient_ids:
                    exempted_count = len(set(non_scheduled_ids) & manually_refreshed_patient_ids)
                    result['manually_refreshed_exempted'] = exempted_count
                    if exempted_count > 0:
                        logger.info(f"Exempting {exempted_count} manually refreshed patients from dormancy marking")
                
                logger.info(f"Marking {len(patients_to_mark_dormant)} non-scheduled patients as dormant (process_non_scheduled_patients is disabled)")
                
                if patients_to_mark_dormant:
                    # Only mark as dormant if last_processed is older than today (local midnight)
                    # This respects the "active for the day" semantic after manual refresh
                    # Uses organization's timezone for proper day-boundary rollover
                    from utils.date_helpers import get_local_midnight_utc
                    org_timezone = organization.timezone if organization else 'UTC'
                    today_start = get_local_midnight_utc(org_timezone)
                    
                    dormant_count = Screening.query.filter(
                        Screening.org_id == self.organization_id,
                        Screening.patient_id.in_(patients_to_mark_dormant),
                        Screening.is_dormant == False,
                        or_(
                            Screening.last_processed.is_(None),
                            Screening.last_processed < today_start
                        )
                    ).update({'is_dormant': True}, synchronize_session=False)
                    
                    result['non_scheduled_marked_dormant'] = dormant_count
                    if dormant_count > 0:
                        logger.info(f"Marked {dormant_count} screenings as dormant for non-scheduled patients (excluding today's refreshes)")
            
            result['applied'] = True
            logger.info(f"Appointment prioritization dormancy applied: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error applying appointment prioritization dormancy: {str(e)}")
            result['error'] = str(e)
            return result
    
    def _get_default_refresh_options(self) -> Dict:
        """Get default refresh options"""
        return {
            'max_patients': 10000,  # Higher limit since no network calls
            'force_refresh': False,
            'check_eligibility': True,
            'update_statuses': True
        }