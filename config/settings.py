"""
Global application settings and constants
Centralized configuration management
"""
import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///healthprep.db')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_timeout': 20,
        'max_overflow': 0
    }
    
    # FHIR Integration
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', '')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', '')
    
    # OCR Settings
    TESSERACT_PATH = os.environ.get('TESSERACT_PATH', '/usr/bin/tesseract')
    OCR_CONFIDENCE_THRESHOLD = 60
    OCR_MAX_PROCESSING_TIME = 300  # seconds
    
    # File Upload Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}
    
    # Session Settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging Settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'healthprep.log')
    
    # Performance Settings
    MAX_BATCH_SIZE = 500  # Maximum patients to process in batch
    SCREENING_REFRESH_TIMEOUT = 300  # seconds
    
    # HIPAA Compliance Settings
    AUDIT_LOG_RETENTION_DAYS = 2555  # 7 years
    SESSION_TIMEOUT_MINUTES = 480  # 8 hours
    FAILED_LOGIN_LOCKOUT_ATTEMPTS = 3
    FAILED_LOGIN_LOCKOUT_DURATION = 900  # 15 minutes

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    WTF_CSRF_ENABLED = False  # Disable CSRF for development
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    WTF_CSRF_ENABLED = True
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    
    # Performance optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_timeout': 20,
        'max_overflow': 10,
        'pool_size': 20
    }

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Application constants
class AppConstants:
    """Application-wide constants"""
    
    # Screening statuses
    SCREENING_STATUS_COMPLETE = 'complete'
    SCREENING_STATUS_DUE = 'due'
    SCREENING_STATUS_DUE_SOON = 'due_soon'
    
    # Document types
    DOC_TYPE_LAB = 'lab'
    DOC_TYPE_IMAGING = 'imaging'
    DOC_TYPE_CONSULT = 'consult'
    DOC_TYPE_HOSPITAL = 'hospital'
    DOC_TYPE_OTHER = 'other'
    
    # User roles
    ROLE_ADMIN = 'admin'
    ROLE_USER = 'user'
    
    # Gender options
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_OTHER = 'Other'
    GENDER_ALL = 'ALL'
    
    # OCR confidence levels
    CONFIDENCE_HIGH = 80
    CONFIDENCE_MEDIUM = 60
    CONFIDENCE_LOW = 40
    
    # Default frequencies (in months)
    DEFAULT_FREQUENCIES = {
        'annual': 12,
        'biannual': 6,
        'quarterly': 3,
        'biennial': 24,
        'triennial': 36
    }
    
    # Medical specialties
    MEDICAL_SPECIALTIES = [
        'Primary Care',
        'Cardiology',
        'Endocrinology',
        'Gastroenterology',
        'Neurology',
        'Oncology',
        'Orthopedics',
        'Pulmonology',
        'Radiology',
        'Surgery',
        'Women\'s Health'
    ]
    
    # Common screening types
    COMMON_SCREENINGS = [
        'Mammogram',
        'Colonoscopy',
        'Pap Smear',
        'DEXA Scan',
        'Lipid Panel',
        'Hemoglobin A1C',
        'Blood Pressure Check',
        'Cholesterol Screening',
        'Diabetes Screening',
        'Prostate Screening'
    ]
    
    # PHI patterns (for reference)
    PHI_PATTERNS = {
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'phone': r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    }

# Validation constants
class ValidationConstants:
    """Validation rules and constraints"""
    
    # Age constraints
    MIN_PATIENT_AGE = 0
    MAX_PATIENT_AGE = 120
    MIN_SCREENING_AGE = 0
    MAX_SCREENING_AGE = 120
    
    # Frequency constraints
    MIN_FREQUENCY_MONTHS = 1
    MAX_FREQUENCY_MONTHS = 120
    MIN_FREQUENCY_YEARS = 1
    MAX_FREQUENCY_YEARS = 10
    
    # Text length constraints
    MAX_SCREENING_NAME_LENGTH = 100
    MAX_SCREENING_DESCRIPTION_LENGTH = 500
    MAX_PATIENT_NAME_LENGTH = 100
    MAX_MRN_LENGTH = 50
    MAX_FILENAME_LENGTH = 255
    
    # Keyword constraints
    MAX_KEYWORDS_PER_SCREENING = 50
    MAX_KEYWORD_LENGTH = 100

# Error messages
class ErrorMessages:
    """Standardized error messages"""
    
    # Authentication errors
    INVALID_CREDENTIALS = "Invalid username or password"
    ACCESS_DENIED = "Access denied. Insufficient permissions."
    SESSION_EXPIRED = "Your session has expired. Please log in again."
    
    # Validation errors
    REQUIRED_FIELD = "This field is required"
    INVALID_EMAIL = "Please enter a valid email address"
    INVALID_PHONE = "Please enter a valid phone number"
    INVALID_DATE = "Please enter a valid date"
    INVALID_AGE = "Age must be between {min} and {max}"
    
    # System errors
    DATABASE_ERROR = "A database error occurred. Please try again."
    FILE_UPLOAD_ERROR = "Error uploading file. Please try again."
    OCR_PROCESSING_ERROR = "Error processing document. Please check file format."
    FHIR_CONNECTION_ERROR = "Unable to connect to EMR system. Please try again later."
    
    # Business logic errors
    PATIENT_NOT_FOUND = "Patient not found"
    SCREENING_TYPE_NOT_FOUND = "Screening type not found"
    DOCUMENT_NOT_FOUND = "Document not found"
    DUPLICATE_SCREENING_TYPE = "A screening type with this name already exists"
    INVALID_SCREENING_CRITERIA = "Invalid screening criteria"

# Success messages
class SuccessMessages:
    """Standardized success messages"""
    
    PATIENT_CREATED = "Patient created successfully"
    PATIENT_UPDATED = "Patient updated successfully"
    SCREENING_TYPE_CREATED = "Screening type created successfully"
    SCREENING_TYPE_UPDATED = "Screening type updated successfully"
    DOCUMENT_UPLOADED = "Document uploaded successfully"
    DOCUMENT_PROCESSED = "Document processed successfully"
    SETTINGS_UPDATED = "Settings updated successfully"
    PREP_SHEET_GENERATED = "Preparation sheet generated successfully"
    SCREENING_REFRESHED = "Screenings refreshed successfully"

# Get current configuration
def get_config():
    """Get the appropriate configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
