"""
Subscription Status Middleware
Enforces access control based on organization subscription status
Uses unified billing_state for consistent access decisions
"""

from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def subscription_required(f):
    """
    Decorator to enforce active subscription using unified billing_state.
    
    Blocks access if:
    - Trial has expired and no active subscription
    - Subscription is past_due, canceled, or incomplete
    - Organization is suspended
    - Organization is pending approval
    
    Allows access if:
    - Subscription is active
    - Trial is active (trialing with valid trial_expires)
    - Manual billing organization (enterprise)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow access if user is not logged in (let login_required handle it)
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        # Root admins bypass subscription check
        if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
            return f(*args, **kwargs)
        
        # Check organization subscription status
        org = current_user.organization
        if not org:
            flash('Organization not found. Please contact support.', 'error')
            return redirect(url_for('auth.login'))
        
        # Use unified billing_state for access decision
        billing = org.billing_state
        state = billing['state']
        
        logger.debug(f"Subscription check for org {org.id}: state={state}, can_access_app={billing['can_access_app']}")
        
        # Handle different billing states
        if state == 'active':
            # Full access for active subscriptions (includes legacy trials mapped to active)
            return f(*args, **kwargs)
        
        elif state == 'payment_required':
            flash('Your payment is past due. Please update your payment method.', 'warning')
            return redirect(url_for('auth.payment_required'))
        
        elif state == 'suspended':
            flash('Your account has been suspended. Please contact support.', 'error')
            return redirect(url_for('auth.account_suspended'))
        
        elif state == 'canceled':
            flash('Your subscription has been canceled. Please contact support or reactivate.', 'error')
            return redirect(url_for('auth.account_suspended'))
        
        elif state == 'paused':
            flash('Your subscription is paused. Please resume your subscription to continue.', 'warning')
            return redirect(url_for('auth.subscription_expired'))
        
        elif state == 'pending_approval':
            # Pending approval organizations can still access the app for onboarding
            # They just can't access Epic OAuth until approved
            if billing['can_access_app']:
                return f(*args, **kwargs)
            else:
                flash('Your account is pending approval. Please check back soon.', 'info')
                return redirect(url_for('auth.login'))
        
        else:
            # Unknown state - fall back to is_active check for safety
            if org.is_active:
                return f(*args, **kwargs)
            else:
                flash('Your account is not active. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
    
    return decorated_function


def oauth_access_required(f):
    """
    Decorator specifically for Epic OAuth routes.
    
    Requires:
    - Active subscription (subscription_status = 'active')
    - Or manual billing organization
    
    Blocks:
    - Pending approval organizations (can onboard but not connect to Epic)
    - Trial expired
    - Payment issues
    - Suspended/canceled
    
    This is stricter than subscription_required because Epic OAuth should only
    be available to fully approved and paying organizations.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        
        if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
            return f(*args, **kwargs)
        
        org = current_user.organization
        if not org:
            flash('Organization not found. Please contact support.', 'error')
            return redirect(url_for('auth.login'))
        
        billing = org.billing_state
        
        logger.debug(f"OAuth access check for org {org.id}: state={billing['state']}, can_access_oauth={billing['can_access_oauth']}")
        
        if billing['can_access_oauth']:
            return f(*args, **kwargs)
        
        if billing['state'] == 'pending_approval':
            flash('Epic connection is only available after your account is approved. Please complete your onboarding and await approval.', 'info')
            return redirect(url_for('admin.dashboard'))
        
        elif billing['state'] == 'payment_required':
            flash('Please update your payment method to access Epic integration.', 'warning')
            return redirect(url_for('auth.payment_required'))
        
        elif billing['state'] in ['suspended', 'canceled']:
            flash('Your account is not active. Please contact support.', 'error')
            return redirect(url_for('auth.account_suspended'))
        
        else:
            flash('Epic connection requires an active subscription.', 'warning')
            return redirect(url_for('auth.subscription_expired'))
    
    return decorated_function


def trial_warning_required(f):
    """
    DEPRECATED: Trial periods have been removed from the billing model.
    
    This decorator is kept for backwards compatibility but no longer shows trial warnings.
    Organizations are now either pending_approval (onboarding) or active (paying).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # No trial warnings needed - billing model simplified to approval-based flow
        return f(*args, **kwargs)
    
    return decorated_function


def get_subscription_context():
    """
    Get subscription status context for templates
    Returns dict with subscription info to display in UI
    Uses unified billing_state for consistent information
    
    SIMPLIFIED BILLING MODEL:
    - Organizations are either pending_approval (onboarding) or active (paying)
    - No trial period - approval triggers immediate payment
    """
    if not current_user.is_authenticated:
        return {}
    
    org = current_user.organization
    if not org:
        return {}
    
    # Root admins don't need subscription warnings
    if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
        return {'is_root_admin': True}
    
    # Use unified billing_state
    billing = org.billing_state
    
    context = {
        'subscription_status': org.subscription_status,
        'is_active': org.is_active,
        'show_pending_approval_banner': billing['state'] == 'pending_approval',
        'show_payment_warning': billing['state'] == 'payment_required',
        'show_canceled_warning': billing['state'] == 'canceled',
        'has_payment_method': org.has_valid_payment_method,
        'billing_state': billing['state'],
        'billing_message': billing['message'],
        'needs_payment': billing['needs_payment'],
        'can_access_oauth': billing['can_access_oauth']
    }
    
    return context
