"""
RBAC, encryption config
Security configurations and access control for healthcare data
"""

import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session, current_app
from flask_login import current_user
import hashlib
import secrets
import logging

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
    
    # HIPAA compliance settings
    AUDIT_ALL_PHI_ACCESS = True
    MINIMUM_NECESSARY_PRINCIPLE = True
    AUTO_LOGOUT_ENABLED = True
    
    # Encryption settings
    ENCRYPTION_ALGORITHM = 'AES-256'
    HASH_ALGORITHM = 'SHA-256'
    
    # API rate limiting
    API_RATE_LIMIT = '100/hour'
    ADMIN_API_RATE_LIMIT = '500/hour'

class RoleBasedAccessControl:
    """Role-based access control system"""
    
    # Define role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        'ma': 1,        # Medical Assistant
        'nurse': 2,     # Nurse
        'user': 3,      # General User
        'admin': 4      # Administrator
    }
    
    # Define permissions for each role
    ROLE_PERMISSIONS = {
        'ma': [
            'view_patients',
            'view_screenings',
            'upload_documents',
            'generate_prep_sheets'
        ],
        'nurse': [
            'view_patients',
            'view_screenings',
            'upload_documents',
            'generate_prep_sheets',
            'edit_patient_info',
            'manage_screenings'
        ],
        'user': [
            'view_patients',
            'view_screenings',
            'upload_documents',
            'generate_prep_sheets',
            'edit_patient_info',
            'manage_screenings',
            'view_reports'
        ],
        'admin': [
            'view_patients',
            'view_screenings',
            'upload_documents',
            'generate_prep_sheets',
            'edit_patient_info',
            'manage_screenings',
            'view_reports',
            'manage_users',
            'access_admin_panel',
            'manage_settings',
            'view_audit_logs',
            'export_data',
            'manage_phi_settings'
        ]
    }
    
    @classmethod
    def get_user_permissions(cls, role):
        """Get all permissions for a role"""
        return cls.ROLE_PERMISSIONS.get(role, [])
    
    @classmethod
    def has_permission(cls, user_role, required_permission):
        """Check if a role has a specific permission"""
        user_permissions = cls.get_user_permissions(user_role)
        return required_permission in user_permissions
    
    @classmethod
    def role_can_access_role(cls, user_role, target_role):
        """Check if a user role can manage/access another role"""
        user_level = cls.ROLE_HIERARCHY.get(user_role, 0)
        target_level = cls.ROLE_HIERARCHY.get(target_role, 0)
        return user_level >= target_level

def require_permission(permission):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            
            if not RoleBasedAccessControl.has_permission(current_user.role, permission):
                log_security_event('unauthorized_access_attempt', 
                                 f'User {current_user.username} attempted to access {permission}')
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Log PHI access if required
            if permission in ['view_patients', 'generate_prep_sheets', 'view_reports']:
                log_phi_access(current_user.id, permission, request.endpoint)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_role(required_role):
    """Decorator to require minimum role level"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_level = RoleBasedAccessControl.ROLE_HIERARCHY.get(current_user.role, 0)
            required_level = RoleBasedAccessControl.ROLE_HIERARCHY.get(required_role, 0)
            
            if user_level < required_level:
                log_security_event('insufficient_role', 
                                 f'User {current_user.username} (role: {current_user.role}) '
                                 f'attempted to access {required_role} resource')
                return jsonify({'error': 'Insufficient role'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not current_user.is_admin():
            log_security_event('admin_access_denied', 
                             f'Non-admin user {current_user.username} attempted admin access')
            return jsonify({'error': 'Admin privileges required'}), 403
        
        log_security_event('admin_access', f'Admin {current_user.username} accessed admin function')
        return f(*args, **kwargs)
    
    return decorated_function

class PHIAccessControl:
    """Protected Health Information access control"""
    
    @staticmethod
    def log_phi_access(user_id, action, resource, patient_id=None, additional_info=None):
        """Log PHI access for HIPAA compliance"""
        from models import AdminLog
        from app import db
        
        try:
            description = f"PHI Access: {action} on {resource}"
            if patient_id:
                description += f" for patient {patient_id}"
            if additional_info:
                description += f" - {additional_info}"
            
            log_entry = AdminLog(
                user_id=user_id,
                action='phi_access',
                description=description,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get('User-Agent', '')[:500] if request else None
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Failed to log PHI access: {str(e)}")
    
    @staticmethod
    def check_minimum_necessary(user_role, requested_data_type):
        """Check if data access follows minimum necessary principle"""
        # Define what data each role needs access to
        role_data_access = {
            'ma': ['basic_patient_info', 'appointments', 'screenings'],
            'nurse': ['basic_patient_info', 'appointments', 'screenings', 'medical_history', 'medications'],
            'user': ['basic_patient_info', 'appointments', 'screenings', 'medical_history', 'medications', 'lab_results'],
            'admin': ['all']  # Admins can access all data for system management
        }
        
        allowed_data = role_data_access.get(user_role, [])
        return 'all' in allowed_data or requested_data_type in allowed_data

def validate_password_strength(password):
    """Validate password against security requirements"""
    errors = []
    
    if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters long")
    
    if SecurityConfig.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if SecurityConfig.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if SecurityConfig.REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    
    if SecurityConfig.REQUIRE_SPECIAL_CHARS and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")
    
    return errors

def generate_secure_token(length=32):
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)

def hash_sensitive_data(data):
    """Hash sensitive data for storage"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    return hashlib.sha256(data).hexdigest()

