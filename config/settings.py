"""
Global constants and settings for the Health-Prep application.
Centralized configuration management.
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET') or 'dev-secret-key-change-in-production'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///health_prep.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'}
    
    # FHIR settings
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://sandbox-api.va.gov/services/fhir/v0/r4')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'demo_client')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'demo_secret')
    
    # OCR settings
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD', 'tesseract')
    OCR_LANGUAGE = 'eng'
    OCR_CONFIG = '--oem 3 --psm 6'
    
    # Screening engine settings
    FUZZY_MATCH_THRESHOLD = 0.8
    DOCUMENT_RELEVANCE_THRESHOLD = 0.3
    SCREENING_REFRESH_BATCH_SIZE = 100
    
    # Performance settings
    PREP_SHEET_TIMEOUT = 30  # seconds
    OCR_PROCESSING_TIMEOUT = 120  # seconds
    BATCH_PROCESSING_SIZE = 50
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = 'health_prep.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Less restrictive settings for development
    SESSION_COOKIE_SECURE = False
    
    # Development database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///health_prep_dev.db'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = False
    
    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Shorter session lifetime for testing
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=5)

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production-specific settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    # Use production database URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Production logging
    LOG_LEVEL = 'WARNING'

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Application constants
class Constants:
    """Application-wide constants"""
    
    # Screening statuses
    SCREENING_STATUS_COMPLETE = 'Complete'
    SCREENING_STATUS_DUE = 'Due'
    SCREENING_STATUS_DUE_SOON = 'Due Soon'
    
    VALID_SCREENING_STATUSES = [
        SCREENING_STATUS_COMPLETE,
        SCREENING_STATUS_DUE,
        SCREENING_STATUS_DUE_SOON
    ]
    
    # Document types
    DOCUMENT_TYPE_LAB = 'lab'
    DOCUMENT_TYPE_IMAGING = 'imaging'
    DOCUMENT_TYPE_CONSULT = 'consult'
    DOCUMENT_TYPE_HOSPITAL = 'hospital'
    
    VALID_DOCUMENT_TYPES = [
        DOCUMENT_TYPE_LAB,
        DOCUMENT_TYPE_IMAGING,
        DOCUMENT_TYPE_CONSULT,
        DOCUMENT_TYPE_HOSPITAL
    ]
    
    # Gender options
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_OTHER = 'Other'
    
    VALID_GENDERS = [GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]
    
    # Frequency units
    FREQUENCY_UNIT_MONTHS = 'months'
    FREQUENCY_UNIT_YEARS = 'years'
    
    VALID_FREQUENCY_UNITS = [FREQUENCY_UNIT_MONTHS, FREQUENCY_UNIT_YEARS]
    
    # OCR confidence levels
    CONFIDENCE_HIGH_THRESHOLD = 0.8
    CONFIDENCE_MEDIUM_THRESHOLD = 0.6
    
    # PHI filter patterns
    PHI_REDACTION_PLACEHOLDER = '[REDACTED]'
    
    # Prep sheet defaults
    DEFAULT_LAB_CUTOFF_MONTHS = 12
    DEFAULT_IMAGING_CUTOFF_MONTHS = 24
    DEFAULT_CONSULT_CUTOFF_MONTHS = 12
    DEFAULT_HOSPITAL_CUTOFF_MONTHS = 24
    
    # Admin log actions
    LOG_ACTION_LOGIN = 'User Login'
    LOG_ACTION_LOGOUT = 'User Logout'
    LOG_ACTION_SCREENING_CREATED = 'Screening Type Created'
    LOG_ACTION_SCREENING_UPDATED = 'Screening Type Updated'
    LOG_ACTION_SCREENING_DELETED = 'Screening Type Deleted'
    LOG_ACTION_PATIENT_CREATED = 'Patient Created'
    LOG_ACTION_DOCUMENT_UPLOADED = 'Document Uploaded'
    LOG_ACTION_PREP_SHEET_GENERATED = 'Prep Sheet Generated'
    LOG_ACTION_SETTINGS_UPDATED = 'Settings Updated'
    
    # Medical terminology
    COMMON_MEDICAL_ABBREVIATIONS = {
        'bp': 'blood pressure',
        'hr': 'heart rate',
        'rr': 'respiratory rate',
        'temp': 'temperature',
        'wbc': 'white blood cell',
        'rbc': 'red blood cell',
        'hgb': 'hemoglobin',
        'hct': 'hematocrit',
        'plt': 'platelets',
        'bun': 'blood urea nitrogen',
        'cr': 'creatinine',
        'na': 'sodium',
        'k': 'potassium',
        'cl': 'chloride',
        'co2': 'carbon dioxide',
        'glu': 'glucose'
    }
    
    # Fuzzy matching synonyms for medical terms
    MEDICAL_SYNONYMS = {
        'mammogram': ['mammography', 'mammo', 'breast imaging'],
        'colonoscopy': ['colon screening', 'colonogram', 'lower endoscopy'],
        'dexa': ['dxa', 'bone density', 'osteoporosis scan'],
        'pap': ['pap smear', 'pap test', 'cervical screening'],
        'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
        'cholesterol': ['lipid panel', 'lipids', 'cholesterol panel'],
        'ecg': ['ekg', 'electrocardiogram'],
        'echo': ['echocardiogram', 'cardiac echo'],
        'stress test': ['exercise stress test', 'cardiac stress test'],
        'chest xray': ['chest x-ray', 'cxr', 'chest radiograph']
    }

# Error messages
class ErrorMessages:
    """Standardized error messages"""
    
    INVALID_CREDENTIALS = "Invalid username or password"
    ACCESS_DENIED = "Access denied. Admin privileges required."
    PATIENT_NOT_FOUND = "Patient not found"
    SCREENING_TYPE_NOT_FOUND = "Screening type not found"
    DOCUMENT_NOT_FOUND = "Document not found"
    INVALID_FILE_TYPE = "Invalid file type. Allowed types: {}"
    FILE_TOO_LARGE = "File too large. Maximum size: 16MB"
    PROCESSING_FAILED = "Document processing failed"
    DATABASE_ERROR = "Database operation failed"
    VALIDATION_ERROR = "Validation failed: {}"
    UNAUTHORIZED_ACTION = "You are not authorized to perform this action"
    SESSION_EXPIRED = "Your session has expired. Please log in again."
    SYSTEM_ERROR = "An internal system error occurred"

# Success messages
class SuccessMessages:
    """Standardized success messages"""
    
    LOGIN_SUCCESS = "Successfully logged in"
    LOGOUT_SUCCESS = "Successfully logged out"
    PATIENT_CREATED = "Patient created successfully"
    SCREENING_TYPE_CREATED = "Screening type created successfully"
    SCREENING_TYPE_UPDATED = "Screening type updated successfully"
    SCREENING_TYPE_DELETED = "Screening type deleted successfully"
    DOCUMENT_UPLOADED = "Document uploaded successfully"
    SETTINGS_UPDATED = "Settings updated successfully"
    PREP_SHEET_GENERATED = "Prep sheet generated successfully"
    SCREENINGS_REFRESHED = "Screenings refreshed successfully"

