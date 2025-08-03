from datetime import datetime, date
from flask_login import UserMixin
from sqlalchemy import Text, JSON
from app import db

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Patient(db.Model):
    """Patient information from FHIR data"""
    id = db.Column(db.Integer, primary_key=True)
    fhir_id = db.Column(db.String(100), unique=True, nullable=False)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='patient', lazy=True)
    documents = db.relationship('MedicalDocument', backref='patient', lazy=True)
    conditions = db.relationship('PatientCondition', backref='patient', lazy=True)

class ScreeningType(db.Model):
    """Screening type definitions with eligibility criteria"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(Text)
    keywords = db.Column(JSON)  # List of keywords for matching
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # 'M', 'F', or None for both
    frequency_number = db.Column(db.Integer)  # e.g., 1, 2, 3
    frequency_unit = db.Column(db.String(10))  # 'years', 'months', 'days'
    trigger_conditions = db.Column(JSON)  # List of condition codes
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)

class Screening(db.Model):
    """Individual screening records for patients"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    status = db.Column(db.String(20), default='Due')  # 'Complete', 'Due', 'Due Soon'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    matched_documents = db.Column(JSON)  # List of document IDs that match
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MedicalDocument(db.Model):
    """Medical documents from FHIR or uploaded files"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    fhir_id = db.Column(db.String(100))
    filename = db.Column(db.String(500))
    document_type = db.Column(db.String(100))  # 'lab', 'imaging', 'consult', 'hospital'
    content = db.Column(Text)  # Original content
    ocr_text = db.Column(Text)  # OCR extracted text
    ocr_confidence = db.Column(db.Float)  # OCR confidence score
    phi_filtered_text = db.Column(Text)  # PHI-filtered text
    date_created = db.Column(db.Date)
    date_uploaded = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

class PatientCondition(db.Model):
    """Patient medical conditions from FHIR"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    fhir_id = db.Column(db.String(100))
    condition_code = db.Column(db.String(100))
    condition_name = db.Column(db.String(500))
    status = db.Column(db.String(50))
    onset_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChecklistSettings(db.Model):
    """Settings for prep sheet generation"""
    id = db.Column(db.Integer, primary_key=True)
    lab_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consult_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=24)
    default_items = db.Column(JSON)  # Default checklist items
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHIFilterSettings(db.Model):
    """PHI filtering configuration"""
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AdminLog(db.Model):
    """Administrative activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.Integer)
    details = db.Column(JSON)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='admin_logs')

class OCRProcessingStats(db.Model):
    """OCR processing statistics"""
    id = db.Column(db.Integer, primary_key=True)
    documents_processed = db.Column(db.Integer, default=0)
    avg_confidence = db.Column(db.Float, default=0.0)
    low_confidence_count = db.Column(db.Integer, default=0)
    processing_time_avg = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
