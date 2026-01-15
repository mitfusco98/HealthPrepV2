"""
Provider Scope Service - Enforces provider-level data isolation

This module provides utilities for:
1. Getting the current user's active provider context
2. Applying provider scope filters to queries
3. Validating provider access in routes

Security: All PHI-related queries should go through these utilities
to ensure proper provider isolation.
"""

import logging
from typing import Optional, List, Any
from flask import session, g
from flask_login import current_user
from functools import wraps

from app import db
from models import Provider, UserProviderAssignment, Patient, Screening, Appointment

logger = logging.getLogger(__name__)


def get_user_providers(user) -> List[Provider]:
    """
    Get all providers a user can access.
    
    - Admins: All providers in their organization
    - Staff: Only assigned providers
    - Practitioners: Their own provider + assigned
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_root_admin:
        return []
    
    if user.is_admin_user():
        return Provider.query.filter_by(
            org_id=user.org_id,
            is_active=True
        ).all()
    
    provider_ids = []
    
    if user.provider_id:
        provider_ids.append(user.provider_id)
    
    assignments = UserProviderAssignment.query.filter_by(
        user_id=user.id
    ).all()
    
    for assignment in assignments:
        if assignment.provider_id not in provider_ids:
            provider_ids.append(assignment.provider_id)
    
    if not provider_ids:
        return []
    
    return Provider.query.filter(
        Provider.id.in_(provider_ids),
        Provider.is_active == True
    ).all()


def get_user_provider_ids(user) -> List[int]:
    """Get list of provider IDs user can access"""
    return [p.id for p in get_user_providers(user)]


def get_active_provider(user) -> Optional[Provider]:
    """
    Get the currently active provider for a user.
    
    Uses session storage to remember which provider the user
    has selected (for multi-provider users).
    """
    if not user or not user.is_authenticated:
        return None
    
    provider_id = session.get('active_provider_id')
    
    if provider_id:
        provider = Provider.query.filter_by(
            id=provider_id,
            is_active=True
        ).first()
        
        if provider:
            if user.is_admin_user() and provider.org_id == user.org_id:
                return provider
            elif user.can_access_provider(provider_id):
                return provider
            else:
                session.pop('active_provider_id', None)
    
    if user.provider_id:
        provider = Provider.query.filter_by(
            id=user.provider_id,
            is_active=True
        ).first()
        if provider:
            session['active_provider_id'] = provider.id
            return provider
    
    providers = get_user_providers(user)
    if providers:
        session['active_provider_id'] = providers[0].id
        return providers[0]
    
    return None


def set_active_provider(user, provider_id: int) -> bool:
    """
    Set the active provider for the current session.
    
    Returns True if successful, False if user cannot access the provider.
    """
    if not user or not user.is_authenticated:
        return False
    
    provider = Provider.query.filter_by(
        id=provider_id,
        is_active=True
    ).first()
    
    if not provider:
        return False
    
    if user.is_admin_user() and provider.org_id == user.org_id:
        session['active_provider_id'] = provider_id
        return True
    
    if user.can_access_provider(provider_id):
        session['active_provider_id'] = provider_id
        return True
    
    return False


def apply_provider_scope(query, model, user, all_providers: bool = False):
    """
    Apply provider scope filter to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        model: Model class being queried (must have provider_id column)
        user: Current user
        all_providers: If True, filter to all user's accessible providers.
                       If False, filter to active provider only.
    
    Returns:
        Filtered query
    """
    if not user or not user.is_authenticated:
        return query.filter(False)
    
    if user.is_root_admin:
        return query
    
    query = query.filter(model.org_id == user.org_id)
    
    if not hasattr(model, 'provider_id'):
        return query
    
    if all_providers:
        provider_ids = get_user_provider_ids(user)
        if not provider_ids:
            if user.is_admin_user():
                return query
            return query.filter(False)
        
        return query.filter(
            db.or_(
                model.provider_id.in_(provider_ids),
                model.provider_id.is_(None)
            )
        )
    else:
        active_provider = get_active_provider(user)
        if not active_provider:
            if user.is_admin_user():
                return query
            return query.filter(False)
        
        return query.filter(
            db.or_(
                model.provider_id == active_provider.id,
                model.provider_id.is_(None)
            )
        )


def get_provider_patients(user, all_providers: bool = False):
    """
    Get patients scoped to user's provider access.
    
    Args:
        user: Current user
        all_providers: If True, get patients from all accessible providers
                      If False, get patients from active provider only
    
    Returns:
        SQLAlchemy query for Patient
    """
    query = Patient.query
    return apply_provider_scope(query, Patient, user, all_providers)


def get_provider_screenings(user, all_providers: bool = False, include_superseded: bool = False):
    """
    Get screenings scoped to user's provider access.
    
    Args:
        user: Current user
        all_providers: If True, get screenings from all accessible providers
        include_superseded: If True, include 'superseded' status screenings (default False)
                           Superseded screenings are variant screenings that were replaced
                           by a more specific variant (e.g., general -> PCOS variant)
    """
    query = Screening.query
    
    # Filter out superseded screenings by default
    # These are obsolete variant screenings replaced by more specific variants
    if not include_superseded:
        query = query.filter(Screening.status != 'superseded')
    
    return apply_provider_scope(query, Screening, user, all_providers)


def get_provider_appointments(user, all_providers: bool = False):
    """
    Get appointments scoped to user's provider access.
    """
    query = Appointment.query
    return apply_provider_scope(query, Appointment, user, all_providers)


def validate_patient_access(user, patient: Patient) -> bool:
    """
    Check if user can access a specific patient.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_root_admin:
        return True
    
    if patient.org_id != user.org_id:
        return False
    
    if user.is_admin_user():
        return True
    
    if not patient.provider_id:
        return True
    
    return user.can_access_provider(patient.provider_id)


def validate_screening_access(user, screening: Screening) -> bool:
    """
    Check if user can access a specific screening.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_root_admin:
        return True
    
    if screening.org_id != user.org_id:
        return False
    
    if user.is_admin_user():
        return True
    
    if not screening.provider_id:
        return True
    
    return user.can_access_provider(screening.provider_id)


def require_provider_context(f):
    """
    Decorator that ensures user has an active provider context.
    
    Injects 'active_provider' into g for use in the route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import flash, redirect, url_for
        
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.is_admin_user():
            providers = get_user_providers(current_user)
            if providers:
                g.active_provider = get_active_provider(current_user) or providers[0]
            else:
                g.active_provider = None
            return f(*args, **kwargs)
        
        active_provider = get_active_provider(current_user)
        
        if not active_provider:
            flash('No provider assigned. Please contact your administrator.', 'warning')
            return redirect(url_for('auth.logout'))
        
        g.active_provider = active_provider
        return f(*args, **kwargs)
    
    return decorated_function


def inject_provider_context():
    """
    Call this in before_request to inject provider context into templates.
    """
    if current_user.is_authenticated:
        g.user_providers = get_user_providers(current_user)
        g.active_provider = get_active_provider(current_user)
        g.has_multiple_providers = len(g.user_providers) > 1
    else:
        g.user_providers = []
        g.active_provider = None
        g.has_multiple_providers = False
