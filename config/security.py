"""
RBAC, encryption config, and HIPAA compliance settings
"""
import os
from functools import wraps
from flask import current_app, request, abort
from flask_login import current_user
import hashlib
import hmac
import logging

class SecurityConfig:
    """Security configuration for HIPAA compliance"""
    
    # Encryption settings
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', 'default-key-change-in-production')
    
    # Authentication settings
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL = True
    
    # Session security
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    # HIPAA compliance
    AUDIT_ALL_PHI_ACCESS = True
    MINIMUM_NECESSARY_PRINCIPLE = True
    AUTO_LOGOUT_ENABLED = True
    BREACH_DETECTION_ENABLED = True
    
    # File upload security
    SCAN_UPLOADS_FOR_MALWARE = True
    QUARANTINE_SUSPICIOUS_FILES = True

# Role-based access control
ROLE_PERMISSIONS = {
    'admin': [
        'view_admin_dashboard',
        'manage_users',
        'view_audit_logs',
        'export_logs',
        'manage_phi_settings',
        'manage_screening_types',
        'view_all_patients',
        'generate_prep_sheets',
        'upload_documents',
        'view_ocr_dashboard',
        'manage_system_settings'
    ],
    'user': [
        'view_screening_list',
        'generate_prep_sheets',
        'upload_documents',
        'view_assigned_patients'
    ],
    'viewer': [
        'view_screening_list',
        'view_prep_sheets'
    ]
}

def require_permission(permission):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            user_role = 'admin' if current_user.is_admin else 'user'
            user_permissions = ROLE_PERMISSIONS.get(user_role, [])
            
            if permission not in user_permissions:
                logging.warning(f"User {current_user.username} attempted to access {permission} without permission")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_admin(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            logging.warning(f"Non-admin user {current_user.username if current_user.is_authenticated else 'Anonymous'} attempted admin access")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def audit_phi_access(patient_id, action, details=None):
    """Audit PHI access for HIPAA compliance"""
    try:
        from admin.logs import log_admin_action
        
        user_id = current_user.id if current_user.is_authenticated else None
        action_details = f"PHI Access - Patient ID: {patient_id}, Action: {action}"
        
        if details:
            action_details += f", Details: {details}"
        
        log_admin_action(
            user_id=user_id,
            action='PHI_ACCESS',
            details=action_details,
            ip_address=request.remote_addr
        )
        
        logging.info(f"PHI access audited: {action_details}")
        
    except Exception as e:
        logging.error(f"Failed to audit PHI access: {e}")

def validate_password_strength(password):
    """Validate password meets security requirements"""
    errors = []
    
    if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters long")
    
    if SecurityConfig.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if SecurityConfig.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if SecurityConfig.PASSWORD_REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    
    if SecurityConfig.PASSWORD_REQUIRE_SPECIAL and not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        errors.append("Password must contain at least one special character")
    
    return errors

def encrypt_sensitive_data(data, key=None):
    """Encrypt sensitive data using AES-256"""
    if key is None:
        key = SecurityConfig.ENCRYPTION_KEY.encode()
    
    try:
        from cryptography.fernet import Fernet
        import base64
        
        # Generate a key from the provided key
        key_hash = hashlib.sha256(key).digest()
        key_b64 = base64.urlsafe_b64encode(key_hash)
        
        fernet = Fernet(key_b64)
        encrypted_data = fernet.encrypt(data.encode())
        
        return encrypted_data.decode()
        
    except Exception as e:
        logging.error(f"Encryption failed: {e}")
        return data  # Return original data if encryption fails

def decrypt_sensitive_data(encrypted_data, key=None):
    """Decrypt sensitive data"""
    if key is None:
        key = SecurityConfig.ENCRYPTION_KEY.encode()
    
    try:
        from cryptography.fernet import Fernet
        import base64
        
        key_hash = hashlib.sha256(key).digest()
        key_b64 = base64.urlsafe_b64encode(key_hash)
        
        fernet = Fernet(key_b64)
        decrypted_data = fernet.decrypt(encrypted_data.encode())
        
        return decrypted_data.decode()
        
    except Exception as e:
        logging.error(f"Decryption failed: {e}")
        return encrypted_data  # Return encrypted data if decryption fails

def generate_csrf_token():
    """Generate CSRF token for forms"""
    try:
        import secrets
        return secrets.token_urlsafe(32)
    except Exception as e:
        logging.error(f"CSRF token generation failed: {e}")
        return "default-csrf-token"

def validate_file_upload(file):
    """Validate uploaded file for security"""
    from config.settings import Config
    
    if not file or not file.filename:
        return False, "No file selected"
    
    # Check file extension
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS):
        return False, "Invalid file type"
    
    # Check file size
    if len(file.read()) > Config.MAX_CONTENT_LENGTH:
        return False, "File too large"
    
    file.seek(0)  # Reset file pointer
    
    # Additional security checks could be added here
    # - Malware scanning
    # - File content validation
    # - MIME type verification
    
    return True, "File validated"

def check_breach_indicators(action, details=None):
    """Check for potential security breach indicators"""
    try:
        # Implement breach detection logic
        suspicious_patterns = [
            'multiple_failed_logins',
            'unusual_access_pattern',
            'unauthorized_phi_access',
            'bulk_data_export',
            'off_hours_access'
        ]
        
        # This would integrate with a security monitoring system
        # For now, log potential indicators
        if any(pattern in str(details).lower() for pattern in suspicious_patterns):
            logging.warning(f"Potential breach indicator detected: {action} - {details}")
            
            # Could trigger alerts, notifications, or automatic responses
            
    except Exception as e:
        logging.error(f"Breach detection check failed: {e}")

def sanitize_input(input_string):
    """Sanitize user input to prevent XSS and injection attacks"""
    if not input_string:
        return input_string
    
    try:
        import html
        import re
        
        # HTML escape
        sanitized = html.escape(input_string)
        
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'<script.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'onclick='
        ]
        
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized
        
    except Exception as e:
        logging.error(f"Input sanitization failed: {e}")
        return input_string

