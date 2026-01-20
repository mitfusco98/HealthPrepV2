"""
Rate Limiting Utility for Prep Sheet Generation

Provides organization-scoped rate limiting to prevent Epic API abuse
and excessive resource consumption from PDF generation.
"""
import logging
import time
from functools import wraps
from collections import defaultdict
from threading import Lock
from flask import request, jsonify
from flask_login import current_user

logger = logging.getLogger(__name__)


class PrepSheetRateLimiter:
    """
    In-memory rate limiter for prep sheet generation.
    
    Limits:
    - Individual generation: 30 per minute per organization
    - Bulk generation: 5 bulk requests per minute per organization
    - Epic writeback: 10 per minute per organization
    
    Thread-safe using locks.
    """
    
    def __init__(self):
        self._individual_requests = defaultdict(list)
        self._bulk_requests = defaultdict(list)
        self._writeback_requests = defaultdict(list)
        self._lock = Lock()
        
        # Rate limits (requests per window)
        self.INDIVIDUAL_LIMIT = 30
        self.BULK_LIMIT = 5
        self.WRITEBACK_LIMIT = 10
        self.WINDOW_SECONDS = 60
    
    def _cleanup_old_requests(self, request_list: list, window_seconds: int) -> list:
        """Remove requests older than the window."""
        cutoff = time.time() - window_seconds
        return [t for t in request_list if t > cutoff]
    
    def _check_rate_limit(self, request_dict: dict, org_id: int, limit: int) -> tuple:
        """
        Check if organization is within rate limit.
        
        Returns:
            tuple: (allowed: bool, remaining: int, reset_seconds: int)
        """
        with self._lock:
            key = org_id
            request_dict[key] = self._cleanup_old_requests(request_dict[key], self.WINDOW_SECONDS)
            
            current_count = len(request_dict[key])
            remaining = max(0, limit - current_count)
            
            if current_count >= limit:
                oldest = min(request_dict[key]) if request_dict[key] else time.time()
                reset_seconds = int(self.WINDOW_SECONDS - (time.time() - oldest))
                return False, 0, max(1, reset_seconds)
            
            request_dict[key].append(time.time())
            return True, remaining - 1, self.WINDOW_SECONDS
    
    def check_individual_limit(self, org_id: int) -> tuple:
        """Check rate limit for individual prep sheet generation."""
        return self._check_rate_limit(self._individual_requests, org_id, self.INDIVIDUAL_LIMIT)
    
    def check_bulk_limit(self, org_id: int) -> tuple:
        """Check rate limit for bulk prep sheet generation."""
        return self._check_rate_limit(self._bulk_requests, org_id, self.BULK_LIMIT)
    
    def check_writeback_limit(self, org_id: int) -> tuple:
        """Check rate limit for Epic writeback operations."""
        return self._check_rate_limit(self._writeback_requests, org_id, self.WRITEBACK_LIMIT)
    
    def get_usage_stats(self, org_id: int) -> dict:
        """Get current rate limit usage for an organization."""
        with self._lock:
            individual = self._cleanup_old_requests(self._individual_requests[org_id], self.WINDOW_SECONDS)
            bulk = self._cleanup_old_requests(self._bulk_requests[org_id], self.WINDOW_SECONDS)
            writeback = self._cleanup_old_requests(self._writeback_requests[org_id], self.WINDOW_SECONDS)
            
            return {
                'individual': {
                    'used': len(individual),
                    'limit': self.INDIVIDUAL_LIMIT,
                    'remaining': max(0, self.INDIVIDUAL_LIMIT - len(individual))
                },
                'bulk': {
                    'used': len(bulk),
                    'limit': self.BULK_LIMIT,
                    'remaining': max(0, self.BULK_LIMIT - len(bulk))
                },
                'writeback': {
                    'used': len(writeback),
                    'limit': self.WRITEBACK_LIMIT,
                    'remaining': max(0, self.WRITEBACK_LIMIT - len(writeback))
                },
                'window_seconds': self.WINDOW_SECONDS
            }


# Global rate limiter instance
prep_sheet_limiter = PrepSheetRateLimiter()


def rate_limit_individual(f):
    """Decorator to rate limit individual prep sheet generation."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        org_id = current_user.org_id
        allowed, remaining, reset = prep_sheet_limiter.check_individual_limit(org_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for org {org_id}: individual prep sheet generation")
            from flask import flash, redirect, url_for
            flash(f'Rate limit exceeded. Please wait {reset} seconds before generating more prep sheets.', 'warning')
            return redirect(url_for('main.dashboard'))
        
        response = f(*args, **kwargs)
        return response
    
    return decorated_function


def rate_limit_bulk(f):
    """Decorator to rate limit bulk prep sheet generation."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        org_id = current_user.org_id
        allowed, remaining, reset = prep_sheet_limiter.check_bulk_limit(org_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for org {org_id}: bulk prep sheet generation")
            from flask import flash
            flash(f'Bulk generation rate limit exceeded. Please wait {reset} seconds before starting another batch.', 'warning')
            from flask import redirect, url_for
            return redirect(url_for('prep_sheet.batch_generate'))
        
        response = f(*args, **kwargs)
        return response
    
    return decorated_function


def rate_limit_writeback(f):
    """Decorator to rate limit Epic writeback operations (JSON API endpoints)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        org_id = current_user.org_id
        allowed, remaining, reset = prep_sheet_limiter.check_writeback_limit(org_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for org {org_id}: Epic writeback")
            return jsonify({
                'success': False,
                'error': f'Epic writeback rate limit exceeded. Please wait {reset} seconds to prevent API throttling.',
                'retry_after': reset,
                'limit': prep_sheet_limiter.WRITEBACK_LIMIT,
                'window': prep_sheet_limiter.WINDOW_SECONDS
            }), 429
        
        response = f(*args, **kwargs)
        return response
    
    return decorated_function
