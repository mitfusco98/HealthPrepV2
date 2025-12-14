"""
Public Signup Routes for Self-Service Onboarding
Handles new organization registration with Stripe integration
"""
import logging
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any

from models import Organization, User, Provider, UserProviderAssignment, db
from services.stripe_service import StripeService
from services.email_service import EmailService
from utils.onboarding_helpers import (
    generate_temp_password,
    generate_username_from_email,
    create_password_reset_token,
    get_password_reset_expiry,
    generate_dummy_password_hash
)
from app import csrf

logger = logging.getLogger(__name__)

signup_bp = Blueprint('signup', __name__)


def create_signup_organization(
    org_name: str,
    contact_email: str,
    specialty: str,
    epic_client_id: str,
    epic_client_secret: str,
    site: str = '',
    address: str = '',
    phone: str = '',
    billing_email: str = '',
    epic_fhir_url: str = '',
    epic_environment: str = 'sandbox',
    admin_type: str = 'provider',
    success_url: str = None,
    cancel_url: str = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Shared signup logic for both HTML form and JSON API.
    
    Returns:
        Tuple of (success: bool, data: dict)
        On success: (True, {"checkout_url": "...", "organization_id": 123, "reset_token": "..."})
        On error: (False, {"error": "Error message"})
    """
    try:
        # Validate required fields (organization basics + Epic credentials)
        if not all([org_name, contact_email, specialty, epic_client_id, epic_client_secret, epic_fhir_url]):
            return False, {"error": "Missing required fields: organization_name, admin_email, specialty, epic_client_id, epic_client_secret, epic_fhir_url"}
        
        # Validate epic_fhir_url format
        if not epic_fhir_url.startswith(('http://', 'https://')) or len(epic_fhir_url.split('://')) < 2:
            return False, {"error": "Invalid epic_fhir_url format. Must be a valid URL starting with http:// or https://"}
        
        # Production organizations cannot use sandbox URL
        sandbox_url = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        if epic_environment == 'production' and epic_fhir_url == sandbox_url:
            return False, {"error": "Production organizations cannot use the sandbox FHIR URL. Please provide your organization's unique Epic FHIR endpoint from your Epic representative."}
        
        # Set defaults
        if not billing_email:
            billing_email = contact_email
        
        # Check if organization name already exists
        existing_org = Organization.query.filter_by(name=org_name).first()
        if existing_org:
            return False, {"error": "Organization name already exists"}
        
        # Validate admin_type
        if admin_type not in ('provider', 'business_admin'):
            admin_type = 'provider'  # Default to provider if invalid
        
        # Check if email already exists - if so, this is a multi-provider setup for same admin
        # We allow same email with different usernames (mitchfusillo, mitchfusillo2, etc.)
        existing_user = User.query.filter_by(email=contact_email).first()
        is_multi_provider_setup = existing_user is not None
        
        # Create organization (pending approval)
        # Convert empty strings to None for Epic credentials
        org = Organization(
            name=org_name,
            display_name=org_name,
            site=site,
            specialty=specialty,
            address=address,
            phone=phone,
            contact_email=contact_email,
            billing_email=billing_email,
            epic_client_id=epic_client_id or None,
            epic_client_secret=epic_client_secret or None,
            epic_fhir_url=epic_fhir_url or None,
            epic_environment=epic_environment,
            setup_status='incomplete',
            onboarding_status='pending_approval',
            max_users=10,
            owner_email=contact_email  # Track owner email for multi-org billing aggregation
        )
        
        # Generate signup completion token for API-based signups
        signup_token = create_password_reset_token()
        org.signup_completion_token = signup_token
        org.signup_completion_token_expires = get_password_reset_expiry(hours=24)
        
        db.session.add(org)
        db.session.flush()
        
        # Generate admin user credentials
        username = generate_username_from_email(contact_email)
        
        # Create admin user with appropriate admin type
        admin_user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_admin=True,
            admin_type=admin_type,  # 'provider' or 'business_admin'
            org_id=org.id,
            is_temp_password=True,
            is_active_user=True,
            email_verified=False,
            password_hash=generate_dummy_password_hash()
        )
        
        db.session.add(admin_user)
        db.session.flush()
        
        # Create a default provider for the organization
        # This represents the first practitioner in the practice
        default_provider = Provider(
            name=f"Provider - {org_name}",
            specialty=specialty,
            org_id=org.id,
            is_active=True
        )
        db.session.add(default_provider)
        db.session.flush()
        
        # Create assignment linking admin to the default provider (so they can manage it)
        admin_assignment = UserProviderAssignment(
            user_id=admin_user.id,
            provider_id=default_provider.id,
            org_id=org.id,
            is_primary=True,
            can_view_patients=True,
            can_edit_patients=True,
            can_generate_prep_sheets=True,
            can_sync_epic=True
        )
        db.session.add(admin_assignment)
        
        # Generate password reset token
        reset_token = create_password_reset_token()
        admin_user.password_reset_token = reset_token
        admin_user.password_reset_expires = get_password_reset_expiry(hours=48)
        
        db.session.commit()
        
        logger.info(f"Created default provider {default_provider.id} for new organization {org.id}")
        
        # Seed organization with sample data for demonstration
        try:
            from scripts.seed_org_sample_data import seed_organization_data
            seed_results = seed_organization_data(org.id, default_provider.id)
            if seed_results:
                logger.info(f"Seeded sample data for new organization {org.id}: {seed_results}")
        except Exception as seed_error:
            logger.warning(f"Could not seed sample data for org {org.id}: {seed_error}")
        
        # Create Stripe checkout session
        try:
            # Use provided URLs or generate default ones
            # For API signups, include token in success URL for session-less flow
            if not success_url:
                success_url = url_for('signup.signup_success', token=signup_token, _external=True)
            if not cancel_url:
                cancel_url = url_for('signup.signup_cancel', _external=True)
            
            checkout_url = StripeService.create_checkout_session(
                organization=org,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            if not checkout_url:
                raise Exception("Stripe checkout session creation returned None")
            
            logger.info(f"New organization signup initiated: {org_name} (ID: {org.id})")
            
            return True, {
                "checkout_url": checkout_url,
                "organization_id": org.id,
                "reset_token": reset_token,
                "username": username,
                "email": contact_email,
                "org_name": org_name
            }
                
        except Exception as stripe_error:
            # Rollback if Stripe fails
            logger.error(f"Stripe checkout creation failed: {str(stripe_error)}")
            db.session.delete(admin_user)
            db.session.delete(org)
            db.session.commit()
            return False, {"error": "Unable to process payment setup. Please try again later."}
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Signup error: {str(e)}")
        return False, {"error": "An error occurred during signup. Please try again."}


@signup_bp.route('/signup', methods=['GET'])
def signup_form():
    """Display public signup form"""
    return render_template('signup/signup.html')


@signup_bp.route('/signup', methods=['POST'])
def signup_submit():
    """Process HTML form signup submission"""
    # Collect form data
    org_name = request.form.get('org_name', '').strip()
    site = request.form.get('site', '').strip()
    specialty = request.form.get('specialty', '').strip()
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip()
    contact_email = request.form.get('contact_email', '').strip()
    billing_email = request.form.get('billing_email', '').strip()
    epic_client_id = request.form.get('epic_client_id', '').strip()
    epic_client_secret = request.form.get('epic_client_secret', '').strip()
    epic_fhir_url = request.form.get('epic_fhir_url', '').strip()
    epic_environment = request.form.get('epic_environment', 'sandbox')
    admin_type = request.form.get('admin_type', 'provider')  # provider or business_admin
    
    # Call shared signup function
    success, data = create_signup_organization(
        org_name=org_name,
        contact_email=contact_email,
        specialty=specialty,
        epic_client_id=epic_client_id,
        epic_client_secret=epic_client_secret,
        site=site,
        address=address,
        phone=phone,
        billing_email=billing_email,
        epic_fhir_url=epic_fhir_url,
        epic_environment=epic_environment,
        admin_type=admin_type
    )
    
    if not success:
        flash(data['error'], 'error')
        return redirect(url_for('signup.signup_form'))
    
    # Store signup data in session for success handler
    session['signup_org_id'] = data['organization_id']
    session['signup_reset_token'] = data['reset_token']
    session['signup_username'] = data['username']
    session['signup_email'] = data['email']
    session['signup_org_name'] = data['org_name']
    
    # Redirect to Stripe checkout
    return redirect(data['checkout_url'])


@signup_bp.route('/signup/success')
def signup_success():
    """Handle successful Stripe checkout - supports both session-based (HTML form) and token-based (API) flows"""
    try:
        # Try token-based flow first (API signups)
        completion_token = request.args.get('token')
        
        if completion_token:
            # Token-based flow - find org by completion token
            org = Organization.query.filter_by(signup_completion_token=completion_token).first()
            
            if not org or not org.signup_completion_token_expires or org.signup_completion_token_expires < datetime.utcnow():
                flash('Invalid or expired signup link. Please contact support.', 'error')
                return redirect(url_for('signup.signup_form'))
            
            # Get admin user for this organization
            admin_user = User.query.filter_by(org_id=org.id, role='admin').first()
            if not admin_user:
                flash('Invalid signup data. Please contact support.', 'error')
                return redirect(url_for('signup.signup_form'))
            
            org_id = org.id
            org_name = org.name
            email = admin_user.email
            username = admin_user.username
            reset_token = admin_user.password_reset_token
            
            # Clear the completion token so it can't be reused
            org.signup_completion_token = None
            org.signup_completion_token_expires = None
            
        else:
            # Session-based flow (HTML form signups)
            org_id = session.get('signup_org_id')
            reset_token = session.get('signup_reset_token')
            username = session.get('signup_username')
            email = session.get('signup_email')
            org_name = session.get('signup_org_name')
            
            if not all([org_id, reset_token, username, email]):
                flash('Invalid signup session. Please try again.', 'error')
                return redirect(url_for('signup.signup_form'))
            
            # Get organization
            org = Organization.query.get(org_id)
            if not org:
                flash('Organization not found. Please contact support.', 'error')
                return redirect(url_for('signup.signup_form'))
        
        # Update organization status - payment confirmed, pending approval
        org.subscription_status = 'payment_method_added'
        # setup_status stays 'incomplete' until approval
        db.session.commit()
        
        # Send welcome email with password setup link (after Stripe checkout succeeds)
        password_setup_url = url_for('password_reset.reset_password', token=reset_token, _external=True)
        
        try:
            EmailService.send_admin_welcome_email(
                email=email,
                username=username,
                org_name=org_name,
                password_setup_url=password_setup_url
            )
            logger.info(f"Welcome email sent to {email} for organization {org_id}")
        except Exception as email_error:
            logger.error(f"Failed to send welcome email: {str(email_error)}")
            flash('Account created successfully, but we had trouble sending your welcome email. Please contact support.', 'warning')
        
        logger.info(f"Signup completed for organization: {org_name} (ID: {org_id})")
        
        # Clear session data (if session-based flow)
        session.pop('signup_org_id', None)
        session.pop('signup_reset_token', None)
        session.pop('signup_username', None)
        session.pop('signup_email', None)
        session.pop('signup_org_name', None)
        
        flash('Thank you for signing up! Check your email to set up your password.', 'success')
        flash('You can log in and configure your organization while awaiting approval. Epic integration will be enabled once approved.', 'info')
        
        return render_template('signup/signup_success.html', 
                             org_name=org_name,
                             email=email)
    
    except Exception as e:
        logger.error(f"Signup success handler error: {str(e)}")
        flash('An error occurred. Please contact support.', 'error')
        return redirect(url_for('auth.login'))


@signup_bp.route('/signup/cancel')
def signup_cancel():
    """Handle cancelled Stripe checkout"""
    try:
        org_id = session.get('signup_org_id')
        
        # Clean up cancelled signup (in proper order due to FK constraints)
        if org_id:
            org = Organization.query.get(org_id)
            if org:
                # Delete user-provider assignments first
                UserProviderAssignment.query.filter_by(org_id=org_id).delete()
                # Delete providers
                Provider.query.filter_by(org_id=org_id).delete()
                # Delete associated user
                User.query.filter_by(org_id=org_id).delete()
                # Delete organization
                db.session.delete(org)
                db.session.commit()
                logger.info(f"Cancelled signup for organization ID: {org_id}")
        
        # Clear session
        session.pop('signup_org_id', None)
        session.pop('signup_temp_password', None)
        session.pop('signup_username', None)
        session.pop('signup_email', None)
        session.pop('signup_org_name', None)
        
        flash('Signup cancelled. No charges were made.', 'info')
        return redirect(url_for('signup.signup_form'))
    
    except Exception as e:
        logger.error(f"Signup cancel handler error: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('signup.signup_form'))
