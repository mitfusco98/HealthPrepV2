"""
RBAC, encryption config, and security settings.
Handles authentication, authorization, and security measures.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, abort, current_app, session
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration and constants"""
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # API rate limiting
    API_RATE_LIMIT = 100  # requests per minute
    RATE_LIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    
    # Encryption settings
    ENCRYPTION_ALGORITHM = 'AES-256'
    HASH_ALGORITHM = 'SHA-256'
    
    # HIPAA compliance settings
    AUDIT_ALL_ACCESS = True
    LOG_PHI_ACCESS = True
    REQUIRE_MFA_FOR_ADMIN = False  # Can be enabled when MFA is implemented
    
    # File upload security
    SCAN_UPLOADS = True
    QUARANTINE_SUSPICIOUS_FILES = True
    
    # Headers for security
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.replit.com; style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.replit.com; font-src 'self' cdnjs.cloudflare.com; img-src 'self' data:;"
    }

class RoleBasedAccessControl:
    """Role-based access control system"""
    
    # Define roles and permissions
    ROLES = {
        'admin': {
            'name': 'Administrator',
            'permissions': [
                'view_all_patients',
                'create_patient',
                'edit_patient',
                'delete_patient',
                'view_all_documents',
                'upload_document',
                'delete_document',
                'view_all_screenings',
                'create_screening_type',
                'edit_screening_type',
                'delete_screening_type',
                'generate_prep_sheet',
                'view_admin_dashboard',
                'manage_users',
                'view_audit_logs',
                'manage_settings',
                'manage_phi_settings',
                'system_administration'
            ]
        },
        'nurse': {
            'name': 'Nurse',
            'permissions': [
                'view_assigned_patients',
                'create_patient',
                'edit_patient',
                'view_patient_documents',
                'upload_document',
                'view_patient_screenings',
                'generate_prep_sheet'
            ]
        },
        'ma': {  # Medical Assistant
            'name': 'Medical Assistant',
            'permissions': [
                'view_assigned_patients',
                'view_patient_documents',
                'upload_document',
                'view_patient_screenings',
                'generate_prep_sheet'
            ]
        },
        'viewer': {
            'name': 'Read-Only User',
            'permissions': [
                'view_assigned_patients',
                'view_patient_documents',
                'view_patient_screenings'
            ]
        }
    }
    
    @classmethod
    def get_user_role(cls, user):
        """Get user role based on user attributes"""
        if user.is_admin:
            return 'admin'
        
        # Additional role logic would go here
        # For now, non-admin users are 'ma' (Medical Assistant)
        return 'ma'
    
    @classmethod
    def has_permission(cls, user, permission):
        """Check if user has specific permission"""
        if not user or not user.is_authenticated:
            return False
        
        user_role = cls.get_user_role(user)
        role_permissions = cls.ROLES.get(user_role, {}).get('permissions', [])
        
        return permission in role_permissions
    
    @classmethod
    def require_permission(cls, permission):
        """Decorator to require specific permission"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated:
                    abort(401)
                
                if not cls.has_permission(current_user, permission):
                    abort(403)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator

class SecurityAudit:
    """Security auditing and monitoring"""
    
    @staticmethod
    def log_security_event(event_type, user_id=None, details=None, ip_address=None):
        """Log security-related events"""
        from admin.logs import log_admin_action
        
        try:
            if not ip_address:
                ip_address = request.remote_addr if request else 'unknown'
            
            log_admin_action(
                user_id=user_id,
                action=f'Security Event: {event_type}',
                details=details,
                ip_address=ip_address
            )
            
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
    
    @staticmethod
    def log_phi_access(user_id, patient_id, access_type='view'):
        """Log PHI access for HIPAA compliance"""
        try:
            from models import Patient
            patient = Patient.query.get(patient_id)
            patient_name = patient.full_name if patient else f'Patient ID {patient_id}'
            
            SecurityAudit.log_security_event(
                event_type='PHI Access',
                user_id=user_id,
                details=f'{access_type.title()} access to PHI for {patient_name}',
                ip_address=request.remote_addr if request else None
            )
            
        except Exception as e:
            logger.error(f"Failed to log PHI access: {str(e)}")
    
    @staticmethod
    def check_suspicious_activity(user_id):
        """Check for suspicious user activity patterns"""
        try:
            from models import AdminLog
            from datetime import datetime, timedelta
            
            # Check for rapid successive logins
            recent_logins = AdminLog.query.filter(
                AdminLog.user_id == user_id,
                AdminLog.action.ilike('%login%'),
                AdminLog.timestamp >= datetime.utcnow() - timedelta(minutes=5)
            ).count()
            
            if recent_logins > 3:
                SecurityAudit.log_security_event(
                    event_type='Suspicious Activity',
                    user_id=user_id,
                    details=f'Multiple rapid logins detected: {recent_logins} in 5 minutes'
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking suspicious activity: {str(e)}")
            return False

class EncryptionHelper:
    """Encryption utilities for sensitive data"""
    
    @staticmethod
    def generate_salt():
        """Generate random salt for password hashing"""
        return secrets.token_hex(32)
    
    @staticmethod
    def hash_password(password, salt=None):
        """Hash password with salt"""
        if not salt:
            salt = EncryptionHelper.generate_salt()
        
        # Combine password and salt
        salted_password = password + salt
        
        # Hash using SHA-256
        hash_object = hashlib.sha256(salted_password.encode())
        return hash_object.hexdigest(), salt
    
    @staticmethod
    def verify_password(password, stored_hash, salt):
        """Verify password against stored hash"""
        hash_to_check, _ = EncryptionHelper.hash_password(password, salt)
        return hash_to_check == stored_hash
    
    @staticmethod
    def generate_api_key():
        """Generate secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_sensitive_data(data):
        """Hash sensitive data for storage"""
        hash_object = hashlib.sha256(data.encode())
        return hash_object.hexdigest()

