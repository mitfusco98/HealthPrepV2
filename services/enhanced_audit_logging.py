"""
Enhanced HIPAA-Compliant Audit Logging Service for HealthPrepV2
Provides comprehensive audit logging for FHIR operations with PHI protection
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import hashlib
from flask import request, session
from flask_login import current_user

from models import db, AdminLog, FHIRApiCall, Patient

logger = logging.getLogger(__name__)


class HIPAAAuditLogger:
    """
    Enhanced audit logging service for HIPAA compliance
    Logs all FHIR operations and patient data access with appropriate PHI protection
    """

    def __init__(self):
        # Create a dedicated logger for HIPAA audit events
        self.logger = logging.getLogger('hipaa_audit')
        self.logger.setLevel(logging.INFO)

        # Ensure logs directory exists
        import os
        os.makedirs('logs', exist_ok=True)

        # Create file handler with rotation
        handler = logging.FileHandler('logs/hipaa_audit.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - ORG:%(org_id)s - USER:%(user_id)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_fhir_data_access(self, organization_id: int, user_id: int, 
                           action: str, patient_identifier: str = None,
                           resource_type: str = None, resource_count: int = None,
                           epic_patient_id: str = None, phi_level: str = 'minimal',
                           additional_data: Dict[str, Any] = None):
        """
        Log FHIR data access events with HIPAA compliance

        Args:
            organization_id: Organization ID
            user_id: User who performed the action
            action: Description of action (e.g., 'fhir_patient_sync', 'document_retrieval')
            patient_identifier: Patient MRN or ID (hashed if needed)
            resource_type: FHIR resource type accessed
            resource_count: Number of resources accessed
            epic_patient_id: Epic patient ID (hashed if needed)
            phi_level: Level of PHI to log ('minimal', 'standard', 'detailed')
            additional_data: Additional structured data
        """
        try:
            # Get organization PHI logging preferences
            from models import Organization
            org = Organization.query.get(organization_id)
            effective_phi_level = org.phi_logging_level if org else 'minimal'

            # Hash sensitive identifiers based on PHI level
            if effective_phi_level == 'minimal':
                # Hash all patient identifiers
                patient_hash = self._hash_identifier(patient_identifier) if patient_identifier else None
                epic_patient_hash = self._hash_identifier(epic_patient_id) if epic_patient_id else None
                safe_additional_data = self._sanitize_phi_data(additional_data) if additional_data else {}
            else:
                # Store identifiers based on organization preference
                patient_hash = patient_identifier
                epic_patient_hash = epic_patient_id
                safe_additional_data = additional_data or {}

            # Create audit log entry
            audit_data = {
                'action': action,
                'patient_identifier_hash': patient_hash,
                'epic_patient_id_hash': epic_patient_hash,
                'resource_type': resource_type,
                'resource_count': resource_count,
                'phi_level': effective_phi_level,
                'ip_address': self._get_client_ip(),
                'user_agent': self._get_user_agent(),
                'session_id': self._get_session_id(),
                **safe_additional_data
            }

            # Log to database
            from models import log_admin_event
            log_admin_event(
                event_type=f'fhir_{action}',
                user_id=user_id,
                org_id=organization_id,
                ip=self._get_client_ip(),
                data=audit_data,
                resource_type='fhir_data',
                action_details=f"{action} - Resource: {resource_type}, Count: {resource_count}",
                session_id=self._get_session_id(),
                user_agent=self._get_user_agent()
            )

            # Log to dedicated HIPAA audit log
            self.logger.info(
                f"FHIR_ACCESS - {action} - Resource: {resource_type} - Count: {resource_count} - Patient: {patient_hash}",
                extra={
                    'org_id': organization_id,
                    'user_id': user_id,
                    'action': action,
                    'resource_type': resource_type,
                    'patient_hash': patient_hash
                }
            )

        except Exception as e:
            logger.error(f"Failed to log FHIR data access: {str(e)}")

    def log_fhir_api_call(self, organization_id: int, endpoint: str, method: str,
                         user_id: int = None, resource_type: str = None,
                         epic_patient_id: str = None, response_status: int = None,
                         response_time_ms: int = None, request_params: dict = None):
        """
        Log individual FHIR API calls for rate limiting and audit
        """
        try:
            api_call = FHIRApiCall.log_api_call(
                org_id=organization_id,
                endpoint=endpoint,
                method=method,
                user_id=user_id,
                resource_type=resource_type,
                epic_patient_id=epic_patient_id,
                response_status=response_status,
                response_time_ms=response_time_ms,
                request_params=self._sanitize_request_params(request_params)
            )

            # Log high-level API call
            self.logger.info(
                f"FHIR_API_CALL - {method} {endpoint} - Status: {response_status} - Time: {response_time_ms}ms",
                extra={
                    'org_id': organization_id,
                    'user_id': user_id,
                    'endpoint': endpoint,
                    'method': method,
                    'status': response_status
                }
            )

            return api_call

        except Exception as e:
            logger.error(f"Failed to log FHIR API call: {str(e)}")
            return None

    def log_patient_data_export(self, organization_id: int, user_id: int,
                              patient_count: int, export_type: str,
                              screening_types: List[str] = None):
        """Log patient data export/prep sheet generation events"""
        try:
            export_data = {
                'export_type': export_type,
                'patient_count': patient_count,
                'screening_types': screening_types or [],
                'export_timestamp': datetime.utcnow().isoformat()
            }

            from models import log_admin_event
            log_admin_event(
                event_type='patient_data_export',
                user_id=user_id,
                org_id=organization_id,
                ip=self._get_client_ip(),
                data=export_data,
                resource_type='patient_data',
                action_details=f"Exported {export_type} for {patient_count} patients",
                session_id=self._get_session_id(),
                user_agent=self._get_user_agent()
            )

            self.logger.info(
                f"PATIENT_EXPORT - Type: {export_type} - Count: {patient_count}",
                extra={
                    'org_id': organization_id,
                    'user_id': user_id,
                    'export_type': export_type,
                    'patient_count': patient_count
                }
            )

        except Exception as e:
            logger.error(f"Failed to log patient data export: {str(e)}")

    def log_epic_document_write(self, organization_id: int, user_id: int,
                              patient_identifier: str, epic_document_id: str,
                              document_type: str, content_length: int):
        """Log when data is written back to Epic"""
        try:
            write_data = {
                'patient_identifier_hash': self._hash_identifier(patient_identifier),
                'epic_document_id': epic_document_id,
                'document_type': document_type,
                'content_length': content_length,
                'write_timestamp': datetime.utcnow().isoformat()
            }

            from models import log_admin_event
            log_admin_event(
                event_type='epic_document_write',
                user_id=user_id,
                org_id=organization_id,
                ip=self._get_client_ip(),
                data=write_data,
                resource_type='epic_document',
                action_details=f"Wrote {document_type} document to Epic for patient {self._hash_identifier(patient_identifier)}",
                session_id=self._get_session_id(),
                user_agent=self._get_user_agent()
            )

            self.logger.info(
                f"EPIC_WRITE - Document: {document_type} - Patient: {self._hash_identifier(patient_identifier)} - Epic Doc: {epic_document_id}",
                extra={
                    'org_id': organization_id,
                    'user_id': user_id,
                    'document_type': document_type,
                    'epic_document_id': epic_document_id
                }
            )

        except Exception as e:
            logger.error(f"Failed to log Epic document write: {str(e)}")

    def log_async_job_audit(self, organization_id: int, user_id: int,
                          job_type: str, job_id: str, status: str,
                          total_patients: int = None, success_count: int = None,
                          failure_count: int = None):
        """Log async job completion for audit trail"""
        try:
            job_data = {
                'job_type': job_type,
                'job_id': job_id,
                'status': status,
                'total_patients': total_patients,
                'success_count': success_count,
                'failure_count': failure_count,
                'completion_timestamp': datetime.utcnow().isoformat()
            }

            from models import log_admin_event
            log_admin_event(
                event_type=f'async_job_{status}',
                user_id=user_id,
                org_id=organization_id,
                ip=self._get_client_ip(),
                data=job_data,
                resource_type='async_job',
                action_details=f"Async {job_type} job {status}: {success_count}/{total_patients} successful",
                session_id=self._get_session_id()
            )

            self.logger.info(
                f"ASYNC_JOB - {job_type} - {status} - Success: {success_count}/{total_patients}",
                extra={
                    'org_id': organization_id,
                    'user_id': user_id,
                    'job_type': job_type,
                    'job_id': job_id,
                    'status': status
                }
            )

        except Exception as e:
            logger.error(f"Failed to log async job audit: {str(e)}")

    def get_audit_report(self, organization_id: int, start_date: datetime,
                        end_date: datetime, event_types: List[str] = None) -> List[Dict]:
        """Generate audit report for specified time period"""
        try:
            query = AdminLog.query.filter(
                AdminLog.org_id == organization_id,
                AdminLog.timestamp >= start_date,
                AdminLog.timestamp <= end_date
            )

            if event_types:
                query = query.filter(AdminLog.event_type.in_(event_types))

            logs = query.order_by(AdminLog.timestamp.desc()).all()

            audit_report = []
            for log in logs:
                audit_entry = {
                    'timestamp': log.timestamp.isoformat(),
                    'event_type': log.event_type,
                    'user_id': log.user_id,
                    'action_details': log.action_details,
                    'resource_type': log.resource_type,
                    'ip_address': log.ip_address,
                    'session_id': log.session_id
                }

                # Include sanitized data if available
                if log.data and isinstance(log.data, dict):
                    audit_entry['metadata'] = self._sanitize_audit_data_for_export(log.data)

                audit_report.append(audit_entry)

            return audit_report

        except Exception as e:
            logger.error(f"Failed to generate audit report: {str(e)}")
            return []

    def _hash_identifier(self, identifier: str) -> str:
        """Hash sensitive patient identifiers for audit logging"""
        if not identifier:
            return None

        # Use SHA-256 hash with salt for patient identifiers
        salt = "hipaa_audit_salt_2024"  # In production, use environment variable
        return hashlib.sha256(f"{identifier}{salt}".encode()).hexdigest()[:16]

    def _sanitize_phi_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or hash PHI from data for minimal logging"""
        if not data:
            return {}

        sanitized = {}
        phi_fields = ['mrn', 'name', 'email', 'phone', 'ssn', 'dob', 'address']

        for key, value in data.items():
            if any(phi_field in key.lower() for phi_field in phi_fields):
                if isinstance(value, str):
                    sanitized[f"{key}_hash"] = self._hash_identifier(value)
                else:
                    sanitized[f"{key}_present"] = value is not None
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_request_params(self, params: dict) -> dict:
        """Sanitize request parameters for logging"""
        if not params:
            return {}

        # Remove sensitive parameters but keep structure for audit
        safe_params = {}
        sensitive_keys = ['access_token', 'refresh_token', 'password', 'secret']

        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                safe_params[key] = '***REDACTED***'
            else:
                safe_params[key] = value

        return safe_params

    def _sanitize_audit_data_for_export(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize audit data for external export/reporting"""
        if not isinstance(data, dict):
            return {}

        sanitized = {}
        for key, value in data.items():
            if 'token' in key.lower() or 'secret' in key.lower() or 'password' in key.lower():
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_audit_data_for_export(value)
            else:
                sanitized[key] = value

        return sanitized

    def _get_client_ip(self) -> str:
        """Get client IP address from request"""
        try:
            if request:
                return request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
            return 'unknown'
        except:
            return 'unknown'

    def _get_user_agent(self) -> str:
        """Get user agent from request"""
        try:
            if request:
                return request.environ.get('HTTP_USER_AGENT', 'unknown')[:500]  # Limit length
            return 'unknown'
        except:
            return 'unknown'

    def _get_session_id(self) -> str:
        """Get session ID for tracking"""
        try:
            if session:
                return session.get('session_id', 'unknown')
            return 'unknown'
        except:
            return 'unknown'


# Global audit logger instance
audit_logger = HIPAAAuditLogger()


def log_fhir_access(organization_id: int, action: str, **kwargs):
    """Convenience function for logging FHIR access"""
    user_id = current_user.id if current_user and current_user.is_authenticated else None
    return audit_logger.log_fhir_data_access(organization_id, user_id, action, **kwargs)


def log_api_call(organization_id: int, endpoint: str, method: str, **kwargs):
    """Convenience function for logging API calls"""
    user_id = current_user.id if current_user and current_user.is_authenticated else None
    return audit_logger.log_fhir_api_call(organization_id, endpoint, method, user_id=user_id, **kwargs)


def log_patient_export(organization_id: int, export_type: str, patient_count: int, **kwargs):
    """Convenience function for logging patient data exports"""
    user_id = current_user.id if current_user and current_user.is_authenticated else None
    return audit_logger.log_patient_data_export(organization_id, user_id, patient_count, export_type, **kwargs)


def log_epic_write(organization_id: int, patient_identifier: str, epic_document_id: str, **kwargs):
    """Convenience function for logging Epic document writes"""
    user_id = current_user.id if current_user and current_user.is_authenticated else None
    return audit_logger.log_epic_document_write(organization_id, user_id, patient_identifier, epic_document_id, **kwargs)


def get_audit_logger() -> HIPAAAuditLogger:
    """Get the global audit logger instance"""
    return audit_logger