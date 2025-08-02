from app import db
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, Date, ForeignKey
from sqlalchemy.orm import relationship

class User(UserMixin, db.Model):
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)  # M, F, Other
    mrn = Column(String(50), unique=True, nullable=False)  # Medical Record Number
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    screenings = relationship("Screening", back_populates="patient")
    documents = relationship("MedicalDocument", back_populates="patient")
    prep_sheets = relationship("PrepSheet", back_populates="patient")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

class ScreeningType(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    keywords = Column(Text)  # JSON string of keywords for matching
    gender_filter = Column(String(10))  # M, F, or None for all
    min_age = Column(Integer)
    max_age = Column(Integer)
    frequency_value = Column(Integer)  # Numeric frequency
    frequency_unit = Column(String(20))  # years, months, days
    trigger_conditions = Column(Text)  # JSON string of medical conditions
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    screenings = relationship("Screening", back_populates="screening_type")

class Screening(db.Model):
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient.id'), nullable=False)
    screening_type_id = Column(Integer, ForeignKey('screening_type.id'), nullable=False)
    status = Column(String(20), default='Due')  # Due, Due Soon, Complete
    last_completed_date = Column(Date)
    next_due_date = Column(Date)
    matched_documents = Column(Text)  # JSON string of document IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="screenings")
    screening_type = relationship("ScreeningType", back_populates="screenings")

class MedicalDocument(db.Model):
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50))  # lab, imaging, consult, hospital
    upload_date = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String(500))
    ocr_text = Column(Text)
    ocr_confidence = Column(Float)
    phi_filtered = Column(Boolean, default=False)
    
    # Relationships
    patient = relationship("Patient", back_populates="documents")

class PrepSheet(db.Model):
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient.id'), nullable=False)
    generated_date = Column(DateTime, default=datetime.utcnow)
    prep_data = Column(Text)  # JSON string of prep sheet content
    cutoff_months = Column(Integer, default=12)  # Data cutoff period
    
    # Relationships
    patient = relationship("Patient", back_populates="prep_sheets")

class AdminLog(db.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    action = Column(String(200), nullable=False)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

class PHIFilterSettings(db.Model):
    id = Column(Integer, primary_key=True)
    filter_enabled = Column(Boolean, default=True)
    filter_ssn = Column(Boolean, default=True)
    filter_phone = Column(Boolean, default=True)
    filter_mrn = Column(Boolean, default=True)
    filter_insurance = Column(Boolean, default=True)
    filter_addresses = Column(Boolean, default=True)
    filter_names = Column(Boolean, default=True)
    filter_dates = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrepSheetSettings(db.Model):
    id = Column(Integer, primary_key=True)
    lab_cutoff_months = Column(Integer, default=12)
    imaging_cutoff_months = Column(Integer, default=12)
    consult_cutoff_months = Column(Integer, default=12)
    hospital_cutoff_months = Column(Integer, default=12)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
