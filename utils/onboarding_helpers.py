"""
Shared onboarding utilities for both self-service signup and manual organization creation
"""
import secrets
import string
from datetime import datetime, timedelta


def generate_temp_password(length=12):
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_username_from_email(email):
    """Generate username from email address"""
    username = email.split('@')[0]
    username = ''.join(c if c.isalnum() or c == '_' else '_' for c in username)
    return username[:50]


def create_password_reset_token():
    """Generate a secure password reset token"""
    return secrets.token_urlsafe(32)


def get_password_reset_expiry(hours=48):
    """Get password reset token expiry datetime"""
    return datetime.utcnow() + timedelta(hours=hours)
