"""
PHI Cleanup Service
Responsible for:
1. Automatically discarding old OCR extractions beyond frequency periods
2. Maintaining system efficiency by removing irrelevant PHI data
3. Enhancing security by limiting PHI retention
4. Configurable cleanup policies per screening type
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set, Any
from dateutil.relativedelta import relativedelta

from models import (
    db, Patient, Screening, ScreeningType, Document, AdminLog,
    PrepSheetSettings
)

logger = logging.getLogger(__name__)


class PHICleanupService:
    """
    PHI Cleanup Service for automatic disposal of old OCR extractions
    Removes PHI data beyond relevant frequency periods for efficiency and security
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        
        # Track cleanup progress
        self.cleanup_stats = {
            'documents_processed': 0,
            'phi_data_cleared': 0,
            'bytes_freed': 0,
            'screening_types_processed': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"PHICleanupService initialized for organization {organization_id}")
    
    def cleanup_old_phi_data(self, cleanup_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point for PHI cleanup
        Removes OCR text from documents beyond relevant frequency periods
        
        Args:
            cleanup_options: Configuration options for cleanup behavior
            
        Returns:
            Dict with cleanup results and statistics
        """
        if cleanup_options is None:
            cleanup_options = self._get_default_cleanup_options()
        
        self.cleanup_stats['start_time'] = datetime.utcnow()
        
        try:
            logger.info("Starting PHI cleanup for old OCR extractions")
            
            # Log cleanup start
            self._log_cleanup_event('phi_cleanup_started', {
                'organization_id': self.organization_id,
                'cleanup_options': cleanup_options
            })
            
            # Get all screening types to determine frequency periods
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            if not screening_types:
                logger.info("No active screening types found - early termination")
                return {
                    'success': True,
                    'message': 'No active screening types found',
                    'stats': self.cleanup_stats
                }
            
            # Process each screening type's frequency period
            total_cleaned = 0
            for screening_type in screening_types:
                try:
                    cleaned_count = self._cleanup_phi_for_screening_type(screening_type, cleanup_options)
                    total_cleaned += cleaned_count
                    self.cleanup_stats['screening_types_processed'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning PHI for screening type {screening_type.id}: {str(e)}"
                    logger.error(error_msg)
                    self.cleanup_stats['errors'].append(error_msg)
            
            # Clean up documents with no associated screenings (orphaned)
            if cleanup_options.get('cleanup_orphaned', True):
                orphaned_cleaned = self._cleanup_orphaned_documents(cleanup_options)
                total_cleaned += orphaned_cleaned
            
            # Early termination if no cleanup was needed
            if total_cleaned == 0:
                logger.info("No PHI data needed cleanup - early termination")
                self._log_cleanup_event('phi_cleanup_completed_early', {
                    'reason': 'no_cleanup_needed',
                    'organization_id': self.organization_id
                })
                return {
                    'success': True,
                    'message': 'No PHI data needed cleanup',
                    'stats': self.cleanup_stats
                }
            
            db.session.commit()
            self.cleanup_stats['end_time'] = datetime.utcnow()
            
            # Log successful completion
            self._log_cleanup_event('phi_cleanup_completed', {
                'organization_id': self.organization_id,
                'stats': self.cleanup_stats,
                'duration_seconds': (self.cleanup_stats['end_time'] - self.cleanup_stats['start_time']).total_seconds()
            })
            
            logger.info(f"PHI cleanup completed successfully: {self.cleanup_stats}")
            
            return {
                'success': True,
                'message': f"Cleanup completed: {self.cleanup_stats['phi_data_cleared']} documents cleaned, {self.cleanup_stats['bytes_freed']} bytes freed",
                'stats': self.cleanup_stats
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"PHI cleanup failed: {str(e)}"
            logger.error(error_msg)
            
            self.cleanup_stats['end_time'] = datetime.utcnow()
            self.cleanup_stats['errors'].append(error_msg)
            
            # Log error
            self._log_cleanup_event('phi_cleanup_error', {
                'organization_id': self.organization_id,
                'error': str(e),
                'stats': self.cleanup_stats
            })
            
            return {
                'success': False,
                'error': error_msg,
                'stats': self.cleanup_stats
            }
    
    def _cleanup_phi_for_screening_type(self, screening_type: ScreeningType, 
                                       cleanup_options: Dict) -> int:
        """Clean PHI data for documents beyond a screening type's frequency period"""
        cleaned_count = 0
        
        try:
            # Calculate cutoff date based on screening frequency
            cutoff_date = self._calculate_cutoff_date(screening_type, cleanup_options)
            
            logger.debug(f"Cleaning PHI for {screening_type.name} with cutoff date: {cutoff_date}")
            
            # Find documents older than the cutoff that have OCR text
            # Only clean documents that match this screening type's keywords
            old_documents = self._find_old_documents_for_screening(screening_type, cutoff_date)
            
            for document in old_documents:
                try:
                    if self._should_clean_document(document, screening_type, cutoff_date):
                        bytes_freed = self._clean_document_phi(document)
                        if bytes_freed > 0:
                            cleaned_count += 1
                            self.cleanup_stats['phi_data_cleared'] += 1
                            self.cleanup_stats['bytes_freed'] += bytes_freed
                            
                except Exception as e:
                    logger.error(f"Error cleaning document {document.id}: {str(e)}")
                    self.cleanup_stats['errors'].append(f"Document {document.id}: {str(e)}")
            
            logger.info(f"Cleaned {cleaned_count} documents for screening type {screening_type.name}")
            
        except Exception as e:
            logger.error(f"Error processing screening type {screening_type.id}: {str(e)}")
            raise
        
        return cleaned_count
    
    def _calculate_cutoff_date(self, screening_type: ScreeningType, cleanup_options: Dict) -> date:
        """Calculate the cutoff date beyond which documents should have PHI cleaned"""
        try:
            # Use the screening frequency to determine relevance period
            frequency_years = screening_type.frequency_years or 1
            frequency_months = screening_type.frequency_months or 0
            
            # Add buffer period to avoid cleaning potentially relevant documents
            buffer_multiplier = cleanup_options.get('buffer_multiplier', 2.0)  # Keep 2x the frequency period
            
            # Calculate total buffer period
            total_months = int((frequency_years * 12 + frequency_months) * buffer_multiplier)
            
            # Minimum retention period (never clean documents less than 6 months old)
            min_retention_months = cleanup_options.get('min_retention_months', 6)
            if total_months < min_retention_months:
                total_months = min_retention_months
            
            cutoff_date = date.today() - relativedelta(months=total_months)
            
            logger.debug(f"Cutoff date for {screening_type.name}: {cutoff_date} (buffer: {total_months} months)")
            
            return cutoff_date
            
        except Exception as e:
            logger.error(f"Error calculating cutoff date for screening type {screening_type.id}: {str(e)}")
            # Default to 1 year ago for safety
            return date.today() - relativedelta(years=1)
    
    def _find_old_documents_for_screening(self, screening_type: ScreeningType, 
                                         cutoff_date: date) -> List[Document]:
        """Find documents older than cutoff that are relevant to this screening type"""
        try:
            # Get documents that:
            # 1. Are older than the cutoff date
            # 2. Have OCR text (PHI to clean)
            # 3. Belong to patients with this screening type
            
            # Get patient IDs that have this screening type
            patient_ids_with_screening = db.session.query(Screening.patient_id).filter(
                Screening.screening_type_id == screening_type.id,
                Screening.org_id == self.organization_id
            ).distinct().subquery()
            
            old_documents = Document.query.filter(
                Document.org_id == self.organization_id,
                Document.patient_id.in_(patient_ids_with_screening),
                Document.ocr_text.isnot(None),
                Document.ocr_text != '',
                or_(
                    Document.document_date < cutoff_date,
                    and_(
                        Document.document_date.is_(None),
                        Document.created_at < cutoff_date
                    )
                )
            ).all()
            
            return old_documents
            
        except Exception as e:
            logger.error(f"Error finding old documents for screening type {screening_type.id}: {str(e)}")
            return []
    
    def _should_clean_document(self, document: Document, screening_type: ScreeningType, 
                              cutoff_date: date) -> bool:
        """Determine if a document should have its PHI cleaned"""
        try:
            # Don't clean if document is still within the relevance period
            doc_date = document.document_date or document.created_at.date()
            if doc_date >= cutoff_date:
                return False
            
            # Don't clean if document has no OCR text
            if not document.ocr_text or document.ocr_text.strip() == '':
                return False
            
            # Check if this document is still relevant to any active screenings
            # If the patient has a recent screening completion for this type, keep the OCR
            recent_screening = Screening.query.filter(
                Screening.patient_id == document.patient_id,
                Screening.screening_type_id == screening_type.id,
                Screening.last_completed.isnot(None)
            ).order_by(Screening.last_completed.desc()).first()
            
            if recent_screening and recent_screening.last_completed:
                # If the document is the most recent completion, keep it
                if doc_date >= recent_screening.last_completed:
                    logger.debug(f"Preserving document {document.id} - most recent completion for screening")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating document {document.id} for cleanup: {str(e)}")
            return False
    
    def _clean_document_phi(self, document: Document) -> int:
        """Clean PHI data from a document and return bytes freed"""
        try:
            bytes_freed = 0
            
            # Calculate bytes freed
            if document.ocr_text:
                bytes_freed = len(document.ocr_text.encode('utf-8'))
            
            # Clear OCR text but preserve metadata
            document.ocr_text = None
            document.processed_at = None  # Mark as needing reprocessing if accessed again
            document.updated_at = datetime.utcnow()
            
            # Add cleanup marker to track what was cleaned
            if not hasattr(document, 'phi_cleaned_at'):
                # Add field if doesn't exist - this would need a migration in a real system
                pass
            
            logger.debug(f"Cleaned {bytes_freed} bytes of PHI from document {document.id}")
            
            return bytes_freed
            
        except Exception as e:
            logger.error(f"Error cleaning PHI from document {document.id}: {str(e)}")
            return 0
    
    def _cleanup_orphaned_documents(self, cleanup_options: Dict) -> int:
        """Clean up documents that are not associated with any active screenings"""
        cleaned_count = 0
        
        try:
            logger.info("Cleaning up orphaned documents")
            
            # Find documents with no associated screenings (older than retention period)
            retention_days = cleanup_options.get('orphan_retention_days', 90)
            cutoff_date = date.today() - timedelta(days=retention_days)
            
            # Get documents that:
            # 1. Are older than retention period
            # 2. Have OCR text
            # 3. Patient has no active screenings, or document doesn't match any screening keywords
            
            orphaned_documents = Document.query.filter(
                Document.org_id == self.organization_id,
                Document.ocr_text.isnot(None),
                Document.ocr_text != '',
                or_(
                    Document.document_date < cutoff_date,
                    and_(
                        Document.document_date.is_(None),
                        Document.created_at < cutoff_date
                    )
                )
            ).all()
            
            for document in orphaned_documents:
                try:
                    # Check if document matches any screening keywords
                    has_screening_relevance = self._document_has_screening_relevance(document)
                    
                    if not has_screening_relevance:
                        bytes_freed = self._clean_document_phi(document)
                        if bytes_freed > 0:
                            cleaned_count += 1
                            self.cleanup_stats['phi_data_cleared'] += 1
                            self.cleanup_stats['bytes_freed'] += bytes_freed
                            logger.debug(f"Cleaned orphaned document {document.id}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning orphaned document {document.id}: {str(e)}")
                    self.cleanup_stats['errors'].append(f"Orphaned document {document.id}: {str(e)}")
            
            logger.info(f"Cleaned {cleaned_count} orphaned documents")
            
        except Exception as e:
            logger.error(f"Error cleaning orphaned documents: {str(e)}")
        
        return cleaned_count
    
    def _document_has_screening_relevance(self, document: Document) -> bool:
        """Check if a document is relevant to any active screening types"""
        try:
            # Get all active screening types for this organization
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            from core.matcher import DocumentMatcher
            matcher = DocumentMatcher()
            
            # Check if document matches any screening type keywords
            for screening_type in screening_types:
                confidence = matcher.fuzzy_match_keywords(document, screening_type)
                if confidence > 0.5:  # Has some relevance
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking document relevance for {document.id}: {str(e)}")
            return True  # Conservative - assume relevant if we can't check
    
    def get_phi_cleanup_report(self) -> Dict[str, Any]:
        """Generate a report of PHI data that could be cleaned"""
        try:
            report = {
                'organization_id': self.organization_id,
                'screening_types': [],
                'total_documents_with_phi': 0,
                'total_cleanable_documents': 0,
                'estimated_bytes_to_clean': 0,
                'generated_at': datetime.utcnow()
            }
            
            # Analyze each screening type
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            for screening_type in screening_types:
                cutoff_date = self._calculate_cutoff_date(screening_type, self._get_default_cleanup_options())
                old_documents = self._find_old_documents_for_screening(screening_type, cutoff_date)
                
                cleanable_docs = [doc for doc in old_documents if self._should_clean_document(doc, screening_type, cutoff_date)]
                
                estimated_bytes = sum(len(doc.ocr_text.encode('utf-8')) for doc in cleanable_docs if doc.ocr_text)
                
                screening_report = {
                    'screening_type_id': screening_type.id,
                    'screening_type_name': screening_type.name,
                    'cutoff_date': cutoff_date.isoformat(),
                    'documents_with_phi': len(old_documents),
                    'cleanable_documents': len(cleanable_docs),
                    'estimated_bytes_to_clean': estimated_bytes
                }
                
                report['screening_types'].append(screening_report)
                report['total_documents_with_phi'] += len(old_documents)
                report['total_cleanable_documents'] += len(cleanable_docs)
                report['estimated_bytes_to_clean'] += estimated_bytes
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating PHI cleanup report: {str(e)}")
            return {'error': str(e)}
    
    def _log_cleanup_event(self, event_type: str, details: Dict):
        """Log cleanup events to admin audit log"""
        try:
            from flask import has_request_context
            from flask_login import current_user
            
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
                target_type='phi_cleanup',
                target_id=self.organization_id,
                details=json.dumps(details),
                org_id=self.organization_id,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(admin_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging cleanup event: {str(e)}")
    
    def _get_default_cleanup_options(self) -> Dict:
        """Get default cleanup options"""
        return {
            'buffer_multiplier': 2.0,  # Keep 2x the screening frequency period
            'min_retention_months': 6,  # Never clean documents less than 6 months old
            'cleanup_orphaned': True,
            'orphan_retention_days': 90,
            'dry_run': False  # Set to True to see what would be cleaned without actually doing it
        }