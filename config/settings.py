"""
Global constants and settings for the HealthPrep application
"""
import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET') or 'dev-secret-key-change-in-production'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///healthprep.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Security settings
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}
    
    # OCR settings
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD', 'tesseract')
    OCR_CONFIDENCE_THRESHOLD = 0.6
    OCR_PROCESSING_TIMEOUT = 60  # seconds
    
    # FHIR settings
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://sandbox.epic.com/interconnect-fhir-oauth/api/FHIR/R4/')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'default_client_id')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'default_secret')
    FHIR_SCOPE = 'system/Patient.read system/DocumentReference.read system/DiagnosticReport.read system/Observation.read system/Condition.read'
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'healthprep.log')
    
    # Performance settings
    SCREENING_REFRESH_BATCH_SIZE = 100
    DOCUMENT_PROCESSING_BATCH_SIZE = 50
    
    # Default cutoff periods (in months)
    DEFAULT_LABS_CUTOFF = 12
    DEFAULT_IMAGING_CUTOFF = 24
    DEFAULT_CONSULTS_CUTOFF = 12
    DEFAULT_HOSPITAL_CUTOFF = 12
    
    # PHI filter settings
    PHI_FILTER_ENABLED = True
    PHI_REDACTION_MARKER = '[REDACTED]'
    
    # Admin settings
    ADMIN_LOG_RETENTION_DAYS = 90
    ADMIN_SESSION_TIMEOUT = 30  # minutes
    
    # Medical terminology
    MEDICAL_SPECIALTIES = [
        'primary_care',
        'cardiology',
        'endocrinology',
        'oncology',
        'women_health',
        'gastroenterology',
        'pulmonology',
        'nephrology',
        'neurology',
        'orthopedics'
    ]
    
    # Screening frequencies
    FREQUENCY_UNITS = ['months', 'years']
    SCREENING_STATUSES = ['due', 'due_soon', 'complete']
    
    # Document types
    DOCUMENT_TYPES = [
        ('lab', 'Laboratory Results'),
        ('imaging', 'Imaging Studies'),
        ('consult', 'Specialist Consults'),
        ('hospital', 'Hospital Records')
    ]
    
    # Status badge mappings
    STATUS_BADGE_CLASSES = {
        'due': 'danger',
        'due_soon': 'warning',
        'complete': 'success'
    }
    
    # Confidence level mappings
    CONFIDENCE_CLASSES = {
        'high': 'success',
        'medium': 'warning',
        'low': 'danger',
        'unknown': 'secondary'
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Relaxed security for development
    SESSION_COOKIE_SECURE = False
    
    # Development database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///healthprep_dev.db'
    
    # Development logging
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production security
    SESSION_COOKIE_SECURE = True
    FORCE_HTTPS = True
    
    # Production database (should be PostgreSQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    # Performance optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 20,
        'max_overflow': 30
    }

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    
    # Test database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Test settings
    OCR_PROCESSING_TIMEOUT = 10
    PHI_FILTER_ENABLED = False

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)

# Medical terminology constants
MEDICAL_KEYWORDS = {
    'cardiovascular': [
        'echocardiogram', 'echo', 'ekg', 'ecg', 'stress test', 'cardiac',
        'heart', 'blood pressure', 'cholesterol', 'lipid', 'angiogram'
    ],
    'endocrine': [
        'a1c', 'hba1c', 'glucose', 'diabetes', 'thyroid', 'tsh',
        'insulin', 'hormone', 'endocrine'
    ],
    'oncology': [
        'mammogram', 'mammography', 'colonoscopy', 'pap smear', 'biopsy',
        'cancer screening', 'tumor marker', 'ct scan', 'mri'
    ],
    'laboratory': [
        'cbc', 'complete blood count', 'metabolic panel', 'liver function',
        'kidney function', 'urinalysis', 'blood work', 'lab results'
    ],
    'imaging': [
        'xray', 'x-ray', 'ct scan', 'mri', 'ultrasound', 'bone density',
        'dxa', 'dexa', 'pet scan', 'nuclear medicine'
    ]
}

# FHIR resource mappings
FHIR_DOCUMENT_CATEGORIES = {
    'laboratory': 'lab',
    'radiology': 'imaging',
    'consultation': 'consult',
    'discharge-summary': 'hospital',
    'clinical-note': 'consult'
}

# OCR confidence thresholds
OCR_CONFIDENCE_THRESHOLDS = {
    'high': 0.8,
    'medium': 0.6,
    'low': 0.4
}

# Time savings estimates (in minutes)
TIME_SAVINGS_ESTIMATES = {
    'prep_sheet_generation': 15,
    'document_processing': 5,
    'screening_identification': 10,
    'automated_matching': 8,
    'compliance_tracking': 12
}

# Screening due dates
DUE_SOON_THRESHOLD_DAYS = 30

# PHI patterns for validation
PHI_VALIDATION_PATTERNS = {
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'phone': r'\(\d{3}\)\s*\d{3}-\d{4}',
    'mrn': r'\bMRN[\s:]*\d+',
    'insurance': r'\bPolicy[\s#:]*\d+',
    'zip': r'\b\d{5}(?:-\d{4})?\b'
}
