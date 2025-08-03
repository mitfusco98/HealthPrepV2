"""
Global constants and settings for the application
Centralized configuration management
"""
import os
from datetime import timedelta

# Flask Configuration
SECRET_KEY = os.environ.get("SESSION_SECRET")
DATABASE_URL = os.environ.get("DATABASE_URL")

# FHIR Configuration
FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "https://fhir.epic.com/interconnect-fhir-oauth")
FHIR_CLIENT_ID = os.environ.get("FHIR_CLIENT_ID", "")
FHIR_CLIENT_SECRET = os.environ.get("FHIR_CLIENT_SECRET", "")

# OCR Configuration
TESSERACT_PATH = os.environ.get("TESSERACT_PATH", "/usr/bin/tesseract")
OCR_CONFIDENCE_THRESHOLD = float(os.environ.get("OCR_CONFIDENCE_THRESHOLD", "0.6"))
MAX_DOCUMENT_SIZE_MB = int(os.environ.get("MAX_DOCUMENT_SIZE_MB", "50"))

# File Upload Configuration
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'}
MAX_CONTENT_LENGTH = MAX_DOCUMENT_SIZE_MB * 1024 * 1024  # Convert to bytes

# Session Configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Logging Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("LOG_FILE", "healthprep.log")

# Screening Engine Configuration
DEFAULT_SCREENING_FREQUENCY_MONTHS = 12
SCREENING_DUE_SOON_DAYS = 30
MAX_DOCUMENTS_PER_SCREENING = 100

# PHI Filtering Configuration
PHI_FILTERING_ENABLED = os.environ.get("PHI_FILTERING_ENABLED", "true").lower() == "true"
PRESERVE_MEDICAL_TERMS = True

# Prep Sheet Configuration
DEFAULT_PREP_SHEET_CUTOFFS = {
    'labs': 12,      # months
    'imaging': 24,   # months
    'consults': 12,  # months
    'hospital': 12   # months
}

# Performance Configuration
BATCH_PROCESSING_SIZE = int(os.environ.get("BATCH_PROCESSING_SIZE", "50"))
OCR_PROCESSING_TIMEOUT = int(os.environ.get("OCR_PROCESSING_TIMEOUT", "300"))  # seconds
DATABASE_POOL_SIZE = int(os.environ.get("DATABASE_POOL_SIZE", "10"))

# HIPAA Compliance Settings
AUDIT_LOG_RETENTION_DAYS = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "2555"))  # 7 years
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "480"))  # 8 hours
PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "8"))

# Medical Terminology Settings
FUZZY_MATCH_THRESHOLD = float(os.environ.get("FUZZY_MATCH_THRESHOLD", "0.8"))
MEDICAL_ALIAS_EXPANSION = True

# Admin Dashboard Settings
DASHBOARD_REFRESH_INTERVAL = int(os.environ.get("DASHBOARD_REFRESH_INTERVAL", "300"))  # seconds
MAX_RECENT_LOGS = int(os.environ.get("MAX_RECENT_LOGS", "100"))

# Email Configuration (if needed for notifications)
MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

# API Rate Limiting
API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "100/hour")
FHIR_API_TIMEOUT = int(os.environ.get("FHIR_API_TIMEOUT", "30"))  # seconds

# Development/Production Settings
DEBUG = os.environ.get("FLASK_ENV") == "development"
TESTING = os.environ.get("TESTING", "false").lower() == "true"

# Feature Flags
ENABLE_FHIR_INTEGRATION = os.environ.get("ENABLE_FHIR_INTEGRATION", "true").lower() == "true"
ENABLE_OCR_PROCESSING = os.environ.get("ENABLE_OCR_PROCESSING", "true").lower() == "true"
ENABLE_PHI_FILTERING = PHI_FILTERING_ENABLED
ENABLE_ANALYTICS = os.environ.get("ENABLE_ANALYTICS", "true").lower() == "true"

# Security Headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; font-src 'self' cdnjs.cloudflare.com; img-src 'self' data:;"
}

# Cache Settings
CACHE_TYPE = os.environ.get("CACHE_TYPE", "simple")
CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))

# Backup and Recovery
AUTO_BACKUP_ENABLED = os.environ.get("AUTO_BACKUP_ENABLED", "false").lower() == "true"
BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))

def get_database_config():
    """Get database configuration based on environment"""
    return {
        'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': DATABASE_POOL_SIZE,
            'pool_recycle': 300,
            'pool_pre_ping': True,
            'pool_timeout': 20,
            'max_overflow': 20
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    }

def get_security_config():
    """Get security configuration"""
    return {
        'SECRET_KEY': SECRET_KEY,
        'SESSION_COOKIE_SECURE': SESSION_COOKIE_SECURE,
        'SESSION_COOKIE_HTTPONLY': SESSION_COOKIE_HTTPONLY,
        'SESSION_COOKIE_SAMESITE': SESSION_COOKIE_SAMESITE,
        'PERMANENT_SESSION_LIFETIME': PERMANENT_SESSION_LIFETIME,
        'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        'SESSION_TIMEOUT_MINUTES': SESSION_TIMEOUT_MINUTES
    }

def get_ocr_config():
    """Get OCR processing configuration"""
    return {
        'TESSERACT_PATH': TESSERACT_PATH,
        'CONFIDENCE_THRESHOLD': OCR_CONFIDENCE_THRESHOLD,
        'MAX_DOCUMENT_SIZE_MB': MAX_DOCUMENT_SIZE_MB,
        'PROCESSING_TIMEOUT': OCR_PROCESSING_TIMEOUT,
        'ALLOWED_EXTENSIONS': ALLOWED_EXTENSIONS
    }

def get_fhir_config():
    """Get FHIR integration configuration"""
    return {
        'BASE_URL': FHIR_BASE_URL,
        'CLIENT_ID': FHIR_CLIENT_ID,
        'CLIENT_SECRET': FHIR_CLIENT_SECRET,
        'API_TIMEOUT': FHIR_API_TIMEOUT,
        'ENABLED': ENABLE_FHIR_INTEGRATION
    }

def validate_required_settings():
    """Validate that all required settings are present"""
    required_settings = [
        ('SECRET_KEY', SECRET_KEY),
        ('DATABASE_URL', DATABASE_URL)
    ]
    
    missing_settings = []
    for setting_name, setting_value in required_settings:
        if not setting_value:
            missing_settings.append(setting_name)
    
    if missing_settings:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_settings)}")
    
    return True
