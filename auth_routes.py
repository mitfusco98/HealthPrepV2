"""
Authentication routes for user login/logout
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import logging

from app import db
from models import User, AdminLog
from forms import LoginForm
from config.security import log_phi_access

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
            
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # Log successful login
                log_entry = AdminLog(
                    user_id=user.id,
                    action='LOGIN_SUCCESS',
                    resource_type='user',
                    resource_id=user.id,
                    details='User logged in successfully',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.session.add(log_entry)
                db.session.commit()
                
                # Redirect to next page or dashboard
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                
                if user.is_admin():
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('main.dashboard'))
            
            else:
                flash('Invalid username or password', 'error')
                
                # Log failed login attempt
                log_entry = AdminLog(
                    action='LOGIN_FAILED',
                    resource_type='user',
                    details=f'Failed login attempt for username: {form.username.data}',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.session.add(log_entry)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login', 'error')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    try:
        # Log logout
        log_entry = AdminLog(
            user_id=current_user.id,
            action='LOGOUT',
            resource_type='user',
            resource_id=current_user.id,
            details='User logged out',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(log_entry)
        db.session.commit()
        
        logout_user()
        flash('You have been logged out successfully', 'info')
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        flash('An error occurred during logout', 'error')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/check-session')
@login_required
def check_session():
    """Check if user session is still valid (for AJAX calls)"""
    return {
        'authenticated': True,
        'user_id': current_user.id,
        'username': current_user.username,
        'is_admin': current_user.is_admin()
    }

