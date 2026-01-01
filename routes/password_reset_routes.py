"""
Password Reset Routes with Security Questions
Allows users to reset passwords using email + security questions
Enhanced with rate limiting and security hardening
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.security import check_password_hash

from models import User, db, log_admin_event
from forms.password_reset_forms import ForgotPasswordForm, SecurityAnswerForm, ResetPasswordForm
from services.email_service import EmailService
from utils.security import (
    RateLimiter, 
    generate_secure_token, 
    get_password_reset_expiry,
    log_security_event,
    invalidate_all_user_tokens
)

logger = logging.getLogger(__name__)

password_reset_bp = Blueprint('password_reset', __name__)

# Track failed security question attempts per session
SECURITY_QUESTION_MAX_ATTEMPTS = 3


def _check_rate_limit_or_redirect(endpoint_type: str, identifier: str = ''):
    """Check rate limit and return redirect if exceeded"""
    is_allowed, wait_time = RateLimiter.check_rate_limit(endpoint_type, identifier or None)
    if not is_allowed:
        wait_minutes = (wait_time // 60) if wait_time else 5
        flash(f'Too many attempts. Please wait {wait_minutes} minutes before trying again.', 'error')
        log_security_event('rate_limit_exceeded', {
            'endpoint': endpoint_type,
            'identifier_hash': hash(identifier) if identifier else None
        })
        return redirect(url_for('auth.login'))
    return None


@password_reset_bp.route('/retrieve-username', methods=['GET', 'POST'])
def retrieve_username():
    """Allow users to retrieve their username by email"""
    from forms.password_reset_forms import ForgotPasswordForm
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email_data = form.email.data
        email = email_data.strip().lower() if email_data else ''
        
        # Rate limiting - check before any database operations
        rate_check = _check_rate_limit_or_redirect('username_retrieval', email)
        if rate_check:
            return rate_check
        
        # Record the attempt (before database lookup to prevent timing attacks)
        RateLimiter.record_attempt('username_retrieval', email, success=False)
        
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
            
            # Log security event
            log_security_event('username_retrieval', {
                'success': True
            }, user_id=user.id, org_id=user.org_id)
        
        # Always show success message (don't reveal if email exists)
        # Opaque response prevents user enumeration
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
        
        # Rate limiting - check before any database operations
        rate_check = _check_rate_limit_or_redirect('password_reset', email)
        if rate_check:
            return rate_check
        
        # Record the attempt
        RateLimiter.record_attempt('password_reset', email, success=False)
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check if user is admin with security questions or regular user (no security questions needed)
            if (user.is_admin or user.is_root_admin):
                # Admin users need security questions for password reset
                if not user.security_answer_1_hash or not user.security_answer_2_hash:
                    # Opaque error - don't reveal admin status
                    flash('If an account exists with this email, you will receive password reset instructions.', 'info')
                    log_security_event('password_reset_no_security_questions', {
                        'email_provided': True
                    }, user_id=user.id, org_id=user.org_id)
                    return redirect(url_for('auth.login'))
                
                # Store email in session for security questions verification
                session['reset_email'] = email
                session['reset_step'] = 'security_questions'
                session['reset_initiated_at'] = datetime.utcnow().isoformat()
                session['security_question_attempts'] = 0
                
                logger.info(f"Password reset initiated for admin user: {email}")
                log_security_event('password_reset_initiated', {
                    'requires_security_questions': True
                }, user_id=user.id, org_id=user.org_id)
                return redirect(url_for('password_reset.verify_security_questions'))
            else:
                # Regular users get direct email reset link (no security questions)
                # Use shorter expiry (30 minutes) for security
                reset_token = generate_secure_token()
                user.password_reset_token = reset_token
                user.password_reset_expires = get_password_reset_expiry(minutes=30)
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
                log_security_event('password_reset_email_sent', {
                    'user_type': 'regular'
                }, user_id=user.id, org_id=user.org_id)
        
        # Always show same message (opaque response - prevents user enumeration)
        flash('If an account exists with this email, you will receive password reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('password_reset/forgot_password.html', form=form)


@password_reset_bp.route('/verify-security-questions', methods=['GET', 'POST'])
def verify_security_questions():
    """Step 2: Answer security questions with rate limiting and lockout"""
    # Check if user has initiated reset
    if 'reset_email' not in session or session.get('reset_step') != 'security_questions':
        flash('Please start the password reset process from the beginning.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    # Check for session timeout (10 minutes)
    reset_initiated = session.get('reset_initiated_at')
    if reset_initiated:
        try:
            initiated_time = datetime.fromisoformat(reset_initiated)
            if (datetime.utcnow() - initiated_time).total_seconds() > 600:  # 10 minutes
                session.clear()
                flash('Session expired. Please start the password reset process again.', 'error')
                log_security_event('security_question_session_expired', {})
                return redirect(url_for('password_reset.forgot_password'))
        except ValueError:
            pass
    
    email = session.get('reset_email', '')
    
    # Rate limiting for security questions
    rate_check = _check_rate_limit_or_redirect('security_question', email or '')
    if rate_check:
        session.clear()
        return rate_check
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        session.clear()
        flash('Invalid session. Please try again.', 'error')
        return redirect(url_for('password_reset.forgot_password'))
    
    # Check attempt counter
    attempts = session.get('security_question_attempts', 0)
    if attempts >= SECURITY_QUESTION_MAX_ATTEMPTS:
        session.clear()
        RateLimiter.record_attempt('security_question', email, success=False)
        flash('Too many failed attempts. Please try again later.', 'error')
        log_security_event('security_question_lockout', {
            'attempts': attempts
        }, user_id=user.id, org_id=user.org_id)
        return redirect(url_for('auth.login'))
    
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
            # Generate reset token with shorter expiry
            reset_token = generate_secure_token()
            user.password_reset_token = reset_token
            user.password_reset_expires = get_password_reset_expiry(minutes=30)
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
            
            # Update session and reset rate limiter
            session['reset_step'] = 'email_sent'
            RateLimiter.record_attempt('security_question', email, success=True)
            
            logger.info(f"Security questions verified for admin user: {email}")
            log_security_event('security_questions_verified', {
                'success': True
            }, user_id=user.id, org_id=user.org_id)
            flash('Password reset link sent to your email!', 'success')
            return redirect(url_for('password_reset.reset_email_sent'))
        else:
            # Increment attempt counter
            session['security_question_attempts'] = attempts + 1
            remaining = SECURITY_QUESTION_MAX_ATTEMPTS - attempts - 1
            
            if remaining > 0:
                flash(f'Security answers are incorrect. {remaining} attempt(s) remaining.', 'error')
            else:
                flash('Security answers are incorrect. Maximum attempts reached.', 'error')
            
            logger.warning(f"Failed security question verification for user: {email} (attempt {attempts + 1})")
            log_security_event('security_question_failed', {
                'attempt_number': attempts + 1
            }, user_id=user.id, org_id=user.org_id)
            
            # Record failed attempt for rate limiting
            RateLimiter.record_attempt('security_question', email, success=False)
            
            if remaining <= 0:
                session.clear()
                return redirect(url_for('auth.login'))
    
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
    # Rate limiting for token validation
    rate_check = _check_rate_limit_or_redirect('password_reset', token[:8])
    if rate_check:
        return rate_check
    
    # Find user with matching reset token and valid expiry
    user = User.query.filter(
        User.password_reset_token == token
    ).first()
    
    # Check if token exists and is not expired
    if user and user.password_reset_expires and user.password_reset_expires <= datetime.utcnow():
        user = None  # Token expired
    
    if not user:
        RateLimiter.record_attempt('password_reset', token[:8], success=False)
        flash('Invalid or expired password reset link. Please request a new one.', 'error')
        log_security_event('invalid_reset_token', {
            'token_prefix': token[:8] if token else 'none'
        })
        return redirect(url_for('password_reset.forgot_password'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        # Set new password
        user.set_password(form.new_password.data)
        
        # Invalidate all tokens
        user.password_reset_token = None
        user.password_reset_expires = None
        user.is_temp_password = False  # Mark as permanent password
        
        # Reset any account locks on successful password change
        user.failed_login_attempts = 0
        user.locked_until = None
        
        db.session.commit()
        
        # Reset rate limiter
        RateLimiter.record_attempt('password_reset', token[:8], success=True)
        
        logger.info(f"Password successfully reset for user: {user.username}")
        log_security_event('password_reset_completed', {
            'success': True
        }, user_id=user.id, org_id=user.org_id)
        
        # Log to admin audit trail
        try:
            log_admin_event(
                event_type='password_reset_completed',
                user_id=user.id,
                org_id=user.org_id or 0,
                ip=request.remote_addr,
                data={
                    'username': user.username,
                    'method': 'email_token',
                    'description': f'Password reset completed for {user.username}'
                }
            )
        except Exception as e:
            logger.error(f"Failed to log password reset: {e}")
        
        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('password_reset/reset_password.html', form=form, token=token)
