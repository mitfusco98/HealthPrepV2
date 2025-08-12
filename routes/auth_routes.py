"""
Authentication routes for user login and session management
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import log_admin_event

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    from forms import LoginForm
    form = LoginForm()

    if form.validate_on_submit():
        from models import User
        from datetime import datetime
        from app import db

        # Find user by username - note: usernames are unique within organizations
        user = User.query.filter_by(username=form.username.data).first()

        if user and form.password.data and user.check_password(form.password.data):
            # Check if account is locked
            if user.is_account_locked():
                flash('Account is temporarily locked due to multiple failed login attempts. Please try again later.', 'error')
                return render_template('auth/login.html', form=form)

            # Check if user is active
            if not user.is_active_user:
                flash('Your account has been deactivated. Please contact your administrator.', 'error')
                return render_template('auth/login.html', form=form)

            # Record successful login
            user.record_login_attempt(success=True)
            login_user(user)

            flash('Login successful!', 'success')

            # Redirect to next page or appropriate dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                # Redirect based on user role
                if user.is_root_admin_user():
                    return redirect(url_for('root_admin.dashboard'))
                elif user.is_admin_user():
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('main.index'))
        else:
            # Record failed login attempt if user exists
            if user:
                user.record_login_attempt(success=False)
                db.session.commit()
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
            try:
                log_admin_event(
                    event_type='password_changed',
                    user_id=current_user.id,
                    org_id=getattr(current_user, 'org_id', 1),
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