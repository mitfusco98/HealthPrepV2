import os
import secrets
from datetime import datetime, timedelta
from flask import session, request, current_app
from functools import wraps
import logging

class SecurityManager:
    """Handles security-related operations for HIPAA compliance"""
    
    def __init__(self):
        self.session_timeout = 30  # minutes
        self.max_failed_attempts = 5
        self.lockout_duration = 15  # minutes
    
    def require_admin(self, f):
        """Decorator to require admin privileges"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            if not current_user.is_authenticated or not current_user.is_admin():
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    
    def require_secure_session(self, f):
        """Decorator to require secure session"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_session_valid():
                from flask import redirect, url_for, flash
                flash('Your session has expired. Please log in again.', 'warning')
                return redirect(url_for('login'))
            
            # Update last activity
            session['last_activity'] = datetime.utcnow().isoformat()
            return f(*args, **kwargs)
        return decorated_function
    
    def is_session_valid(self):
        """Check if current session is valid"""
        if 'last_activity' not in session:
            return False
        
        try:
            last_activity = datetime.fromisoformat(session['last_activity'])
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.session_timeout)
            
            return last_activity > timeout_threshold
        except (ValueError, TypeError):
            return False
    
    def generate_csrf_token(self):
        """Generate CSRF token for forms"""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        return session['csrf_token']
    
    def validate_csrf_token(self, token):
        """Validate CSRF token"""
        return secrets.compare_digest(
            session.get('csrf_token', ''),
            token or ''
        )
    
    def log_security_event(self, event_type, details=None):
        """Log security-related events"""
        try:
            from admin.logs import log_admin_action
            from flask_login import current_user
            
            user_id = current_user.id if current_user.is_authenticated else None
            ip_address = request.remote_addr
            
            log_admin_action(
                f'SECURITY_{event_type}',
                details or event_type,
                user_id=user_id,
                ip_address=ip_address
            )
            
        except Exception as e:
            logging.error(f"Failed to log security event: {str(e)}")
    
    def check_password_strength(self, password):
        """Check password strength for HIPAA compliance"""
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    def sanitize_input(self, text):
        """Sanitize user input to prevent XSS"""
        if not text:
            return text
        
        # Basic HTML escaping
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;'
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        return text
    
    def is_safe_redirect_url(self, url):
        """Check if redirect URL is safe"""
        if not url:
            return False
        
        # Only allow relative URLs or same domain
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # Must be relative or same host
        if parsed.netloc and parsed.netloc != request.host:
            return False
        
        # No javascript: or data: schemes
        if parsed.scheme and parsed.scheme.lower() not in ['http', 'https', '']:
            return False
        
        return True
    
    def generate_secure_filename(self, original_filename):
        """Generate secure filename for uploads"""
        from werkzeug.utils import secure_filename
        import uuid
        
        # Get file extension
        name, ext = os.path.splitext(original_filename)
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        safe_name = secure_filename(name)[:50]  # Limit length
        
        return f"{safe_name}_{unique_id}{ext}"
    
    def audit_data_access(self, data_type, patient_id=None, user_action=None):
        """Audit data access for HIPAA compliance"""
        try:
            from flask_login import current_user
            
            details = f"Accessed {data_type}"
            if patient_id:
                details += f" for patient ID {patient_id}"
            if user_action:
                details += f" - {user_action}"
            
            self.log_security_event('DATA_ACCESS', details)
            
        except Exception as e:
            logging.error(f"Failed to audit data access: {str(e)}")

class RateLimiter:
    """Rate limiting for API endpoints"""
    
    def __init__(self):
        self.attempts = {}
        self.rate_limit = 100  # requests per minute
        self.window_size = 60  # seconds
    
    def is_allowed(self, identifier):
        """Check if request is allowed under rate limit"""
        now = datetime.utcnow()
        
        # Clean old entries
        self._cleanup_old_entries(now)
        
        # Check current rate
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        
        # Count requests in current window
        window_start = now - timedelta(seconds=self.window_size)
        recent_attempts = [
            attempt for attempt in self.attempts[identifier]
            if attempt > window_start
        ]
        
        if len(recent_attempts) >= self.rate_limit:
            return False
        
        # Record this attempt
        self.attempts[identifier].append(now)
        return True
    
    def _cleanup_old_entries(self, now):
        """Clean up old rate limit entries"""
        cutoff = now - timedelta(seconds=self.window_size * 2)
        
        for identifier in list(self.attempts.keys()):
            self.attempts[identifier] = [
                attempt for attempt in self.attempts[identifier]
                if attempt > cutoff
            ]
            
            if not self.attempts[identifier]:
                del self.attempts[identifier]

# Global instances
security_manager = SecurityManager()
rate_limiter = RateLimiter()

def init_security(app):
    """Initialize security components"""
    
    @app.before_request
    def security_headers():
        """Add security headers to all responses"""
        pass  # Headers will be added in after_request
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response
    
    @app.context_processor
    def inject_csrf_token():
        """Inject CSRF token into all templates"""
        return dict(csrf_token=security_manager.generate_csrf_token)
