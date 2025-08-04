from datetime import datetime, date
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text, JSON
import json

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit = db.Column(db.DateTime)
    
    # Relationships
    documents = db.relationship('MedicalDocument', backref='patient', lazy=True)
    screenings = db.relationship('Screening', backref='patient', lazy=True)
    conditions = db.relationship('PatientCondition', backref='patient', lazy=True)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

class ScreeningType(db.Model):
    __tablename__ = 'screening_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(Text)
    keywords = db.Column(Text)  # JSON string of keywords
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    gender_restriction = db.Column(db.String(10))  # 'M', 'F', or None
    frequency_value = db.Column(db.Integer, nullable=False, default=12)
    frequency_unit = db.Column(db.String(10), nullable=False, default='months')
    trigger_conditions = db.Column(Text)  # JSON string of conditions
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)
    
    def get_keywords_list(self):
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except:
                return []
        return []
    
    def set_keywords_list(self, keywords_list):
        self.keywords = json.dumps(keywords_list)
    
    def get_trigger_conditions_list(self):
        if self.trigger_conditions:
            try:
                return json.loads(self.trigger_conditions)
            except:
                return []
        return []
    
    def set_trigger_conditions_list(self, conditions_list):
        self.trigger_conditions = json.dumps(conditions_list)

class MedicalDocument(db.Model):
    __tablename__ = 'medical_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    document_date = db.Column(db.Date, nullable=False)
    content = db.Column(Text)  # OCR extracted text
    confidence_score = db.Column(db.Float, default=0.0)
    has_phi_filtered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    screening_matches = db.relationship('ScreeningDocumentMatch', backref='document', lazy=True)

class Screening(db.Model):
    __tablename__ = 'screenings'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_types.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Due')  # 'Complete', 'Due', 'Due Soon'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document_matches = db.relationship('ScreeningDocumentMatch', backref='screening', lazy=True)

class ScreeningDocumentMatch(db.Model):
    __tablename__ = 'screening_document_matches'
    
    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(db.Integer, db.ForeignKey('screenings.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('medical_documents.id'), nullable=False)
    match_confidence = db.Column(db.Float, default=0.0)
    matched_keywords = db.Column(Text)  # JSON string of matched keywords
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PatientCondition(db.Model):
    __tablename__ = 'patient_conditions'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    diagnosis_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='admin_logs')

class ChecklistSettings(db.Model):
    __tablename__ = 'checklist_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consults_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=36)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHISettings(db.Model):
    __tablename__ = 'phi_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    filter_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
