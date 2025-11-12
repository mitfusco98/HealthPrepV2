"""
Public Signup Routes for Self-Service Onboarding
Handles new organization registration with Stripe integration
"""
import logging
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta

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

logger = logging.getLogger(__name__)

signup_bp = Blueprint('signup', __name__)


@signup_bp.route('/signup', methods=['GET'])
def signup_form():
    """Display public signup form"""
    return render_template('signup/signup.html')


@signup_bp.route('/signup', methods=['POST'])
def signup_submit():
    """Process signup form submission"""
    try:
        # Collect organization information
        org_name = request.form.get('org_name', '').strip()
        site = request.form.get('site', '').strip()
        specialty = request.form.get('specialty', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        billing_email = request.form.get('billing_email', '').strip() or contact_email
        
        # Collect Epic FHIR credentials
        epic_client_id = request.form.get('epic_client_id', '').strip()
        epic_client_secret = request.form.get('epic_client_secret', '').strip()
        epic_fhir_url = request.form.get('epic_fhir_url', '').strip() or \
                       'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        
        # Validate required fields
        if not all([org_name, contact_email, epic_client_id, epic_client_secret]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('signup.signup_form'))
        
        # Check if organization name already exists
        existing_org = Organization.query.filter_by(name=org_name).first()
        if existing_org:
            flash('An organization with this name already exists. Please choose a different name.', 'error')
            return redirect(url_for('signup.signup_form'))
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=contact_email).first()
        if existing_user:
            flash('This email is already registered. Please use a different email or contact support.', 'error')
            return redirect(url_for('signup.signup_form'))
        
        # Create organization (pending approval)
        # Trial dates will be set when root admin approves the organization
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
            epic_client_secret=epic_client_secret,  # Will be encrypted by model
            epic_fhir_url=epic_fhir_url,
            epic_environment='sandbox',
            setup_status='incomplete',  # Will be 'trial' after approval by root admin
            onboarding_status='pending_approval',  # Root admin must approve to start trial
            max_users=10
        )
        
        db.session.add(org)
        db.session.flush()  # Get org.id
        
        # Generate admin user credentials
        username = generate_username_from_email(contact_email)
        temp_password = generate_temp_password()
        
        # Create admin user - active immediately so they can set up while pending approval
        admin_user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_admin=True,
            org_id=org.id,
            is_temp_password=True,  # Will use password reset flow to set real password
            is_active_user=True,  # Active immediately - can login and configure while pending
            email_verified=False,
            password_hash=generate_dummy_password_hash()  # Dummy hash until user sets real password via reset link
        )
        
        db.session.add(admin_user)
        db.session.flush()  # Get user ID for password reset token
        
        # Generate password reset token for welcome email
        reset_token = create_password_reset_token()
        admin_user.password_reset_token = reset_token
        admin_user.password_reset_expires = get_password_reset_expiry(hours=48)
        
        db.session.commit()
        
        # Store org info in session for Stripe checkout
        # Email will be sent AFTER successful Stripe checkout to avoid sending broken links if payment fails
        session['signup_org_id'] = org.id
        session['signup_reset_token'] = reset_token
        session['signup_username'] = username
        session['signup_email'] = contact_email
        session['signup_org_name'] = org_name
        
        # Create Stripe checkout session
        success_url = url_for('signup.signup_success', _external=True)
        cancel_url = url_for('signup.signup_cancel', _external=True)
        
        try:
            checkout_url = StripeService.create_checkout_session(
                organization=org,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            if not checkout_url:
                raise Exception("Stripe checkout session creation returned None")
                
        except Exception as stripe_error:
            # Rollback if Stripe fails
            logger.error(f"Stripe checkout creation failed: {str(stripe_error)}")
            db.session.delete(admin_user)
            db.session.delete(org)
            db.session.commit()
            flash('Unable to process payment setup. Please try again later or contact support.', 'error')
            return redirect(url_for('signup.signup_form'))
        
        logger.info(f"New organization signup initiated: {org_name} (ID: {org.id})")
        
        # Redirect to Stripe checkout
        return redirect(checkout_url)
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Signup error: {str(e)}")
        flash('An error occurred during signup. Please try again.', 'error')
        return redirect(url_for('signup.signup_form'))


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
