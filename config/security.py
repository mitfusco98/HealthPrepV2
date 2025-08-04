"""
Security and HIPAA compliance configuration
"""
import re
from datetime import datetime, timedelta

class SecurityConfig:
    """Security settings for HIPAA compliance"""
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_NUMBERS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # Session security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Audit requirements
    AUDIT_ALL_ACCESS = True
    AUDIT_PHI_ACCESS = True
    LOG_RETENTION_YEARS = 7

class PHIPatterns:
    """Regex patterns for PHI detection and filtering"""
    
    # Social Security Numbers
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b')
    
    # Phone Numbers
    PHONE_PATTERN = re.compile(r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
    
    # Medical Record Numbers (common patterns)
    MRN_PATTERN = re.compile(r'\b(?:MRN|mrn|medical record|patient id)[:\s]+[A-Z0-9]{5,15}\b', re.IGNORECASE)
    
    # Insurance Member IDs
    INSURANCE_PATTERN = re.compile(r'\b(?:member id|policy|insurance)[:\s]+[A-Z0-9]{8,20}\b', re.IGNORECASE)
    
    # Addresses (basic pattern)
    ADDRESS_PATTERN = re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\b', re.IGNORECASE)
    
    # Dates (but preserve medical values)
    DATE_PATTERN = re.compile(r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b')
    
    # Email addresses
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

class MedicalTermsProtection:
    """Medical terms to preserve during PHI filtering"""
    
    PRESERVE_PATTERNS = [
        # Lab values
        r'\b\d+\.?\d*\s*mg/dL\b',
        r'\b\d+\.?\d*\s*mmol/L\b',
        r'\b\d+\.?\d*\s*%\b',
        r'\b\d+/\d+\s*mmHg\b',
        
        # Medical procedures
        r'\bmammogram\b',
        r'\bcolonoscopy\b',
        r'\bdexa\b',
        r'\ba1c\b',
        r'\bhba1c\b',
        
        # Medical conditions
        r'\bdiabetes\b',
        r'\bhypertension\b',
        r'\bosteoporosis\b',
        
        # Medical measurements
        r'\b\d+\.?\d*\s*cm\b',
        r'\b\d+\.?\d*\s*mm\b',
        r'\b\d+\.?\d*\s*kg\b',
        r'\b\d+\.?\d*\s*lbs?\b'
    ]

def validate_password(password):
    """Validate password against HIPAA security requirements"""
    errors = []
    
    if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters long")
    
    if SecurityConfig.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if SecurityConfig.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if SecurityConfig.REQUIRE_NUMBERS and not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    if SecurityConfig.REQUIRE_SPECIAL_CHARS and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    return errors

def log_phi_access(user_id, resource_type, resource_id, action, ip_address=None):
    """Log PHI access for audit trail"""
    from models import AdminLog
    from app import db
    
    log_entry = AdminLog(
        user_id=user_id,
        action=f"PHI_ACCESS_{action}",
        resource_type=resource_type,
        resource_id=resource_id,
        details=f"PHI access logged for compliance",
        ip_address=ip_address,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(log_entry)
    db.session.commit()
