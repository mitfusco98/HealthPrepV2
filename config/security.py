"""
Security configuration and HIPAA compliance settings
Handles security headers, encryption, and access controls
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from flask import request, session, current_app, abort, jsonify
from flask_login import current_user
import secrets
import hashlib

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration for HIPAA compliance"""
    
    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGITS = True
    PASSWORD_REQUIRE_SPECIAL = True
    PASSWORD_HISTORY_COUNT = 5  # Remember last 5 passwords
    PASSWORD_MAX_AGE_DAYS = 90  # Require password change every 90 days
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    SESSION_WARNING_MINUTES = 30   # Warn 30 minutes before timeout
    CONCURRENT_SESSION_LIMIT = 3   # Max concurrent sessions per user
    
    # Account lockout
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # Audit logging
    LOG_ALL_ACCESS = True
    LOG_FAILED_ATTEMPTS = True
    LOG_ADMINISTRATIVE_ACTIONS = True
    
    # Data encryption
    ENCRYPTION_ALGORITHM = 'AES-256'
    USE_FIELD_LEVEL_ENCRYPTION = True
    ENCRYPT_PHI_FIELDS = True
    
    # Network security
    REQUIRE_HTTPS = True
    HSTS_MAX_AGE = 31536000  # 1 year
    SECURE_HEADERS_ENABLED = True
    
    # API security
    RATE_LIMIT_REQUESTS_PER_MINUTE = 100
    REQUIRE_API_AUTHENTICATION = True

class SecurityHeaders:
    """HIPAA-compliant security headers"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get security headers for HIPAA compliance"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': f'max-age={SecurityConfig.HSTS_MAX_AGE}; includeSubDomains',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.replit.com cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' cdn.replit.com cdnjs.cloudflare.com; "
                "font-src 'self' cdnjs.cloudflare.com; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            ),
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            'Cache-Control': 'no-store, no-cache, must-revalidate, private'
        }

class PasswordValidator:
    """Password validation for HIPAA compliance"""
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """
        Validate password against HIPAA requirements
        
        Args:
            password: Password to validate
        
        Returns:
            Dict containing validation results
        """
        errors = []
        
        if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters long")
        
        if SecurityConfig.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if SecurityConfig.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if SecurityConfig.PASSWORD_REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if SecurityConfig.PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        # Check for common weak patterns
        weak_patterns = ['123456', 'password', 'qwerty', 'abc123', 'admin']
        if any(pattern in password.lower() for pattern in weak_patterns):
            errors.append("Password contains common weak patterns")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'strength_score': PasswordValidator._calculate_strength_score(password)
        }
    
    @staticmethod
    def _calculate_strength_score(password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length score
        score += min(password.__len__() * 2, 20)
        
        # Character variety score
        if any(c.isupper() for c in password):
            score += 10
        if any(c.islower() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 15
        
        # Uniqueness score
        unique_chars = len(set(password))
        score += min(unique_chars * 2, 20)
        
        # Pattern penalty
        if any(pattern in password.lower() for pattern in ['123', 'abc', 'qwe']):
            score -= 10
        
        return max(0, min(100, score))

class AccessControl:
    """Role-based access control for HIPAA compliance"""
    
    ROLES = {
        'admin': {
            'permissions': [
                'view_all_patients',
                'manage_users',
                'manage_screening_types',
                'access_admin_dashboard',
                'view_audit_logs',
                'manage_system_settings',
                'export_data'
            ],
            'description': 'System administrator with full access'
        },
        'clinician': {
            'permissions': [
                'view_assigned_patients',
                'create_prep_sheets',
                'view_screening_results',
                'upload_documents',
                'view_patient_data'
            ],
            'description': 'Clinical staff with patient care access'
        },
        'user': {
            'permissions': [
                'view_assigned_patients',
                'create_prep_sheets',
                'upload_documents'
            ],
            'description': 'Basic user with limited access'
        },
        'readonly': {
            'permissions': [
                'view_assigned_patients',
                'view_screening_results'
            ],
            'description': 'Read-only access for reporting'
        }
    }
    
    @staticmethod
    def require_permission(permission: str):
        """Decorator to require specific permission"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated:
                    abort(401)
                
                user_permissions = AccessControl.get_user_permissions(current_user.role)
                if permission not in user_permissions:
                    logger.warning(f"Access denied: User {current_user.username} attempted to access {permission}")
                    abort(403)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    @staticmethod
    def get_user_permissions(role: str) -> List[str]:
        """Get permissions for a user role"""
        return AccessControl.ROLES.get(role, {}).get('permissions', [])
    
    @staticmethod
    def has_permission(user_role: str, permission: str) -> bool:
        """Check if user role has specific permission"""
        permissions = AccessControl.get_user_permissions(user_role)
        return permission in permissions

class AuditLogger:
    """HIPAA-compliant audit logging"""
    
    @staticmethod
    def log_access(resource_type: str, resource_id: str = None, action: str = 'view'):
        """Log access to PHI or system resources"""
        if not SecurityConfig.LOG_ALL_ACCESS:
            return
        
        from admin.logs import log_admin_action
        
        description = f"Accessed {resource_type}"
        if resource_id:
            description += f" (ID: {resource_id})"
        
        log_admin_action(
            action=f'access_{action}',
            resource_type=resource_type,
            resource_id=resource_id,
            description=description
        )
    
    @staticmethod
    def log_phi_access(patient_id: str, data_type: str, action: str = 'view'):
        """Log access to Protected Health Information"""
        from admin.logs import log_admin_action
        
        log_admin_action(
            action=f'phi_{action}',
            resource_type='patient_data',
            resource_id=patient_id,
            description=f'Accessed {data_type} for patient {patient_id}'
        )
    
    @staticmethod
    def log_failed_login(username: str, ip_address: str, reason: str):
        """Log failed login attempts"""
        if not SecurityConfig.LOG_FAILED_ATTEMPTS:
            return
        
        from admin.logs import log_admin_action
        
        log_admin_action(
            action='login_failed',
            resource_type='authentication',
            resource_id=username,
            description=f'Failed login attempt: {reason} from {ip_address}'
        )

