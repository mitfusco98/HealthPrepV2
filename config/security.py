"""
Security configuration and HIPAA compliance settings.
Implements role-based access control and security policies.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from functools import wraps
from flask import request, abort, current_app
from flask_login import current_user

# Role Definitions
ROLES = {
    'admin': {
        'name': 'Administrator',
        'permissions': [
            'admin_access',
            'user_management',
            'system_config',
            'phi_access',
            'audit_logs',
            'screening_management',
            'patient_management',
            'document_management',
            'prep_sheet_generation',
            'analytics_access',
            'backup_restore'
        ]
    },
    'user': {
        'name': 'Standard User',
        'permissions': [
            'patient_management',
            'document_management',
            'prep_sheet_generation',
            'screening_management',
            'phi_access'
        ]
    },
    'nurse': {
        'name': 'Nurse',
        'permissions': [
            'patient_management',
            'document_management',
            'prep_sheet_generation',
            'screening_management',
            'phi_access'
        ]
    },
    'ma': {
        'name': 'Medical Assistant',
        'permissions': [
            'patient_management',
            'document_management',
            'prep_sheet_generation',
            'phi_access'
        ]
    }
}

# HIPAA Security Requirements
HIPAA_PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digits': True,
    'require_special_chars': True,
    'max_age_days': 90,
    'history_count': 12,  # Cannot reuse last 12 passwords
    'lockout_attempts': 5,
    'lockout_duration_minutes': 30
}

# Session Security
SESSION_SECURITY = {
    'timeout_minutes': 30,
    'absolute_timeout_hours': 8,
    'require_https': os.getenv('REQUIRE_HTTPS', 'True').lower() == 'true',
    'secure_cookies': True,
    'httponly_cookies': True,
    'samesite_cookies': 'Strict'
}

# Audit Requirements
AUDIT_REQUIREMENTS = {
    'log_all_phi_access': True,
    'log_authentication': True,
    'log_data_modifications': True,
    'log_admin_actions': True,
    'log_failed_attempts': True,
    'retention_years': 7
}

# IP Address Restrictions (optional)
ALLOWED_IP_RANGES = os.getenv('ALLOWED_IP_RANGES', '').split(',') if os.getenv('ALLOWED_IP_RANGES') else []
BLOCKED_IP_ADDRESSES = os.getenv('BLOCKED_IP_ADDRESSES', '').split(',') if os.getenv('BLOCKED_IP_ADDRESSES') else []

class SecurityManager:
    """Manages security policies and access control"""
    
    def __init__(self):
        self.failed_login_attempts = {}
        self.locked_accounts = {}
    
    def check_permission(self, user, permission: str) -> bool:
        """Check if user has specific permission"""
        if not user or not user.is_authenticated:
            return False
        
        user_role = getattr(user, 'role', 'user')
        role_config = ROLES.get(user_role, ROLES['user'])
        
        return permission in role_config.get('permissions', [])
    
    def check_ip_restrictions(self, ip_address: str) -> bool:
        """Check if IP address is allowed"""
        if not ALLOWED_IP_RANGES and not BLOCKED_IP_ADDRESSES:
            return True
        
        # Check blocked IPs first
        if ip_address in BLOCKED_IP_ADDRESSES:
            return False
        
        # If allowed ranges are specified, check them
        if ALLOWED_IP_RANGES:
            return self._ip_in_ranges(ip_address, ALLOWED_IP_RANGES)
        
        return True
    
    def _ip_in_ranges(self, ip: str, ranges: List[str]) -> bool:
        """Check if IP is in allowed ranges"""
        import ipaddress
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            for range_str in ranges:
                if '/' in range_str:
                    # CIDR notation
                    network = ipaddress.ip_network(range_str, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    # Single IP
                    if str(ip_obj) == range_str.strip():
                        return True
            return False
        except ValueError:
            return False
    
    def record_failed_login(self, username: str, ip_address: str) -> bool:
        """Record failed login attempt and check if account should be locked"""
        key = f"{username}:{ip_address}"
        current_time = datetime.utcnow()
        
        if key not in self.failed_login_attempts:
            self.failed_login_attempts[key] = []
        
        # Clean old attempts (older than lockout duration)
        cutoff_time = current_time - timedelta(minutes=HIPAA_PASSWORD_POLICY['lockout_duration_minutes'])
        self.failed_login_attempts[key] = [
            attempt for attempt in self.failed_login_attempts[key] 
            if attempt > cutoff_time
        ]
        
        # Add current attempt
        self.failed_login_attempts[key].append(current_time)
        
        # Check if should be locked
        if len(self.failed_login_attempts[key]) >= HIPAA_PASSWORD_POLICY['lockout_attempts']:
            self.locked_accounts[username] = current_time + timedelta(
                minutes=HIPAA_PASSWORD_POLICY['lockout_duration_minutes']
            )
            return True
        
        return False
    
    def is_account_locked(self, username: str) -> bool:
        """Check if account is currently locked"""
        if username in self.locked_accounts:
            if datetime.utcnow() < self.locked_accounts[username]:
                return True
            else:
                # Lock expired, remove it
                del self.locked_accounts[username]
        
        return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validate password against HIPAA requirements"""
        issues = []
        
        if len(password) < HIPAA_PASSWORD_POLICY['min_length']:
            issues.append(f"Password must be at least {HIPAA_PASSWORD_POLICY['min_length']} characters long")
        
        if HIPAA_PASSWORD_POLICY['require_uppercase'] and not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        
        if HIPAA_PASSWORD_POLICY['require_lowercase'] and not any(c.islower() for c in password):
            issues.append("Password must contain at least one lowercase letter")
        
        if HIPAA_PASSWORD_POLICY['require_digits'] and not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one digit")
        
        if HIPAA_PASSWORD_POLICY['require_special_chars']:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                issues.append("Password must contain at least one special character")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'strength_score': self._calculate_password_strength(password)
        }
    
    def _calculate_password_strength(self, password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length score (up to 25 points)
        score += min(25, len(password) * 2)
        
        # Character variety (up to 75 points)
        if any(c.isupper() for c in password):
            score += 15
        if any(c.islower() for c in password):
            score += 15
        if any(c.isdigit() for c in password):
            score += 15
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 15
        
        # Uniqueness bonus
        unique_chars = len(set(password))
        if unique_chars > len(password) * 0.7:
            score += 15
        
        return min(100, score)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for secure storage"""
        return hashlib.sha256(data.encode()).hexdigest()

# Security Decorators
def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = SecurityManager()
            if not security_manager.check_permission(current_user, permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_admin():
    """Decorator to require admin role"""
    return require_permission('admin_access')

def require_phi_access():
    """Decorator to require PHI access permission"""
    return require_permission('phi_access')

def ip_restriction():
    """Decorator to enforce IP restrictions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = SecurityManager()
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if not security_manager.check_ip_restrictions(client_ip):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def audit_log(action: str):
    """Decorator to automatically log actions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from admin.logs import log_user_action
            
            # Execute function
            result = f(*args, **kwargs)
            
            # Log action
            details = f"Function: {f.__name__}, Args: {args}, Kwargs: {kwargs}"
            log_user_action(action, details)
            
            return result
        return decorated_function
    return decorator

# Security Middleware
class SecurityMiddleware:
    """WSGI middleware for security headers and policies"""
    
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        def new_start_response(status, response_headers):
            # Add security headers
            security_headers = [
                ('X-Content-Type-Options', 'nosniff'),
                ('X-Frame-Options', 'DENY'),
                ('X-XSS-Protection', '1; mode=block'),
                ('Strict-Transport-Security', 'max-age=31536000; includeSubDomains'),
                ('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.replit.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.replit.com https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:"),
                ('Referrer-Policy', 'strict-origin-when-cross-origin'),
                ('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
            ]
            
            response_headers.extend(security_headers)
            return start_response(status, response_headers)
        
        return self.app(environ, new_start_response)

# HIPAA Compliance Checker
class HIPAACompliance:
    """Utility class for HIPAA compliance validation"""
    
    @staticmethod
    def check_minimum_necessary(user_role: str, requested_data: str) -> bool:
        """Check if data access follows minimum necessary principle"""
        # Define what data each role needs access to
        role_data_access = {
            'admin': ['all'],
            'user': ['patient_data', 'screening_data', 'documents'],
            'nurse': ['patient_data', 'screening_data', 'documents'],
            'ma': ['patient_data', 'screening_data', 'documents']
        }
        
        allowed_data = role_data_access.get(user_role, [])
        return 'all' in allowed_data or requested_data in allowed_data
    
    @staticmethod
    def requires_audit_log(action: str) -> bool:
        """Check if action requires audit logging"""
        audit_actions = [
            'phi_access',
            'patient_create',
            'patient_update',
            'document_view',
            'document_upload',
            'prep_sheet_generate',
            'user_login',
            'user_logout',
            'admin_action'
        ]
        
        return action in audit_actions
    
    @staticmethod
    def get_data_retention_policy() -> Dict[str, int]:
        """Get data retention periods in days"""
        return {
            'patient_data': AUDIT_REQUIREMENTS['retention_years'] * 365,
            'audit_logs': AUDIT_REQUIREMENTS['retention_years'] * 365,
            'session_data': 1,  # 1 day
            'temp_files': 7,    # 7 days
            'backup_data': 2555  # 7 years
        }

# Initialize security manager
security_manager = SecurityManager()
