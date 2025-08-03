from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from sqlalchemy import Text, JSON, Index
import json

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin', 'user', 'nurse', 'ma'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('MedicalDocument', backref='patient', lazy=True, cascade='all, delete-orphan')
    screenings = db.relationship('Screening', backref='patient', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')

class ScreeningType(db.Model):
    __tablename__ = 'screening_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(Text)
    keywords = db.Column(Text)  # JSON string of keywords
    eligible_genders = db.Column(db.String(20))  # 'M', 'F', 'both'
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    frequency_number = db.Column(db.Integer)  # e.g., 12 for "12 months"
    frequency_unit = db.Column(db.String(20))  # 'months', 'years'
    trigger_conditions = db.Column(Text)  # JSON string of conditions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_keywords_list(self):
        """Parse keywords JSON string into list"""
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except (json.JSONDecodeError, TypeError):
                return self.keywords.split(',') if self.keywords else []
        return []
    
    def set_keywords_list(self, keywords_list):
        """Set keywords from list"""
        self.keywords = json.dumps(keywords_list) if keywords_list else None

class MedicalDocument(db.Model):
    __tablename__ = 'medical_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    document_type = db.Column(db.String(100))  # 'lab', 'imaging', 'consult', 'hospital'
    document_date = db.Column(db.Date)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # OCR fields
    ocr_text = db.Column(Text)
    ocr_confidence = db.Column(db.Float)
    ocr_processed = db.Column(db.Boolean, default=False)
    ocr_processed_at = db.Column(db.DateTime)
    
    # PHI filtering
    phi_filtered = db.Column(db.Boolean, default=False)
    original_text = db.Column(Text)  # Before PHI filtering
    
    # Metadata
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_document_patient_date', 'patient_id', 'document_date'),
        Index('idx_document_type_date', 'document_type', 'document_date'),
        Index('idx_ocr_processed', 'ocr_processed'),
    )

class Screening(db.Model):
    __tablename__ = 'screenings'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_types.id'), nullable=False)
    status = db.Column(db.String(20), default='Due')  # 'Complete', 'Due', 'Due Soon'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    matched_documents = db.Column(Text)  # JSON string of document IDs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screening_type = db.relationship('ScreeningType', backref='screenings')
    
    def get_matched_documents_list(self):
        """Parse matched documents JSON string into list"""
        if self.matched_documents:
            try:
                return json.loads(self.matched_documents)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Scheduled')
    notes = db.Column(Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='admin_logs')

class ChecklistSettings(db.Model):
    __tablename__ = 'checklist_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    cutoff_labs = db.Column(db.Integer, default=12)  # months
    cutoff_imaging = db.Column(db.Integer, default=24)  # months
    cutoff_consults = db.Column(db.Integer, default=12)  # months
    cutoff_hospital = db.Column(db.Integer, default=24)  # months
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHISettings(db.Model):
    __tablename__ = 'phi_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    phi_filtering_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
