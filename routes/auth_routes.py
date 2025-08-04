"""
Authentication routes for user login and session management
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

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
        user = User.query.filter_by(username=form.username.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)

            # Update last login
            from datetime import datetime
            user.last_login = datetime.utcnow()
            from app import db
            db.session.commit()

            flash('Login successful!', 'success')

            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            elif user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('auth/login.html', form=form)

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
        if check_password_hash(current_user.password_hash, form.current_password.data):
            # Update password
            current_user.password_hash = generate_password_hash(form.new_password.data)

            from app import db
            db.session.commit()

            # Log password change
            from admin.logs import AdminLogger
            admin_logger = AdminLogger()
            admin_logger.log_action(
                user_id=current_user.id,
                action='password_changed',
                resource_type='user',
                resource_id=current_user.id,
                details={'username': current_user.username},
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )

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