class SessionSecurity:
    """Session management and security"""
    
    @staticmethod
    def is_session_valid():
        """Check if current session is valid"""
        if 'last_activity' not in session:
            return False
        
        last_activity = session.get('last_activity')
        if not last_activity:
            return False
        
        # Check session timeout
        timeout_minutes = SecurityConfig.SESSION_TIMEOUT_MINUTES
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        if last_activity < timeout_threshold:
            return False
        
        return True
    
    @staticmethod
    def update_session_activity():
        """Update last activity timestamp in session"""
        session['last_activity'] = datetime.utcnow()
    
    @staticmethod
    def invalidate_session():
        """Invalidate current session"""
        session.clear()
    
    @staticmethod
    def regenerate_session_id():
        """Regenerate session ID for security"""
        # Flask doesn't have built-in session ID regeneration
        # This is a placeholder for when it's implemented
        pass

class IPAddressValidator:
    """IP address validation and blocking"""
    
    # List of blocked IP addresses/ranges
    BLOCKED_IPS = set()
    
    # List of allowed IP ranges (for internal networks)
    ALLOWED_IP_RANGES = []
    
    @classmethod
    def is_ip_blocked(cls, ip_address):
        """Check if IP address is blocked"""
        return ip_address in cls.BLOCKED_IPS
    
    @classmethod
    def block_ip(cls, ip_address, reason=None):
        """Block an IP address"""
        cls.BLOCKED_IPS.add(ip_address)
        
        SecurityAudit.log_security_event(
            event_type='IP Blocked',
            details=f'IP {ip_address} blocked. Reason: {reason or "Manual block"}',
            ip_address=ip_address
        )
    
    @classmethod
    def unblock_ip(cls, ip_address):
        """Unblock an IP address"""
        cls.BLOCKED_IPS.discard(ip_address)
        
        SecurityAudit.log_security_event(
            event_type='IP Unblocked',
            details=f'IP {ip_address} unblocked',
            ip_address=ip_address
        )

def require_admin(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def require_permission(permission):
    """Decorator to require specific permission"""
    return RoleBasedAccessControl.require_permission(permission)

def log_phi_access(patient_id, access_type='view'):
    """Decorator to log PHI access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_authenticated:
                SecurityAudit.log_phi_access(
                    user_id=current_user.id,
                    patient_id=patient_id,
                    access_type=access_type
                )
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def apply_security_headers(response):
    """Apply security headers to response"""
    for header, value in SecurityConfig.SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

