"""
SMART on FHIR OAuth2 routes for Epic integration
Handles OAuth2 authorization flow and token management
"""

from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, current_app
from flask_login import login_required, current_user
from middleware.subscription_check import subscription_required
import logging
import secrets
from datetime import datetime, timedelta

from emr.fhir_client import FHIRClient
from models import db, Organization, Provider, UserProviderAssignment
from functools import wraps
from flask import abort
from services.smart_discovery import smart_discovery
from services.jwt_client_auth import JWTClientAuthService
from services.epic_session_cleanup import EpicSessionCleanupService
from markupsafe import Markup
import json


def render_oauth_completion_page(success: bool, message: str, redirect_url: str):
    """
    Render an OAuth completion page that uses postMessage for cross-origin communication.
    This is used when OAuth flow completes in a popup window.
    
    The page:
    1. Detects if running in a popup (has window.opener)
    2. Sends a postMessage to the parent window with the result
    3. Closes itself if in a popup, or redirects if not
    """
    message_escaped = json.dumps(message)
    redirect_url_escaped = json.dumps(redirect_url)
    success_js = 'true' if success else 'false'
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Epic Authorization {'Complete' if success else 'Failed'}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: {'#d4edda' if success else '#f8d7da'};
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            max-width: 400px;
        }}
        .icon {{
            font-size: 48px;
            margin-bottom: 20px;
        }}
        h1 {{
            color: {'#155724' if success else '#721c24'};
            margin: 0 0 15px 0;
            font-size: 24px;
        }}
        p {{
            color: #666;
            margin: 0 0 20px 0;
        }}
        .redirect-note {{
            font-size: 14px;
            color: #888;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{'✓' if success else '✗'}</div>
        <h1>{'Authorization Successful!' if success else 'Authorization Failed'}</h1>
        <p id="message-display"></p>
        <p class="redirect-note">This window will close automatically...</p>
    </div>
    
    <script>
        (function() {{
            // Safely parse the escaped values
            var message = {message_escaped};
            var redirectUrl = {redirect_url_escaped};
            var success = {success_js};
            
            // Display the message
            document.getElementById('message-display').textContent = message;
            
            // Determine the target origin for postMessage
            var targetOrigin = window.location.origin;
            
            // Message payload
            var messagePayload = {{
                type: 'epic_oauth_complete',
                success: success,
                message: message,
                redirectUrl: redirectUrl
            }};
            
            // Check if we're in a popup (has opener)
            if (window.opener && !window.opener.closed) {{
                try {{
                    // Send message to parent window
                    window.opener.postMessage(messagePayload, targetOrigin);
                    
                    // Close this popup after a short delay
                    setTimeout(function() {{
                        window.close();
                    }}, 1500);
                }} catch (e) {{
                    console.error('Failed to communicate with opener:', e);
                    // Fall back to redirect
                    setTimeout(function() {{
                        window.location.href = redirectUrl;
                    }}, 2000);
                }}
            }} else {{
                // Not in a popup, redirect normally
                setTimeout(function() {{
                    window.location.href = redirectUrl;
                }}, 2000);
            }}
            
            // Fallback: if popup doesn't close after 5 seconds, show redirect link
            setTimeout(function() {{
                if (!window.closed) {{
                    var link = document.createElement('a');
                    link.href = redirectUrl;
                    link.textContent = 'click here';
                    var note = document.querySelector('.redirect-note');
                    note.textContent = 'If this window doesn\\'t close, ';
                    note.appendChild(link);
                    note.appendChild(document.createTextNode(' to continue.'));
                }}
            }}, 5000);
        }})();
    </script>
</body>
</html>'''
    
    return Markup(html)


def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def require_approved_organization(f):
    """Decorator to require organization approval before Epic integration access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        
        org = current_user.organization
        if not org:
            flash('No organization found for your account.', 'error')
            return redirect(url_for('index'))
        
        # Use unified billing_state for access control
        billing = org.billing_state
        
        if not billing['can_access_oauth']:
            if billing['state'] == 'pending_approval':
                flash('Epic FHIR integration will be available once your organization is approved. Complete your onboarding and await root admin approval. Your subscription will begin upon approval.', 'warning')
            else:
                flash('Epic FHIR integration requires an active subscription.', 'warning')
            return redirect(url_for('admin.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

oauth_bp = Blueprint('oauth', __name__)
logger = logging.getLogger(__name__)


@oauth_bp.route('/epic-authorize-debug')
@login_required
@subscription_required
@require_admin
@require_approved_organization
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
@subscription_required
@require_admin
@require_approved_organization
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


@oauth_bp.route('/launch')
def smart_launch():
    """
    SMART on FHIR Launch endpoint
    Handles launch with iss and launch parameters
    """
    try:
        # Get launch parameters
        iss = request.args.get('iss')
        launch = request.args.get('launch')
        
        logger.info(f"SMART launch initiated - iss: {iss}, launch: {launch}")
        
        if not iss:
            return jsonify({"error": "Missing required parameter 'iss'"}), 400
        
        # Fetch SMART configuration
        try:
            cfg = smart_discovery.fetch(iss)
            logger.info(f"Retrieved SMART config from {iss}")
        except Exception as e:
            logger.error(f"SMART discovery failed for {iss}: {e}")
            return jsonify({"error": f"SMART discovery failed: {e}"}), 400
        
        # Get organization's Epic configuration
        if current_user.is_authenticated:
            org = current_user.organization
            if not org or not org.epic_client_id:
                flash('Epic FHIR configuration not found. Please configure Epic credentials first.', 'error')
                return redirect(url_for('fhir.epic_config'))
        else:
            # For public launch, use default config or redirect to login
            return redirect(url_for('auth.login', next=request.url))
        
        # Build authorization URL with SMART launch context
        redirect_uri = url_for('oauth.epic_callback', _external=True)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://')
        
        # Generate state parameter
        state = secrets.token_urlsafe(32)
        
        # Store launch context in session
        session['epic_oauth_state'] = state
        session['epic_launch_context'] = {
            'iss': iss,
            'launch': launch,
            'timestamp': datetime.now().isoformat()
        }
        
        # Build authorization parameters
        scopes = ['openid', 'fhirUser', 'launch']
        if launch:
            scopes.append('launch')  # Required for EHR launch
        else:
            scopes.extend(['launch/patient'])  # Standalone launch
        
        # Add data access scopes
        scopes.extend([
            'patient/Patient.read',
            'patient/Observation.read',
            'patient/Condition.read',
            'patient/DocumentReference.read'
        ])
        
        from urllib.parse import urlencode
        params = {
            'response_type': 'code',
            'client_id': org.epic_client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(scopes),
            'state': state,
            'aud': iss
        }
        
        # Add launch parameter if provided
        if launch:
            params['launch'] = launch
        
        auth_url = f"{cfg['authorization_endpoint']}?{urlencode(params)}"
        
        logger.info(f"Redirecting to Epic authorization: {auth_url}")
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Error in SMART launch: {str(e)}")
        return jsonify({"error": f"Launch failed: {str(e)}"}), 500


@oauth_bp.route('/epic-authorize')
@login_required
@subscription_required
@require_admin
@require_approved_organization
def epic_authorize():
    """
    Start Epic OAuth2 authorization flow
    Redirects user to Epic's authorization endpoint
    """
    try:
        # SECURITY DEBUG: Track user and organization context
        logger.info(f"=== EPIC OAUTH AUTHORIZE DEBUG ===")
        logger.info(f"Current user ID: {current_user.id}")
        logger.info(f"Current user username: {current_user.username}")
        logger.info(f"Current user org_id: {current_user.org_id}")
        logger.info(f"Current user organization object: {current_user.organization}")
        logger.info(f"Session epic_org_id: {session.get('epic_org_id', 'None')}")
        if current_user.organization:
            logger.info(f"Organization ID: {current_user.organization.id}")
            logger.info(f"Organization name: {current_user.organization.name}")
            logger.info(f"Organization epic_client_id: {current_user.organization.epic_client_id}")
        logger.info(f"================================")
        
        # Get organization's Epic configuration
        org = current_user.organization
        if not org or not org.epic_client_id:
            logger.error(f"SECURITY: User {current_user.username} (org {current_user.org_id}) attempted OAuth without Epic credentials")
            flash('Epic FHIR configuration not found. Please configure Epic credentials first.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # ADDITIONAL SECURITY CHECK: Verify organization owns Epic credentials
        if org.id != current_user.org_id:
            logger.error(f"CRITICAL SECURITY VIOLATION: User {current_user.username} (org {current_user.org_id}) attempting OAuth with different organization {org.id}")
            flash('Security error: Organization mismatch detected.', 'error')
            return redirect(url_for('auth.logout'))
        
        # ADDITIONAL SECURITY CHECK: Verify Epic credentials are properly configured for THIS specific organization
        if not org.epic_client_secret:
            logger.error(f"SECURITY: Organization {org.id} missing Epic client secret")
            flash('Epic client secret not configured. Please complete Epic configuration.', 'error')
            return redirect(url_for('fhir.epic_config'))

        # Initialize FHIR client with organization config
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }

        redirect_uri = url_for('oauth.epic_callback', _external=True)
        # Ensure HTTPS for Epic OAuth (required by Epic App Orchard)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://')
        
        fhir_client = FHIRClient(epic_config, redirect_uri)

        # Debug logging for OAuth flow
        logger.info(f"OAuth redirect URI: {redirect_uri}")
        logger.info(f"Epic client ID: {org.epic_client_id}")
        logger.info(f"Epic auth URL: {fhir_client.auth_url}")

        # Check if scope changes require session cleanup
        default_scopes = [
            'openid', 'fhirUser', 'launch/patient',
            'patient/Patient.read', 'patient/Observation.read', 
            'patient/Condition.read', 'patient/DocumentReference.read'
        ]
        
        # Prepare for potential scope changes
        scope_prep_result = EpicSessionCleanupService.prepare_for_scope_change(
            org.id, default_scopes
        )
        
        if scope_prep_result['scope_changed']:
            logger.info(f"Scope changes detected for org {org.id}, session cleanup performed")
            if scope_prep_result['added_scopes']:
                flash(f'OAuth scope expanded to include: {", ".join(scope_prep_result["added_scopes"])}', 'info')
        
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


def require_provider_access(f):
    """Decorator to require user has access to the specified provider"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provider_id = kwargs.get('provider_id') or request.args.get('provider_id')
        if not provider_id:
            abort(400, description='Provider ID is required')
        
        provider = Provider.query.filter_by(id=provider_id).first()
        if not provider:
            abort(404, description='Provider not found')
        
        if provider.org_id != current_user.org_id:
            abort(403, description='Access denied to this provider')
        
        if current_user.role == 'admin':
            return f(*args, **kwargs)
        
        assignment = UserProviderAssignment.query.filter_by(
            user_id=current_user.id,
            provider_id=provider_id
        ).first()
        
        if not assignment:
            abort(403, description='You do not have access to this provider')
        
        return f(*args, **kwargs)
    return decorated_function


@oauth_bp.route('/provider/<int:provider_id>/epic-authorize')
@login_required
@subscription_required
@require_approved_organization
def provider_epic_authorize(provider_id):
    """
    Start Epic OAuth2 authorization flow for a specific provider.
    The authenticated user authorizing must be the provider themselves 
    (practitioner must do their own OAuth).
    
    This stores tokens on the Provider model and extracts fhirUser claim.
    """
    try:
        provider = Provider.query.filter_by(id=provider_id, org_id=current_user.org_id).first()
        if not provider:
            flash('Provider not found.', 'error')
            return redirect(url_for('admin_dashboard.provider_management'))
        
        if not provider.is_active:
            flash('This provider is inactive.', 'error')
            return redirect(url_for('admin_dashboard.provider_management'))
        
        logger.info(f"=== PROVIDER EPIC OAUTH AUTHORIZE ===")
        logger.info(f"Provider ID: {provider.id}")
        logger.info(f"Provider Name: {provider.name}")
        logger.info(f"Authorizing User: {current_user.username}")
        logger.info(f"Organization: {current_user.organization.name}")
        
        org = current_user.organization
        if not org or not org.epic_client_id:
            flash('Epic FHIR configuration not found. Please configure Epic credentials first.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        if not org.epic_client_secret:
            flash('Epic client secret not configured. Please complete Epic configuration.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }

        redirect_uri = url_for('oauth.epic_callback', _external=True)
        if redirect_uri.startswith('http://'):
            redirect_uri = redirect_uri.replace('http://', 'https://')
        
        fhir_client = FHIRClient(epic_config, redirect_uri)
        
        provider_scopes = [
            'openid', 'fhirUser', 'launch/patient',
            'offline_access',
            'patient/Patient.rs',
            'patient/Observation.rs',
            'patient/Condition.rs',
            'patient/DocumentReference.rs',
            'patient/DocumentReference.c',
            'patient/DiagnosticReport.rs',
            'patient/Appointment.rs',
            'patient/Immunization.rs',
        ]
        
        auth_url, state = fhir_client.get_authorization_url(scopes=provider_scopes)
        
        session['epic_oauth_state'] = state
        session['epic_auth_timestamp'] = datetime.now().isoformat()
        session['epic_oauth_provider_id'] = provider.id
        session['epic_oauth_type'] = 'provider'
        
        logger.info(f"Starting Epic OAuth flow for provider {provider.id} ({provider.name})")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error starting provider Epic OAuth flow: {str(e)}")
        flash('Failed to start Epic authorization. Please try again.', 'error')
        return redirect(url_for('admin_dashboard.provider_management'))


@oauth_bp.route('/provider/<int:provider_id>/epic-disconnect', methods=['POST'])
@login_required
@subscription_required
@require_approved_organization
def provider_epic_disconnect(provider_id):
    """
    Disconnect Epic OAuth2 for a specific provider.
    Clears stored tokens on the Provider model.
    """
    try:
        provider = Provider.query.filter_by(id=provider_id, org_id=current_user.org_id).first()
        if not provider:
            flash('Provider not found.', 'error')
            return redirect(url_for('admin_dashboard.provider_management'))
        
        provider.access_token = None
        provider.refresh_token = None
        provider.token_expires_at = None
        provider.token_scope = None
        provider.is_epic_connected = False
        provider.epic_practitioner_id = None
        provider.last_epic_error = None
        
        db.session.commit()
        
        logger.info(f"Epic disconnected for provider {provider.id} ({provider.name})")
        flash(f'Epic connection disconnected for {provider.name}.', 'info')
        return redirect(url_for('admin_dashboard.provider_management'))

    except Exception as e:
        logger.error(f"Error disconnecting provider Epic OAuth: {str(e)}")
        flash('Error disconnecting from Epic', 'error')
        return redirect(url_for('admin_dashboard.provider_management'))


def extract_fhir_user_practitioner_id(id_token_or_token_data):
    """
    Extract the Practitioner ID from the fhirUser claim in the ID token.
    
    The fhirUser claim format is typically:
    - "Practitioner/eOPiqtxdD35SmjVN0xkGLtg3" (relative reference)
    - "https://fhir.epic.com/api/FHIR/R4/Practitioner/eOPiqtxdD35SmjVN0xkGLtg3" (absolute URL)
    
    Returns the Practitioner ID portion, or None if not found/invalid.
    """
    import base64
    
    fhir_user = None
    
    if isinstance(id_token_or_token_data, dict):
        fhir_user = id_token_or_token_data.get('fhirUser')
        if not fhir_user and 'id_token' in id_token_or_token_data:
            try:
                id_token = id_token_or_token_data['id_token']
                parts = id_token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += '=' * padding
                    decoded = base64.urlsafe_b64decode(payload)
                    claims = json.loads(decoded)
                    fhir_user = claims.get('fhirUser')
            except Exception as e:
                logger.warning(f"Failed to decode id_token for fhirUser: {e}")
    elif isinstance(id_token_or_token_data, str):
        try:
            parts = id_token_or_token_data.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += '=' * padding
                decoded = base64.urlsafe_b64decode(payload)
                claims = json.loads(decoded)
                fhir_user = claims.get('fhirUser')
        except Exception as e:
            logger.warning(f"Failed to decode id_token string for fhirUser: {e}")
    
    if not fhir_user:
        logger.warning("No fhirUser claim found in token data")
        return None
    
    if 'Practitioner/' in fhir_user:
        practitioner_id = fhir_user.split('Practitioner/')[-1].split('?')[0].split('/')[0]
        logger.info(f"Extracted Practitioner ID from fhirUser: {practitioner_id}")
        return practitioner_id
    
    logger.warning(f"fhirUser claim does not contain Practitioner reference: {fhir_user}")
    return None


@oauth_bp.route('/epic-callback')
@login_required
@subscription_required
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
            
            # Check if this is a session conflict error and handle automatically
            if current_user.is_authenticated:
                org_id = current_user.org_id if current_user.organization else None
                if org_id:
                    conflict_result = EpicSessionCleanupService.handle_oauth_conflict_error(
                        org_id, error, error_description
                    )
                    
                    if conflict_result['is_conflict'] and conflict_result['success']:
                        logger.info(f"Epic session conflict resolved for org {org_id}")
                        flash('Epic session conflict detected. Server-side sessions cleared. '
                              'To fully resolve: (1) Open Epic connection in a private/incognito window, OR '
                              '(2) Clear epic.com cookies from your browser, then try again.', 'warning')
                        return redirect(url_for('fhir.epic_config'))
                    elif conflict_result['is_conflict']:
                        logger.error(f"Failed to resolve Epic session conflict for org {org_id}")
                        flash('Epic session conflict detected. Please: (1) Try in a private/incognito window, OR '
                              '(2) Clear epic.com cookies from your browser, OR '
                              '(3) Use the "Clear Epic Sessions" button below, then try again.', 'error')
                        return redirect(url_for('fhir.epic_config'))
            
            # For non-conflict errors or if conflict resolution failed
            flash(f'Epic authorization failed: {error_description or error}', 'error')
            return render_oauth_completion_page(
                success=False,
                message=f'Epic authorization failed: {error_description or error}',
                redirect_url=url_for('epic_registration.epic_registration')
            )

        if not code:
            logger.error("No authorization code received from Epic OAuth callback")
            flash('No authorization code received from Epic', 'error')
            return render_oauth_completion_page(
                success=False,
                message='No authorization code received from Epic',
                redirect_url=url_for('epic_registration.epic_registration')
            )

        # Validate state parameter
        stored_state = session.get('epic_oauth_state')
        if not stored_state or stored_state != state:
            logger.error(f"Invalid OAuth state parameter - stored: {stored_state}, received: {state}")
            flash('Invalid authorization state. Please try again.', 'error')
            return render_oauth_completion_page(
                success=False,
                message='Invalid authorization state. Please try again.',
                redirect_url=url_for('epic_registration.epic_registration')
            )

        # Check if user is still logged in
        if not current_user.is_authenticated:
            flash('Session expired during authorization', 'error')
            return redirect(url_for('auth.login'))

        # SECURITY DEBUG: Track user and organization context in callback
        logger.info(f"=== EPIC OAUTH CALLBACK USER DEBUG ===")
        logger.info(f"Callback current user ID: {current_user.id}")
        logger.info(f"Callback current user username: {current_user.username}")
        logger.info(f"Callback current user org_id: {current_user.org_id}")
        logger.info(f"Callback current user organization object: {current_user.organization}")
        if current_user.organization:
            logger.info(f"Callback Organization ID: {current_user.organization.id}")
            logger.info(f"Callback Organization name: {current_user.organization.name}")
            logger.info(f"Callback Organization epic_client_id: {current_user.organization.epic_client_id}")
        logger.info(f"=======================================")

        # Get organization config
        org = current_user.organization
        
        # ADDITIONAL SECURITY CHECK: Verify organization consistency in callback
        if not org or org.id != current_user.org_id:
            logger.error(f"CRITICAL SECURITY VIOLATION IN CALLBACK: User {current_user.username} (org {current_user.org_id}) with organization mismatch {org.id if org else 'None'}")
            flash('Security error: Organization mismatch in callback.', 'error')
            return redirect(url_for('auth.logout'))
        
        # SECURITY CHECK: Verify organization has Epic credentials (should not proceed without them)
        if not org.epic_client_id or not org.epic_client_secret:
            logger.error(f"CRITICAL SECURITY ERROR: Callback reached for organization {org.id} without proper Epic credentials")
            flash('Security error: No Epic credentials configured for your organization.', 'error')
            return redirect(url_for('fhir.epic_config'))
        
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

        # Check if this is a provider-specific OAuth flow
        oauth_type = session.get('epic_oauth_type')
        provider_id = session.get('epic_oauth_provider_id')
        
        from models import EpicCredentials
        from app import db

        # Calculate token expiry
        token_expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
        
        if oauth_type == 'provider' and provider_id:
            # Provider-specific OAuth: store tokens on Provider model
            provider = Provider.query.filter_by(id=provider_id, org_id=org.id).first()
            
            if not provider:
                logger.error(f"Provider {provider_id} not found during OAuth callback")
                flash('Provider not found. Please try again.', 'error')
                return redirect(url_for('admin_dashboard.provider_management'))
            
            # Extract fhirUser claim to get Practitioner ID
            practitioner_id = extract_fhir_user_practitioner_id(token_data)
            
            if practitioner_id:
                provider.epic_practitioner_id = practitioner_id
                logger.info(f"Stored Epic Practitioner ID {practitioner_id} for provider {provider.name}")
            else:
                logger.warning(f"No Practitioner ID extracted from fhirUser for provider {provider.name}")
            
            # Store tokens on Provider model
            provider.access_token = token_data.get('access_token')
            provider.refresh_token = token_data.get('refresh_token')
            provider.token_expires_at = token_expires_at
            provider.token_scope = ' '.join(token_data.get('scope', '').split())
            provider.is_epic_connected = True
            provider.epic_connection_date = datetime.now()
            provider.last_epic_sync = datetime.now()
            provider.last_epic_error = None
            
            db.session.commit()
            
            # Clean up provider OAuth session state
            session.pop('epic_oauth_state', None)
            session.pop('epic_auth_timestamp', None)
            session.pop('epic_oauth_provider_id', None)
            session.pop('epic_oauth_type', None)
            
            logger.info(f"Epic OAuth flow completed for provider {provider.id} ({provider.name})")
            flash(f'Successfully connected {provider.name} to Epic FHIR!', 'success')
            
            return render_oauth_completion_page(
                success=True,
                message=f'Successfully connected {provider.name} to Epic FHIR!',
                redirect_url=url_for('admin_dashboard.provider_management')
            )
        
        else:
            # Organization-level OAuth (legacy): store tokens on EpicCredentials
            # Create or update Epic credentials for the organization
            epic_creds = EpicCredentials.query.filter_by(org_id=org.id).first()
            if not epic_creds:
                epic_creds = EpicCredentials(org_id=org.id)
                db.session.add(epic_creds)

            # Update token data
            epic_creds.access_token = token_data.get('access_token')
            epic_creds.refresh_token = token_data.get('refresh_token')
            epic_creds.token_expires_at = token_expires_at
            epic_creds.token_scope = ' '.join(token_data.get('scope', '').split())
            epic_creds.updated_at = datetime.now()

            # Update organization connection status
            org.is_epic_connected = True
            org.epic_token_expiry = token_expires_at
            org.last_epic_sync = datetime.now()
            org.last_epic_error = None
            org.connection_retry_count = 0

            db.session.commit()

            # Also store in session for immediate admin access
            # SECURITY: Store organization ID with session tokens for security isolation
            session['epic_access_token'] = token_data.get('access_token')
            session['epic_refresh_token'] = token_data.get('refresh_token')
            session['epic_token_expires'] = token_expires_at.isoformat()
            session['epic_token_scopes'] = token_data.get('scope', '').split()
            session['epic_patient_id'] = token_data.get('patient')
            session['epic_org_id'] = org.id  # Track which organization these tokens belong to

            # Clean up OAuth state
            session.pop('epic_oauth_state', None)
            session.pop('epic_auth_timestamp', None)

            logger.info(f"Epic OAuth flow completed successfully for organization {org.id}")
            flash('Successfully connected to Epic FHIR! All users in your organization can now sync with Epic.', 'success')

            # Return popup-aware response that uses postMessage for cross-origin communication
            return render_oauth_completion_page(
                success=True,
                message='Successfully connected to Epic FHIR!',
                redirect_url=url_for('epic_registration.epic_registration')
            )

    except Exception as e:
        logger.error(f"Error handling Epic OAuth callback: {str(e)}", exc_info=True)
        flash('Failed to complete Epic authorization. Please try again.', 'error')
        return render_oauth_completion_page(
            success=False,
            message='Failed to complete Epic authorization. Please try again.',
            redirect_url=url_for('epic_registration.epic_registration')
        )


@oauth_bp.route('/epic-disconnect', methods=['POST'])
@login_required
@require_admin
@require_approved_organization
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
            'epic_patient_id',
            'epic_org_id'  # Clear organization tracking too
        ]

        for key in epic_keys:
            session.pop(key, None)

        flash('Disconnected from Epic FHIR', 'info')
        return redirect(url_for('fhir.epic_config'))

    except Exception as e:
        logger.error(f"Error disconnecting Epic OAuth: {str(e)}")
        flash('Error disconnecting from Epic', 'error')
        return redirect(url_for('fhir.epic_config'))


@oauth_bp.route('/epic-clear-sessions', methods=['POST'])
@login_required
@require_admin
def epic_clear_sessions():
    """
    Clear all Epic sessions and tokens to resolve browser conflicts
    Useful when Epic shows "another process already logged in" error
    """
    try:
        org = current_user.organization
        if not org:
            flash('Organization not found', 'error')
            return redirect(url_for('fhir.epic_config'))
        
        # Perform comprehensive session cleanup
        cleanup_result = EpicSessionCleanupService.clear_all_epic_sessions(org.id)
        
        if cleanup_result['success']:
            logger.info(f"Manual Epic session cleanup completed for org {org.id}")
            flash('Epic sessions cleared successfully. You can now try connecting again.', 'success')
        else:
            logger.error(f"Manual Epic session cleanup failed for org {org.id}: {cleanup_result['message']}")
            flash(f'Session cleanup failed: {cleanup_result["message"]}', 'error')
        
        return redirect(url_for('fhir.epic_config'))

    except Exception as e:
        logger.error(f"Error clearing Epic sessions: {str(e)}")
        flash('Error clearing Epic sessions', 'error')
        return redirect(url_for('fhir.epic_config'))


@oauth_bp.route('/check-epic-credentials')
@login_required
@require_admin
@require_approved_organization
def check_epic_credentials():
    """
    Check if organization has Epic credentials configured (for UI validation)
    Returns JSON response for AJAX calls
    """
    try:
        org = current_user.organization
        
        # SECURITY CHECK: Verify organization consistency
        if not org or org.id != current_user.org_id:
            logger.error(f"SECURITY VIOLATION: User {current_user.username} (org {current_user.org_id}) organization mismatch in credentials check")
            return jsonify({'error': 'Organization security error', 'has_credentials': False}), 403
        
        has_credentials = bool(org.epic_client_id and org.epic_client_secret)
        
        if not has_credentials:
            return jsonify({
                'has_credentials': False,
                'error': 'Epic FHIR configuration not found. Please configure Epic credentials first.',
                'missing_fields': []
            })
        
        missing_fields = []
        if not org.epic_client_id:
            missing_fields.append('Epic Client ID')
        if not org.epic_client_secret:
            missing_fields.append('Epic Client Secret')
        if not org.epic_fhir_url:
            missing_fields.append('Epic FHIR Base URL')
        
        return jsonify({
            'has_credentials': len(missing_fields) == 0,
            'missing_fields': missing_fields,
            'error': f'Missing required fields: {", ".join(missing_fields)}' if missing_fields else None
        })
        
    except Exception as e:
        logger.error(f"Error checking Epic credentials: {str(e)}")
        return jsonify({'error': str(e), 'has_credentials': False}), 500


@oauth_bp.route('/epic-status')
@login_required
@require_admin
@require_approved_organization
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

        # SECURITY: Only check tokens for current user's organization
        from models import EpicCredentials
        org = current_user.organization
        
        # SECURITY CHECK: Verify organization consistency
        if not org or org.id != current_user.org_id:
            logger.error(f"SECURITY VIOLATION: User {current_user.username} (org {current_user.org_id}) organization mismatch in status check")
            return jsonify({'error': 'Organization security error'}), 403
        
        # SECURITY CHECK: Only query credentials for user's specific organization
        epic_creds = EpicCredentials.query.filter_by(org_id=current_user.org_id).first() if org else None

        if epic_creds and epic_creds.access_token:
            status['connected'] = True
            status['expires_at'] = epic_creds.token_expires_at.isoformat() if epic_creds.token_expires_at else None
            status['scopes'] = epic_creds.token_scope.split() if epic_creds.token_scope else []
            status['expired'] = epic_creds.is_expired if hasattr(epic_creds, 'is_expired') else (
                epic_creds.token_expires_at and datetime.now() >= epic_creds.token_expires_at
            )
        else:
            # SECURITY: Always check session token organization before using
            session_org_id = session.get('epic_org_id')
            
            # Clear any session tokens that don't belong to current organization
            if session_org_id and session_org_id != current_user.org_id:
                logger.warning(f"SECURITY: Clearing cross-organization session tokens for user {current_user.username} (org {current_user.org_id}, session org {session_org_id})")
                epic_keys = ['epic_access_token', 'epic_refresh_token', 'epic_token_expires', 'epic_token_scopes', 'epic_patient_id', 'epic_org_id']
                for key in epic_keys:
                    session.pop(key, None)
                status['connected'] = False
                status['expired'] = True
            elif session_org_id == current_user.org_id:
                # Session tokens belong to current organization - safe to use
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
                else:
                    status['connected'] = False
                    status['expired'] = True
            else:
                # No session organization ID or doesn't match - no tokens available
                status['connected'] = False
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


@oauth_bp.route('/epic-flow-status')
def epic_flow_status():
    """
    Debug endpoint to check OAuth flow session status
    """
    try:
        session_info = {
            'epic_oauth_state': session.get('epic_oauth_state', 'None'),
            'epic_auth_timestamp': session.get('epic_auth_timestamp', 'None'),
            'epic_access_token': 'Present' if session.get('epic_access_token') else 'None',
            'epic_refresh_token': 'Present' if session.get('epic_refresh_token') else 'None',
            'epic_token_expires': session.get('epic_token_expires', 'None'),
            'epic_patient_id': session.get('epic_patient_id', 'None'),
            'user_authenticated': current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else 'Unknown'
        }
        
        return f"""
        <h1>Epic OAuth Flow Status</h1>
        <h3>Session Information:</h3>
        <table border="1" cellpadding="5">
            <tr><th>Session Key</th><th>Value</th></tr>
            {''.join(f'<tr><td>{key}</td><td>{value}</td></tr>' for key, value in session_info.items())}
        </table>
        
        <h3>Available OAuth Routes:</h3>
        <ul>
            <li><a href="{url_for('oauth.epic_authorize_debug')}">/oauth/epic-authorize-debug</a> - Debug authorization URL</li>
            <li><a href="{url_for('oauth.epic_oauth_debug')}">/oauth/epic-oauth-debug</a> - Debug OAuth parameters</li>
            <li><a href="{url_for('oauth.epic_authorize')}">/oauth/epic-authorize</a> - Start OAuth flow</li>
            <li><a href="{url_for('oauth.epic_callback_test')}">/oauth/epic-callback-test</a> - Test callback accessibility</li>
            <li><a href="{url_for('oauth.epic_status')}">/oauth/epic-status</a> - Check connection status (JSON)</li>
        </ul>
        
        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
        """
        
    except Exception as e:
        return f"Error checking OAuth flow status: {str(e)}"


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


def get_epic_fhir_client_background(organization_id: int):
    """
    Background-compatible helper function to get configured FHIR client with stored credentials
    Loads tokens from EpicCredentials table instead of session
    For use in background processes, async tasks, and scheduled jobs
    """
    from models import Organization, EpicCredentials
    
    try:
        # Get organization and verify it exists
        org = Organization.query.get(organization_id)
        if not org or not org.epic_client_id:
            logger.error(f"Organization {organization_id} not found or missing Epic configuration")
            return None
        
        # Load stored credentials from database
        epic_creds = EpicCredentials.query.filter_by(org_id=organization_id).first()
        if not epic_creds:
            logger.error(f"No Epic credentials found for organization {organization_id}")
            return None
        
        # Check if credentials are available
        if not epic_creds.access_token:
            logger.error(f"No access token stored for organization {organization_id}")
            return None
        
        # Initialize client with organization config
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        
        fhir_client = FHIRClient(epic_config, organization=org)
        
        # Calculate expires_in from stored expiry
        expires_in = 3600  # Default
        if epic_creds.token_expires_at:
            expires_in = max(0, int((epic_creds.token_expires_at - datetime.now()).total_seconds()))
        
        # Parse scopes
        scopes = []
        if epic_creds.token_scope:
            scopes = epic_creds.token_scope.split()
        
        # Set tokens from database
        fhir_client.set_tokens(
            epic_creds.access_token,
            epic_creds.refresh_token,
            expires_in,
            scopes
        )
        
        # Update last used timestamp
        epic_creds.last_used = datetime.now()
        db.session.commit()
        
        logger.info(f"Background Epic FHIR client created for organization {organization_id}")
        return fhir_client
        
    except Exception as e:
        logger.error(f"Error creating background Epic FHIR client for org {organization_id}: {str(e)}")
        return None