class SessionManager:
    """Enhanced session management for HIPAA compliance"""
    
    @staticmethod
    def extend_session():
        """Extend current session if user is active"""
        if current_user.is_authenticated:
            session.permanent = True
            session['last_activity'] = datetime.utcnow().isoformat()
    
    @staticmethod
    def check_session_timeout():
        """Check if session has timed out"""
        if 'last_activity' not in session:
            session['last_activity'] = datetime.utcnow().isoformat()
            return False
        
        last_activity = datetime.fromisoformat(session['last_activity'])
        timeout_threshold = datetime.utcnow() - timedelta(minutes=SecurityConfig.SESSION_TIMEOUT_MINUTES)
        
        return last_activity < timeout_threshold
    
    @staticmethod
    def get_session_warning_time() -> Optional[datetime]:
        """Get time when session warning should be shown"""
        if 'last_activity' not in session:
            return None
        
        last_activity = datetime.fromisoformat(session['last_activity'])
        warning_time = last_activity + timedelta(
            minutes=SecurityConfig.SESSION_TIMEOUT_MINUTES - SecurityConfig.SESSION_WARNING_MINUTES
        )
        
        return warning_time if warning_time > datetime.utcnow() else None

class EncryptionManager:
    """Field-level encryption for PHI data"""
    
    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new encryption key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def encrypt_field(data: str, key: str = None) -> str:
        """Encrypt sensitive field data"""
        if not SecurityConfig.USE_FIELD_LEVEL_ENCRYPTION:
            return data
        
        # This is a simplified implementation
        # In production, use proper encryption libraries like cryptography
        if not key:
            key = current_app.config.get('ENCRYPTION_KEY', 'default_key')
        
        # Hash the data for demonstration (use proper encryption in production)
        hashed = hashlib.sha256((data + key).encode()).hexdigest()
        return f"encrypted:{hashed[:32]}"
    
    @staticmethod
    def decrypt_field(encrypted_data: str, key: str = None) -> str:
        """Decrypt sensitive field data"""
        if not encrypted_data.startswith('encrypted:'):
            return encrypted_data
        
        # This is a simplified implementation
        # In production, implement proper decryption
        return "[ENCRYPTED DATA]"
    
    @staticmethod
    def is_phi_field(field_name: str) -> bool:
        """Check if field contains PHI and should be encrypted"""
        phi_fields = [
            'ssn', 'social_security_number',
            'mrn', 'medical_record_number',
            'phone', 'phone_number',
            'email', 'email_address',
            'address', 'home_address',
            'emergency_contact',
            'insurance_id', 'policy_number'
        ]
        
        return field_name.lower() in phi_fields

class RateLimiter:
    """Rate limiting for API endpoints"""
    
    def __init__(self):
        self.attempts = {}
    
    def is_rate_limited(self, identifier: str, limit: int = None) -> bool:
        """Check if identifier is rate limited"""
        if limit is None:
            limit = SecurityConfig.RATE_LIMIT_REQUESTS_PER_MINUTE
        
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old attempts
        if identifier in self.attempts:
            self.attempts[identifier] = [
                attempt for attempt in self.attempts[identifier]
                if attempt > minute_ago
            ]
        else:
            self.attempts[identifier] = []
        
        # Check if limit exceeded
        if len(self.attempts[identifier]) >= limit:
            return True
        
        # Record this attempt
        self.attempts[identifier].append(now)
        return False

# Global rate limiter instance
rate_limiter = RateLimiter()

def require_https():
    """Decorator to require HTTPS for sensitive endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if SecurityConfig.REQUIRE_HTTPS and not request.is_secure:
                return jsonify({'error': 'HTTPS required'}), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(limit: int = None):
    """Decorator to apply rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            identifier = request.environ.get('REMOTE_ADDR', 'unknown')
            
            if current_user.is_authenticated:
                identifier = f"user_{current_user.id}"
            
            if rate_limiter.is_rate_limited(identifier, limit):
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def audit_access(resource_type: str, action: str = 'view'):
    """Decorator to audit resource access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract resource ID from kwargs if present
            resource_id = kwargs.get('id') or kwargs.get('patient_id') or kwargs.get('document_id')
            
            # Log the access
            AuditLogger.log_access(resource_type, str(resource_id) if resource_id else None, action)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Security middleware setup
def setup_security_middleware(app):
    """Setup security middleware for the application"""
    
    @app.before_request
    def security_checks():
        """Perform security checks on each request"""
        
        # Check session timeout
        if current_user.is_authenticated and SessionManager.check_session_timeout():
            from flask_login import logout_user
            logout_user()
            return jsonify({'error': 'Session expired'}), 401
        
        # Extend session if user is active
        if current_user.is_authenticated:
            SessionManager.extend_session()
        
        # Check rate limiting for API endpoints
        if request.path.startswith('/api/'):
            identifier = request.environ.get('REMOTE_ADDR', 'unknown')
            if current_user.is_authenticated:
                identifier = f"user_{current_user.id}"
            
            if rate_limiter.is_rate_limited(identifier):
                return jsonify({'error': 'Rate limit exceeded'}), 429
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        if SecurityConfig.SECURE_HEADERS_ENABLED:
            headers = SecurityHeaders.get_security_headers()
            for header, value in headers.items():
                response.headers[header] = value
        
        return response

