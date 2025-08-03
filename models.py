from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, Float, JSON
from sqlalchemy.orm import relationship
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    role = Column(String(20), default='user')  # 'admin', 'user', 'nurse', 'ma'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = Column(Integer, primary_key=True)
    mrn = Column(String(20), unique=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)  # 'M', 'F', 'Other'
    phone = Column(String(20))
    email = Column(String(120))
    address = Column(Text)
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    insurance_id = Column(String(50))
    primary_physician = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = relationship('Screening', back_populates='patient', cascade='all, delete-orphan')
    documents = relationship('MedicalDocument', back_populates='patient', cascade='all, delete-orphan')
    visits = relationship('Visit', back_populates='patient', cascade='all, delete-orphan')
    conditions = relationship('Condition', back_populates='patient', cascade='all, delete-orphan')
    
    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<Patient {self.mrn}: {self.full_name}>'

class ScreeningType(db.Model):
    __tablename__ = 'screening_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    keywords = Column(JSON)  # List of keywords for document matching
    eligible_genders = Column(JSON)  # List of eligible genders
    min_age = Column(Integer)
    max_age = Column(Integer)
    frequency_years = Column(Integer)
    frequency_months = Column(Integer)
    trigger_conditions = Column(JSON)  # List of conditions that trigger this screening
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = relationship('Screening', back_populates='screening_type', cascade='all, delete-orphan')
    variants = relationship('ScreeningVariant', back_populates='screening_type', cascade='all, delete-orphan')
    
    def is_eligible(self, patient):
        """Check if patient is eligible for this screening type"""
        # Check gender eligibility
        if self.eligible_genders and patient.gender not in self.eligible_genders:
            return False
        
        # Check age eligibility
        if patient.age is not None:
            if self.min_age and patient.age < self.min_age:
                return False
            if self.max_age and patient.age > self.max_age:
                return False
        
        return True
    
    def __repr__(self):
        return f'<ScreeningType {self.name}>'

class ScreeningVariant(db.Model):
    __tablename__ = 'screening_variants'
    
    id = Column(Integer, primary_key=True)
    screening_type_id = Column(Integer, ForeignKey('screening_types.id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    trigger_conditions = Column(JSON)  # Specific conditions for this variant
    frequency_years = Column(Integer)
    frequency_months = Column(Integer)
    keywords = Column(JSON)  # Additional keywords for this variant
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    screening_type = relationship('ScreeningType', back_populates='variants')
    
    def __repr__(self):
        return f'<ScreeningVariant {self.name}>'

class Screening(db.Model):
    __tablename__ = 'screenings'
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    screening_type_id = Column(Integer, ForeignKey('screening_types.id'), nullable=False)
    status = Column(String(20), default='Due')  # 'Due', 'Due Soon', 'Complete', 'Overdue'
    last_completed_date = Column(Date)
    next_due_date = Column(Date)
    matched_documents = Column(JSON)  # List of document IDs that match this screening
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship('Patient', back_populates='screenings')
    screening_type = relationship('ScreeningType', back_populates='screenings')
    
    def __repr__(self):
        return f'<Screening {self.patient.mrn}: {self.screening_type.name}>'

class MedicalDocument(db.Model):
    __tablename__ = 'medical_documents'
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    document_type = Column(String(50))  # 'lab', 'imaging', 'consult', 'hospital', 'screening'
    document_date = Column(Date)
    ocr_text = Column(Text)
    ocr_confidence = Column(Float)
    phi_filtered_text = Column(Text)
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(20), default='pending')  # 'pending', 'processing', 'completed', 'failed'
    content_summary = Column(Text)
    keywords_matched = Column(JSON)  # Keywords that matched this document
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship('Patient', back_populates='documents')
    
    def __repr__(self):
        return f'<MedicalDocument {self.filename}>'

class Visit(db.Model):
    __tablename__ = 'visits'
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    visit_date = Column(Date, nullable=False)
    visit_type = Column(String(50))  # 'routine', 'follow-up', 'urgent', 'physical'
    provider = Column(String(100))
    chief_complaint = Column(Text)
    diagnosis = Column(Text)
    treatment_plan = Column(Text)
    next_appointment = Column(Date)
    visit_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship('Patient', back_populates='visits')
    
    def __repr__(self):
        return f'<Visit {self.patient.mrn}: {self.visit_date}>'

class Condition(db.Model):
    __tablename__ = 'conditions'
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    condition_name = Column(String(200), nullable=False)
    icd10_code = Column(String(10))
    snomed_code = Column(String(20))
    diagnosis_date = Column(Date)
    status = Column(String(20), default='active')  # 'active', 'resolved', 'inactive'
    severity = Column(String(20))  # 'mild', 'moderate', 'severe'
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship('Patient', back_populates='conditions')
    
    def __repr__(self):
        return f'<Condition {self.condition_name}>'

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    description = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User')
    
    def __repr__(self):
        return f'<AdminLog {self.action}>'

class ChecklistSettings(db.Model):
    __tablename__ = 'checklist_settings'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    lab_cutoff_months = Column(Integer, default=12)
    imaging_cutoff_months = Column(Integer, default=24)
    consult_cutoff_months = Column(Integer, default=12)
    hospital_cutoff_months = Column(Integer, default=24)
    default_prep_items = Column(JSON)  # Default items to include in prep sheets
    status_options = Column(JSON)  # Available status options for screening
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChecklistSettings {self.name}>'

class PHIFilterSettings(db.Model):
    __tablename__ = 'phi_filter_settings'
    
    id = Column(Integer, primary_key=True)
    is_enabled = Column(Boolean, default=True)
    filter_ssn = Column(Boolean, default=True)
    filter_phone = Column(Boolean, default=True)
    filter_mrn = Column(Boolean, default=True)
    filter_insurance = Column(Boolean, default=True)
    filter_addresses = Column(Boolean, default=True)
    filter_names = Column(Boolean, default=False)
    filter_dates = Column(Boolean, default=False)
    preserve_medical_terms = Column(Boolean, default=True)
    confidence_threshold = Column(Float, default=0.8)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PHIFilterSettings {self.id}>'

class OCRProcessingStats(db.Model):
    __tablename__ = 'ocr_processing_stats'
    
    id = Column(Integer, primary_key=True)
    total_documents = Column(Integer, default=0)
    processed_documents = Column(Integer, default=0)
    failed_documents = Column(Integer, default=0)
    average_confidence = Column(Float, default=0.0)
    processing_time_avg = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<OCRProcessingStats {self.total_documents} total>'
