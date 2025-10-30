"""
Password Reset Routes with Security Questions
Allows users to reset passwords using email + security questions
"""
import logging
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, db
from forms.password_reset_forms import ForgotPasswordForm, SecurityAnswerForm, ResetPasswordForm
from services.email_service import EmailService

logger = logging.getLogger(__name__)

password_reset_bp = Blueprint('password_reset', __name__)


def generate_reset_token():
    """Generate a secure password reset token"""
    return secrets.token_urlsafe(32)


@password_reset_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Step 1: Enter email to initiate password reset"""
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email_data = form.email.data
        email = email_data.strip().lower() if email_data else ''
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check if user has security questions set up
            if not user.security_question_1_answer or not user.security_question_2_answer:
                flash('Security questions not set up for this account. Please contact support.', 'error')
                return redirect(url_for('password_reset.forgot_password'))
            
            # Store email in session for next step
            session['reset_email'] = email
            session['reset_step'] = 'security_questions'
            
            logger.info(f"Password reset initiated for user: {email}")
            return redirect(url_for('password_reset.verify_security_questions'))
        else:
            # Don't reveal if email exists or not (security best practice)
            flash('If an account exists with this email, you will receive password reset instructions.', 'info')
    
    return render_template('password_reset/forgot_password.html', form=form)


@password_reset_bp.route('/verify-security-questions', methods=['GET', 'POST'])
def verify_security_questions():
    """Step 2: Answer security questions"""
    # Check if user has initiated reset
    if 'reset_email' not in session or session.get('reset_step') != 'security_questions':
        flash('Please start the password reset process from the beginning.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    email = session.get('reset_email')
    user = User.query.filter_by(email=email).first()
    
    if not user:
        session.clear()
        flash('Invalid session. Please try again.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    form = SecurityAnswerForm()
    
    if form.validate_on_submit():
        answer1_data = form.answer_1.data
        answer2_data = form.answer_2.data
        
        answer1 = answer1_data.strip().lower() if answer1_data else ''
        answer2 = answer2_data.strip().lower() if answer2_data else ''
        
        # Verify security answers
        answer1_correct = check_password_hash(user.security_question_1_answer, answer1)
        answer2_correct = check_password_hash(user.security_question_2_answer, answer2)
        
        if answer1_correct and answer2_correct:
            # Generate reset token (plaintext for URL, hashed for storage)
            reset_token = generate_reset_token()
            user.reset_token = generate_password_hash(reset_token)  # Store hashed token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Send reset email with plaintext token
            from flask import url_for
            reset_url = url_for('password_reset.reset_password', token=reset_token, _external=True)
            EmailService.send_password_reset_email(
                email=user.email,
                username=user.username,
                reset_token=reset_token,
                reset_url=reset_url
            )
            
            # Update session
            session['reset_step'] = 'email_sent'
            
            logger.info(f"Security questions verified for user: {email}")
            flash('Password reset link sent to your email!', 'success')
            return redirect(url_for('password_reset.reset_email_sent'))
        else:
            flash('Security answers are incorrect. Please try again.', 'error')
            logger.warning(f"Failed security question verification for user: {email}")
    
    return render_template('password_reset/verify_security.html', form=form)


@password_reset_bp.route('/reset-email-sent')
def reset_email_sent():
    """Confirmation page after reset email sent"""
    if session.get('reset_step') != 'email_sent':
        return redirect(url_for('password_reset.forgot_password'))
    
    email = session.get('reset_email')
    session.clear()
    
    return render_template('password_reset/reset_email_sent.html', email=email)


@password_reset_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Step 3: Reset password with valid token"""
    # Find user with matching hashed token
    # We need to check all users with unexpired tokens (inefficient but necessary for hashed tokens)
    users_with_tokens = User.query.filter(
        User.reset_token.isnot(None),
        User.reset_token_expires > datetime.utcnow()
    ).all()
    
    user = None
    for u in users_with_tokens:
        if check_password_hash(u.reset_token, token):
            user = u
            break
    
    if not user:
        flash('Invalid or expired password reset link. Please request a new one.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        # Set new password
        user.set_password(form.new_password.data)
        user.reset_token = None
        user.reset_token_expires = None
        user.is_temp_password = False  # Mark as permanent password
        db.session.commit()
        
        logger.info(f"Password successfully reset for user: {user.username}")
        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('password_reset/reset_password.html', form=form, token=token)
