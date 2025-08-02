"""
Security configuration and HIPAA compliance utilities.
Implements role-based access control, session management, and security policies.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from functools import wraps
from flask import request, session, current_user, abort, flash, redirect, url_for
from flask_login import login_required
import secrets
import hashlib

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration constants."""
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = False
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    SESSION_WARNING_MINUTES = 5
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # HIPAA compliance
    AUDIT_ALL_ACCESS = True
    PHI_ACCESS_LOGGING = True
    MINIMUM_LOG_LEVEL = 'INFO'
    
    # IP and request security
    ENABLE_IP_WHITELIST = False
    ALLOWED_IPS = []
    MAX_REQUESTS_PER_MINUTE = 100
    
    # File upload security
    SCAN_UPLOADS = True
    MAX_FILE_SIZE_MB = 50
    ALLOWED_MIME_TYPES = [
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/tiff',
        'image/bmp'
    ]

class RoleBasedAccessControl:
    """Role-based access control system."""
    
    ROLES = {
        'admin': {
            'name': 'Administrator',
            'permissions': [
                'user_management',
                'system_configuration',
                'audit_logs',
                'data_export',
                'phi_access',
                'screening_management',
                'document_management',
                'prep_sheet_generation'
            ]
        },
        'user': {
            'name': 'Standard User',
            'permissions': [
                'screening_management',
                'document_management',
                'prep_sheet_generation',
                'limited_phi_access'
            ]
        },
        'viewer': {
            'name': 'Read-Only Viewer',
            'permissions': [
                'view_screenings',
                'view_documents',
                'view_prep_sheets'
            ]
        }
    }
    
    @classmethod
    def get_user_role(cls, user) -> str:
        """Get the role for a user."""
        if hasattr(user, 'is_admin') and user.is_admin:
            return 'admin'
        elif hasattr(user, 'role'):
            return user.role
        else:
            return 'user'  # Default role
    
    @classmethod
    def has_permission(cls, user, permission: str) -> bool:
        """Check if user has a specific permission."""
        try:
            user_role = cls.get_user_role(user)
            role_permissions = cls.ROLES.get(user_role, {}).get('permissions', [])
            return permission in role_permissions
        except Exception as e:
            logger.error(f"Error checking permission {permission} for user: {e}")
            return False
    
    @classmethod
    def require_permission(cls, permission: str):
        """Decorator to require a specific permission."""
        def decorator(f):
            @wraps(f)
            @login_required
            def decorated_function(*args, **kwargs):
                if not cls.has_permission(current_user, permission):
                    logger.warning(f"Access denied: User {current_user.username} lacks permission {permission}")
                    abort(403)
                return f(*args, **kwargs)
            return decorated_function
        return decorator

class SessionManager:
    """Enhanced session management with security features."""
    
    @staticmethod
    def create_secure_session(user_id: int) -> str:
        """Create a secure session token."""
        timestamp = datetime.utcnow().isoformat()
        random_data = secrets.token_urlsafe(32)
        session_data = f"{user_id}:{timestamp}:{random_data}"
        
        # Create session hash
        session_token = hashlib.sha256(session_data.encode()).hexdigest()
        
        session['user_id'] = user_id
        session['session_token'] = session_token
        session['created_at'] = timestamp
        session['last_activity'] = timestamp
        
        logger.info(f"Created secure session for user {user_id}")
        return session_token
    
    @staticmethod
    def validate_session() -> bool:
        """Validate current session security."""
        try:
            if 'user_id' not in session or 'session_token' not in session:
                return False
            
            # Check session timeout
            if 'created_at' in session:
                created_at = datetime.fromisoformat(session['created_at'])
                if datetime.utcnow() - created_at > timedelta(minutes=SecurityConfig.SESSION_TIMEOUT_MINUTES):
                    SessionManager.destroy_session()
                    return False
            
            # Update last activity
            session['last_activity'] = datetime.utcnow().isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False
    
    @staticmethod
    def destroy_session():
        """Securely destroy the current session."""
        user_id = session.get('user_id', 'unknown')
        session.clear()
        logger.info(f"Destroyed session for user {user_id}")
    
    @staticmethod
    def get_session_info() -> Dict[str, Any]:
        """Get current session information."""
        return {
            'user_id': session.get('user_id'),
            'created_at': session.get('created_at'),
            'last_activity': session.get('last_activity'),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown')
        }

