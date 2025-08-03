"""
Global constants and settings
Application-wide configuration and default values
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SESSION_SECRET')
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # OCR settings
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD', '/usr/bin/tesseract')
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif'}
    
    # FHIR settings
    FHIR_BASE_URL = os.environ.get('FHIR_BASE_URL', 'https://fhir.epic.com/interconnect-fhir-oauth')
    FHIR_CLIENT_ID = os.environ.get('FHIR_CLIENT_ID', 'demo_client')
    FHIR_CLIENT_SECRET = os.environ.get('FHIR_CLIENT_SECRET', 'demo_secret')
    FHIR_SCOPES = ['patient/Patient.read', 'patient/DocumentReference.read', 'patient/Condition.read', 'patient/Observation.read']
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Pagination settings
    ITEMS_PER_PAGE = 25
    MAX_ITEMS_PER_PAGE = 100

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Healthcare-specific constants
class HealthcareConstants:
    """Healthcare-specific constants and settings"""
    
    # Standard document types
    DOCUMENT_TYPES = {
        'lab': 'Laboratory Results',
        'imaging': 'Imaging Studies',
        'consult': 'Specialist Consultations',
        'hospital': 'Hospital Records',
        'screening': 'Screening Tests',
        'other': 'Other Documents'
    }
    
    # Standard screening statuses
    SCREENING_STATUSES = ['Due', 'Due Soon', 'Complete', 'Overdue']
    
    # Status colors for UI
    STATUS_COLORS = {
        'Due': 'warning',
        'Due Soon': 'info',
        'Complete': 'success',
        'Overdue': 'danger'
    }
    
    # Gender options
    GENDER_OPTIONS = ['M', 'F', 'Other']
    
    # Common medical file extensions
    MEDICAL_FILE_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.dcm']
    
    # OCR confidence thresholds
    OCR_CONFIDENCE_THRESHOLDS = {
        'high': 80,
        'medium': 60,
        'low': 40
    }
    
    # Default cutoff periods (in months)
    DEFAULT_CUTOFFS = {
        'lab_cutoff_months': 12,
        'imaging_cutoff_months': 24,
        'consult_cutoff_months': 12,
        'hospital_cutoff_months': 24
    }
    
    # PHI filter patterns
    PHI_PATTERNS = {
        'ssn': r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
        'phone': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
        'mrn': r'\b(?:MRN|Medical\s+Record|Patient\s+ID|ID)\s*[:#]?\s*([A-Z0-9]{6,12})\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'date': r'\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b'
    }
    
    # Medical terminology preservation list
    MEDICAL_TERMS = [
        'glucose', 'cholesterol', 'triglycerides', 'hdl', 'ldl', 'a1c', 'hba1c',
        'creatinine', 'bun', 'gfr', 'hemoglobin', 'hematocrit', 'wbc', 'rbc',
        'platelet', 'inr', 'pt', 'ptt', 'tsh', 'free t4', 'vitamin d',
        'mg/dl', 'mmol/l', 'ng/ml', 'pg/ml', 'iu/ml', 'u/l', 'g/dl',
        'mmhg', 'bpm', 'kg', 'lbs', 'cm', 'inches', 'ft',
        'mammogram', 'colonoscopy', 'endoscopy', 'biopsy', 'ultrasound',
        'ct scan', 'mri', 'xray', 'x-ray', 'ecg', 'ekg', 'echo',
        'heart', 'lung', 'liver', 'kidney', 'brain', 'spine', 'chest',
        'abdomen', 'pelvis', 'extremities', 'skin', 'eye', 'ear'
    ]

class SystemDefaults:
    """System default values and configurations"""
    
    # Default user roles
    USER_ROLES = ['admin', 'user', 'nurse', 'ma']
    
    # Default admin user (for initial setup)
    DEFAULT_ADMIN = {
        'username': 'admin',
        'email': 'admin@healthprep.local',
        'first_name': 'System',
        'last_name': 'Administrator',
        'role': 'admin'
    }
    
    # Default screening types (basic set)
    DEFAULT_SCREENING_TYPES = [
        {
            'name': 'Annual Physical',
            'description': 'Annual comprehensive physical examination',
            'keywords': ['physical', 'annual exam', 'wellness visit'],
            'eligible_genders': ['M', 'F'],
            'min_age': 18,
            'max_age': None,
            'frequency_years': 1,
            'frequency_months': None,
            'trigger_conditions': [],
            'is_active': True
        },
        {
            'name': 'Blood Pressure Check',
            'description': 'Blood pressure screening',
            'keywords': ['blood pressure', 'bp', 'hypertension'],
            'eligible_genders': ['M', 'F'],
            'min_age': 18,
            'max_age': None,
            'frequency_years': 1,
            'frequency_months': None,
            'trigger_conditions': [],
            'is_active': True
        }
    ]
    
    # Default checklist settings
    DEFAULT_CHECKLIST_SETTINGS = {
        'name': 'Default Prep Sheet Settings',
        'lab_cutoff_months': 12,
        'imaging_cutoff_months': 24,
        'consult_cutoff_months': 12,
        'hospital_cutoff_months': 24,
        'default_prep_items': [
            'Review recent lab results',
            'Check imaging studies',
            'Review specialist consultations',
            'Verify screening compliance',
            'Update medication list',
            'Review allergies'
        ],
        'status_options': ['Due', 'Due Soon', 'Complete', 'Overdue'],
        'is_active': True
    }
    
    # Default PHI filter settings
    DEFAULT_PHI_SETTINGS = {
        'is_enabled': True,
        'filter_ssn': True,
        'filter_phone': True,
        'filter_mrn': True,
        'filter_insurance': True,
        'filter_addresses': True,
        'filter_names': False,
        'filter_dates': False,
        'preserve_medical_terms': True,
        'confidence_threshold': 80.0
    }

def initialize_default_data():
    """Initialize default data for new installations"""
    from models import User, ChecklistSettings, PHIFilterSettings, ScreeningType
    from werkzeug.security import generate_password_hash
    from app import db
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Check if admin user exists
        admin_user = User.query.filter_by(username=SystemDefaults.DEFAULT_ADMIN['username']).first()
        if not admin_user:
            # Create default admin user
            admin_user = User(
                username=SystemDefaults.DEFAULT_ADMIN['username'],
                email=SystemDefaults.DEFAULT_ADMIN['email'],
                first_name=SystemDefaults.DEFAULT_ADMIN['first_name'],
                last_name=SystemDefaults.DEFAULT_ADMIN['last_name'],
                role=SystemDefaults.DEFAULT_ADMIN['role'],
                is_active=True
            )
            admin_user.set_password('admin123')  # Should be changed on first login
            
            from app import db
            db.session.add(admin_user)
            logger.info("Created default admin user")
        
        # Check if checklist settings exist
        checklist_settings = ChecklistSettings.query.filter_by(is_active=True).first()
        if not checklist_settings:
            checklist_settings = ChecklistSettings(**SystemDefaults.DEFAULT_CHECKLIST_SETTINGS)
            db.session.add(checklist_settings)
            logger.info("Created default checklist settings")
        
        # Check if PHI settings exist
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            phi_settings = PHIFilterSettings(**SystemDefaults.DEFAULT_PHI_SETTINGS)
            db.session.add(phi_settings)
            logger.info("Created default PHI filter settings")
        
        # Check if screening types exist
        existing_screening_count = ScreeningType.query.count()
        if existing_screening_count == 0:
            for screening_data in SystemDefaults.DEFAULT_SCREENING_TYPES:
                screening_type = ScreeningType(**screening_data)
                db.session.add(screening_type)
            logger.info(f"Created {len(SystemDefaults.DEFAULT_SCREENING_TYPES)} default screening types")
        
        db.session.commit()
        logger.info("Default data initialization completed")
        
    except Exception as e:
        logger.error(f"Error initializing default data: {str(e)}")
        db.session.rollback()

# Configuration factory
def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig
    elif env == 'testing':
        return TestingConfig
    else:
        return DevelopmentConfig

# Application constants that can be imported throughout the app
DOCUMENT_TYPES = HealthcareConstants.DOCUMENT_TYPES
SCREENING_STATUSES = HealthcareConstants.SCREENING_STATUSES
STATUS_COLORS = HealthcareConstants.STATUS_COLORS
GENDER_OPTIONS = HealthcareConstants.GENDER_OPTIONS
OCR_CONFIDENCE_THRESHOLDS = HealthcareConstants.OCR_CONFIDENCE_THRESHOLDS
DEFAULT_CUTOFFS = HealthcareConstants.DEFAULT_CUTOFFS
