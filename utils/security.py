"""
Security utilities for HealthPrep application
Provides rate limiting, security token management, and hardening functions
"""

import secrets
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Tuple
from flask import request, session, g

logger = logging.getLogger(__name__)

# In-memory rate limiting storage (for single-instance deployment)
# For production multi-instance deployment, use Redis
_rate_limit_storage: Dict[str, Dict] = {}

# Redis connection for distributed rate limiting (production)
_redis_client = None


def _get_redis_client():
    """
    Get Redis client for distributed rate limiting in production.
    
    SECURITY: In production with multiple instances, in-memory rate limiting
    doesn't work - attackers can hit different instances to bypass limits.
    Redis provides centralized rate limit tracking across all instances.
    
    Configure via REDIS_URL environment variable.
    Falls back to in-memory storage if Redis is not available.
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    redis_url = os.environ.get('REDIS_URL')
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if redis_url:
        try:
            import redis
            _redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            _redis_client.ping()
            logger.info("Redis connected for distributed rate limiting")
            return _redis_client
        except ImportError:
            if is_production:
                logger.warning(
                    "SECURITY: Redis package not installed but REDIS_URL is set. "
                    "Install redis package for distributed rate limiting in production."
                )
            _redis_client = False  # Mark as unavailable
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if is_production:
                logger.warning(
                    "SECURITY: Redis connection failed in production. "
                    "Rate limiting will use in-memory storage (NOT distributed across instances)."
                )
            _redis_client = False  # Mark as unavailable
    else:
        if is_production:
            logger.warning(
                "SECURITY: REDIS_URL not configured in production. "
                "Rate limiting will use in-memory storage (NOT distributed across instances). "
                "Set REDIS_URL for proper distributed rate limiting."
            )
        _redis_client = False  # Mark as unavailable
    
    return None


class RateLimiter:
    """
    Rate limiter for security-sensitive endpoints.
    Implements sliding window rate limiting with lockout support.
    """
    
    # Default limits for different endpoint types
    LIMITS = {
        'password_reset': {'max_attempts': 5, 'window_seconds': 300, 'lockout_seconds': 900},  # 5 per 5min, 15min lockout
        'username_retrieval': {'max_attempts': 5, 'window_seconds': 300, 'lockout_seconds': 900},
        'security_question': {'max_attempts': 3, 'window_seconds': 300, 'lockout_seconds': 1800},  # 3 per 5min, 30min lockout
        '2fa_verification': {'max_attempts': 5, 'window_seconds': 300, 'lockout_seconds': 1800},
        'login': {'max_attempts': 5, 'window_seconds': 300, 'lockout_seconds': 1800},
        'api_general': {'max_attempts': 100, 'window_seconds': 60, 'lockout_seconds': 300}
    }
    
    @classmethod
    def _get_client_key(cls, endpoint_type: str, identifier: Optional[str] = None) -> str:
        """Generate a unique key for the client based on IP and optional identifier"""
        ip = request.remote_addr or 'unknown'
        if identifier:
            return f"{endpoint_type}:{ip}:{identifier}"
        return f"{endpoint_type}:{ip}"
    
    @classmethod
    def _cleanup_expired_entries(cls):
        """Remove expired entries from storage"""
        current_time = time.time()
        expired_keys = []
        
        for key, data in _rate_limit_storage.items():
            # Remove entries that are past their lockout period
            if data.get('locked_until', 0) < current_time and data.get('last_attempt', 0) < current_time - 3600:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _rate_limit_storage[key]
    
    @classmethod
    def check_rate_limit(cls, endpoint_type: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[int]]:
        """
        Check if the request should be rate limited.
        
        Uses Redis for distributed rate limiting in production (if available),
        falls back to in-memory storage for single-instance deployments.
        
        Args:
            endpoint_type: Type of endpoint (password_reset, login, etc.)
            identifier: Optional additional identifier (email, username)
            
        Returns:
            Tuple of (is_allowed, seconds_until_allowed)
        """
        redis_client = _get_redis_client()
        
        if redis_client:
            return cls._check_rate_limit_redis(endpoint_type, identifier, redis_client)
        else:
            return cls._check_rate_limit_memory(endpoint_type, identifier)
    
    @classmethod
    def _check_rate_limit_redis(cls, endpoint_type: str, identifier: Optional[str], redis_client) -> Tuple[bool, Optional[int]]:
        """Check rate limit using Redis (distributed)"""
        current_time = int(time.time())
        key = f"ratelimit:{cls._get_client_key(endpoint_type, identifier)}"
        lockout_key = f"{key}:lockout"
        limits = cls.LIMITS.get(endpoint_type, cls.LIMITS['api_general'])
        
        try:
            # Check if currently locked out
            lockout_ttl = redis_client.ttl(lockout_key)
            if lockout_ttl and lockout_ttl > 0:
                logger.warning(f"Rate limit lockout active for {key}, {lockout_ttl}s remaining")
                return False, lockout_ttl
            
            # Count attempts in the current window using a sorted set
            window_start = current_time - limits['window_seconds']
            
            # Remove old entries and count current ones
            redis_client.zremrangebyscore(key, 0, window_start)
            attempt_count = redis_client.zcard(key)
            
            if attempt_count >= limits['max_attempts']:
                # Trigger lockout
                redis_client.setex(lockout_key, limits['lockout_seconds'], '1')
                logger.warning(f"Rate limit exceeded for {key}, lockout for {limits['lockout_seconds']}s")
                return False, limits['lockout_seconds']
            
            return True, None
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}, falling back to in-memory")
            return cls._check_rate_limit_memory(endpoint_type, identifier)
    
    @classmethod
    def _check_rate_limit_memory(cls, endpoint_type: str, identifier: Optional[str]) -> Tuple[bool, Optional[int]]:
        """Check rate limit using in-memory storage (single-instance only)"""
        current_time = time.time()
        key = cls._get_client_key(endpoint_type, identifier)
        limits = cls.LIMITS.get(endpoint_type, cls.LIMITS['api_general'])
        
        # Cleanup periodically
        if len(_rate_limit_storage) > 10000:
            cls._cleanup_expired_entries()
        
        # Get or create entry
        if key not in _rate_limit_storage:
            _rate_limit_storage[key] = {
                'attempts': [],
                'locked_until': 0
            }
        
        entry = _rate_limit_storage[key]
        
        # Check if currently locked out
        if entry['locked_until'] > current_time:
            remaining = int(entry['locked_until'] - current_time)
            logger.warning(f"Rate limit lockout active for {key}, {remaining}s remaining")
            return False, remaining
        
        # Clean up old attempts outside the window
        window_start = current_time - limits['window_seconds']
        entry['attempts'] = [t for t in entry['attempts'] if t > window_start]
        
        # Check if under limit
        if len(entry['attempts']) >= limits['max_attempts']:
            # Trigger lockout
            entry['locked_until'] = current_time + limits['lockout_seconds']
            logger.warning(f"Rate limit exceeded for {key}, lockout for {limits['lockout_seconds']}s")
            return False, limits['lockout_seconds']
        
        return True, None
    
    @classmethod
    def record_attempt(cls, endpoint_type: str, identifier: Optional[str] = None, success: bool = False):
        """
        Record an attempt at the endpoint.
        
        Uses Redis for distributed tracking in production (if available),
        falls back to in-memory storage for single-instance deployments.
        
        Args:
            endpoint_type: Type of endpoint
            identifier: Optional additional identifier
            success: If True and successful, reset the attempt counter
        """
        redis_client = _get_redis_client()
        
        if redis_client:
            cls._record_attempt_redis(endpoint_type, identifier, success, redis_client)
        else:
            cls._record_attempt_memory(endpoint_type, identifier, success)
    
    @classmethod
    def _record_attempt_redis(cls, endpoint_type: str, identifier: Optional[str], success: bool, redis_client):
        """Record attempt using Redis"""
        current_time = int(time.time())
        key = f"ratelimit:{cls._get_client_key(endpoint_type, identifier)}"
        lockout_key = f"{key}:lockout"
        limits = cls.LIMITS.get(endpoint_type, cls.LIMITS['api_general'])
        
        try:
            if success:
                # Successful attempt - delete keys
                redis_client.delete(key, lockout_key)
                logger.info(f"Rate limit reset for {key} due to successful attempt")
            else:
                # Failed attempt - add to sorted set with timestamp as score
                redis_client.zadd(key, {str(current_time): current_time})
                # Set TTL on the key to auto-cleanup
                redis_client.expire(key, limits['window_seconds'] + limits['lockout_seconds'])
        except Exception as e:
            logger.error(f"Redis record_attempt failed: {e}, falling back to in-memory")
            cls._record_attempt_memory(endpoint_type, identifier, success)
    
    @classmethod
    def _record_attempt_memory(cls, endpoint_type: str, identifier: Optional[str], success: bool):
        """Record attempt using in-memory storage"""
        current_time = time.time()
        key = cls._get_client_key(endpoint_type, identifier)
        
        if key not in _rate_limit_storage:
            _rate_limit_storage[key] = {
                'attempts': [],
                'locked_until': 0
            }
        
        entry = _rate_limit_storage[key]
        
        if success:
            # Successful attempt - reset counters
            entry['attempts'] = []
            entry['locked_until'] = 0
            logger.info(f"Rate limit reset for {key} due to successful attempt")
        else:
            # Failed attempt - record it
            entry['attempts'].append(current_time)
            entry['last_attempt'] = current_time


def rate_limit(endpoint_type: str, get_identifier=None):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        endpoint_type: Type of endpoint for rate limit configuration
        get_identifier: Optional function to extract identifier from request
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            identifier = None
            if get_identifier:
                try:
                    identifier = get_identifier()
                except Exception:
                    pass
            
            is_allowed, wait_time = RateLimiter.check_rate_limit(endpoint_type, identifier)
            
            if not is_allowed:
                from flask import flash, redirect, url_for
                wait_minutes = (wait_time // 60) if wait_time else 5
                flash(f'Too many attempts. Please wait {wait_minutes} minutes before trying again.', 'error')
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token"""
    return secrets.token_urlsafe(length)


