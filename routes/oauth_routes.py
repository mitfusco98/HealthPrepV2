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


@oauth_bp.route('/epic-authorize-debug')
@login_required
@require_admin
def epic_authorize_debug():
    """
    Debug endpoint to show Epic authorization URL without redirecting
    """
    try:
        # Get organization's Epic configuration
        org = current_user.organization
        if not org or not org.epic_client_id:
            return "Epic FHIR configuration not found. Please configure Epic credentials first."

        # Initialize FHIR client with organization config
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }

        redirect_uri = url_for('oauth.epic_callback', _external=True)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://')

        fhir_client = FHIRClient(epic_config, redirect_uri)

        # Generate authorization URL
        auth_url, state = fhir_client.get_authorization_url()

        return f"""
        <h1>Epic OAuth Debug</h1>
        <h3>Configuration:</h3>
        <ul>
            <li><strong>Client ID:</strong> {org.epic_client_id}</li>
            <li><strong>Redirect URI:</strong> {redirect_uri}</li>
            <li><strong>Auth URL:</strong> {fhir_client.auth_url}</li>
            <li><strong>Token URL:</strong> {fhir_client.token_url}</li>
            <li><strong>Base URL:</strong> {fhir_client.base_url}</li>
        </ul>
        <h3>Generated Authorization URL:</h3>
        <p><a href="{auth_url}" target="_blank">{auth_url}</a></p>
        <h3>Next Steps:</h3>
        <ol>
            <li>Copy the authorization URL above</li>
            <li>Paste it in a new browser tab</li>
            <li>Check what Epic returns</li>
            <li>Verify your app is approved in Epic App Orchard</li>
        </ol>
        """

    except Exception as e:
        return f"Error: {str(e)}"


