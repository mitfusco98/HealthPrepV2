from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import db, login_manager
from models import User, AdminLog
from forms import LoginForm
import logging

auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            
            # Log successful login
            log_entry = AdminLog(
                user_id=user.id,
                action='user_login',
                details=f'User {user.username} logged in successfully',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(log_entry)
            db.session.commit()
            
            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
            
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page)
        else:
            # Log failed login attempt
            log_entry = AdminLog(
                action='failed_login',
                details=f'Failed login attempt for username: {form.username.data}',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    # Log logout
    log_entry = AdminLog(
        user_id=current_user.id,
        action='user_logout',
        details=f'User {current_user.username} logged out',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(log_entry)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out successfully.', 'info')
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
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'error')
        elif len(new_password) < 8:
            flash('New password must be at least 8 characters long', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            
            # Log password change
            log_entry = AdminLog(
                user_id=current_user.id,
                action='password_change',
                details=f'User {current_user.username} changed their password',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('Password changed successfully', 'success')
            return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')