def hash_token_for_storage(token: str) -> str:
    """
    Hash a token for secure storage.
    The original token is given to the user, but only the hash is stored.
    This prevents token theft from the database.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, stored_hash: str) -> bool:
    """Verify a token against its stored hash"""
    computed_hash = hash_token_for_storage(token)
    return secrets.compare_digest(computed_hash, stored_hash)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Perform constant-time string comparison to prevent timing attacks"""
    return secrets.compare_digest(val1, val2)


def get_password_reset_expiry(minutes: int = 30) -> datetime:
    """
    Get expiry time for password reset tokens.
    Shortened from 1 hour to 30 minutes for security.
    """
    return datetime.utcnow() + timedelta(minutes=minutes)


def log_security_event(event_type: str, details: dict, user_id: Optional[int] = None, org_id: Optional[int] = None):
    """
    Log security-related events for audit trail.
    
    Args:
        event_type: Type of security event
        details: Additional event details
        user_id: Optional user ID involved
        org_id: Optional organization ID
    """
    from models import log_admin_event
    
    # Ensure we don't log sensitive data
    safe_details = {k: v for k, v in details.items() if k not in ['password', 'token', 'secret']}
    safe_details['ip_address'] = request.remote_addr
    safe_details['user_agent'] = request.user_agent.string[:200] if request.user_agent else 'unknown'
    
    try:
        log_admin_event(
            event_type=f'security_{event_type}',
            user_id=user_id or 0,
            org_id=org_id or 0,
            ip=request.remote_addr,
            data=safe_details,
            action_details=f'Security event: {event_type}'
        )
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")


def invalidate_all_user_tokens(user_id: int):
    """Invalidate all password reset tokens for a user after successful reset"""
    from models import User, db
    
    try:
        user = User.query.get(user_id)
        if user:
            user.password_reset_token = None
            user.password_reset_expires = None
            db.session.commit()
            logger.info(f"Invalidated all tokens for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to invalidate tokens for user {user_id}: {e}")


def add_security_headers(response):
    """Add security headers to response"""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Content Security Policy (basic)
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self';"
    
    return response
