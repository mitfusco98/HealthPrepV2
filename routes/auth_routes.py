"""
Authentication routes for user login and session management
Enhanced with rate limiting, security hardening, and breach alerting
"""

import logging
from datetime import datetime
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import log_admin_event
from utils.security import RateLimiter, log_security_event
from services.security_alerts import SecurityAlertService

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

# Security question verification limits
SECURITY_QUESTION_MAX_ATTEMPTS = 3
SECURITY_VERIFICATION_TIMEOUT_SECONDS = 300  # 5 minutes


def _requires_login_security_questions(user):
    """
    Determine if a user requires security question verification at login
    
    Rules:
    - Regular users (MA, nurse): Never require security questions
    - Org admins: MUST set up security questions; can bypass if Epic OAuth is active OR recent successful login (last 1 hour)
    - Root admins: Always require security questions (no bypass ever)
    
    Args:
        user: User object
        
    Returns:
        bool: True if security questions are required, 'force_setup' if questions not set
    """
    from datetime import datetime, timedelta
    
    # Regular users never need security questions at login
    if not user.is_admin and not user.is_root_admin:
        return False
    
    # Root admins always require security questions
    if user.is_root_admin:
        # If they don't have questions set up, force them to set up
        if not user.has_security_questions():
            return 'force_setup'
        return True
    
    # Org admins: Must have security questions set up
    if user.is_admin:
        if not user.has_security_questions():
            # Force org admins to set up security questions (just like root admins)
            return 'force_setup'
        
        # Bypass if Epic OAuth is active (valid, non-expired tokens) for their organization
        if user.organization:
            epic_creds = user.organization.epic_credentials
            if epic_creds:
                # Get most recent credential
                latest_cred = max(epic_creds, key=lambda c: c.updated_at)
                if latest_cred and not latest_cred.is_expired:
                    logger.info(f"Bypassing security questions for {user.username}: Epic OAuth active with valid tokens")
                    return False
        
        # Bypass if recent successful login (within last 1 hour)
        if user.last_login:
            time_since_login = datetime.utcnow() - user.last_login
            hours_since_login = time_since_login.total_seconds() / 3600
            if hours_since_login <= 1:
                logger.info(f"Bypassing security questions for {user.username}: Recent login ({hours_since_login:.1f} hours ago)")
                return False
    
    return True


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page with IP-based rate limiting to prevent credential stuffing"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    from forms import LoginForm
    form = LoginForm()

    if form.validate_on_submit():
        from models import User
        from datetime import datetime
        from app import db
        
        # SECURITY: IP-based rate limiting to prevent credential stuffing attacks
        # This protects against attackers trying many usernames from the same IP
        is_allowed, wait_time = RateLimiter.check_rate_limit('login')
        if not is_allowed:
            log_security_event('login_rate_limited', {
                'ip': request.remote_addr,
                'username_attempted': form.username.data,
                'wait_time': wait_time
            })
            flash(f'Too many login attempts. Please wait {wait_time} seconds before trying again.', 'error')
            return render_template('auth/login.html', form=form)

        # Find user by username - note: usernames are unique within organizations
        user = User.query.filter_by(username=form.username.data).first()

        if user and form.password.data and user.check_password(form.password.data):
            # Check if account is locked
            if user.is_account_locked():
                flash('Account is temporarily locked due to multiple failed login attempts. Please try again later.', 'error')
                log_security_event('login_attempt_on_locked_account', {
                    'username': user.username,
                    'ip': request.remote_addr
                }, user_id=user.id, org_id=user.org_id or 0)
                return render_template('auth/login.html', form=form)

            # Check if user is active
            if not user.is_active_user:
                flash('Your account has been deactivated. Please contact your administrator.', 'error')
                return render_template('auth/login.html', form=form)

            # Check if login-time security questions are required
            security_check = _requires_login_security_questions(user)
            if security_check == 'force_setup':
                # Admin without security questions - DO NOT log them in, force setup first
                logger.info(f"Admin {user.username} attempting login without security questions, forcing setup")
                session['force_security_setup_user_id'] = user.id
                session['force_security_setup_next'] = request.args.get('next')
                return redirect(url_for('first_login.setup_security_questions'))
            elif security_check:
                # Store user ID in session for security question verification
                session['login_pending_user_id'] = user.id
                session['login_pending_next'] = request.args.get('next')
                session['login_pending_initiated_at'] = datetime.utcnow().isoformat()
                session['login_security_attempts'] = 0
                logger.info(f"Security question verification required for user: {user.username}")
                return redirect(url_for('auth.verify_login_security'))

            # Record successful login
            user.record_login_attempt(success=True)
            # SECURITY: Reset IP rate limiter on successful login
            RateLimiter.record_attempt('login', success=True)
            login_user(user)
            
            # Log the login event to audit log
            # Root admin events go to system org (0), never to tenant orgs
            from models import log_admin_event
            if user.is_root_admin:
                log_org_id = 0  # System org for root admin events
            else:
                log_org_id = user.org_id  # Org admins must have valid org_id
            
            log_admin_event(
                event_type='user_login',
                user_id=user.id,
                org_id=log_org_id,
                ip=request.remote_addr,
                data={
                    'username': user.username,
                    'role': user.role,
                    'description': f'Successful login: {user.username}'
                }
            )

            flash('Login successful!', 'success')

            # Redirect to next page or appropriate dashboard
            next_page = request.args.get('next')
            if next_page:
                parsed = urlparse(next_page)
                if not parsed.netloc and not parsed.scheme:
                    return redirect(next_page)
            
            # Redirect based on user role (default fallback)
            if user.is_root_admin_user():
                return redirect(url_for('root_admin.dashboard'))
            elif user.is_admin_user():
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            # SECURITY: Get client IP for all security tracking
            client_ip = request.remote_addr or 'unknown'
            
            # Record failed login attempt if user exists
            if user:
                user.record_login_attempt(success=False)
                db.session.commit()
                
                # SECURITY: Send lockout alert if account just got locked
                if user.is_account_locked() and user.failed_login_attempts == 5:
                    SecurityAlertService.send_account_lockout_alert(
                        user=user,
                        ip_address=client_ip,
                        failed_attempts=user.failed_login_attempts
                    )
                    logger.warning(f"Account lockout alert sent for user {user.username}")
            
            # SECURITY: Log failed login attempt for brute force tracking (even for nonexistent users)
            target_org_id = user.org_id if user else 0
            log_admin_event(
                event_type='login_failed',
                user_id=user.id if user else None,
                org_id=target_org_id,
                ip=client_ip,
                data={
                    'username': form.username.data,
                    'user_exists': user is not None
                }
            )
            
            # SECURITY: Check for brute force pattern from this IP (runs for ALL failed attempts)
            # This catches credential stuffing with random usernames
            SecurityAlertService.check_and_alert_brute_force(
                ip_address=client_ip,
                org_id=target_org_id
            )
            
            # SECURITY: Record failed attempt for IP-based rate limiting
            RateLimiter.record_attempt('login', success=False)
            flash('Invalid username or password.', 'error')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    from forms import RegisterForm
    form = RegisterForm()

    if form.validate_on_submit():
        from models import User
        from app import db

        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return render_template('auth/register.html', form=form)

        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('auth/register.html', form=form)

        # Create new user (requires org_id for regular users)
        # Note: Registration is for regular users within an organization
        # Root admins should be created through setup scripts
        from models import Organization

        # Get default organization or first available organization
        default_org = Organization.query.filter_by(name='Default Organization').first()
        if not default_org:
            default_org = Organization.query.first()

        if not default_org:
            flash('No organization available for registration. Please contact administrator.', 'error')
            return render_template('auth/register.html', form=form)

        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.role = 'nurse'  # Default role
        user.is_admin = False
        user.org_id = default_org.id
        user.set_password(form.password.data)

        try:
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')

    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/verify-login-security', methods=['GET', 'POST'])
