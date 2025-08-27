"""
SMART on FHIR Authentication Routes
Handles EHR launch and standalone launch flows
"""

import logging
import secrets
from typing import Optional
from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, current_app
from flask_login import login_user, current_user
from urllib.parse import urlencode, parse_qs

from services.oauth_client import get_oauth_client
from services.smart_discovery import smart_discovery
from models import User, Organization
from app import db

logger = logging.getLogger(__name__)
smart_auth_bp = Blueprint('smart_auth', __name__, url_prefix='/smart')

@smart_auth_bp.route('/launch')
def launch():
    """
    SMART on FHIR Launch Endpoint
    Handles both EHR-embedded and standalone launches
    """
    try:
        # Get launch parameters
        iss = request.args.get('iss')  # FHIR server URL (required)
        launch = request.args.get('launch')  # Launch context token (EHR launch only)
        
        if not iss:
            logger.error("Missing 'iss' parameter in SMART launch")
            flash('Invalid launch: missing FHIR server URL', 'error')
            return redirect(url_for('auth.login'))
        
        logger.info(f"SMART launch initiated for ISS: {iss}")
        
        # Store launch context in session
        session['smart_launch_iss'] = iss
        session['smart_launch_type'] = 'ehr' if launch else 'standalone'
        
        # Test SMART discovery and endpoints
        try:
            config = smart_discovery.fetch(iss)
            endpoint_tests = smart_discovery.test_endpoints(iss)
            
            if not endpoint_tests.get('authorization_endpoint'):
                logger.warning(f"Authorization endpoint unreachable for {iss}")
            
            if not endpoint_tests.get('token_endpoint'):
                logger.warning(f"Token endpoint unreachable for {iss}")
                
        except Exception as e:
            logger.error(f"SMART discovery failed for {iss}: {e}")
            flash(f'SMART discovery failed: {e}', 'error')
            return redirect(url_for('auth.login'))
        
        # Determine scopes based on launch type
        if launch:
            # EHR launch - context will be provided
            scopes = [
                'openid', 'profile', 'fhirUser',
                'patient/Patient.read',
                'patient/Observation.read',
                'patient/DocumentReference.read',
                'patient/Condition.read',
                'patient/DiagnosticReport.read'
            ]
        else:
            # Standalone launch - need to select patient
            scopes = [
                'openid', 'profile', 'fhirUser',
                'patient/Patient.read',
                'patient/Observation.read', 
                'patient/DocumentReference.read',
                'patient/Condition.read',
                'patient/DiagnosticReport.read',
                'launch/patient'  # Allows patient selection
            ]
        
        # Build authorization URL
        try:
            oauth_client = get_oauth_client()
            auth_url, state = oauth_client.build_authorization_url(
                iss=iss,
                scopes=scopes,
                launch=launch,
                aud=iss
            )
            
            # Store state in session for validation
            session['smart_oauth_state'] = state
            session['smart_scopes'] = scopes
            
            logger.info(f"Redirecting to authorization URL for {iss}")
            return redirect(auth_url)
            
        except Exception as e:
            logger.error(f"Failed to build authorization URL: {e}")
            flash(f'Authorization setup failed: {e}', 'error')
            return redirect(url_for('auth.login'))
    
    except Exception as e:
        logger.error(f"SMART launch error: {e}")
        flash('Launch failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@smart_auth_bp.route('/callback')
def callback():
    """
    SMART on FHIR OAuth2 Callback Endpoint
    Handles authorization code exchange and user authentication
    """
    try:
        # Get callback parameters
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        
        # Check for OAuth errors
        if error:
            logger.error(f"OAuth error: {error} - {error_description}")
            flash(f'Authorization failed: {error_description or error}', 'error')
            return redirect(url_for('auth.login'))
        
        if not code:
            logger.error("Missing authorization code in callback")
            flash('Authorization failed: no code received', 'error')
            return redirect(url_for('auth.login'))
        
        # Validate state parameter
        expected_state = session.get('smart_oauth_state')
        oauth_client = get_oauth_client()
        if not state or not expected_state or not oauth_client.validate_state(state, expected_state):
            flash('Security validation failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        # Get launch context from session
        iss = session.get('smart_launch_iss')
        if not iss:
            logger.error("Missing ISS in session during callback")
            flash('Session expired. Please restart launch.', 'error')
            return redirect(url_for('auth.login'))
        
        logger.info(f"Processing SMART callback for ISS: {iss}")
        
        # Exchange code for tokens
        try:
            oauth_client = get_oauth_client()
            token_info = oauth_client.exchange_code_for_token(iss, code, state)
            
            # Store tokens in session (in production, use secure token storage)
            session['smart_access_token'] = token_info['access_token']
            session['smart_refresh_token'] = token_info.get('refresh_token')
            session['smart_patient_id'] = token_info.get('patient')
            session['smart_user_id'] = token_info.get('user')
            session['smart_token_expires'] = token_info.get('expires_in')
            
            # Parse FHIR user information
            user_info = oauth_client.parse_fhir_user(token_info)
            if user_info:
                session['smart_user_info'] = user_info
            
            logger.info("Successfully exchanged code for tokens")
            
            # Create or find user based on FHIR user ID
            fhir_user_id = token_info.get('user')
            if fhir_user_id:
                user = _find_or_create_fhir_user(fhir_user_id, iss, user_info or {})
                if user:
                    login_user(user)
                    flash('Successfully authenticated via SMART on FHIR!', 'success')
                    
                    # Redirect to appropriate dashboard
                    if user.is_admin_user():
                        return redirect(url_for('admin.dashboard'))
                    else:
                        return redirect(url_for('index'))
            
            # If no user context, redirect to main dashboard with SMART session
            flash('SMART authentication successful!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            flash(f'Token exchange failed: {e}', 'error')
            return redirect(url_for('auth.login'))
    
    except Exception as e:
        logger.error(f"SMART callback error: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@smart_auth_bp.route('/logout')
def logout():
    """
    SMART on FHIR Logout
    Clears SMART session data
    """
    # Clear SMART session data
    smart_keys = [key for key in session.keys() if key.startswith('smart_')]
    for key in smart_keys:
        session.pop(key, None)
    
    flash('SMART session ended', 'info')
    return redirect(url_for('auth.logout'))

@smart_auth_bp.route('/patient-select')
def patient_select():
    """
    Patient Selection for Standalone Launch
    (For future implementation - shows available patients)
    """
    access_token = session.get('smart_access_token')
    if not access_token:
        flash('No active SMART session', 'error')
        return redirect(url_for('smart_auth.launch'))
    
    # TODO: Implement patient selection UI
    # This would query the FHIR server for available patients
    # and present a selection interface
    
    return jsonify({
        'message': 'Patient selection not yet implemented',
        'has_token': bool(access_token),
        'patient_id': session.get('smart_patient_id')
    })

@smart_auth_bp.route('/session-info')
def session_info():
    """
    Debug endpoint to show SMART session information
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    smart_session = {
        'iss': session.get('smart_launch_iss'),
        'launch_type': session.get('smart_launch_type'),
        'patient_id': session.get('smart_patient_id'),
        'user_id': session.get('smart_user_id'),
        'has_access_token': bool(session.get('smart_access_token')),
        'has_refresh_token': bool(session.get('smart_refresh_token')),
        'token_expires': session.get('smart_token_expires'),
        'scopes': session.get('smart_scopes'),
        'user_info': session.get('smart_user_info')
    }
    
    return jsonify(smart_session)

def _find_or_create_fhir_user(fhir_user_id: str, iss: str, user_info: dict = None) -> Optional[User]:
    """
    Find or create user based on FHIR user ID
    
    Args:
        fhir_user_id: FHIR user identifier
        iss: FHIR server ISS
        user_info: Additional user information from FHIR
        
    Returns:
        User object or None
    """
    try:
        # Try to find existing user by FHIR user ID
        # (This would require adding fhir_user_id field to User model)
        user = User.query.filter_by(username=fhir_user_id).first()
        
        if user:
            logger.info(f"Found existing user for FHIR ID: {fhir_user_id}")
            return user
        
        # Create new user if doesn't exist
        # Find appropriate organization based on ISS
        org = Organization.query.filter_by(epic_fhir_url=iss).first()
        if not org:
            # Use default organization
            org = Organization.query.first()
        
        if not org:
            logger.error("No organization found for FHIR user creation")
            return None
        
        # Create new user
        user = User()
        user.username = fhir_user_id
        user.email = f"{fhir_user_id}@fhir.local"  # Placeholder email
        user.role = 'nurse'  # Default role
        user.is_admin = False
        user.org_id = org.id
        user.is_active_user = True
        
        # Set placeholder password (FHIR users don't use password auth)
        user.set_password(secrets.token_urlsafe(32))
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"Created new user for FHIR ID: {fhir_user_id}")
        return user
        
    except Exception as e:
        logger.error(f"Failed to find/create FHIR user: {e}")
        db.session.rollback()
        return None

# Helper functions for templates
@smart_auth_bp.app_template_global()
def has_smart_session():
    """Template helper to check if user has active SMART session"""
    return bool(session.get('smart_access_token'))

@smart_auth_bp.app_template_global()
def get_smart_patient_id():
    """Template helper to get current SMART patient ID"""
    return session.get('smart_patient_id')

@smart_auth_bp.app_template_global()
def get_smart_iss():
    """Template helper to get current SMART ISS"""
    return session.get('smart_launch_iss')