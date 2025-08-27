"""
Configuration settings for HealthPrep Medical Screening System
"""

import os
import json
from datetime import timedelta
from models import User, ScreeningType

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///healthprep.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'doc', 'docx'}

    # OCR configuration
    OCR_CONFIDENCE_THRESHOLD = 0.6
    OCR_PROCESSING_TIMEOUT = 300  # 5 minutes

    # PHI filtering configuration
    PHI_FILTER_ENABLED = True
    PHI_REDACTION_CHAR = 'X'

    # Admin configuration
    ADMIN_LOG_RETENTION_DAYS = 365
    
    # SMART on FHIR OAuth2 configuration
    SMART_CLIENT_ID = os.environ.get('NONPROD_CLIENT_ID')
    SMART_REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/smart/callback')
    SMART_PRIVATE_KEY_PEM = os.environ.get('NONPROD_PRIVATE_KEY_PEM')
    SMART_PRIVATE_KEY_KID = os.environ.get('NONPROD_PRIVATE_KEY_KID', 'np-2025-08-a')
    
    # SMART Discovery settings
    SMART_DISCOVERY_CACHE_TIMEOUT = 300  # 5 minutes
    SMART_TOKEN_TIMEOUT = 30  # 30 seconds for token exchange
    
    # Epic FHIR default endpoints
    EPIC_SANDBOX_ISS = 'https://fhir.epic.com/interconnect-fhir-oauth'
    EPIC_SANDBOX_AUTH_URL = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize'
    EPIC_SANDBOX_TOKEN_URL = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
    
    # Default SMART scopes
    SMART_DEFAULT_SCOPES = [
        'openid', 'profile', 'fhirUser',
        'patient/Patient.read',
        'patient/Observation.read',
        'patient/DocumentReference.read',
        'patient/Condition.read',
        'patient/DiagnosticReport.read'
    ]

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Production SMART configuration
    SMART_CLIENT_ID = os.environ.get('PROD_CLIENT_ID')
    SMART_PRIVATE_KEY_PEM = os.environ.get('PROD_PRIVATE_KEY_PEM')
    SMART_PRIVATE_KEY_KID = os.environ.get('PROD_PRIVATE_KEY_KID', 'p-2025-08-a')

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def initialize_default_data():
    """Initialize default data for the application"""
    from app import db

    # Create default admin user if it doesn't exist
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)

    # Create a basic user if it doesn't exist
    basic_user = User.query.filter_by(username='user').first()
    if not basic_user:
        basic_user = User(
            username='user',
            email='user@example.com',
            is_admin=False
        )
        basic_user.set_password('user123')
        db.session.add(basic_user)

    # Create some default screening types
    default_screenings = [
            {
                'name': 'Mammogram',
                'keywords': json.dumps(['mammogram', 'mammography', 'breast screening']),
                'eligible_genders': 'F',
                'min_age': 40,
                'max_age': 75,
                'frequency_years': 1.0  # 1 year frequency
            },
            {
                'name': 'Colonoscopy',
                'keywords': json.dumps(['colonoscopy', 'colon screening', 'colorectal']),
                'eligible_genders': 'both',
                'min_age': 50,
                'max_age': 75,
                'frequency_years': 10.0  # 10 year frequency
            },
            {
                'name': 'Pap Smear',
                'keywords': json.dumps(['pap smear', 'cervical screening', 'cytology']),
                'eligible_genders': 'F',
                'min_age': 21,
                'max_age': 65,
                'frequency_years': 3.0  # 3 year frequency
            }
        ]

    for screening_data in default_screenings:
        existing = ScreeningType.query.filter_by(name=screening_data['name']).first()
        if not existing:
            screening_type = ScreeningType(**screening_data)
            db.session.add(screening_type)

    try:
        db.session.commit()
        print("Default users created:")
        print("  Admin: username='admin', password='admin123'")
        print("  User: username='user', password='user123'")
    except Exception as e:
        db.session.rollback()
        raise e