from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text, JSON
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('MedicalDocument', backref='patient', lazy=True, cascade='all, delete-orphan')
    screenings = db.relationship('PatientScreening', backref='patient', lazy=True, cascade='all, delete-orphan')
    conditions = db.relationship('PatientCondition', backref='patient', lazy=True, cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = datetime.now().date()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

class ScreeningType(db.Model):
    __tablename__ = 'screening_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(Text)
    keywords = db.Column(JSON)  # List of keywords for document matching
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    gender_restriction = db.Column(db.String(10))  # 'male', 'female', or None
    frequency_value = db.Column(db.Integer, nullable=False)
    frequency_unit = db.Column(db.String(10), nullable=False)  # 'months', 'years'
    trigger_conditions = db.Column(JSON)  # List of conditions that trigger this screening
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('PatientScreening', backref='screening_type', lazy=True)
    
    def is_eligible(self, patient):
        """Check if patient is eligible for this screening type"""
        # Age check
        if self.min_age and patient.age < self.min_age:
            return False
        if self.max_age and patient.age > self.max_age:
            return False
        
        # Gender check
        if self.gender_restriction and patient.gender.lower() != self.gender_restriction.lower():
            return False
        
        return True

class PatientScreening(db.Model):
    __tablename__ = 'patient_screenings'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_types.id'), nullable=False)
    status = db.Column(db.String(20), default='due')  # 'complete', 'due', 'due_soon'
    last_completed_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    matched_documents = db.Column(JSON)  # List of document IDs that match this screening
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_status(self):
        """Calculate screening status based on frequency and last completion"""
        if not self.last_completed_date:
            self.status = 'due'
            return
        
        screening_type = self.screening_type
        if screening_type.frequency_unit == 'months':
            next_due = self.last_completed_date + timedelta(days=30 * screening_type.frequency_value)
        else:  # years
            next_due = self.last_completed_date + timedelta(days=365 * screening_type.frequency_value)
        
        self.next_due_date = next_due
        today = datetime.now().date()
        
        if today >= next_due:
            self.status = 'due'
        elif today >= (next_due - timedelta(days=30)):  # Due within 30 days
            self.status = 'due_soon'
        else:
            self.status = 'complete'

class MedicalDocument(db.Model):
    __tablename__ = 'medical_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    document_date = db.Column(db.Date)
    ocr_text = db.Column(Text)
    ocr_confidence = db.Column(db.Float)
    phi_filtered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def confidence_level(self):
        """Return confidence level as string"""
        if not self.ocr_confidence:
            return 'unknown'
        if self.ocr_confidence >= 0.8:
            return 'high'
        elif self.ocr_confidence >= 0.6:
            return 'medium'
        else:
            return 'low'

class PatientCondition(db.Model):
    __tablename__ = 'patient_conditions'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    icd10_code = db.Column(db.String(10))
    diagnosis_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # 'active', 'resolved', 'chronic'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='admin_logs')

class ChecklistSettings(db.Model):
    __tablename__ = 'checklist_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=12)
    consults_cutoff_months = db.Column(db.Integer, default=6)
    hospital_cutoff_months = db.Column(db.Integer, default=12)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHIFilterSettings(db.Model):
    __tablename__ = 'phi_filter_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    filter_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
