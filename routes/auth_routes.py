"""
Authentication routes for user login/logout
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import logging
from models import User
from admin.logs import admin_logger

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('screening.screening_list'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_template('auth/login.html')
        
        try:
            # Find user by username or email
            user = User.query.filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user and user.is_active and check_password_hash(user.password_hash, password):
                # Update last login
                from datetime import datetime
                user.last_login = datetime.utcnow()
                
                # Log the login
                admin_logger.log_action(
                    user_id=user.id,
                    action='user_login',
                    details=f'User {username} logged in',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')
                )
                
                login_user(user, remember=remember)
                
                # Redirect based on user role
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                elif user.is_admin:
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('screening.screening_list'))
            else:
                # Log failed login attempt
                admin_logger.log_action(
                    action='login_failed',
                    details=f'Failed login attempt for username: {username}',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')
                )
                
                flash('Invalid username or password.', 'error')
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    try:
        # Log the logout
        admin_logger.log_action(
            user_id=current_user.id,
            action='user_logout',
            details=f'User {current_user.username} logged out',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        
        logout_user()
        flash('You have been logged out successfully.', 'info')
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        flash('An error occurred during logout.', 'error')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    try:
        return render_template('auth/profile.html', user=current_user)
    except Exception as e:
        logger.error(f"Profile page error: {str(e)}")
        flash('Error loading profile page.', 'error')
        return redirect(url_for('index'))
