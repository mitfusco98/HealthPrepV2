"""
RBAC, encryption config, and security utilities
Handles security-related configuration and utilities
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, abort, current_app
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

# Role definitions
ROLES = {
    'admin': {
        'permissions': [
            'view_admin_dashboard',
            'manage_users',
            'manage_screening_types',
            'view_all_patients',
            'manage_system_settings',
            'view_audit_logs',
            'export_data',
            'manage_phi_settings',
            'system_administration'
        ]
    },
    'user': {
        'permissions': [
            'view_screening_list',
            'view_patient_details',
            'generate_prep_sheets',
            'upload_documents',
            'view_own_activity'
        ]
    },
    'readonly': {
        'permissions': [
            'view_screening_list',
            'view_patient_details',
            'view_prep_sheets'
        ]
    }
}

# Security constants
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "480"))  # 8 hours
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.environ.get("LOCKOUT_DURATION_MINUTES", "30"))
PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "8"))

class SecurityManager:
    """Handles security operations and validations"""
    
    def __init__(self):
        self.failed_logins = {}  # In production, use Redis or database
    
    def check_permission(self, user, permission):
        """Check if user has specific permission"""
        if not user or not user.is_authenticated:
            return False
        
        user_role = getattr(user, 'role', 'user')
        role_config = ROLES.get(user_role, {})
        permissions = role_config.get('permissions', [])
        
        return permission in permissions
    
    def require_permission(self, permission):
        """Decorator to require specific permission"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not self.check_permission(current_user, permission):
                    logger.warning(f"Permission denied: {permission} for user {current_user.id if current_user.is_authenticated else 'anonymous'}")
                    abort(403)
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def is_admin(self, user):
        """Check if user is admin"""
        return self.check_permission(user, 'system_administration')
    
    def validate_session_security(self):
        """Validate session security and handle timeouts"""
        if not current_user.is_authenticated:
            return True
        
        # Check session timeout
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity_time = datetime.fromisoformat(last_activity)
            if datetime.utcnow() - last_activity_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                logger.info(f"Session timeout for user {current_user.id}")
                return False
        
        # Update last activity
        session['last_activity'] = datetime.utcnow().isoformat()
        session.permanent = True
        
        return True
    
    def check_rate_limit(self, identifier, max_attempts=10, window_minutes=60):
        """Check rate limiting for various operations"""
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(minutes=window_minutes)
        
        # Clean old attempts
        if identifier in self.failed_logins:
            self.failed_logins[identifier] = [
                attempt for attempt in self.failed_logins[identifier]
                if attempt > window_start
            ]
        
        # Check current attempts
        attempts = len(self.failed_logins.get(identifier, []))
        return attempts < max_attempts
    
    def record_failed_attempt(self, identifier):
        """Record a failed login/operation attempt"""
        if identifier not in self.failed_logins:
            self.failed_logins[identifier] = []
        
        self.failed_logins[identifier].append(datetime.utcnow())
        logger.warning(f"Failed attempt recorded for {identifier}")
    
    def is_locked_out(self, identifier):
        """Check if identifier is currently locked out"""
        if identifier not in self.failed_logins:
            return False
        
        recent_failures = [
            attempt for attempt in self.failed_logins[identifier]
            if datetime.utcnow() - attempt < timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        ]
        
        return len(recent_failures) >= MAX_LOGIN_ATTEMPTS
    
    def validate_password_strength(self, password):
        """Validate password meets security requirements"""
        errors = []
        
        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        return errors
    
    def generate_secure_token(self, length=32):
        """Generate a cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def hash_sensitive_data(self, data):
        """Hash sensitive data for logging/storage"""
        if not data:
            return None
        
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]
    
    def sanitize_input(self, input_string, max_length=1000):
        """Sanitize user input to prevent injection attacks"""
        if not input_string:
            return ""
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n', '\r']
        sanitized = input_string
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Limit length
        return sanitized[:max_length]
    
    def audit_security_event(self, event_type, details=None):
        """Log security-related events for audit trail"""
        from admin.logs import log_admin_action
        
        user_id = current_user.id if current_user.is_authenticated else None
        ip_address = request.remote_addr if request else None
        
        log_admin_action(
            user_id=user_id,
            action=f"security_event_{event_type}",
            resource_type="security",
            details={
                'event_type': event_type,
                'ip_address': ip_address,
                'user_agent': request.headers.get('User-Agent') if request else None,
                'timestamp': datetime.utcnow().isoformat(),
                **(details or {})
            },
            ip_address=ip_address
        )

# Security decorators
def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            logger.warning(f"Admin access denied for user {current_user.id if current_user.is_authenticated else 'anonymous'}")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def require_permission(permission):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = SecurityManager()
            if not security_manager.check_permission(current_user, permission):
                logger.warning(f"Permission denied: {permission} for user {current_user.id if current_user.is_authenticated else 'anonymous'}")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_session_security(f):
    """Decorator to validate session security"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        security_manager = SecurityManager()
        if not security_manager.validate_session_security():
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(max_attempts=10, window_minutes=60):
    """Decorator for rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = SecurityManager()
            identifier = request.remote_addr
            
            if not security_manager.check_rate_limit(identifier, max_attempts, window_minutes):
                logger.warning(f"Rate limit exceeded for {identifier}")
                abort(429)  # Too Many Requests
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Security headers middleware
def add_security_headers(response):
    """Add security headers to response"""
    from config.settings import SECURITY_HEADERS
    
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    return response

# HIPAA compliance utilities
def log_phi_access(patient_id, access_type, details=None):
    """Log PHI access for HIPAA compliance"""
    security_manager = SecurityManager()
    security_manager.audit_security_event(
        'phi_access',
        {
            'patient_id': patient_id,
            'access_type': access_type,
            'details': details
        }
    )

def validate_hipaa_compliance(f):
    """Decorator to ensure HIPAA compliance for PHI access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Log the access attempt
        patient_id = kwargs.get('patient_id') or request.view_args.get('patient_id')
        if patient_id:
            log_phi_access(patient_id, f.__name__)
        
        return f(*args, **kwargs)
    return decorated_function

# Encryption utilities for sensitive data
class DataEncryption:
    """Handle encryption/decryption of sensitive data"""
    
    def __init__(self):
        self.key = os.environ.get("ENCRYPTION_KEY", "").encode()
        if not self.key:
            # Generate a key if not provided (for development)
            self.key = os.urandom(32)
            logger.warning("No encryption key provided, using generated key (development only)")
    
    def encrypt_data(self, data):
        """Encrypt sensitive data (placeholder - implement with proper encryption library)"""
        # In production, use proper encryption like Fernet from cryptography library
        import base64
        return base64.b64encode(str(data).encode()).decode()
    
    def decrypt_data(self, encrypted_data):
        """Decrypt sensitive data (placeholder - implement with proper encryption library)"""
        # In production, use proper decryption
        import base64
        try:
            return base64.b64decode(encrypted_data.encode()).decode()
        except:
            return encrypted_data

# Initialize security manager
security_manager = SecurityManager()
data_encryption = DataEncryption()
