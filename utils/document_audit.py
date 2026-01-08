"""
Document Processing Audit Logger
Provides structured HIPAA-compliant audit logging for document processing operations
Implements HITRUST CSF Domain 09 - Audit Logging requirements

This module ensures all document processing events are logged with:
- User context (who triggered processing)
- Document metadata (what was processed)
- Processing outcomes (success/failure, confidence scores)
- PHI detection events (what was found and redacted)
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from flask import has_request_context, request
from flask_login import current_user

logger = logging.getLogger(__name__)


class DocumentAuditLogger:
    """Structured audit logger for document processing operations"""
    
    EVENT_TYPES = {
        'document_processed': 'Document successfully processed',
        'document_processing_started': 'Document processing initiated',
        'document_processing_failed': 'Document processing failed',
        'ocr_completed': 'OCR text extraction completed',
        'ocr_failed': 'OCR text extraction failed',
        'ocr_timeout': 'OCR processing timed out',
        'phi_redacted': 'PHI detected and redacted',
        'phi_filter_applied': 'PHI filter applied to text',
        'phi_filter_failed': 'PHI filter encountered error',
        'file_secure_deleted': 'Original file securely deleted',
        'file_deletion_failed': 'Secure file deletion failed'
    }
    
    @staticmethod
    def get_request_context() -> Dict[str, Any]:
        """
        Extract user and request context for audit logging
        
        Returns:
            Dictionary with user_id, org_id, ip_address, session_id, user_agent
        """
        context: Dict[str, Any] = {
            'user_id': None,
            'org_id': None,
            'ip_address': None,
            'session_id': None,
            'user_agent': None
        }
        
        if has_request_context():
            forwarded = request.headers.get('X-Forwarded-For')
            context['ip_address'] = forwarded if forwarded else (request.remote_addr or 'unknown')
            user_agent = request.headers.get('User-Agent', '')
            context['user_agent'] = user_agent[:200] if user_agent else ''
            
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                context['user_id'] = current_user.id
                context['org_id'] = current_user.org_id
        
        return context
    
    @staticmethod
    def log_processing_started(
        document_id: int,
        document_type: str,
        org_id: int,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log that document processing has started"""
        from models import log_admin_event
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='document_processing_started',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details='Document processing initiated',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'started_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(f"Audit: Processing started for {document_type} {document_id}")
    
    @staticmethod
    def log_processing_completed(
        document_id: int,
        document_type: str,
        org_id: int,
        confidence: float,
        text_length: int,
        processing_method: str,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log successful document processing completion"""
        from models import log_admin_event
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='document_processed',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details=f'Document processed successfully with {processing_method}',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'confidence': round(confidence, 4),
                'text_length': text_length,
                'processing_method': processing_method,
                'completed_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Audit: Document {document_id} processed successfully (confidence: {confidence:.2f})")
    
    @staticmethod
    def log_processing_failed(
        document_id: int,
        document_type: str,
        org_id: int,
        error_message: str,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log document processing failure"""
        from models import log_admin_event
        from services.security_alerts import SecurityAlertService
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='document_processing_failed',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details=f'Document processing failed: {error_message[:100]}',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'error_message': error_message,
                'failed_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.warning(f"Audit: Document {document_id} processing failed: {error_message}")
    
    @staticmethod
    def log_ocr_completed(
        document_id: int,
        document_type: str,
        org_id: int,
        extraction_method: str,
        confidence: float,
        text_length: int,
        pages_processed: int = 1,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log OCR extraction completion"""
        from models import log_admin_event
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='ocr_completed',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details=f'OCR completed via {extraction_method}',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'extraction_method': extraction_method,
                'confidence': round(confidence, 4),
                'text_length': text_length,
                'pages_processed': pages_processed,
                'completed_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.debug(f"Audit: OCR completed for {document_id} via {extraction_method}")
    
    @staticmethod
    def log_phi_redacted(
        document_id: int,
        document_type: str,
        org_id: int,
        phi_types_found: Dict[str, int],
        original_length: int,
        filtered_length: int,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log PHI detection and redaction
        
        Args:
            phi_types_found: Dict mapping PHI type to count, e.g. {'ssn': 2, 'phone': 1}
        """
        from models import log_admin_event
        
        ctx = DocumentAuditLogger.get_request_context()
        
        total_redactions = sum(phi_types_found.values())
        
        log_admin_event(
            event_type='phi_redacted',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details=f'PHI filter applied: {total_redactions} items redacted',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'phi_types_found': phi_types_found,
                'total_redactions': total_redactions,
                'original_length': original_length,
                'filtered_length': filtered_length,
                'redacted_at': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Audit: PHI redacted from {document_id} - {total_redactions} items of types {list(phi_types_found.keys())}")
    
    @staticmethod
    def log_phi_filter_failed(
        document_id: int,
        document_type: str,
        org_id: int,
        error_message: str,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log PHI filter failure and trigger security alert"""
        from models import log_admin_event
        from services.security_alerts import SecurityAlertService
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='phi_filter_failed',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details=f'PHI filter failed: {error_message[:100]}',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'error_message': error_message,
                'failed_at': datetime.utcnow().isoformat()
            }
        )
        
        SecurityAlertService.send_phi_filter_failure_alert(
            org_id=org_id,
            document_id=document_id,
            document_type=document_type,
            error_message=error_message
        )
        
        logger.error(f"Audit: PHI filter failed for {document_id}: {error_message}")
    
    @staticmethod
    def log_file_secure_deleted(
        document_id: int,
        document_type: str,
        org_id: int,
        file_path_hash: str,
        patient_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log secure file deletion for HIPAA compliance"""
        from models import log_admin_event
        
        ctx = DocumentAuditLogger.get_request_context()
        
        log_admin_event(
            event_type='file_secure_deleted',
            user_id=user_id or ctx['user_id'],
            org_id=org_id,
            ip=ip_address or ctx['ip_address'],
            patient_id=patient_id,
            resource_type=document_type,
            resource_id=document_id,
            action_details='Original file securely deleted (3-pass overwrite)',
            session_id=ctx['session_id'],
            user_agent=ctx['user_agent'],
            data={
                'document_id': document_id,
                'document_type': document_type,
                'file_path_hash': file_path_hash,
                'deleted_at': datetime.utcnow().isoformat(),
                'deletion_method': '3-pass_overwrite'
            }
        )
        
        logger.info(f"Audit: File securely deleted for document {document_id}")
