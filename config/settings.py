import os
from datetime import timedelta

class Config:
    """Application configuration settings"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
    
    # OCR settings
    OCR_CONFIDENCE_THRESHOLD = 0.6
    OCR_PROCESSING_TIMEOUT = 300  # 5 minutes
    
    # FHIR settings
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://api.logicahealth.org/demo/open')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'demo_client')
    FHIR_ACCESS_TOKEN = os.environ.get('FHIR_ACCESS_TOKEN')
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Admin settings
    ADMIN_LOGS_RETENTION_DAYS = 365
    MAX_ADMIN_LOGS_PER_PAGE = 100
    
    # Performance settings
    PREP_SHEET_GENERATION_TIMEOUT = 30  # seconds
    SCREENING_REFRESH_BATCH_SIZE = 50
    
    # PHI filtering settings
    PHI_FILTER_ENABLED = True
    PHI_AUDIT_ENABLED = True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    
    # Enhanced security for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 20,
        "max_overflow": 40
    }

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

# Medical screening defaults
SCREENING_DEFAULTS = {
    'frequency_units': ['months', 'years'],
    'gender_options': ['any', 'male', 'female'],
    'confidence_thresholds': {
        'high': 0.8,
        'medium': 0.6,
        'low': 0.0
    },
    'document_types': ['lab', 'imaging', 'consult', 'hospital', 'other'],
    'screening_statuses': ['due', 'due_soon', 'complete']
}

# HIPAA compliance settings
HIPAA_SETTINGS = {
    'audit_all_access': True,
    'session_timeout_minutes': 30,
    'password_requirements': {
        'min_length': 8,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_numbers': True,
        'require_special_chars': True
    },
    'encryption': {
        'at_rest': 'AES-256',
        'in_transit': 'TLS-1.2+'
    }
}

# Performance monitoring
PERFORMANCE_SETTINGS = {
    'max_prep_generation_time': 10,  # seconds
    'max_ocr_processing_time': 300,  # seconds
    'batch_processing_limit': 500,
    'api_rate_limit': 100  # requests per minute
}
