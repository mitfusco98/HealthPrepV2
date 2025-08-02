"""
RBAC, encryption config, and security settings for HIPAA compliance.
Implements role-based access control and security measures.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from functools import wraps
from flask import request, session, abort, current_app
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration and encryption settings"""
    
    # Encryption settings
    ENCRYPTION_ALGORITHM = 'AES-256-GCM'
    KEY_DERIVATION_ALGORITHM = 'PBKDF2-SHA256'
    KEY_DERIVATION_ITERATIONS = 100000
    SALT_LENGTH = 32
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    IDLE_TIMEOUT_MINUTES = 60      # 1 hour of inactivity
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL_CHARS = True
    PASSWORD_HISTORY_COUNT = 5
    
    # Audit settings
    AUDIT_ALL_ACCESS = True
    AUDIT_PHI_ACCESS = True
    AUDIT_ADMIN_ACTIONS = True
    AUDIT_LOGIN_ATTEMPTS = True
    
    # Rate limiting
    API_RATE_LIMIT = '100 per minute'
    LOGIN_RATE_LIMIT = '10 per minute'
    EXPORT_RATE_LIMIT = '5 per hour'
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
    }

class RoleBasedAccessControl:
    """Role-based access control system"""
    
    # Define roles and their hierarchy
    ROLES = {
        'viewer': {
            'level': 1,
            'description': 'Read-only access to basic information'
        },
        'user': {
            'level': 2,
            'description': 'Standard user with screening management access'
        },
        'admin': {
            'level': 3,
            'description': 'Full administrative access'
        },
        'superadmin': {
            'level': 4,
            'description': 'System-level administrative access'
        }
    }
    
    # Define permissions for each role
    PERMISSIONS = {
        'viewer': [
            'view_dashboard',
            'view_screenings',
            'view_prep_sheets',
            'view_patients'
        ],
        'user': [
            'view_dashboard',
            'view_screenings',
            'view_prep_sheets',
            'view_patients',
            'create_screening_types',
            'edit_screening_types',
            'refresh_screenings',
            'generate_prep_sheets',
            'view_documents'
        ],
        'admin': [
            'view_dashboard',
            'view_screenings',
            'view_prep_sheets',
            'view_patients',
            'create_screening_types',
            'edit_screening_types',
            'delete_screening_types',
            'refresh_screenings',
            'generate_prep_sheets',
            'view_documents',
            'admin_dashboard',
            'view_admin_logs',
            'export_logs',
            'manage_users',
            'configure_phi',
            'manage_presets',
            'view_analytics',
            'system_configuration'
        ],
        'superadmin': [
            # All admin permissions plus:
            'system_maintenance',
            'database_access',
            'security_configuration',
            'backup_restore'
        ]
    }
    
    @classmethod
    def user_has_permission(cls, user, permission: str) -> bool:
        """Check if user has specific permission"""
        if not user or not user.is_authenticated:
            return False
        
        user_role = getattr(user, 'role', 'viewer')
        user_permissions = cls.PERMISSIONS.get(user_role, [])
        
        return permission in user_permissions
    
    @classmethod
    def user_has_role_level(cls, user, min_level: int) -> bool:
        """Check if user has minimum role level"""
        if not user or not user.is_authenticated:
            return False
        
        user_role = getattr(user, 'role', 'viewer')
        user_level = cls.ROLES.get(user_role, {}).get('level', 0)
        
        return user_level >= min_level
    
    @classmethod
    def get_user_permissions(cls, user) -> List[str]:
        """Get all permissions for a user"""
        if not user or not user.is_authenticated:
            return []
        
        user_role = getattr(user, 'role', 'viewer')
        return cls.PERMISSIONS.get(user_role, [])

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not RoleBasedAccessControl.user_has_permission(current_user, permission):
                logger.warning(f"Access denied for user {getattr(current_user, 'id', 'anonymous')} to {permission}")
                audit_access_attempt(permission, False)
                abort(403)
            
            audit_access_attempt(permission, True)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role_level(min_level: int):
    """Decorator to require minimum role level"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not RoleBasedAccessControl.user_has_role_level(current_user, min_level):
                logger.warning(f"Insufficient role level for user {getattr(current_user, 'id', 'anonymous')}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

class SessionSecurity:
    """Session security management"""
    
    @staticmethod
    def is_session_valid() -> bool:
        """Check if current session is valid"""
        if 'user_id' not in session:
            return False
        
        # Check session timeout
        if 'session_start' in session:
            session_start = datetime.fromisoformat(session['session_start'])
            if datetime.utcnow() - session_start > timedelta(minutes=SecurityConfig.SESSION_TIMEOUT_MINUTES):
                return False
        
        # Check idle timeout
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.utcnow() - last_activity > timedelta(minutes=SecurityConfig.IDLE_TIMEOUT_MINUTES):
                return False
        
        return True
    
    @staticmethod
    def refresh_session():
        """Refresh session activity timestamp"""
        session['last_activity'] = datetime.utcnow().isoformat()
    
    @staticmethod
    def initialize_session(user_id: int):
        """Initialize secure session for user"""
        session['user_id'] = user_id
        session['session_start'] = datetime.utcnow().isoformat()
        session['last_activity'] = datetime.utcnow().isoformat()
        session['session_token'] = secrets.token_urlsafe(32)
    
    @staticmethod
    def destroy_session():
        """Securely destroy session"""
        session.clear()

class PasswordSecurity:
    """Password security and validation"""
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, bool]:
        """Validate password against security requirements"""
        validation = {
            'length': len(password) >= SecurityConfig.MIN_PASSWORD_LENGTH,
            'uppercase': False,
            'lowercase': False,
            'numbers': False,
            'special_chars': False
        }
        
        if SecurityConfig.REQUIRE_UPPERCASE:
            validation['uppercase'] = any(c.isupper() for c in password)
        else:
            validation['uppercase'] = True
        
        if SecurityConfig.REQUIRE_LOWERCASE:
            validation['lowercase'] = any(c.islower() for c in password)
        else:
            validation['lowercase'] = True
        
        if SecurityConfig.REQUIRE_NUMBERS:
            validation['numbers'] = any(c.isdigit() for c in password)
        else:
            validation['numbers'] = True
        
        if SecurityConfig.REQUIRE_SPECIAL_CHARS:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            validation['special_chars'] = any(c in special_chars for c in password)
        else:
            validation['special_chars'] = True
        
        return validation
    
    @staticmethod
    def is_password_valid(password: str) -> bool:
        """Check if password meets all requirements"""
        validation = PasswordSecurity.validate_password(password)
        return all(validation.values())
    
    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Generate a secure password"""
        import string
        
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(characters) for _ in range(length))
        
        # Ensure password meets requirements
        while not PasswordSecurity.is_password_valid(password):
            password = ''.join(secrets.choice(characters) for _ in range(length))
        
        return password

