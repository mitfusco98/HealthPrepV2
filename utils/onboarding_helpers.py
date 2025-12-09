"""
Shared onboarding utilities for both self-service signup and manual organization creation
"""
import secrets
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash


def generate_temp_password(length=12):
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_username_from_email(email, check_existing=True):
    """
    Generate username from email address with incremental numbering for duplicates.
    
    When same email registers multiple times (for multi-provider setup),
    generates: mitchfusillo, mitchfusillo2, mitchfusillo3, etc.
    
    Args:
        email: Email address to generate username from
        check_existing: If True, checks database for existing usernames and increments
    
    Returns:
        Unique username string
    """
    base_username = email.split('@')[0]
    base_username = ''.join(c if c.isalnum() or c == '_' else '_' for c in base_username)
    base_username = base_username[:45]  # Leave room for numeric suffix
    
    if not check_existing:
        return base_username[:50]
    
    # Check for existing usernames with this base
    from models import User
    
    # Try base username first
    existing = User.query.filter_by(username=base_username).first()
    if not existing:
        return base_username
    
    # Find next available number
    counter = 2
    while True:
        candidate = f"{base_username}{counter}"
        existing = User.query.filter_by(username=candidate).first()
        if not existing:
            return candidate[:50]
        counter += 1
        if counter > 999:  # Safety limit
            import secrets
            return f"{base_username[:40]}_{secrets.token_hex(4)}"


def create_password_reset_token():
    """Generate a secure password reset token"""
    return secrets.token_urlsafe(32)


def get_password_reset_expiry(hours=48):
    """Get password reset token expiry datetime"""
    return datetime.utcnow() + timedelta(hours=hours)


def generate_dummy_password_hash():
    """
    Generate a dummy/unusable password hash for users awaiting password setup.
    This satisfies the database NOT NULL constraint while preventing login attempts.
    The hash is replaced when the user sets their real password via the reset link.
    """
    # Generate a random string that will never match any user input
    dummy_password = f"__UNUSABLE__{secrets.token_urlsafe(32)}__TEMP__"
    return generate_password_hash(dummy_password)
