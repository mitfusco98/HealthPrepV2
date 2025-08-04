"""
Global application settings and configuration
Centralized configuration management for HealthPrep application
"""

import os
from datetime import timedelta
from typing import Dict, Any

class Config:
    """Base configuration class"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SESSION_SECRET') or 'health-prep-secret-key-change-in-production'
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///healthprep.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_timeout': 20,
        'max_overflow': 10
    }
    
    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8-hour sessions
    
    # HIPAA Security Headers
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif'}
    
    # OCR Configuration
    OCR_CONFIDENCE_THRESHOLD = float(os.environ.get('OCR_CONFIDENCE_THRESHOLD', '0.6'))
    OCR_PROCESSING_TIMEOUT = int(os.environ.get('OCR_PROCESSING_TIMEOUT', '300'))  # 5 minutes
    
    # FHIR Configuration
    FHIR_SERVER_URL = os.environ.get('FHIR_SERVER_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'health_prep_client')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'default_secret')
    FHIR_REDIRECT_URI = os.environ.get('FHIR_REDIRECT_URI', 'http://localhost:5000/fhir/callback')
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'healthprep.log')
    
    # Admin Configuration
    ADMIN_LOG_RETENTION_DAYS = int(os.environ.get('ADMIN_LOG_RETENTION_DAYS', '2555'))  # 7 years
    
    # Performance Configuration
    SCREENING_BATCH_SIZE = int(os.environ.get('SCREENING_BATCH_SIZE', '100'))
    OCR_BATCH_SIZE = int(os.environ.get('OCR_BATCH_SIZE', '10'))
    
    # Email Configuration (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Cache Configuration
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '300'))
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disabled for easier development
    
    # Development database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///healthprep_dev.db'
    
    # Development logging
    LOG_LEVEL = 'DEBUG'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Test database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Test-specific settings
    OCR_CONFIDENCE_THRESHOLD = 0.5
    SCREENING_BATCH_SIZE = 10
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production security requirements
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # Production database with connection pooling
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'max_overflow': 20,
        'pool_size': 10
    }
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    @classmethod
    def init_app(cls, app):
        """Initialize production app"""
        Config.init_app(app)
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Application-specific settings
class HealthPrepSettings:
    """Health-specific application settings"""
    
    # Medical terminology settings
    MEDICAL_TERMINOLOGY_API_URL = os.environ.get('MEDICAL_TERMINOLOGY_API_URL')
    MEDICAL_TERMINOLOGY_API_KEY = os.environ.get('MEDICAL_TERMINOLOGY_API_KEY')
    
    # Screening engine settings
    DEFAULT_SCREENING_FREQUENCIES = {
        'preventive': {'years': 1},
        'diagnostic': {'months': 6},
        'followup': {'months': 3},
        'chronic_condition': {'months': 3}
    }
    
    # OCR processing settings
    OCR_SUPPORTED_LANGUAGES = ['eng']  # English only for now
    OCR_PAGE_LIMIT = 20  # Maximum pages to process per document
    
    # PHI filtering settings
    PHI_REPLACEMENT_PATTERNS = {
        'ssn': '[SSN REDACTED]',
        'phone': '[PHONE REDACTED]',
        'mrn': '[MRN REDACTED]',
        'insurance': '[INSURANCE ID REDACTED]',
        'address': '[ADDRESS REDACTED]',
        'name': '[NAME REDACTED]',
        'date': '[DATE REDACTED]'
    }
    
    # Document classification settings
    DOCUMENT_TYPES = {
        'lab': {
            'keywords': ['laboratory', 'lab result', 'pathology', 'blood work'],
            'confidence_threshold': 0.7
        },
        'imaging': {
            'keywords': ['radiology', 'x-ray', 'ct scan', 'mri', 'ultrasound'],
            'confidence_threshold': 0.8
        },
        'consult': {
            'keywords': ['consultation', 'specialist', 'referral', 'assessment'],
            'confidence_threshold': 0.6
        },
        'hospital': {
            'keywords': ['discharge', 'admission', 'hospital', 'emergency'],
            'confidence_threshold': 0.8
        }
    }
    
    # Prep sheet settings
    PREP_SHEET_SECTIONS = [
        'patient_header',
        'patient_summary',
        'medical_data',
        'quality_checklist',
        'enhanced_data'
    ]
    
    # Default cutoff periods (in months)
    DEFAULT_CUTOFF_PERIODS = {
        'lab': 12,
        'imaging': 24,
        'consult': 12,
        'hospital': 24
    }
    
    # Confidence color coding
    CONFIDENCE_LEVELS = {
        'high': {'threshold': 0.8, 'color': '#155724', 'bg_color': '#d4edda'},
        'medium': {'threshold': 0.6, 'color': '#856404', 'bg_color': '#fff3cd'},
        'low': {'threshold': 0.0, 'color': '#721c24', 'bg_color': '#f8d7da'}
    }
    
    # Screening status configurations
    SCREENING_STATUSES = {
        'Complete': {
            'color': 'success',
            'description': 'Screening completed within frequency period'
        },
        'Due Soon': {
            'color': 'warning',
            'description': 'Screening due within 30 days'
        },
        'Due': {
            'color': 'danger',
            'description': 'Screening overdue or never completed'
        }
    }
    
    # Business analytics settings
    TIME_ESTIMATES_MINUTES = {
        'manual_prep_sheet': 30,
        'manual_screening_review': 5,
        'manual_document_review': 3,
        'manual_gap_identification': 10,
        'manual_ocr_processing': 15
    }
    
    HOURLY_RATES_USD = {
        'medical_assistant': 18.0,
        'nurse': 35.0,
        'physician': 150.0
    }

def get_config_by_name(config_name: str = None) -> Config:
    """Get configuration class by name"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    return config.get(config_name, config['default'])

def get_health_prep_settings() -> Dict[str, Any]:
    """Get HealthPrep-specific settings as dictionary"""
    settings_class = HealthPrepSettings()
    settings_dict = {}
    
    for attr_name in dir(settings_class):
        if not attr_name.startswith('_'):
            attr_value = getattr(settings_class, attr_name)
            if not callable(attr_value):
                settings_dict[attr_name.lower()] = attr_value
    
    return settings_dict

# Environment-specific overrides
def configure_for_environment():
    """Configure settings based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    
    if env == 'production':
        # Production-specific configurations
        os.environ.setdefault('OCR_CONFIDENCE_THRESHOLD', '0.8')
        os.environ.setdefault('SCREENING_BATCH_SIZE', '500')
        os.environ.setdefault('OCR_BATCH_SIZE', '50')
    elif env == 'testing':
        # Testing-specific configurations
        os.environ.setdefault('OCR_CONFIDENCE_THRESHOLD', '0.5')
        os.environ.setdefault('SCREENING_BATCH_SIZE', '10')
    else:
        # Development defaults
        os.environ.setdefault('OCR_CONFIDENCE_THRESHOLD', '0.6')
        os.environ.setdefault('SCREENING_BATCH_SIZE', '100')

# Initialize environment configuration
configure_for_environment()

