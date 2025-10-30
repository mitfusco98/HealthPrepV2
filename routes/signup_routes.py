"""
Public Signup Routes for Self-Service Onboarding
Handles new organization registration with Stripe integration
"""
import logging
import secrets
import string
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta

from models import Organization, User, db
from services.stripe_service import StripeService
from services.email_service import EmailService

logger = logging.getLogger(__name__)

signup_bp = Blueprint('signup', __name__)


def generate_temp_password(length=12):
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_username_from_email(email):
    """Generate username from email address"""
    # Take part before @ and sanitize
    username = email.split('@')[0]
    # Remove special characters, keep only alphanumeric and underscores
    username = ''.join(c if c.isalnum() or c == '_' else '_' for c in username)
    return username[:50]  # Limit to 50 chars


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
            setup_status='incomplete',  # Will be changed to 'trial' after Stripe checkout
            onboarding_status='pending_approval',  # Root admin must approve
            trial_start_date=datetime.utcnow(),
            trial_expires=datetime.utcnow() + timedelta(days=14),
            max_users=10
        )
        
        db.session.add(org)
        db.session.flush()  # Get org.id
        
        # Generate admin user credentials
        username = generate_username_from_email(contact_email)
        temp_password = generate_temp_password()
        
        # Create admin user
        admin_user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_admin=True,
            org_id=org.id,
            is_temp_password=True,  # Force password change on first login
            is_active_user=False,  # Will be activated when org is approved
            email_verified=False
        )
        admin_user.set_password(temp_password)
        
        db.session.add(admin_user)
        db.session.commit()
        
        # Store temp password and org info in session for Stripe checkout
        session['signup_org_id'] = org.id
        session['signup_temp_password'] = temp_password
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
        temp_password = session.get('signup_temp_password')
        username = session.get('signup_username')
        email = session.get('signup_email')
        org_name = session.get('signup_org_name')
        
        if not all([org_id, temp_password, username, email]):
            flash('Invalid signup session. Please try again.', 'error')
            return redirect(url_for('signup.signup_form'))
        
        # Update organization status
        org = Organization.query.get(org_id)
        if org:
            org.setup_status = 'trial'
            org.subscription_status = 'trialing'
            db.session.commit()
            
            # Send welcome email
            EmailService.send_welcome_email(
                email=email,
                username=username,
                temp_password=temp_password,
                org_name=org_name
            )
            
            logger.info(f"Signup completed for organization: {org_name} (ID: {org_id})")
        
        # Clear session data
        session.pop('signup_org_id', None)
        session.pop('signup_temp_password', None)
        session.pop('signup_username', None)
        session.pop('signup_email', None)
        session.pop('signup_org_name', None)
        
        flash('Thank you for signing up! Check your email for login credentials.', 'success')
        flash('Your organization is pending approval by our admin team. You will receive an email when approved.', 'info')
        
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
