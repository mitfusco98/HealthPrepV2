"""
First Login Routes for Password Change and Security Question Setup
Forces users with temporary passwords to set permanent credentials
"""
import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db
from forms.first_login_forms import FirstLoginPasswordForm, SecurityQuestionsForm

logger = logging.getLogger(__name__)

first_login_bp = Blueprint('first_login', __name__)


@first_login_bp.route('/first-login/password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Force password change for users with temporary passwords"""
    # Check if user needs to change password
    if not current_user.is_temp_password:
        return redirect(url_for('index'))
    
    form = FirstLoginPasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('first_login/change_password.html', form=form)
        
        # Ensure new password is different
        if form.current_password.data == form.new_password.data:
            flash('New password must be different from your temporary password.', 'error')
            return render_template('first_login/change_password.html', form=form)
        
        # Update password
        current_user.set_password(form.new_password.data)
        current_user.is_temp_password = False
        db.session.commit()
        
        logger.info(f"User {current_user.username} changed temporary password")
        
        flash('Password changed successfully!', 'success')
        
        # Only redirect to security questions if user is an admin
        if current_user.is_admin or current_user.is_root_admin:
            return redirect(url_for('first_login.setup_security_questions'))
        else:
            # Regular users go straight to dashboard
            return redirect(url_for('ui.dashboard'))
    
    return render_template('first_login/change_password.html', form=form)


@first_login_bp.route('/first-login/security-questions', methods=['GET', 'POST'])
def setup_security_questions():
    """Set up security questions for account recovery (admin users only)"""
    # Check if user is being forced to set up security questions (not logged in yet)
    force_setup_user_id = session.get('force_security_setup_user_id')
    
    if force_setup_user_id:
        # User trying to log in but doesn't have security questions set up
        from models import User
        user = User.query.get(force_setup_user_id)
        if not user:
            session.clear()
            flash('Invalid session. Please log in again.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check that user is admin (root or org)
        if not user.is_admin and not user.is_root_admin:
            session.clear()
            flash('Invalid session. Please log in again.', 'error')
            return redirect(url_for('auth.login'))
    elif current_user.is_authenticated:
        # User is already logged in - use current_user
        user = current_user
        
        # Non-admin users don't need security questions
        if not user.is_admin and not user.is_root_admin:
            return redirect(url_for('ui.dashboard'))
        
        # Check if user has already set up security questions
        if user.security_answer_1_hash and user.security_answer_2_hash:
            # Already set up, redirect to appropriate dashboard
            if user.is_root_admin:
                return redirect(url_for('root_admin.dashboard'))
            elif user.is_admin:
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('ui.dashboard'))
        
        # Check if user still has temp password (must change password first)
        if user.is_temp_password:
            return redirect(url_for('first_login.change_password'))
    else:
        # No valid session
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    form = SecurityQuestionsForm()
    
    if form.validate_on_submit():
        # Set security questions (hashed for security)
        answer1 = form.security_answer_1.data
        answer2 = form.security_answer_2.data
        
        if answer1 and answer2:
            # Store the hard-coded question text
            user.security_question_1 = "What year did you graduate high school?"
            user.security_question_2 = "What is your mother's maiden name?"
            
            # Store hashed answers
            user.security_answer_1_hash = generate_password_hash(
                answer1.strip().lower()
            )
            user.security_answer_2_hash = generate_password_hash(
                answer2.strip().lower()
            )
        db.session.commit()
        
        logger.info(f"Admin user {user.username} set up security questions")
        
        flash('Security questions set up successfully! Your account is now fully configured.', 'success')
        
        # If this was a forced setup during login, now log the user in
        if force_setup_user_id:
            user.record_login_attempt(success=True)
            login_user(user)
            
            # Log the login event
            from models import log_admin_event
            log_admin_event(
                event_type='user_login',
                user_id=user.id,
                org_id=(user.org_id or 1),
                ip=request.remote_addr,
                data={
                    'username': user.username,
                    'role': user.role,
                    'security_questions_setup': True,
                    'description': f'Successful login after security setup: {user.username}'
                }
            )
            
            # Clear session and redirect
            next_page = session.get('force_security_setup_next')
            session.pop('force_security_setup_user_id', None)
            session.pop('force_security_setup_next', None)
            
            if next_page:
                return redirect(next_page)
        
        # Redirect to appropriate dashboard
        if user.is_root_admin:
            return redirect(url_for('root_admin.dashboard'))
        elif user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('ui.dashboard'))
    
    return render_template('first_login/security_questions.html', form=form)
