"""
Subscription Status Middleware
Enforces access control based on organization subscription status
"""

from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def subscription_required(f):
    """
    Decorator to enforce active subscription
    Blocks access if:
    - Trial has expired and no active subscription
    - Subscription is past_due, canceled, or incomplete
    - Organization is suspended
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
        
        # Check for canceled or terminated subscriptions FIRST (before is_active check)
        if org.subscription_status in ['canceled', 'incomplete_expired', 'unpaid']:
            flash('Your subscription has been canceled. Please contact support or reactivate your subscription.', 'error')
            return redirect(url_for('auth.account_suspended'))
        
        # Check for payment issues (past_due, incomplete)
        if org.subscription_status in ['past_due', 'incomplete']:
            flash('Your payment is past due. Please update your payment method.', 'warning')
            return redirect(url_for('auth.payment_required'))
        
        # Check if organization is active (uses is_active @property)
        if not org.is_active:
            # Trial expired
            if org.subscription_status == 'trialing' and org.trial_expires and org.trial_expires < datetime.utcnow():
                flash('Your free trial has expired. Please update your payment method to continue.', 'warning')
                return redirect(url_for('auth.subscription_expired'))
            
            # Suspended
            elif org.setup_status == 'suspended':
                flash('Your account has been suspended. Please contact support.', 'error')
                return redirect(url_for('auth.account_suspended'))
            
            # Other inactive reasons
            else:
                flash('Your account is not active. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
        
        # Allow access
        return f(*args, **kwargs)
    
    return decorated_function


def trial_warning_required(f):
    """
    Decorator that allows access but adds warning flash messages for expiring trials
    Use this for routes that should show warnings but not block access
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and hasattr(current_user, 'organization'):
            org = current_user.organization
            
            # Skip root admins
            if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
                return f(*args, **kwargs)
            
            # Check for expiring trial (7 days or less)
            if org and org.subscription_status == 'trialing' and org.trial_expires:
                days_remaining = (org.trial_expires - datetime.utcnow()).days
                
                if 0 < days_remaining <= 7:
                    if org.stripe_customer_id:
                        flash(f'Your trial ends in {days_remaining} day{"s" if days_remaining != 1 else ""}. Your subscription will begin automatically.', 'info')
                    else:
                        flash(f'Your trial expires in {days_remaining} day{"s" if days_remaining != 1 else ""}. Update your payment method to avoid interruption.', 'warning')
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_subscription_context():
    """
    Get subscription status context for templates
    Returns dict with subscription info to display in UI
    """
    if not current_user.is_authenticated:
        return {}
    
    org = current_user.organization
    if not org:
        return {}
    
    # Root admins don't need subscription warnings
    if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
        return {'is_root_admin': True}
    
    context = {
        'subscription_status': org.subscription_status,
        'trial_expires': org.trial_expires,
        'is_active': org.is_active,
        'show_trial_banner': False,
        'trial_days_remaining': None,
        'trial_is_expired': False,
        'show_payment_warning': False,
        'show_canceled_warning': False,
        'has_payment_method': bool(org.stripe_customer_id)
    }
    
    # Calculate trial days remaining and expiration status
    if org.subscription_status == 'trialing' and org.trial_expires:
        delta = org.trial_expires - datetime.utcnow()
        days_remaining = max(0, delta.days)
        context['trial_days_remaining'] = days_remaining
        
        # Direct datetime comparison for accurate expiration status
        context['trial_is_expired'] = org.trial_expires < datetime.utcnow()
        
        # Show banner if trial expires in 14 days or less (but still use days for messaging)
        if days_remaining <= 14:
            context['show_trial_banner'] = True
    
    # Show payment warning for past_due, incomplete, or canceled
    if org.subscription_status in ['past_due', 'incomplete']:
        context['show_payment_warning'] = True
    
    # Show canceled warning
    if org.subscription_status in ['canceled', 'incomplete_expired', 'unpaid']:
        context['show_canceled_warning'] = True
    
    return context
