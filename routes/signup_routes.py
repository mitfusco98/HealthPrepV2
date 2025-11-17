"""
Public Signup Routes for Self-Service Onboarding
Handles new organization registration with Stripe integration
"""
import logging
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any

from models import Organization, User, db
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
        # Validate required fields
        if not all([org_name, contact_email, epic_client_id, epic_client_secret, specialty]):
            return False, {"error": "Missing required fields: organization_name, admin_email, specialty, epic_client_id, epic_client_secret"}
        
        # Set defaults
        if not billing_email:
            billing_email = contact_email
        if not epic_fhir_url:
            epic_fhir_url = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        
        # Check if organization name already exists
        existing_org = Organization.query.filter_by(name=org_name).first()
        if existing_org:
            return False, {"error": "Organization name already exists"}
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=contact_email).first()
        if existing_user:
            return False, {"error": "Email address already registered"}
        
        # Create organization (pending approval)
        org = Organization(
            name=org_name,
            display_name=org_name,
            site=site,
            specialty=specialty,
            address=address,
            phone=phone,
            contact_email=contact_email,
            billing_email=billing_email,
            epic_client_id=epic_client_id,
            epic_client_secret=epic_client_secret,
            epic_fhir_url=epic_fhir_url,
            epic_environment='sandbox',
            setup_status='incomplete',
            onboarding_status='pending_approval',
            max_users=10
        )
        
        db.session.add(org)
        db.session.flush()
        
        # Generate admin user credentials
        username = generate_username_from_email(contact_email)
        
        # Create admin user
        admin_user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_admin=True,
            org_id=org.id,
            is_temp_password=True,
            is_active_user=True,
            email_verified=False,
            password_hash=generate_dummy_password_hash()
        )
        
        db.session.add(admin_user)
        db.session.flush()
        
        # Generate password reset token
        reset_token = create_password_reset_token()
        admin_user.password_reset_token = reset_token
        admin_user.password_reset_expires = get_password_reset_expiry(hours=48)
        
        db.session.commit()
        
        # Create Stripe checkout session
        try:
            # Use provided URLs or generate default ones
            if not success_url:
                success_url = url_for('signup.signup_success', _external=True)
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
        epic_fhir_url=epic_fhir_url
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
    """Handle successful Stripe checkout"""
    try:
        org_id = session.get('signup_org_id')
        reset_token = session.get('signup_reset_token')
        username = session.get('signup_username')
        email = session.get('signup_email')
        org_name = session.get('signup_org_name')
        
        if not all([org_id, reset_token, username, email]):
            flash('Invalid signup session. Please try again.', 'error')
            return redirect(url_for('signup.signup_form'))
        
        # Update organization status - payment confirmed, pending approval
        org = Organization.query.get(org_id)
        if org:
            org.subscription_status = 'trialing'  # Stripe subscription active
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
                logger.info(f"Welcome email sent to {email}")
            except Exception as email_error:
                logger.error(f"Failed to send welcome email: {str(email_error)}")
                flash('Account created successfully, but we had trouble sending your welcome email. Please contact support.', 'warning')
            
            logger.info(f"Signup completed for organization: {org_name} (ID: {org_id})")
        
        # Clear session data
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
        
        # Clean up cancelled signup
        if org_id:
            org = Organization.query.get(org_id)
            if org:
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