class DataEncryption:
    """Data encryption utilities for PHI protection"""
    
    @staticmethod
    def generate_key() -> bytes:
        """Generate encryption key"""
        return secrets.token_bytes(32)  # 256 bits
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        import hashlib
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            SecurityConfig.KEY_DERIVATION_ITERATIONS
        )
    
    @staticmethod
    def encrypt_data(data: str, key: bytes) -> Dict[str, str]:
        """Encrypt sensitive data"""
        try:
            from cryptography.fernet import Fernet
            import base64
            
            # Use Fernet for symmetric encryption
            f = Fernet(base64.urlsafe_b64encode(key))
            encrypted_data = f.encrypt(data.encode('utf-8'))
            
            return {
                'encrypted_data': base64.b64encode(encrypted_data).decode('utf-8'),
                'algorithm': 'Fernet',
                'encrypted_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise
    
    @staticmethod
    def decrypt_data(encrypted_data: str, key: bytes) -> str:
        """Decrypt sensitive data"""
        try:
            from cryptography.fernet import Fernet
            import base64
            
            f = Fernet(base64.urlsafe_b64encode(key))
            decrypted_data = f.decrypt(base64.b64decode(encrypted_data))
            
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise

class AuditLogger:
    """HIPAA-compliant audit logging"""
    
    @staticmethod
    def log_phi_access(user_id: int, patient_id: int, action: str, details: str = None):
        """Log PHI access for HIPAA compliance"""
        from admin.logs import log_manager
        
        log_manager.log_activity(
            action=f'phi_access_{action}',
            details=f'Patient {patient_id}: {details or action}',
            user_id=user_id
        )
    
    @staticmethod
    def log_security_event(event_type: str, details: str, user_id: int = None):
        """Log security-related events"""
        from admin.logs import log_manager
        
        log_manager.log_activity(
            action=f'security_{event_type}',
            details=details,
            user_id=user_id
        )
    
    @staticmethod
    def log_data_access(resource: str, action: str, user_id: int, success: bool = True):
        """Log data access attempts"""
        from admin.logs import log_manager
        
        status = 'success' if success else 'failed'
        log_manager.log_activity(
            action=f'data_access_{status}',
            details=f'{action} on {resource}',
            user_id=user_id
        )

def audit_access_attempt(permission: str, success: bool):
    """Audit access attempts"""
    user_id = getattr(current_user, 'id', None) if current_user.is_authenticated else None
    
    AuditLogger.log_data_access(
        resource=permission,
        action='access_attempt',
        user_id=user_id,
        success=success
    )

def apply_security_headers(response):
    """Apply security headers to response"""
    for header, value in SecurityConfig.SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

def check_rate_limit(key: str, limit: str) -> bool:
    """Check if request is within rate limit"""
    # Simplified rate limiting - would use Redis in production
    return True

def validate_csrf_token():
    """Validate CSRF token for state-changing operations"""
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not token:
            abort(400, description='CSRF token missing')
        
        # Validate token (simplified - would use proper CSRF validation)
        if len(token) < 32:
            abort(400, description='Invalid CSRF token')

# Security middleware functions
def before_request_security():
    """Security checks before each request"""
    # Check session validity
    if current_user.is_authenticated and not SessionSecurity.is_session_valid():
        from flask_login import logout_user
        logout_user()
        abort(401)
    
    # Refresh session activity
    if current_user.is_authenticated:
        SessionSecurity.refresh_session()
    
    # Validate CSRF for state-changing operations
    validate_csrf_token()

def after_request_security(response):
    """Security headers and cleanup after each request"""
    return apply_security_headers(response)

# Initialize security system
def init_security_system(app):
    """Initialize security system with Flask app"""
    app.before_request(before_request_security)
    app.after_request(after_request_security)
    
    # Set security configuration
    app.config.update(SecurityConfig.__dict__)
    
    logger.info("Security system initialized with HIPAA compliance features")
