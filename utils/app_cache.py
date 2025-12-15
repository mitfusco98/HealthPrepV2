"""
Application-level cache for expensive queries.
Uses in-memory dictionary with TTL for single-instance deployments.
Thread-safe using threading locks.
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Set, Any

import logging

logger = logging.getLogger(__name__)

_cache = {}
_cache_lock = threading.Lock()
_cache_ttl_seconds = 3600  # 1 hour default TTL


def get_cached_priority_patients(org_id: int) -> Optional[Set[int]]:
    """
    Get cached priority patient IDs for an organization.
    
    Returns:
        Set of patient IDs if cache is valid, None if cache is stale or missing
    """
    cache_key = f'priority_patients_{org_id}'
    
    with _cache_lock:
        if cache_key in _cache:
            entry = _cache[cache_key]
            if datetime.utcnow() - entry['timestamp'] < timedelta(seconds=_cache_ttl_seconds):
                return entry['data']
            else:
                del _cache[cache_key]
    
    return None


def set_cached_priority_patients(org_id: int, patient_ids: Set[int]) -> None:
    """
    Cache priority patient IDs for an organization.
    
    Args:
        org_id: Organization ID
        patient_ids: Set of patient IDs to cache
    """
    cache_key = f'priority_patients_{org_id}'
    
    with _cache_lock:
        _cache[cache_key] = {
            'data': patient_ids,
            'timestamp': datetime.utcnow()
        }


def invalidate_priority_patients_cache(org_id: int) -> None:
    """
    Invalidate the priority patients cache for an organization.
    Call this when appointments are synced or updated.
    """
    cache_key = f'priority_patients_{org_id}'
    
    with _cache_lock:
        if cache_key in _cache:
            del _cache[cache_key]
            logger.info(f"Invalidated priority patients cache for org {org_id}")


def get_cache_stats() -> dict:
    """Get statistics about the cache for monitoring."""
    with _cache_lock:
        stats = {
            'total_entries': len(_cache),
            'entries': {}
        }
        for key, entry in _cache.items():
            age_seconds = (datetime.utcnow() - entry['timestamp']).total_seconds()
            stats['entries'][key] = {
                'age_seconds': age_seconds,
                'size': len(entry['data']) if hasattr(entry['data'], '__len__') else 1
            }
        return stats