def verify_login_security():
    """Verify security questions for admin users at login with rate limiting and lockout"""
    # Check if there's a pending login
    user_id = session.get('login_pending_user_id')
    if not user_id:
        flash('Invalid session. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    from models import User
    from app import db
    
    user = User.query.get(user_id)
    if not user:
        session.clear()
        flash('Invalid session. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check for session timeout (5 minutes for security verification)
    initiated_at = session.get('login_pending_initiated_at')
    if initiated_at:
        try:
            initiated_time = datetime.fromisoformat(initiated_at)
            if (datetime.utcnow() - initiated_time).total_seconds() > SECURITY_VERIFICATION_TIMEOUT_SECONDS:
                session.clear()
                flash('Security verification timed out. Please log in again.', 'error')
                log_security_event('security_verification_timeout', {
                    'username': user.username
                }, user_id=user.id, org_id=user.org_id or 0)
                return redirect(url_for('auth.login'))
        except ValueError:
            pass
    
    # Check rate limiting
    is_allowed, wait_time = RateLimiter.check_rate_limit('2fa_verification', user.username)
    if not is_allowed:
        session.clear()
        flash(f'Too many failed attempts. Please wait {wait_time // 60} minutes before trying again.', 'error')
        log_security_event('security_verification_rate_limited', {
            'username': user.username
        }, user_id=user.id, org_id=user.org_id or 0)
        return redirect(url_for('auth.login'))
    
    # Check attempt counter
    attempts = session.get('login_security_attempts', 0)
    if attempts >= SECURITY_QUESTION_MAX_ATTEMPTS:
        session.clear()
        user.record_login_attempt(success=False)  # Count as failed login
        db.session.commit()
        RateLimiter.record_attempt('2fa_verification', user.username, success=False)
        flash('Too many failed attempts. Please try again later.', 'error')
        log_security_event('security_verification_lockout', {
            'username': user.username,
            'attempts': attempts
        }, user_id=user.id, org_id=user.org_id or 0)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Get security answers from form
        answer_1 = request.form.get('answer_1', '').strip()
        answer_2 = request.form.get('answer_2', '').strip()
        
        # Both root admins and org admins must answer BOTH questions correctly
        answer_1_correct = user.check_security_answer_1(answer_1) if answer_1 else False
        answer_2_correct = user.check_security_answer_2(answer_2) if answer_2 else False
        
        # Both root admins and org admins must answer BOTH questions correctly
        if answer_1_correct and answer_2_correct:
            # Successful verification
            user.record_login_attempt(success=True)
            login_user(user)
            
            # Reset rate limiter on success
            RateLimiter.record_attempt('2fa_verification', user.username, success=True)
            
            # Log the login event to audit log
            # Root admin logs to org_id=0 (System Org), org admins log to their org_id
            from models import log_admin_event
            if user.is_root_admin:
                log_org_id = 0  # System org for root admin events
            else:
                log_org_id = user.org_id  # Org admins must have valid org_id
            
            log_admin_event(
                event_type='user_login',
                user_id=user.id,
                org_id=log_org_id,
                ip=request.remote_addr,
                data={
                    'username': user.username,
                    'role': user.role,
                    'security_verified': True,
                    'description': f'Successful login with security verification: {user.username}'
                }
            )
            
            # Clear session login state
            next_page = session.get('login_pending_next')
            session.pop('login_pending_user_id', None)
            session.pop('login_pending_next', None)
            session.pop('login_pending_initiated_at', None)
            session.pop('login_security_attempts', None)
            
            logger.info(f"{user.role} {user.username} verified security questions successfully")
            flash('Login successful!', 'success')
            
            # Redirect based on role
            if next_page:
                return redirect(next_page)
            elif user.is_root_admin:
                return redirect(url_for('root_admin.dashboard'))
            else:
                return redirect(url_for('admin.dashboard'))
        else:
            # Increment attempt counter
            session['login_security_attempts'] = attempts + 1
            remaining = SECURITY_QUESTION_MAX_ATTEMPTS - attempts - 1
            
            # Record failed attempt for rate limiting
            RateLimiter.record_attempt('2fa_verification', user.username, success=False)
            
            if remaining > 0:
                flash(f'Security answers are incorrect. {remaining} attempt(s) remaining.', 'error')
            else:
                flash('Security answers are incorrect. Maximum attempts reached.', 'error')
            
            logger.warning(f"Failed security verification for {user.role}: {user.username} (attempt {attempts + 1})")
            log_security_event('security_verification_failed', {
                'username': user.username,
                'attempt_number': attempts + 1
            }, user_id=user.id, org_id=user.org_id or 0)
            
            if remaining <= 0:
                session.clear()
                user.record_login_attempt(success=False)
                db.session.commit()
                return redirect(url_for('auth.login'))
    
    # Display security questions
    return render_template('auth/verify_login_security.html',
                         user=user,
                         question_1=user.security_question_1,
                         question_2=user.security_question_2,
                         is_root_admin=user.is_root_admin)


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    from forms import ChangePasswordForm
    from werkzeug.security import generate_password_hash

    form = ChangePasswordForm()

    if form.validate_on_submit():
        if form.current_password.data and check_password_hash(current_user.password_hash, form.current_password.data):
            # Update password
            if form.new_password.data:
                current_user.password_hash = generate_password_hash(form.new_password.data)

            from app import db
            db.session.commit()

            # Log password change
            # Root admin events go to system org (0), org admins log to their org
            if current_user.is_root_admin:
                log_org_id = 0  # System org for root admin events
            else:
                log_org_id = current_user.org_id  # Org admins must have valid org_id
            
            try:
                log_admin_event(
                    event_type='password_changed',
                    user_id=current_user.id,
                    org_id=log_org_id,
                    ip=request.remote_addr,
                    data={'username': current_user.username, 'user_agent': request.user_agent.string, 'description': f'Password changed for user {current_user.username}'}
                )
            except Exception as e:
                logger.error(f'Failed to log password change: {str(e)}')
                pass

            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Current password is incorrect.', 'error')

    return render_template('auth/change_password.html', form=form)

@auth_bp.route('/session-info')
@login_required
def session_info():
    """Display session information for debugging"""
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))

    session_data = {
        'user_id': current_user.id,
        'username': current_user.username,
        'is_admin': current_user.is_admin,
        'last_login': current_user.last_login,
        'session_keys': list(session.keys()),
        'request_info': {
            'remote_addr': request.remote_addr,
            'user_agent': request.user_agent.string,
            'endpoint': request.endpoint,
            'method': request.method
        }
    }

    return render_template('auth/session_info.html', session_data=session_data)

