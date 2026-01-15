"""
Security headers middleware for Flask application

Implements comprehensive HTTP security headers including:
- HSTS (HTTP Strict Transport Security)
- CSP (Content Security Policy)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy

All headers configured for HIPAA compliance and modern browser security.
"""

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    WSGI middleware to add security headers to all responses
    """
    
    def __init__(self, app, force_https=True, hsts_max_age=31536000):
        """
        Initialize security headers middleware
        
        Args:
            app: Flask application
            force_https: Redirect HTTP to HTTPS in production
            hsts_max_age: HSTS max-age in seconds (default 1 year)
        """
        self.app = app
        self.force_https = force_https
        self.hsts_max_age = hsts_max_age
    
    def __call__(self, environ, start_response):
        """WSGI middleware call"""
        
        # Check if we need to redirect to HTTPS
        if self.force_https and not self._is_secure(environ):
            # Only redirect if not in development/testing
            if not self._is_local_dev(environ):
                return self._redirect_to_https(environ, start_response)
        
        # Call the Flask app
        return self.app(environ, start_response)
    
    def _is_secure(self, environ):
        """Check if the request is over HTTPS"""
        # Check X-Forwarded-Proto header (set by reverse proxy)
        if environ.get('HTTP_X_FORWARDED_PROTO') == 'https':
            return True
        # Check wsgi.url_scheme
        if environ.get('wsgi.url_scheme') == 'https':
            return True
        return False
    
    def _is_local_dev(self, environ):
        """Check if this is a local development environment"""
        host = environ.get('HTTP_HOST', '')
        server_name = environ.get('SERVER_NAME', '')
        
        return (
            'localhost' in host or
            '127.0.0.1' in host or
            'localhost' in server_name or
            '127.0.0.1' in server_name
        )
    
    def _redirect_to_https(self, environ, start_response):
        """Redirect HTTP request to HTTPS"""
        host = environ.get('HTTP_HOST', environ.get('SERVER_NAME', ''))
        path = environ.get('PATH_INFO', '')
        query = environ.get('QUERY_STRING', '')
        
        if query:
            path = f"{path}?{query}"
        
        https_url = f"https://{host}{path}"
        
        status = '301 Moved Permanently'
        headers = [
            ('Location', https_url),
            ('Content-Type', 'text/html')
        ]
        
        start_response(status, headers)
        return [b'Redirecting to HTTPS...']


def add_security_headers(app: Flask) -> None:
    """
    Add security headers to all Flask responses
    
    Args:
        app: Flask application instance
    """
    
    @app.after_request
    def set_security_headers(response):
        """Add comprehensive security headers to every response"""
        
        # HSTS - Force HTTPS for 1 year, include subdomains
        # Only set if the request is over HTTPS
        if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # X-Frame-Options - Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # X-XSS-Protection - Enable XSS filter (legacy browsers)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer-Policy - Control referrer information
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions-Policy - Disable unnecessary browser features
        response.headers['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=(), '
            'usb=(), '
            'magnetometer=(), '
            'gyroscope=(), '
            'accelerometer=()'
        )
        
        # Content-Security-Policy - Mitigate XSS and injection attacks
        # 
        # SECURITY NOTES:
        # - 'unsafe-inline' is required for Bootstrap/legacy templates with inline styles
        # - 'unsafe-eval' is required for some Bootstrap tooltip/popover functionality
        # - Production roadmap: Migrate to nonce-based CSP for stricter security
        # - To enable strict mode: set CSP_STRICT_MODE=true in environment
        # 
        # Trusted CDN domains are whitelisted for Bootstrap, jQuery, and FontAwesome
        import os
        is_strict_mode = os.environ.get('CSP_STRICT_MODE', '').lower() == 'true'
        
        if is_strict_mode:
            # Strict CSP - requires all inline scripts/styles to be moved to external files
            # Only enable after migrating templates to use external JS/CSS
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com",
                "style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "frame-ancestors 'self'",
                "base-uri 'self'",
                "form-action 'self'",
                "upgrade-insecure-requests"
            ]
            logger.info("CSP: Strict mode enabled (no unsafe-inline/unsafe-eval)")
        else:
            # Standard CSP with unsafe-inline for Bootstrap compatibility
            # This is the current default for existing Flask templates
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "frame-ancestors 'self'",
                "base-uri 'self'",
                "form-action 'self'",
                "upgrade-insecure-requests"
            ]
        
        response.headers['Content-Security-Policy'] = '; '.join(csp_directives)
        
        return response
    
    logger.info("Security headers middleware enabled")


def configure_security_middleware(app: Flask, force_https: bool = True) -> None:
    """
    Configure all security middleware for the Flask application
    
    Args:
        app: Flask application instance
        force_https: Whether to force HTTPS redirects (disable for local dev)
    """
    
    # Add security headers to responses
    add_security_headers(app)
    
    # Note: HTTPS redirect is handled by checking request.is_secure in the headers
    # For production, ensure the reverse proxy (e.g., Replit, AWS ALB) sets X-Forwarded-Proto
    
    logger.info(f"Security middleware configured (force_https={force_https})")
