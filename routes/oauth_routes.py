"""
SMART on FHIR OAuth2 routes for Epic integration
Handles OAuth2 authorization flow and token management
"""

from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, current_app
from flask_login import login_required, current_user
import logging
import secrets
from datetime import datetime, timedelta

from emr.fhir_client import FHIRClient
from models import db, Organization
from functools import wraps
from flask import abort

def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

oauth_bp = Blueprint('oauth', __name__)
logger = logging.getLogger(__name__)


@oauth_bp.route('/epic-authorize')
@login_required
@require_admin
def epic_authorize():
    """
    Start Epic OAuth2 authorization flow
    Redirects user to Epic's authorization endpoint
    """
    try:
        # Get organization's Epic configuration
        org = current_user.organization
        if not org or not org.epic_client_id:
            flash('Epic FHIR configuration not found. Please configure Epic credentials first.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # Initialize FHIR client with organization config
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        
        redirect_uri = url_for('oauth.epic_callback', _external=True)
        fhir_client = FHIRClient(epic_config, redirect_uri)
        
        # Generate authorization URL
        auth_url, state = fhir_client.get_authorization_url()
        
        # Store state in session for validation
        session['epic_oauth_state'] = state
        session['epic_auth_timestamp'] = datetime.now().isoformat()
        
        logger.info(f"Starting Epic OAuth flow for organization {org.id}")
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Error starting Epic OAuth flow: {str(e)}")
        flash('Failed to start Epic authorization. Please try again.', 'error')
        return redirect(url_for('fhir.epic_config'))


@oauth_bp.route('/epic-callback')
def epic_callback():
    """
    Handle Epic OAuth2 callback
    Exchanges authorization code for access token
    """
    try:
        # Get authorization code and state from callback
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            logger.error(f"Epic OAuth error: {error}")
            flash(f'Epic authorization failed: {error}', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        if not code:
            flash('No authorization code received from Epic', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # Validate state parameter
        stored_state = session.get('epic_oauth_state')
        if not stored_state or stored_state != state:
            logger.error("Invalid OAuth state parameter")
            flash('Invalid authorization state. Please try again.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # Check if user is still logged in
        if not current_user.is_authenticated:
            flash('Session expired during authorization', 'error')
            return redirect(url_for('auth.login'))
        
        # Get organization config
        org = current_user.organization
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        
        redirect_uri = url_for('oauth.epic_callback', _external=True)
        fhir_client = FHIRClient(epic_config, redirect_uri)
        
        # Exchange code for tokens
        token_data = fhir_client.exchange_code_for_token(code, state)
        
        if not token_data:
            flash('Failed to exchange authorization code for access token', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # Store tokens in session (secure server-side storage)
        session['epic_access_token'] = token_data.get('access_token')
        session['epic_refresh_token'] = token_data.get('refresh_token')
        session['epic_token_expires'] = (datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))).isoformat()
        session['epic_token_scopes'] = token_data.get('scope', '').split()
        session['epic_patient_id'] = token_data.get('patient')  # If patient-specific token
        
        # Clean up OAuth state
        session.pop('epic_oauth_state', None)
        session.pop('epic_auth_timestamp', None)
        
        logger.info(f"Epic OAuth flow completed successfully for organization {org.id}")
        flash('Successfully connected to Epic FHIR!', 'success')
        
        return redirect(url_for('fhir.screening_mapping'))
        
    except Exception as e:
        logger.error(f"Error handling Epic OAuth callback: {str(e)}")
        flash('Failed to complete Epic authorization. Please try again.', 'error')
        return redirect(url_for('fhir.epic_config'))


@oauth_bp.route('/epic-disconnect', methods=['POST'])
@login_required
@require_admin
def epic_disconnect():
    """
    Disconnect Epic OAuth2 session
    Clears stored tokens
    """
    try:
        # Clear Epic tokens from session
        epic_keys = [
            'epic_access_token',
            'epic_refresh_token', 
            'epic_token_expires',
            'epic_token_scopes',
            'epic_patient_id'
        ]
        
        for key in epic_keys:
            session.pop(key, None)
        
        flash('Disconnected from Epic FHIR', 'info')
        return redirect(url_for('fhir.epic_config'))
        
    except Exception as e:
        logger.error(f"Error disconnecting Epic OAuth: {str(e)}")
        flash('Error disconnecting from Epic', 'error')
        return redirect(url_for('fhir.epic_config'))


@oauth_bp.route('/epic-status')
@login_required
@require_admin
def epic_status():
    """
    Check Epic OAuth2 connection status
    Returns JSON with connection details
    """
    try:
        status = {
            'connected': False,
            'expires_at': None,
            'scopes': [],
            'patient_id': None
        }
        
        access_token = session.get('epic_access_token')
        if access_token:
            status['connected'] = True
            status['expires_at'] = session.get('epic_token_expires')
            status['scopes'] = session.get('epic_token_scopes', [])
            status['patient_id'] = session.get('epic_patient_id')
            
            # Check if token is expired
            expires_str = status['expires_at']
            if expires_str:
                expires_at = datetime.fromisoformat(expires_str)
                status['expired'] = datetime.now() >= expires_at
            else:
                status['expired'] = True
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error checking Epic OAuth status: {str(e)}")
        return jsonify({'error': str(e)}), 500


def get_epic_fhir_client():
    """
    Helper function to get configured FHIR client with current session tokens
    """
    if not current_user.is_authenticated:
        return None
    
    org = current_user.organization
    if not org or not org.epic_client_id:
        return None
    
    access_token = session.get('epic_access_token')
    if not access_token:
        return None
    
    # Initialize client with organization config
    epic_config = {
        'epic_client_id': org.epic_client_id,
        'epic_client_secret': org.epic_client_secret,
        'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
    }
    
    fhir_client = FHIRClient(epic_config)
    
    # Set tokens from session
    refresh_token = session.get('epic_refresh_token')
    expires_str = session.get('epic_token_expires')
    scopes = session.get('epic_token_scopes', [])
    
    expires_in = 3600  # Default
    if expires_str:
        expires_at = datetime.fromisoformat(expires_str)
        expires_in = max(0, int((expires_at - datetime.now()).total_seconds()))
    
    fhir_client.set_tokens(access_token, refresh_token, expires_in, scopes)
    
    return fhir_client