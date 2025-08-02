"""
Authentication routes for user login, logout, and session management.
Handles both standard login and SMART on FHIR authentication.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import logging

from models import User, db
from admin.logs import AdminLogger

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)
admin_logger = AdminLogger()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page and authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('screening.screening_list'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html')
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and user.check_password(password):
            # Successful login
            login_user(user, remember=remember_me)
            
            # Update last login
            from datetime import datetime
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log the login
            admin_logger.log_action(
                user_id=user.id,
                action='user_login',
                details=f'User {username} logged in successfully',
                ip_address=request.remote_addr
            )
            
            # Redirect to intended page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            elif user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('screening.screening_list'))
        else:
            # Failed login
            admin_logger.log_action(
                action='failed_login',
                details=f'Failed login attempt for username: {username}',
                ip_address=request.remote_addr
            )
            
            flash('Invalid username or password.', 'error')
            logger.warning(f"Failed login attempt for username: {username}")
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    # Log the logout
    admin_logger.log_action(
        user_id=current_user.id,
        action='user_logout',
        details=f'User {current_user.username} logged out',
        ip_address=request.remote_addr
    )
    
    username = current_user.username
    logout_user()
    flash(f'You have been logged out successfully.', 'info')
    logger.info(f"User {username} logged out")
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/fhir/authorize')
def fhir_authorize():
    """Initiate SMART on FHIR authorization flow."""
    try:
        from emr.fhir_client import FHIRClient
        
        fhir_client = FHIRClient()
        
        # Generate state parameter for security
        import secrets
        state = secrets.token_urlsafe(32)
        session['fhir_state'] = state
        
        # Get authorization URL
        auth_url = fhir_client.get_authorization_url(state=state)
        
        if not auth_url:
            flash('Unable to connect to FHIR server. Please try again later.', 'error')
            return redirect(url_for('auth.login'))
        
        admin_logger.log_action(
            action='fhir_auth_initiated',
            details='SMART on FHIR authorization flow initiated',
            ip_address=request.remote_addr
        )
        
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating FHIR authorization: {e}")
        flash('Authentication service is currently unavailable.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/fhir/callback')
def fhir_callback():
    """Handle SMART on FHIR authorization callback."""
    try:
        # Verify state parameter
        state = request.args.get('state')
        if not state or state != session.get('fhir_state'):
            flash('Invalid authentication state. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        # Get authorization code
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            flash(f'FHIR authorization error: {error}', 'error')
            admin_logger.log_action(
                action='fhir_auth_error',
                details=f'FHIR authorization error: {error}',
                ip_address=request.remote_addr
            )
            return redirect(url_for('auth.login'))
        
        if not code:
            flash('No authorization code received.', 'error')
            return redirect(url_for('auth.login'))
        
        # Exchange code for token
        from emr.fhir_client import FHIRClient
        fhir_client = FHIRClient()
        
        token_result = fhir_client.exchange_code_for_token(code)
        
        if not token_result['success']:
            flash('Failed to obtain access token.', 'error')
            admin_logger.log_action(
                action='fhir_token_error',
                details=f'Failed to exchange code for token: {token_result.get("error")}',
                ip_address=request.remote_addr
            )
            return redirect(url_for('auth.login'))
        
        # Store token information in session (in production, this should be more secure)
        session['fhir_token'] = token_result['token_data']
        session['fhir_authenticated'] = True
        
        # For now, create or get a default FHIR user
        # In production, this would extract user info from FHIR
        fhir_user = User.query.filter_by(username='fhir_user').first()
        if not fhir_user:
            fhir_user = User(
                username='fhir_user',
                email='fhir@example.com',
                is_admin=False
            )
            fhir_user.set_password('fhir_default')  # This should be more secure
            db.session.add(fhir_user)
            db.session.commit()
        
        # Log in the FHIR user
        login_user(fhir_user)
        
        admin_logger.log_action(
            user_id=fhir_user.id,
            action='fhir_login_success',
            details='Successful SMART on FHIR authentication',
            ip_address=request.remote_addr
        )
        
        flash('Successfully authenticated with FHIR system.', 'success')
        return redirect(url_for('screening.screening_list'))
        
    except Exception as e:
        logger.error(f"Error in FHIR callback: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page."""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password."""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('auth/change_password.html')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/change_password.html')
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='password_changed',
            details=f'User {current_user.username} changed password',
            ip_address=request.remote_addr
        )
        
        flash('Password changed successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration (if enabled)."""
    # For security in healthcare, registration might be disabled
    # This is a basic implementation
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/register.html')
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            flash('Username or email already exists.', 'error')
            return render_template('auth/register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            is_admin=False  # New users are not admin by default
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        admin_logger.log_action(
            action='user_registered',
            details=f'New user registered: {username}',
            ip_address=request.remote_addr
        )
        
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/check_session')
@login_required
def check_session():
    """Check if user session is still valid (AJAX endpoint)."""
    return {
        'authenticated': True,
        'user_id': current_user.id,
        'username': current_user.username,
        'is_admin': current_user.is_admin
    }

@auth_bp.route('/session_timeout')
def session_timeout():
    """Handle session timeout."""
    flash('Your session has expired. Please log in again.', 'warning')
    return redirect(url_for('auth.login'))

# Error handlers specific to auth
@auth_bp.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized access."""
    flash('You must be logged in to access this page.', 'error')
    return redirect(url_for('auth.login'))
