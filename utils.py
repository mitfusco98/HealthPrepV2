from functools import wraps
from flask import abort
from flask_login import current_user

def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def get_confidence_class(confidence):
    """Get CSS class based on OCR confidence score"""
    if confidence is None:
        return 'confidence-unknown'
    elif confidence >= 0.8:
        return 'confidence-high'
    elif confidence >= 0.6:
        return 'confidence-medium'
    else:
        return 'confidence-low'

def format_frequency(frequency_value, frequency_unit):
    """Format frequency for display"""
    if frequency_value == 1:
        return f"Every {frequency_unit[:-1]}"  # Remove 's' from unit
    else:
        return f"Every {frequency_value} {frequency_unit}"

def calculate_age(birth_date):
    """Calculate age from birth date"""
    from datetime import date
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
