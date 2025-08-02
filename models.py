from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import json

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    """Patient demographic and clinical information"""
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='patient', lazy='dynamic')
    documents = db.relationship('MedicalDocument', backref='patient', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic')
    conditions = db.relationship('Condition', backref='patient', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = datetime.utcnow().date()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def __repr__(self):
        return f'<Patient {self.mrn}: {self.full_name}>'

class ScreeningType(db.Model):
    """Screening type definitions with eligibility criteria"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(db.Text)  # JSON array of keywords
    gender_criteria = db.Column(db.String(20))  # 'M', 'F', 'Both'
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    frequency_number = db.Column(db.Integer, default=1)
    frequency_unit = db.Column(db.String(10), default='years')  # 'years', 'months', 'days'
    trigger_conditions = db.Column(db.Text)  # JSON array of condition names
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy='dynamic')
    
    @property
    def keywords_list(self):
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except json.JSONDecodeError:
                return []
        return []
    
    @keywords_list.setter
    def keywords_list(self, value):
        self.keywords = json.dumps(value) if value else None
    
    @property
    def trigger_conditions_list(self):
        if self.trigger_conditions:
            try:
                return json.loads(self.trigger_conditions)
            except json.JSONDecodeError:
                return []
        return []
    
    @trigger_conditions_list.setter
    def trigger_conditions_list(self, value):
        self.trigger_conditions = json.dumps(value) if value else None
    
    def __repr__(self):
        return f'<ScreeningType {self.name}>'

class Screening(db.Model):
    """Individual screening instances for patients"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    status = db.Column(db.String(20), default='Due')  # 'Complete', 'Due', 'Due Soon'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    matched_documents = db.Column(db.Text)  # JSON array of document IDs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def matched_documents_list(self):
        if self.matched_documents:
            try:
                return json.loads(self.matched_documents)
            except json.JSONDecodeError:
                return []
        return []
    
    @matched_documents_list.setter
    def matched_documents_list(self, value):
        self.matched_documents = json.dumps(value) if value else None
    
    def __repr__(self):
        return f'<Screening {self.patient.mrn}: {self.screening_type.name}>'

class MedicalDocument(db.Model):
    """Medical documents with OCR processing and categorization"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    document_date = db.Column(db.Date)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(500))
    
    # OCR fields
    ocr_text = db.Column(db.Text)
    ocr_confidence = db.Column(db.Float, default=0.0)
    ocr_processed = db.Column(db.Boolean, default=False)
    ocr_processed_at = db.Column(db.DateTime)
    
    # PHI filtering
    original_text = db.Column(db.Text)  # Before PHI filtering
    phi_filtered = db.Column(db.Boolean, default=False)
    phi_patterns_found = db.Column(db.Text)  # JSON array of found patterns
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def phi_patterns_list(self):
        if self.phi_patterns_found:
            try:
                return json.loads(self.phi_patterns_found)
            except json.JSONDecodeError:
                return []
        return []
    
    @phi_patterns_list.setter
    def phi_patterns_list(self, value):
        self.phi_patterns_found = json.dumps(value) if value else None
    
    def __repr__(self):
        return f'<MedicalDocument {self.filename}>'

class Condition(db.Model):
    """Patient medical conditions"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    icd10_code = db.Column(db.String(10))
    onset_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # 'active', 'resolved', 'inactive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Condition {self.condition_name}>'

class Appointment(db.Model):
    """Patient appointments"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(100))
    status = db.Column(db.String(20), default='scheduled')  # 'scheduled', 'completed', 'cancelled'
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Appointment {self.patient.mrn}: {self.appointment_date}>'

class AdminLog(db.Model):
    """Admin activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))  # 'screening_type', 'patient', 'document'
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='admin_logs')
    
    def __repr__(self):
        return f'<AdminLog {self.user.username}: {self.action}>'

class ChecklistSettings(db.Model):
    """Global settings for prep sheet generation"""
    id = db.Column(db.Integer, primary_key=True)
    lab_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consult_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=24)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    updated_by_user = db.relationship('User', backref='checklist_settings')
    
    @classmethod
    def get_current(cls):
        """Get current settings or create default"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

class PHISettings(db.Model):
    """PHI filtering configuration"""
    id = db.Column(db.Integer, primary_key=True)
    phi_filtering_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=False)  # Be careful with medical dates
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    updated_by_user = db.relationship('User', backref='phi_settings')
    
    @classmethod
    def get_current(cls):
        """Get current PHI settings or create default"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