@oauth_bp.route('/epic-oauth-debug')
@login_required
@require_admin
def epic_oauth_debug():
    """
    Debug Epic OAuth parameters without redirecting
    """
    try:
        org = current_user.organization
        if not org or not org.epic_client_id:
            return "Epic FHIR configuration not found. Please configure Epic credentials first."

        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }

        redirect_uri = url_for('oauth.epic_callback', _external=True)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://')

        fhir_client = FHIRClient(epic_config, redirect_uri)
        auth_url, state = fhir_client.get_authorization_url()

        # Parse the URL to show individual parameters
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(auth_url)
        query_params = parse_qs(parsed_url.query)

        return f"""
        <h1>Epic OAuth Debug - Parameter Analysis</h1>
        <h3>Base Authorization URL:</h3>
        <p><code>{fhir_client.auth_url}</code></p>

        <h3>Parameters Being Sent:</h3>
        <table border="1" cellpadding="5">
            <tr><th>Parameter</th><th>Value</th><th>Status</th></tr>
            <tr><td>response_type</td><td>{query_params.get('response_type', ['Missing'])[0]}</td><td>{'✓' if query_params.get('response_type') == ['code'] else '✗'}</td></tr>
            <tr><td>client_id</td><td>{org.epic_client_id}</td><td>{'✓' if org.epic_client_id else '✗'}</td></tr>
            <tr><td>redirect_uri</td><td>{redirect_uri}</td><td>✓</td></tr>
            <tr><td>scope</td><td>{query_params.get('scope', ['Missing'])[0]}</td><td>✓</td></tr>
            <tr><td>aud (audience)</td><td>{query_params.get('aud', ['Missing'])[0]}</td><td>{'✓' if query_params.get('aud') else '✗'}</td></tr>
            <tr><td>state</td><td>{state[:16]}...</td><td>✓</td></tr>
        </table>

        <h3>Full Authorization URL:</h3>
        <p><textarea rows="3" cols="100">{auth_url}</textarea></p>

        <h3>Epic Registration Verification:</h3>
        <ul>
            <li><strong>Client ID:</strong> {org.epic_client_id}</li>
            <li><strong>Expected Redirect URI:</strong> {redirect_uri}</li>
            <li><strong>Epic Base URL:</strong> {fhir_client.base_url}</li>
        </ul>

        <h3>Common Epic OAuth Issues:</h3>
        <ul>
            <li>❓ Redirect URI must be EXACTLY registered in Epic App Orchard (case-sensitive)</li>
            <li>❓ Client ID must be approved by Epic (can take 1-2 business days)</li>
            <li>❓ App must be in "Active" status in Epic App Orchard</li>
            <li>❓ Scopes must match what's registered in Epic</li>
        </ul>

        <p><a href="{auth_url}" target="_blank">Test Authorization URL</a></p>
        """

    except Exception as e:
        return f"Error: {str(e)}"


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

        # Debug logging for OAuth flow
        logger.info(f"OAuth redirect URI: {redirect_uri}")
        logger.info(f"Epic client ID: {org.epic_client_id}")
        logger.info(f"Epic auth URL: {fhir_client.auth_url}")

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
        error_description = request.args.get('error_description')

        # Comprehensive debug logging for callback
        logger.info(f"=== Epic OAuth Callback Debug ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Query parameters received:")
        logger.info(f"  - code: {'<present>' if code else 'None'}")
        logger.info(f"  - state: {'<present>' if state else 'None'}")
        logger.info(f"  - error: {error}")
        logger.info(f"  - error_description: {error_description}")
        logger.info(f"  - all query args: {dict(request.args)}")
        logger.info(f"Session state: {session.get('epic_oauth_state', 'None')}")
        logger.info(f"Session user: {current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else 'Unknown'}")
        logger.info(f"================================")

        if error:
            logger.error(f"Epic OAuth error: {error} - {error_description}")
            flash(f'Epic authorization failed: {error}', 'error')
            return redirect(url_for('epic_registration.epic_registration'))

        if not code:
            logger.error("No authorization code received from Epic OAuth callback")
            flash('No authorization code received from Epic', 'error')
            return redirect(url_for('epic_registration.epic_registration'))

        # Validate state parameter
        stored_state = session.get('epic_oauth_state')
        if not stored_state or stored_state != state:
            logger.error(f"Invalid OAuth state parameter - stored: {stored_state}, received: {state}")
            flash('Invalid authorization state. Please try again.', 'error')
            return redirect(url_for('epic_registration.epic_registration'))

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

        # Debug logging for callback token exchange
        logger.info(f"Token exchange - redirect URI: {redirect_uri}")
        logger.info(f"Token exchange - client ID: {org.epic_client_id}")
        logger.info(f"Token exchange - token URL: {fhir_client.token_url}")

        # Exchange code for tokens
        token_data = fhir_client.exchange_code_for_token(code, state)

        if not token_data:
            logger.error("Token exchange failed - no token data returned")
            flash('Failed to exchange authorization code for access token', 'error')
            return redirect(url_for('epic_registration.epic_registration'))

        # Store tokens at organization level for all users to access
        from models import EpicCredentials
        from app import db

        # Calculate token expiry
        token_expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))

        # Create or update Epic credentials for the organization
        epic_creds = EpicCredentials.query.filter_by(org_id=org.id).first()
        if not epic_creds:
            epic_creds = EpicCredentials(org_id=org.id)
            db.session.add(epic_creds)

        # Update token data
        epic_creds.access_token = token_data.get('access_token')
        epic_creds.refresh_token = token_data.get('refresh_token')
        epic_creds.token_expires_at = token_expires_at
        epic_creds.token_scopes = ' '.join(token_data.get('scope', '').split())
        epic_creds.patient_id = token_data.get('patient')
        epic_creds.updated_at = datetime.now()

        # Update organization connection status
        org.is_epic_connected = True
        org.epic_token_expiry = token_expires_at
        org.last_epic_sync = datetime.now()
        org.last_epic_error = None
        org.connection_retry_count = 0

        db.session.commit()

        # Also store in session for immediate admin access
        session['epic_access_token'] = token_data.get('access_token')
        session['epic_refresh_token'] = token_data.get('refresh_token')
        session['epic_token_expires'] = token_expires_at.isoformat()
        session['epic_token_scopes'] = token_data.get('scope', '').split()
        session['epic_patient_id'] = token_data.get('patient')

        # Clean up OAuth state
        session.pop('epic_oauth_state', None)
        session.pop('epic_auth_timestamp', None)

        logger.info(f"Epic OAuth flow completed successfully for organization {org.id}")
        flash('Successfully connected to Epic FHIR! All users in your organization can now sync with Epic.', 'success')

        return redirect(url_for('epic_registration.epic_registration'))

    except Exception as e:
        logger.error(f"Error handling Epic OAuth callback: {str(e)}", exc_info=True)
        flash('Failed to complete Epic authorization. Please try again.', 'error')
        return redirect(url_for('epic_registration.epic_registration'))


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

        # Check organization-level tokens first, then fall back to session
        from models import EpicCredentials
        org = current_user.organization
        epic_creds = EpicCredentials.query.filter_by(org_id=org.id).first() if org else None

        if epic_creds and epic_creds.access_token:
            status['connected'] = True
            status['expires_at'] = epic_creds.token_expires_at.isoformat() if epic_creds.token_expires_at else None
            status['scopes'] = epic_creds.token_scopes.split() if epic_creds.token_scopes else []
            status['patient_id'] = epic_creds.patient_id
            status['expired'] = epic_creds.is_expired if hasattr(epic_creds, 'is_expired') else (
                epic_creds.token_expires_at and datetime.now() >= epic_creds.token_expires_at
            )
        else:
            # Fall back to session-based tokens (for backward compatibility)
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


@oauth_bp.route('/epic-callback-test')
def epic_callback_test():
    """
    Test endpoint to verify redirect URI is accessible
    Visit this URL to confirm Epic can reach your callback
    """
    return f"""
    <h1>Epic Callback Test</h1>
    <p><strong>✅ SUCCESS:</strong> This URL is accessible!</p>
    <p><strong>Callback URL:</strong> {request.url.replace('/epic-callback-test', '/epic-callback')}</p>
    <p><strong>Your redirect URI should be:</strong> {url_for('oauth.epic_callback', _external=True)}</p>
    <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
    <hr>
    <h3>Epic Registration Checklist:</h3>
    <ul>
        <li>✅ App registered in Epic App Orchard</li>
        <li>❓ Redirect URI exactly matches: <code>{url_for('oauth.epic_callback', _external=True)}</code></li>
        <li>❓ App approved by Epic (can take 1-2 business days)</li>
        <li>❓ Client ID and Secret are correct</li>
    </ul>
    """


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