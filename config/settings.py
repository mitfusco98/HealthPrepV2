"""
Global constants and settings for Health-Prep application
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SESSION_SECRET')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

# Application constants
APP_NAME = "HealthPrep"
APP_VERSION = "2.0.0"

# Medical screening constants
SCREENING_STATUSES = ['Due', 'Due Soon', 'Complete']
DOCUMENT_TYPES = ['lab', 'imaging', 'consult', 'hospital', 'general']
GENDER_OPTIONS = ['M', 'F', 'Other']

# OCR processing constants
OCR_CONFIDENCE_THRESHOLDS = {
    'high': 0.8,
    'medium': 0.5,
    'low': 0.0
}

# FHIR integration settings
FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'http://hapi.fhir.org/baseR4')
FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'health-prep-client')
FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'default_secret')

# Performance goals
PREP_SHEET_GENERATION_TARGET = 10  # seconds
DOCUMENT_CLASSIFICATION_ACCURACY_TARGET = 0.95
SYSTEM_UPTIME_TARGET = 0.999

# Screening engine settings
DEFAULT_DUE_SOON_DAYS = 30
DEFAULT_CUTOFF_MONTHS = 12
SELECTIVE_REFRESH_BATCH_SIZE = 100

# Admin settings
ADMIN_LOG_RETENTION_DAYS = 90
DEFAULT_PAGINATION_SIZE = 50

# Medical terminology fuzzy matching
FUZZY_MATCH_THRESHOLD = 0.8
MEDICAL_VARIANT_CONFIDENCE = 0.9

# PHI filtering settings
PHI_REDACTION_PATTERNS = {
    'ssn_replacement': '[SSN REDACTED]',
    'phone_replacement': '[PHONE REDACTED]',
    'mrn_replacement': '[MRN REDACTED]',
    'insurance_replacement': '[INSURANCE REDACTED]',
    'address_replacement': '[ADDRESS REDACTED]',
    'name_replacement': '[NAME REDACTED]',
    'date_replacement': '[DATE REDACTED]'
}

