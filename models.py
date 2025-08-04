"""
Database models for HealthPrep Medical Screening System
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json

# Import db from app module
from app import db

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        """Check if user is active (Flask-Login requirement)"""
        return True  # All users are active by default

    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    """Patient model"""
    __tablename__ = 'patient'

    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    screenings = db.relationship('Screening', backref='patient', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='patient', lazy=True, cascade='all, delete-orphan')
    conditions = db.relationship('PatientCondition', backref='patient', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')

    @property
    def age(self):
        """Calculate patient age"""
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    @property
    def full_name(self):
        """Get patient's full name - compatibility property"""
        return self.name

    def __repr__(self):
        return f'<Patient {self.name} ({self.mrn})>'

class ScreeningType(db.Model):
    """Screening type configuration"""
    __tablename__ = 'screening_type'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(db.Text)  # JSON string of keywords
    gender_restriction = db.Column(db.String(10))  # 'male', 'female', or None
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    frequency_number = db.Column(db.Integer, nullable=False)
    frequency_unit = db.Column(db.String(10), nullable=False)  # 'months' or 'years'
    trigger_conditions = db.Column(db.Text)  # JSON string of conditions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)

    @property
    def keywords_list(self):
        """Return keywords as a list"""
        if not self.keywords:
            return []
        try:
            return json.loads(self.keywords)
        except:
            return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]

    @property
    def trigger_conditions_list(self):
        """Return trigger conditions as a list"""
        if not self.trigger_conditions:
            return []
        try:
            return json.loads(self.trigger_conditions)
        except:
            return [cond.strip() for cond in self.trigger_conditions.split(',') if cond.strip()]

    def __repr__(self):
        return f'<ScreeningType {self.name}>'

class Screening(db.Model):
    """Patient screening record"""
    __tablename__ = 'screening'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'due', 'due_soon', 'complete'
    last_completed = db.Column(db.Date)
    next_due = db.Column(db.Date)
    matched_documents = db.Column(db.Text)  # JSON string of document IDs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def matched_documents_list(self):
        """Return matched documents as a list"""
        if not self.matched_documents:
            return []
        try:
            return json.loads(self.matched_documents)
        except:
            return []

    def __repr__(self):
        return f'<Screening {self.screening_type.name} for {self.patient.name}>'

class Document(db.Model):
    """Document model"""
    __tablename__ = 'document'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    content = db.Column(db.Text)  # OCR extracted text
    ocr_confidence = db.Column(db.Float)
    phi_filtered = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Document {self.filename}>'

class PatientCondition(db.Model):
    """Patient medical conditions"""
    __tablename__ = 'patient_condition'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    diagnosis_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Condition {self.condition_name} for {self.patient.name}>'

class Appointment(db.Model):
    """Patient appointments"""
    __tablename__ = 'appointment'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(100))
    status = db.Column(db.String(20), default='scheduled')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Appointment {self.appointment_date} for {self.patient.name}>'

class AdminLog(db.Model):
    """Admin activity logging"""
    __tablename__ = 'admin_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='admin_logs')

    def __repr__(self):
        return f'<AdminLog {self.action} by {self.user.username if self.user else "Unknown"}>'

# Additional models for system functionality
class PrepSheetSettings(db.Model):
    """Prep sheet configuration"""
    __tablename__ = 'prep_sheet_settings'

    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consults_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=12)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChecklistSettings(db.Model):
    """Checklist configuration settings"""
    __tablename__ = 'checklist_settings'

    id = db.Column(db.Integer, primary_key=True)
    lab_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consult_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=12)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHIFilterSettings(db.Model):
    """PHI filter configuration"""
    __tablename__ = 'phi_filter_settings'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OCRStats(db.Model):
    """OCR processing statistics"""
    __tablename__ = 'ocr_stats'

    id = db.Column(db.Integer, primary_key=True)
    total_documents = db.Column(db.Integer, default=0)
    processed_documents = db.Column(db.Integer, default=0)
    pending_documents = db.Column(db.Integer, default=0)
    average_confidence = db.Column(db.Float, default=0.0)
    processing_errors = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScreeningDocumentMatch(db.Model):
    """Junction table for screening-document matches"""
    __tablename__ = 'screening_document_match'

    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(db.Integer, db.ForeignKey('screening.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    match_confidence = db.Column(db.Float)
    matched_keywords = db.Column(db.Text)  # JSON of matched keywords
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    screening = db.relationship('Screening', backref='document_matches')
    document = db.relationship('Document', backref='screening_matches')