"""
Global constants and settings for the HealthPrep application.
Centralizes configuration management and environment-specific settings.
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///healthprep.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # File upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'}
    
    # OCR settings
    TESSERACT_PATH = os.environ.get('TESSERACT_PATH', '/usr/bin/tesseract')
    OCR_CONFIDENCE_THRESHOLD = 60
    OCR_PROCESSING_TIMEOUT = 300  # 5 minutes
    
    # FHIR settings
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'default_client_id')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'default_client_secret')
    FHIR_SCOPE = 'system/Patient.read system/Observation.read system/DiagnosticReport.read system/Condition.read system/Encounter.read system/DocumentReference.read'
    
    # PHI filtering settings
    PHI_FILTER_ENABLED = True
    PHI_AUDIT_LOGGING = True
    PHI_RETENTION_DAYS = 2555  # 7 years for HIPAA compliance
    
    # Screening engine settings
    SCREENING_REFRESH_BATCH_SIZE = 100
    SCREENING_FREQUENCY_GRACE_DAYS = 30
    FUZZY_MATCH_THRESHOLD = 70
    
    # Admin settings
    ADMIN_LOG_RETENTION_DAYS = 2555  # 7 years
    MAX_EXPORT_RECORDS = 10000
    DEFAULT_PAGINATION_SIZE = 50
    
    # Email settings (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Cache settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = '1000 per hour'
    
    # Monitoring and analytics
    ANALYTICS_ENABLED = True
    PERFORMANCE_MONITORING = True
    ERROR_REPORTING = True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Less restrictive security for development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    
    # Development database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///healthprep_dev.db')
    
    # Development OCR settings
    OCR_CONFIDENCE_THRESHOLD = 50
    
    # Enable SQL query logging in development
    SQLALCHEMY_ECHO = True

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Fast processing for tests
    OCR_PROCESSING_TIMEOUT = 30
    SCREENING_REFRESH_BATCH_SIZE = 10

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production database from environment
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Strict security in production
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # Production logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/healthprep/app.log'
    
    # Production rate limiting
    RATELIMIT_DEFAULT = '100 per hour'
    
    # Production monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN')

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Medical terminology and screening constants
MEDICAL_SPECIALTIES = [
    'Primary Care',
    'Cardiology',
    'Endocrinology',
    'Gastroenterology',
    'Obstetrics & Gynecology',
    'Oncology',
    'Pulmonology',
    'Nephrology',
    'Orthopedics',
    'Neurology',
    'Dermatology',
    'Ophthalmology',
    'Radiology',
    'Pathology'
]

SCREENING_FREQUENCIES = [
    ('years', 'Years'),
    ('months', 'Months'),
    ('weeks', 'Weeks'),
    ('days', 'Days')
]

DOCUMENT_TYPES = [
    ('lab', 'Laboratory'),
    ('imaging', 'Imaging'),
    ('consult', 'Consultation'),
    ('hospital', 'Hospital'),
    ('unknown', 'Unknown')
]

SCREENING_STATUSES = [
    ('due', 'Due'),
    ('due_soon', 'Due Soon'),
    ('complete', 'Complete'),
    ('overdue', 'Overdue')
]

USER_ROLES = [
    ('admin', 'Administrator'),
    ('user', 'User'),
    ('viewer', 'Viewer')
]

# HIPAA compliance constants
HIPAA_RETENTION_PERIODS = {
    'medical_records': 2555,      # 7 years in days
    'admin_logs': 2555,           # 7 years in days
    'audit_trails': 2555,         # 7 years in days
    'phi_access_logs': 2555,      # 7 years in days
    'system_logs': 365            # 1 year in days
}

# OCR confidence levels
OCR_CONFIDENCE_LEVELS = {
    'high': 85,
    'medium': 60,
    'low': 40,
    'failed': 0
}

# Default prep sheet cutoffs (in months)
DEFAULT_CUTOFFS = {
    'labs': 12,
    'imaging': 12,
    'consults': 12,
    'hospital': 12
}

# System performance targets
PERFORMANCE_TARGETS = {
    'prep_generation_seconds': 10,
    'uptime_percentage': 99.9,
    'emr_sync_delay_minutes': 30,
    'document_classification_accuracy': 95
}

# Feature flags
FEATURE_FLAGS = {
    'fhir_integration': True,
    'ocr_processing': True,
    'phi_filtering': True,
    'batch_processing': True,
    'real_time_sync': True,
    'advanced_analytics': True,
    'preset_import_export': True,
    'email_notifications': False,  # Disabled by default
    'mobile_interface': False      # Future feature
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature flag is enabled"""
    return FEATURE_FLAGS.get(feature_name, False)

def get_medical_terminology():
    """Get medical terminology mappings for fuzzy matching"""
    return {
        'screening_aliases': {
            'mammogram': ['mammography', 'breast imaging', 'breast screening', 'mammo'],
            'colonoscopy': ['colon scope', 'colonoscope', 'colon screening', 'colo scope'],
            'dexa': ['dxa', 'bone density', 'bone scan', 'osteoporosis screening'],
            'pap': ['pap smear', 'cervical screening', 'pap test', 'cervical cytology'],
            'a1c': ['hemoglobin a1c', 'hba1c', 'glycated hemoglobin', 'diabetic screening'],
            'lipid': ['lipid panel', 'cholesterol', 'lipid profile', 'cholesterol panel'],
            'cbc': ['complete blood count', 'blood count', 'full blood count'],
            'cmp': ['comprehensive metabolic panel', 'basic metabolic panel', 'bmp']
        },
        'condition_aliases': {
            'diabetes': ['diabetes mellitus', 'dm', 'diabetic', 'type 1 diabetes', 'type 2 diabetes'],
            'hypertension': ['high blood pressure', 'htn', 'elevated blood pressure'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'hypercholesterolemia'],
            'coronary_artery_disease': ['cad', 'heart disease', 'coronary disease'],
            'chronic_kidney_disease': ['ckd', 'kidney disease', 'renal disease']
        }
    }
