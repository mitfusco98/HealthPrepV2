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


@password_reset_bp.route('/retrieve-username', methods=['GET', 'POST'])
def retrieve_username():
    """Allow users to retrieve their username by email"""
    from forms.password_reset_forms import ForgotPasswordForm
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email_data = form.email.data
        email = email_data.strip().lower() if email_data else ''
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Send email with username
            from services.email_service import EmailService
            subject = "HealthPrep - Username Retrieval"
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2>Username Retrieval</h2>
                <p>Hello,</p>
                
                <p>You requested your username for HealthPrep.</p>
                
                <h3>Your Account Details:</h3>
                <ul>
                    <li><strong>Username:</strong> {user.username}</li>
                    <li><strong>Email:</strong> {user.email}</li>
                    <li><strong>Organization:</strong> {user.organization.name if user.organization else 'N/A'}</li>
                </ul>
                
                <p>You can use this username to log in at the HealthPrep login page.</p>
                
                <p>If you didn't request this information, please contact support immediately.</p>
                
                <p>Best regards,<br>The HealthPrep Team</p>
            </body>
            </html>
            """
            
            EmailService._send_email(user.email, subject, html_body)
            logger.info(f"Username retrieval requested for: {email}")
        
        # Always show success message (don't reveal if email exists)
        flash('If an account exists with this email, your username has been sent.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('password_reset/retrieve_username.html', form=form)


@password_reset_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Step 1: Enter email to initiate password reset"""
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email_data = form.email.data
        email = email_data.strip().lower() if email_data else ''
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check if user is admin with security questions or regular user (no security questions needed)
            if (user.is_admin or user.is_root_admin):
                # Admin users need security questions for password reset
                if not user.security_answer_1_hash or not user.security_answer_2_hash:
                    flash('Security questions not set up for this account. Please contact support.', 'error')
                    return redirect(url_for('password_reset.forgot_password'))
                
                # Store email in session for security questions verification
                session['reset_email'] = email
                session['reset_step'] = 'security_questions'
                
                logger.info(f"Password reset initiated for admin user: {email}")
                return redirect(url_for('password_reset.verify_security_questions'))
            else:
                # Regular users get direct email reset link (no security questions)
                reset_token = generate_reset_token()
                user.password_reset_token = reset_token
                user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
                db.session.commit()
                
                # Send reset email
                from flask import url_for as flask_url_for
                reset_url = flask_url_for('password_reset.reset_password', token=reset_token, _external=True)
                EmailService.send_password_reset_email(
                    email=user.email,
                    username=user.username,
                    reset_token=reset_token,
                    reset_url=reset_url
                )
                
                logger.info(f"Password reset email sent to regular user: {email}")
                flash('If an account exists with this email, you will receive password reset instructions.', 'info')
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
        answer1_correct = check_password_hash(user.security_answer_1_hash, answer1)
        answer2_correct = check_password_hash(user.security_answer_2_hash, answer2)
        
        if answer1_correct and answer2_correct:
            # Generate reset token
            reset_token = generate_reset_token()
            user.password_reset_token = reset_token
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Send reset email
            from flask import url_for as flask_url_for
            reset_url = flask_url_for('password_reset.reset_password', token=reset_token, _external=True)
            EmailService.send_password_reset_email(
                email=user.email,
                username=user.username,
                reset_token=reset_token,
                reset_url=reset_url
            )
            
            # Update session
            session['reset_step'] = 'email_sent'
            
            logger.info(f"Security questions verified for admin user: {email}")
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
    # Find user with matching reset token
    user = User.query.filter(
        User.password_reset_token == token,
        User.password_reset_expires > datetime.utcnow()
    ).first()
    
    if not user:
        flash('Invalid or expired password reset link. Please request a new one.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        # Set new password
        user.set_password(form.new_password.data)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.is_temp_password = False  # Mark as permanent password
        db.session.commit()
        
        logger.info(f"Password successfully reset for user: {user.username}")
        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('password_reset/reset_password.html', form=form, token=token)