def encrypt_phi_data(data, key=None):
    """Encrypt PHI data (placeholder for actual encryption implementation)"""
    # In a production system, this would use proper AES-256 encryption
    # For now, return a placeholder indicating encryption would occur
    return f"[ENCRYPTED:{hash_sensitive_data(data)[:16]}]"

def decrypt_phi_data(encrypted_data, key=None):
    """Decrypt PHI data (placeholder for actual decryption implementation)"""
    # In a production system, this would decrypt AES-256 encrypted data
    # For now, return indication that decryption would occur
    if encrypted_data.startswith("[ENCRYPTED:"):
        return "[DECRYPTED_DATA]"
    return encrypted_data

class SessionSecurity:
    """Session security management"""
    
    @staticmethod
    def is_session_expired():
        """Check if current session is expired"""
        if 'last_activity' not in session:
            return True
        
        last_activity = datetime.fromisoformat(session['last_activity'])
        timeout = timedelta(minutes=SecurityConfig.SESSION_TIMEOUT_MINUTES)
        
        return datetime.utcnow() - last_activity > timeout
    
    @staticmethod
    def update_session_activity():
        """Update session last activity timestamp"""
        session['last_activity'] = datetime.utcnow().isoformat()
    
    @staticmethod
    def invalidate_session():
        """Invalidate current session"""
        session.clear()
    
    @staticmethod
    def check_concurrent_sessions(user_id):
        """Check for concurrent sessions (placeholder implementation)"""
        # In a production system, this would check for multiple active sessions
        # and potentially limit concurrent logins
        return True

def log_security_event(event_type, description, user_id=None):
    """Log security-related events"""
    from models import AdminLog
    from app import db
    
    try:
        log_entry = AdminLog(
            user_id=user_id or (current_user.id if current_user.is_authenticated else None),
            action=f'security_{event_type}',
            description=description,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent', '')[:500] if request else None
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to application logger for monitoring
        logging.warning(f"Security Event: {event_type} - {description}")
        
    except Exception as e:
        logging.error(f"Failed to log security event: {str(e)}")

def log_phi_access(user_id, action, resource, patient_id=None):
    """Log PHI access for HIPAA compliance"""
    PHIAccessControl.log_phi_access(user_id, action, resource, patient_id)

class BreachDetection:
    """Detect potential security breaches"""
    
    @staticmethod
    def detect_unusual_access_patterns(user_id, timeframe_hours=24):
        """Detect unusual access patterns for a user"""
        from models import AdminLog
        from sqlalchemy import and_
        
        cutoff_time = datetime.utcnow() - timedelta(hours=timeframe_hours)
        
        # Count PHI access events
        phi_access_count = AdminLog.query.filter(
            and_(
                AdminLog.user_id == user_id,
                AdminLog.action == 'phi_access',
                AdminLog.created_at >= cutoff_time
            )
        ).count()
        
        # Define normal access thresholds
        normal_thresholds = {
            'ma': 50,
            'nurse': 100,
            'user': 150,
            'admin': 500
        }
        
        if current_user.is_authenticated:
            threshold = normal_thresholds.get(current_user.role, 100)
            if phi_access_count > threshold:
                log_security_event('unusual_access_pattern', 
                                 f'User {user_id} accessed PHI {phi_access_count} times in {timeframe_hours} hours')
                return True
        
        return False
    
    @staticmethod
    def detect_after_hours_access():
        """Detect access outside normal business hours"""
        current_hour = datetime.now().hour
        
        # Define business hours (6 AM to 10 PM)
        if current_hour < 6 or current_hour > 22:
            if current_user.is_authenticated:
                log_security_event('after_hours_access', 
                                 f'User {current_user.username} accessed system at {datetime.now()}')
                return True
        
        return False

# Security middleware function
def apply_security_headers(response):
    """Apply security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
    return response

# Audit compliance functions
def generate_audit_report(start_date, end_date):
    """Generate HIPAA audit report"""
    from models import AdminLog
    from sqlalchemy import and_
    
    audit_events = AdminLog.query.filter(
        and_(
            AdminLog.created_at >= start_date,
            AdminLog.created_at <= end_date,
            AdminLog.action.in_(['phi_access', 'security_login', 'security_logout', 'security_unauthorized_access_attempt'])
        )
    ).order_by(AdminLog.created_at.desc()).all()
    
    return {
        'period': f"{start_date} to {end_date}",
        'total_events': len(audit_events),
        'phi_access_events': len([e for e in audit_events if e.action == 'phi_access']),
        'security_events': len([e for e in audit_events if e.action.startswith('security_')]),
        'events': [
            {
                'timestamp': event.created_at,
                'user_id': event.user_id,
                'action': event.action,
                'description': event.description,
                'ip_address': event.ip_address
            }
            for event in audit_events
        ]
    }
