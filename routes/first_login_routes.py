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
@login_required
def setup_security_questions():
    """Set up security questions for account recovery (admin users only)"""
    # Non-admin users don't need security questions
    if not current_user.is_admin and not current_user.is_root_admin:
        return redirect(url_for('ui.dashboard'))
    
    # Check if user has already set up security questions
    if current_user.security_answer_1_hash and current_user.security_answer_2_hash:
        # Already set up, redirect to appropriate dashboard
        if current_user.is_root_admin:
            return redirect(url_for('root_admin.dashboard'))
        elif current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('ui.dashboard'))
    
    # Check if user still has temp password (must change password first)
    if current_user.is_temp_password:
        return redirect(url_for('first_login.change_password'))
    
    form = SecurityQuestionsForm()
    
    if form.validate_on_submit():
        # Set security questions (hashed for security)
        answer1 = form.security_answer_1.data
        answer2 = form.security_answer_2.data
        
        if answer1 and answer2:
            # Store the hard-coded question text
            current_user.security_question_1 = "What year did you graduate high school?"
            current_user.security_question_2 = "What is your mother's maiden name?"
            
            # Store hashed answers
            current_user.security_answer_1_hash = generate_password_hash(
                answer1.strip().lower()
            )
            current_user.security_answer_2_hash = generate_password_hash(
                answer2.strip().lower()
            )
        db.session.commit()
        
        logger.info(f"Admin user {current_user.username} set up security questions")
        
        flash('Security questions set up successfully! Your account is now fully configured.', 'success')
        
        # Redirect to appropriate dashboard
        if current_user.is_root_admin:
            return redirect(url_for('root_admin.dashboard'))
        elif current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('ui.dashboard'))
    
    return render_template('first_login/security_questions.html', form=form)