# Custom login manager functions
def init_login_manager(login_manager):
    """Initialize login manager with custom handlers"""

    @login_manager.unauthorized_handler
    def unauthorized():
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    @login_manager.needs_refresh_handler
    def refresh():
        flash('Please log in again to confirm your identity.', 'info')
        return redirect(url_for('auth.login'))

# Role-based access decorators
def admin_required(f):
    """Decorator to require admin access"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        if not current_user.is_admin:
            flash('Administrator access required.', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function

def user_required(f):
    """Decorator to require authenticated user"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)

    return decorated_function

def non_admin_required(f):
    """Decorator to prevent admin users from accessing regular user routes"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        if current_user.is_admin:
            flash('Admin users should use the admin dashboard.', 'info')
            return redirect(url_for('admin.dashboard'))

        return f(*args, **kwargs)

    return decorated_function

# Security utilities
def check_session_validity():
    """Check if current session is valid"""
    if not current_user.is_authenticated:
        return False

    # Add session timeout check here if needed
    # For now, rely on Flask-Login's built-in session management

    return True

def get_user_permissions(user):
    """Get user permissions based on role"""
    if not user or not user.is_authenticated:
        return []

    permissions = ['read_screenings', 'read_patients']

    if user.is_admin:
        permissions.extend([
            'admin_dashboard',
            'manage_users',
            'manage_settings',
            'view_logs',
            'manage_screening_types'
        ])

    return permissions

def has_permission(permission):
    """Check if current user has a specific permission"""
    if not current_user.is_authenticated:
        return False

    user_permissions = get_user_permissions(current_user)
    return permission in user_permissions

@auth_bp.route('/subscription-expired')
@login_required
def subscription_expired():
    """Trial expired page"""
    return render_template('subscription/trial_expired.html')

@auth_bp.route('/account-suspended')
@login_required
def account_suspended():
    """Account suspended page"""
    return render_template('subscription/account_suspended.html')

@auth_bp.route('/payment-required')
@login_required
def payment_required():
    """Payment required page"""
    return render_template('subscription/payment_required.html')