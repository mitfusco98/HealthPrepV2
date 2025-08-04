from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text, JSON
import json

class User(UserMixin, db.Model):
    """User model for authentication and role management"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')  # 'admin', 'user'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

class Patient(db.Model):
    """Patient demographic and basic information"""
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
    documents = db.relationship('Document', backref='patient', lazy=True, cascade='all, delete-orphan')
    screenings = db.relationship('Screening', backref='patient', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    conditions = db.relationship('PatientCondition', backref='patient', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

class ScreeningType(db.Model):
    """Screening type definitions with eligibility criteria"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(Text)
    keywords = db.Column(Text)  # JSON string of keywords
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # 'M', 'F', or null for both
    frequency_value = db.Column(db.Integer)  # e.g., 1, 2, 3
    frequency_unit = db.Column(db.String(10))  # 'years', 'months'
    trigger_conditions = db.Column(Text)  # JSON string of conditions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)

    @property
    def keywords_list(self):
        """Get keywords as a list"""
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except:
                return self.keywords.split(',') if self.keywords else []
        return []

    @keywords_list.setter
    def keywords_list(self, value):
        """Set keywords from a list"""
        if isinstance(value, list):
            self.keywords = json.dumps(value)
        else:
            self.keywords = value

    @property
    def trigger_conditions_list(self):
        """Get trigger conditions as a list"""
        if self.trigger_conditions:
            try:
                return json.loads(self.trigger_conditions)
            except:
                return self.trigger_conditions.split(',') if self.trigger_conditions else []
        return []

    @property
    def frequency_display(self):
        """Human readable frequency"""
        if self.frequency_value and self.frequency_unit:
            return f"{self.frequency_value} {self.frequency_unit}"
        return "Not specified"

class Document(db.Model):
    """Medical documents with OCR processing and PHI filtering"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    document_date = db.Column(db.Date)
    ocr_text = db.Column(Text)
    ocr_confidence = db.Column(db.Float)
    phi_filtered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

    # Relationships
    screening_matches = db.relationship('ScreeningDocumentMatch', backref='document', lazy=True, cascade='all, delete-orphan')

    @property
    def confidence_level(self):
        """Get confidence level category"""
        if self.ocr_confidence is None:
            return 'unknown'
        elif self.ocr_confidence >= 0.8:
            return 'high'
        elif self.ocr_confidence >= 0.6:
            return 'medium'
        else:
            return 'low'

class Screening(db.Model):
    """Patient screening results and status tracking"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    status = db.Column(db.String(20), default='due')  # 'due', 'due_soon', 'complete'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    notes = db.Column(Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document_matches = db.relationship('ScreeningDocumentMatch', backref='screening', lazy=True, cascade='all, delete-orphan')

class ScreeningDocumentMatch(db.Model):
    """Links between screenings and matching documents"""
    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(db.Integer, db.ForeignKey('screening.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    match_confidence = db.Column(db.Float)
    match_keywords = db.Column(Text)  # JSON string of matched keywords
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Appointment(db.Model):
    """Patient appointments and visit information"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(100))
    notes = db.Column(Text)
    status = db.Column(db.String(20), default='scheduled')  # 'scheduled', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PatientCondition(db.Model):
    """Patient medical conditions for screening eligibility"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    icd_code = db.Column(db.String(20))
    diagnosis_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PrepSheetSettings(db.Model):
    """Global settings for prep sheet generation"""
    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=12)
    consults_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=12)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHIFilterSettings(db.Model):
    """PHI filtering configuration"""
    id = db.Column(db.Integer, primary_key=True)
    filter_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AdminLog(db.Model):
    """Admin activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='admin_logs')

class OCRStats(db.Model):
    """OCR processing statistics"""
    id = db.Column(db.Integer, primary_key=True)
    total_documents = db.Column(db.Integer, default=0)
    processed_documents = db.Column(db.Integer, default=0)
    average_confidence = db.Column(db.Float, default=0.0)
    processing_time_avg = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
