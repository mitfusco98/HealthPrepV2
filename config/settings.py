"""
Global application settings and constants.
Centralized configuration management for the HealthPrep system.
"""

import os
from datetime import timedelta

# Application Information
APP_NAME = "HealthPrep"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "HIPAA-compliant healthcare preparation system with FHIR integration"

# Environment Configuration
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
TESTING = os.getenv('TESTING', 'False').lower() == 'true'
SECRET_KEY = os.getenv('SESSION_SECRET')

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
DATABASE_ENGINE_OPTIONS = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20
}

# File Upload Configuration
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'}

# OCR Configuration
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
OCR_LANGUAGES = ['eng']  # English by default
OCR_CONFIG = r'--oem 3 --psm 6'
OCR_CONFIDENCE_THRESHOLD = 0.6

# FHIR Configuration
FHIR_BASE_URL = os.getenv('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
FHIR_CLIENT_ID = os.getenv('FHIR_CLIENT_ID', 'health-prep-client')
FHIR_CLIENT_SECRET = os.getenv('FHIR_CLIENT_SECRET')
FHIR_SCOPES = [
    'system/Patient.read',
    'system/Observation.read',
    'system/DiagnosticReport.read',
    'system/DocumentReference.read',
    'system/Condition.read',
    'system/Procedure.read'
]

# Security Configuration
CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8 hour sessions

# HIPAA Compliance Settings
PHI_RETENTION_DAYS = 2555  # 7 years as per HIPAA requirements
AUDIT_LOG_RETENTION_DAYS = 2555  # 7 years for audit logs
REQUIRE_MFA = os.getenv('REQUIRE_MFA', 'False').lower() == 'true'
SESSION_TIMEOUT_MINUTES = 30
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_SPECIAL_CHARS = True

# Screening Engine Configuration
DEFAULT_SCREENING_FREQUENCY_MONTHS = 12
MAX_SCREENING_AGE_YEARS = 120
MIN_SCREENING_AGE_YEARS = 0
FUZZY_MATCH_THRESHOLD = 0.8
KEYWORD_MATCH_CASE_SENSITIVE = False

# Performance Configuration
PAGINATION_PAGE_SIZE = 20
MAX_PAGINATION_PAGE_SIZE = 100
CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
SCREENING_REFRESH_BATCH_SIZE = 100

# Email Configuration (for notifications)
MAIL_SERVER = os.getenv('MAIL_SERVER')
MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@healthprep.com')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.getenv('LOG_FILE', 'healthprep.log')
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Admin Configuration
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@healthprep.com')
SYSTEM_MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'False').lower() == 'true'
BACKUP_RETENTION_DAYS = 30

# Integration Configuration
ENABLE_FHIR_INTEGRATION = os.getenv('ENABLE_FHIR_INTEGRATION', 'True').lower() == 'true'
ENABLE_OCR_PROCESSING = os.getenv('ENABLE_OCR_PROCESSING', 'True').lower() == 'true'
ENABLE_PHI_FILTERING = os.getenv('ENABLE_PHI_FILTERING', 'True').lower() == 'true'

# Monitoring and Analytics
ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'True').lower() == 'true'
ANALYTICS_RETENTION_DAYS = 365
PERFORMANCE_MONITORING = os.getenv('PERFORMANCE_MONITORING', 'True').lower() == 'true'

# Default System Values
DEFAULT_CUTOFF_SETTINGS = {
    'labs': 12,      # months
    'imaging': 24,   # months
    'consults': 12,  # months
    'hospital': 24   # months
}

DEFAULT_PHI_SETTINGS = {
    'phi_filtering_enabled': True,
    'filter_ssn': True,
    'filter_phone': True,
    'filter_mrn': True,
    'filter_insurance': True,
    'filter_addresses': True,
    'filter_names': True,
    'filter_dates': True
}

# Medical Terminology Configuration
MEDICAL_SPECIALTIES = [
    'Cardiology',
    'Endocrinology',
    'Gastroenterology',
    'Hematology/Oncology',
    'Nephrology',
    'Neurology',
    'Orthopedics',
    'Pulmonology',
    'Radiology',
    'Urology',
    'Gynecology',
    'Dermatology',
    'Ophthalmology',
    'Psychiatry',
    'General Surgery'
]

DOCUMENT_TYPES = [
    'lab',
    'imaging',
    'consult',
    'hospital',
    'procedure',
    'other'
]

SCREENING_STATUSES = [
    'Complete',
    'Due',
    'Due Soon'
]

# API Rate Limiting
API_RATE_LIMIT = os.getenv('API_RATE_LIMIT', '100/hour')
API_BURST_LIMIT = os.getenv('API_BURST_LIMIT', '10/minute')

# Feature Flags
FEATURES = {
    'advanced_analytics': os.getenv('FEATURE_ADVANCED_ANALYTICS', 'True').lower() == 'true',
    'bulk_import': os.getenv('FEATURE_BULK_IMPORT', 'True').lower() == 'true',
    'automated_scheduling': os.getenv('FEATURE_AUTOMATED_SCHEDULING', 'False').lower() == 'true',
    'patient_portal': os.getenv('FEATURE_PATIENT_PORTAL', 'False').lower() == 'true',
    'mobile_app': os.getenv('FEATURE_MOBILE_APP', 'False').lower() == 'true',
    'ai_recommendations': os.getenv('FEATURE_AI_RECOMMENDATIONS', 'False').lower() == 'true'
}

# Timezone Configuration
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', 'UTC')
DISPLAY_TIMEZONE = os.getenv('DISPLAY_TIMEZONE', 'America/New_York')

# Backup Configuration
BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'True').lower() == 'true'
BACKUP_SCHEDULE = os.getenv('BACKUP_SCHEDULE', 'daily')  # daily, weekly, monthly
BACKUP_LOCATION = os.getenv('BACKUP_LOCATION', 'backups/')

def get_config_summary():
    """Get a summary of current configuration for admin dashboard"""
    return {
        'app_info': {
            'name': APP_NAME,
            'version': APP_VERSION,
            'debug_mode': DEBUG,
            'testing_mode': TESTING
        },
        'integrations': {
            'fhir_enabled': ENABLE_FHIR_INTEGRATION,
            'ocr_enabled': ENABLE_OCR_PROCESSING,
            'phi_filtering_enabled': ENABLE_PHI_FILTERING
        },
        'security': {
            'session_timeout_minutes': SESSION_TIMEOUT_MINUTES,
            'password_min_length': PASSWORD_MIN_LENGTH,
            'mfa_required': REQUIRE_MFA
        },
        'features': FEATURES,
        'limits': {
            'max_file_size_mb': MAX_CONTENT_LENGTH // (1024 * 1024),
            'pagination_size': PAGINATION_PAGE_SIZE,
            'session_lifetime_hours': PERMANENT_SESSION_LIFETIME.total_seconds() // 3600
        }
    }

def validate_required_settings():
    """Validate that all required settings are present"""
    required_settings = [
        'SESSION_SECRET',
        'DATABASE_URL'
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not os.getenv(setting):
            missing_settings.append(setting)
    
    if missing_settings:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_settings)}")
    
    return True

# Validate settings on import
if not TESTING:
    validate_required_settings()
