from datetime import datetime, date
from typing import List, Optional
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    __tablename__ = 'patients'

    id = Column(Integer, primary_key=True)
    mrn = Column(String(50), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    gender = Column(String(10))
    phone = Column(String(20))
    email = Column(String(120))
    address = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conditions = relationship('Condition', back_populates='patient', lazy='dynamic')
    documents = relationship('MedicalDocument', back_populates='patient', lazy='dynamic')
    screenings = relationship('Screening', back_populates='patient', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

class ScreeningType(db.Model):
    __tablename__ = 'screening_types'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    keywords = Column(Text)  # JSON string of keywords
    frequency_number = Column(Integer, default=1)
    frequency_unit = Column(String(20), default='years')
    min_age = Column(Integer)
    max_age = Column(Integer)
    gender_criteria = Column(String(10))  # 'Male', 'Female', 'Both'
    trigger_conditions = Column(Text)  # JSON string of conditions
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    screenings = relationship('Screening', back_populates='screening_type')

    @property
    def keywords_list(self):
        if self.keywords:
            try:
                import json
                return json.loads(self.keywords)
            except:
                return self.keywords.split(',') if self.keywords else []
        return []

    @property
    def trigger_conditions_list(self):
        if self.trigger_conditions:
            try:
                import json
                return json.loads(self.trigger_conditions)
            except:
                return self.trigger_conditions.split(',') if self.trigger_conditions else []
        return []

class Screening(db.Model):
    __tablename__ = 'screenings'

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    screening_type_id = Column(Integer, ForeignKey('screening_types.id'), nullable=False)
    status = Column(String(20), default='Due')  # 'Due', 'Complete', 'Due Soon'
    last_completed_date = Column(Date)
    next_due_date = Column(Date)
    matched_documents = Column(Text)  # JSON string of document IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship('Patient', back_populates='screenings')
    screening_type = relationship('ScreeningType', back_populates='screenings')

    @property
    def matched_documents_list(self):
        if self.matched_documents:
            try:
                import json
                return json.loads(self.matched_documents)
            except:
                return []
        return []

    @matched_documents_list.setter
    def matched_documents_list(self, value):
        import json
        self.matched_documents = json.dumps(value) if value else None

class MedicalDocument(db.Model):
    __tablename__ = 'medical_documents'

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50))  # 'lab', 'consult', 'imaging', etc.
    document_date = Column(Date)
    content = Column(Text)  # OCR extracted text
    confidence = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship('Patient', back_populates='documents')

class Condition(db.Model):
    __tablename__ = 'conditions'

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    condition_name = Column(String(200), nullable=False)
    icd_code = Column(String(20))
    diagnosis_date = Column(Date)
    status = Column(String(20), default='active')  # 'active', 'resolved', 'inactive'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship('Patient', back_populates='conditions')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    details = Column(Text)  # JSON string
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship('User')

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