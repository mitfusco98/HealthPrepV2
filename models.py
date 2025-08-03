from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import JSON

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')  # 'admin', 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    last_visit = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='patient', lazy=True)
    screenings = db.relationship('Screening', backref='patient', lazy=True)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    conditions = db.relationship('Condition', backref='patient', lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = datetime.today().date()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

class ScreeningType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    keywords = db.Column(JSON)  # List of keywords for document matching
    eligibility_criteria = db.Column(JSON)  # Gender, age range, conditions
    frequency_value = db.Column(db.Integer, nullable=False)  # Number
    frequency_unit = db.Column(db.String(10), nullable=False)  # 'months', 'years'
    trigger_conditions = db.Column(JSON)  # Medical conditions that trigger this screening
    status = db.Column(db.String(10), default='active')  # 'active', 'inactive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', etc.
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    document_date = db.Column(db.DateTime)
    
    # OCR fields
    ocr_text = db.Column(db.Text)
    ocr_confidence = db.Column(db.Float)
    ocr_processed = db.Column(db.Boolean, default=False)
    phi_filtered = db.Column(db.Boolean, default=False)
    
    # Relationships
    screening_documents = db.relationship('ScreeningDocument', backref='document', lazy=True)

class Screening(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    status = db.Column(db.String(20), default='due')  # 'complete', 'due', 'due_soon'
    last_completed = db.Column(db.DateTime)
    next_due = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('ScreeningDocument', backref='screening', lazy=True)

class ScreeningDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(db.Integer, db.ForeignKey('screening.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    match_confidence = db.Column(db.Float)  # How well the document matches the screening
    matched_keywords = db.Column(JSON)  # Which keywords matched
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(100))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')  # 'scheduled', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Condition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    condition_name = db.Column(db.String(200), nullable=False)
    icd10_code = db.Column(db.String(10))
    diagnosis_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # 'active', 'resolved', 'chronic'
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.Integer)
    details = db.Column(JSON)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='admin_logs')

class ChecklistSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)
    imaging_cutoff_months = db.Column(db.Integer, default=24)
    consults_cutoff_months = db.Column(db.Integer, default=12)
    hospital_cutoff_months = db.Column(db.Integer, default=12)
    default_items = db.Column(JSON)  # Default checklist items
    status_options = db.Column(JSON)  # Custom status options
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PHISettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phi_filtering_enabled = db.Column(db.Boolean, default=True)
    filter_ssn = db.Column(db.Boolean, default=True)
    filter_phone = db.Column(db.Boolean, default=True)
    filter_mrn = db.Column(db.Boolean, default=True)
    filter_insurance = db.Column(db.Boolean, default=True)
    filter_addresses = db.Column(db.Boolean, default=True)
    filter_names = db.Column(db.Boolean, default=True)
    filter_dates = db.Column(db.Boolean, default=True)
    preserve_medical_terms = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OCRProcessingStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    processing_time = db.Column(db.Float)  # Time in seconds
    confidence_score = db.Column(db.Float)
    pages_processed = db.Column(db.Integer, default=1)
    characters_extracted = db.Column(db.Integer)
    phi_items_filtered = db.Column(db.Integer, default=0)
    ocr_engine = db.Column(db.String(50), default='tesseract')
    processing_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    document = db.relationship('Document', backref='ocr_stats')