class AuditLogger:
    """HIPAA-compliant audit logging."""
    
    @staticmethod
    def log_access(user_id: int, resource: str, action: str, patient_id: Optional[int] = None, 
                   phi_accessed: bool = False, details: str = None):
        """Log access to resources for HIPAA compliance."""
        try:
            from models import AdminLog, db
            
            audit_details = {
                'resource': resource,
                'action': action,
                'patient_id': patient_id,
                'phi_accessed': phi_accessed,
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if details:
                audit_details['additional_details'] = details
            
            # Create audit log entry
            audit_log = AdminLog(
                user_id=user_id,
                action=f'access_{action}',
                details=f"Resource: {resource}" + (f", Patient: {patient_id}" if patient_id else "") + 
                       (f", PHI Access: {phi_accessed}" if phi_accessed else ""),
                ip_address=request.remote_addr,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
            if phi_accessed:
                logger.warning(f"PHI ACCESS: User {user_id} accessed {resource} for patient {patient_id}")
            else:
                logger.info(f"AUDIT: User {user_id} performed {action} on {resource}")
                
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")

class InputValidator:
    """Input validation and sanitization."""
    
    @staticmethod
    def validate_mrn(mrn: str) -> bool:
        """Validate Medical Record Number format."""
        if not mrn or len(mrn) < 3 or len(mrn) > 20:
            return False
        
        # Allow alphanumeric characters and hyphens
        import re
        pattern = r'^[A-Za-z0-9\-]+$'
        return bool(re.match(pattern, mrn))
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """Validate password against security requirements."""
        errors = []
        
        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters long")
        
        if len(password) > SecurityConfig.MAX_PASSWORD_LENGTH:
            errors.append(f"Password must be no more than {SecurityConfig.MAX_PASSWORD_LENGTH} characters long")
        
        if SecurityConfig.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if SecurityConfig.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if SecurityConfig.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if SecurityConfig.REQUIRE_SPECIAL_CHARS:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'strength': InputValidator._calculate_password_strength(password)
        }
    
    @staticmethod
    def _calculate_password_strength(password: str) -> str:
        """Calculate password strength score."""
        score = 0
        
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if any(c.isupper() for c in password):
            score += 1
        if any(c.islower() for c in password):
            score += 1
        if any(c.isdigit() for c in password):
            score += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 1
        
        if score <= 2:
            return 'weak'
        elif score <= 4:
            return 'medium'
        else:
            return 'strong'
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize uploaded filename."""
        import re
        
        # Remove path information
        filename = os.path.basename(filename)
        
        # Replace problematic characters
        filename = re.sub(r'[^a-zA-Z0-9\-_\.]', '_', filename)
        
        # Ensure it's not too long
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        
        return filename

class FileSecurityValidator:
    """File upload security validation."""
    
    @staticmethod
    def validate_file_upload(file, filename: str) -> Dict[str, Any]:
        """Comprehensive file upload validation."""
        errors = []
        
        # Check file size
        if hasattr(file, 'content_length') and file.content_length:
            max_size = SecurityConfig.MAX_FILE_SIZE_MB * 1024 * 1024
            if file.content_length > max_size:
                errors.append(f"File size exceeds maximum allowed size of {SecurityConfig.MAX_FILE_SIZE_MB}MB")
        
        # Check file extension
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            errors.append(f"File type '{file_ext}' is not allowed")
        
        # Check MIME type
        if hasattr(file, 'content_type'):
            if file.content_type not in SecurityConfig.ALLOWED_MIME_TYPES:
                errors.append(f"MIME type '{file.content_type}' is not allowed")
        
        # Basic content validation (read first few bytes to check magic numbers)
        try:
            file.seek(0)
            header = file.read(20)
            file.seek(0)
            
            if not FileSecurityValidator._validate_file_header(header, file_ext):
                errors.append("File content does not match the file extension")
                
        except Exception as e:
            logger.error(f"Error validating file header: {e}")
            errors.append("Could not validate file content")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized_filename': InputValidator.sanitize_filename(filename)
        }
    
    @staticmethod
    def _validate_file_header(header: bytes, file_ext: str) -> bool:
        """Validate file header matches extension."""
        magic_numbers = {
            '.pdf': [b'%PDF'],
            '.jpg': [b'\xff\xd8\xff'],
            '.jpeg': [b'\xff\xd8\xff'],
            '.png': [b'\x89PNG\r\n\x1a\n'],
            '.tiff': [b'II*\x00', b'MM\x00*'],
            '.bmp': [b'BM']
        }
        
        expected_headers = magic_numbers.get(file_ext, [])
        
        for expected in expected_headers:
            if header.startswith(expected):
                return True
        
        return False

# Security decorators
def audit_access(resource: str, phi_access: bool = False):
    """Decorator to audit resource access."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            patient_id = kwargs.get('patient_id') or request.args.get('patient_id')
            
            AuditLogger.log_access(
                user_id=current_user.id,
                resource=resource,
                action=f.__name__,
                patient_id=patient_id,
                phi_accessed=phi_access
            )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_admin(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Administrator privileges required.', 'error')
            logger.warning(f"Non-admin user {current_user.username} attempted to access admin function {f.__name__}")
            return redirect(url_for('screening.screening_list'))
        return f(*args, **kwargs)
    return decorated_function

def session_timeout_check(f):
    """Decorator to check session timeout."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SessionManager.validate_session():
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize security settings
def init_security_config():
    """Initialize security configuration."""
    logger.info("Initializing security configuration")
    
    # Set secure headers
    security_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com;"
    }
    
    return security_headers

def get_security_summary() -> Dict[str, Any]:
    """Get current security configuration summary."""
    return {
        'password_requirements': {
            'min_length': SecurityConfig.MIN_PASSWORD_LENGTH,
            'require_uppercase': SecurityConfig.REQUIRE_UPPERCASE,
            'require_lowercase': SecurityConfig.REQUIRE_LOWERCASE,
            'require_digits': SecurityConfig.REQUIRE_DIGITS,
            'require_special_chars': SecurityConfig.REQUIRE_SPECIAL_CHARS
        },
        'session_security': {
            'timeout_minutes': SecurityConfig.SESSION_TIMEOUT_MINUTES,
            'max_login_attempts': SecurityConfig.MAX_LOGIN_ATTEMPTS,
            'lockout_duration': SecurityConfig.LOCKOUT_DURATION_MINUTES
        },
        'file_security': {
            'max_file_size_mb': SecurityConfig.MAX_FILE_SIZE_MB,
            'allowed_types': SecurityConfig.ALLOWED_MIME_TYPES,
            'scan_uploads': SecurityConfig.SCAN_UPLOADS
        },
        'audit_settings': {
            'audit_all_access': SecurityConfig.AUDIT_ALL_ACCESS,
            'phi_access_logging': SecurityConfig.PHI_ACCESS_LOGGING
        }
    }
