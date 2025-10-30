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
        return redirect(url_for('first_login.setup_security_questions'))
    
    return render_template('first_login/change_password.html', form=form)


@first_login_bp.route('/first-login/security-questions', methods=['GET', 'POST'])
@login_required
def setup_security_questions():
    """Set up security questions for account recovery"""
    # Check if user has already set up security questions
    if current_user.security_question_1_answer and current_user.security_question_2_answer:
        return redirect(url_for('index'))
    
    # Check if user still has temp password (must change password first)
    if current_user.is_temp_password:
        return redirect(url_for('first_login.change_password'))
    
    form = SecurityQuestionsForm()
    
    if form.validate_on_submit():
        # Set security questions (hashed for security)
        answer1 = form.security_answer_1.data
        answer2 = form.security_answer_2.data
        
        if answer1 and answer2:
            current_user.security_question_1_answer = generate_password_hash(
                answer1.strip().lower()
            )
            current_user.security_question_2_answer = generate_password_hash(
                answer2.strip().lower()
            )
        db.session.commit()
        
        logger.info(f"User {current_user.username} set up security questions")
        
        flash('Security questions set up successfully! Your account is now fully configured.', 'success')
        return redirect(url_for('index'))
    
    return render_template('first_login/security_questions.html', form=form)
