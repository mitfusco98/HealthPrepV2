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
            # Full access for active subscriptions
            return f(*args, **kwargs)
        
        elif state == 'trialing':
            # Full access during valid trial period
            if billing['needs_payment'] and billing.get('trial_days_remaining', 0) <= 7:
                # Warn about upcoming trial expiration if no payment method
                flash(f"Your trial expires in {billing.get('trial_days_remaining', 0)} days. Please add a payment method.", 'warning')
            return f(*args, **kwargs)
        
        elif state == 'trial_expired':
            # If org has payment method, try to auto-activate subscription
            if org.has_valid_payment_method:
                from services.stripe_service import StripeService
                logger.info(f"Attempting auto-activation for trial-expired org {org.id} with payment method")
                if StripeService.ensure_subscription_exists(org):
                    # Subscription activated successfully - refresh billing state and allow access
                    new_billing = org.billing_state
                    if new_billing['state'] == 'active':
                        flash('Your subscription has been activated. Welcome back!', 'success')
                        return f(*args, **kwargs)
                    elif new_billing['state'] == 'trialing':
                        return f(*args, **kwargs)
                # Auto-activation failed - redirect to payment page
                flash('Unable to activate your subscription. Please update your payment method.', 'warning')
            else:
                flash('Your free trial has expired. Please add a payment method to continue.', 'warning')
            return redirect(url_for('auth.subscription_expired'))
        
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
        
        elif state in ['pending_approval', 'pending_activation']:
            flash('Your account is pending activation. Please check back soon.', 'info')
            return redirect(url_for('auth.login'))
        
        else:
            # Unknown state - fall back to is_active check for safety
            if org.is_active:
                return f(*args, **kwargs)
            else:
                flash('Your account is not active. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
    
    return decorated_function


def trial_warning_required(f):
    """
    Decorator that allows access but adds warning flash messages for expiring trials
    Use this for routes that should show warnings but not block access
    Uses unified billing_state for consistent messaging
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and hasattr(current_user, 'organization'):
            org = current_user.organization
            
            # Skip root admins
            if hasattr(current_user, 'is_root_admin') and current_user.is_root_admin:
                return f(*args, **kwargs)
            
            if org:
                billing = org.billing_state
                
                # Check for expiring trial (7 days or less)
                if billing['state'] == 'trialing':
                    days_remaining = billing.get('trial_days_remaining', 0)
                    
                    if days_remaining is not None and 0 < days_remaining <= 7:
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
    Uses unified billing_state for consistent information
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
        'trial_expires': org.trial_expires,
        'is_active': org.is_active,
        'show_trial_banner': False,
        'trial_days_remaining': billing.get('trial_days_remaining'),
        'trial_is_expired': billing['state'] == 'trial_expired',
        'show_payment_warning': billing['state'] == 'payment_required',
        'show_canceled_warning': billing['state'] == 'canceled',
        'has_payment_method': org.has_valid_payment_method,
        'billing_state': billing['state'],
        'billing_message': billing['message'],
        'needs_payment': billing['needs_payment']
    }
    
    # Show trial banner during trial period
    if billing['state'] == 'trialing':
        days_remaining = billing.get('trial_days_remaining', 0)
        if days_remaining is not None and days_remaining <= 14:
            context['show_trial_banner'] = True
    
    return context
