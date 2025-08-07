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
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    def is_admin_user(self):
        """Check if user has admin privileges"""
        return self.is_admin

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
    keywords = db.Column(db.Text)  # JSON string of keywords for fuzzy detection
    eligible_genders = db.Column(db.String(10), default='both')  # 'M', 'F', or 'both'
    min_age = db.Column(db.Integer)
    max_age = db.Column(db.Integer)
    frequency_years = db.Column(db.Float, nullable=False)  # Frequency in years (can be fractional like 0.25 for 3 months)
    trigger_conditions = db.Column(db.Text)  # JSON string of conditions that modify screening protocols
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
        """Return trigger conditions as a list, filtering out empty/invalid conditions"""
        if not self.trigger_conditions or self.trigger_conditions.strip() == "":
            return []
        
        # Handle special cases like "[]", "null", empty arrays
        if self.trigger_conditions.strip() in ["[]", "null", "None"]:
            return []
            
        try:
            conditions = json.loads(self.trigger_conditions)
            # Handle case where JSON loads to None
            if conditions is None:
                return []
            # Ensure it's a list
            if not isinstance(conditions, list):
                return []
            # Filter out empty strings, None values, and whitespace-only strings
            filtered_conditions = [cond for cond in conditions if cond and str(cond).strip()]
            return filtered_conditions
        except (json.JSONDecodeError, TypeError):
            # Fallback to comma-separated parsing
            return [cond.strip() for cond in self.trigger_conditions.split(',') if cond and cond.strip()]
    
    def get_content_keywords(self):
        """Get keywords for content matching"""
        return self.keywords_list
    
    def set_content_keywords(self, keywords):
        """Set keywords for content matching"""
        if isinstance(keywords, list):
            self.keywords = json.dumps(keywords)
        else:
            self.keywords = keywords
    
    def get_trigger_conditions(self):
        """Get trigger conditions as a list"""
        if self.trigger_conditions:
            try:
                return json.loads(self.trigger_conditions)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def set_trigger_conditions(self, conditions):
        """Set trigger conditions from a list"""
        self.trigger_conditions = json.dumps(conditions) if conditions else None

    @property
    def frequency_display(self):
        """Return frequency in user-friendly format"""
        frequency_months = self.frequency_years * 12
        
        # Special cases for common frequencies
        if self.frequency_years == 1.0:
            return "Every year"
        elif self.frequency_years == 0.5:
            return "Every 6 months"
        elif self.frequency_years == 2.0:
            return "Every 2 years"
        
        # If it's a clean number of months and less than 12 months, show in months
        if frequency_months < 12 and frequency_months == int(frequency_months):
            months = int(frequency_months)
            return f"Every {months} month{'s' if months != 1 else ''}"
        # If it's a clean number of months between 12-23 months (but not 12), show in months
        elif 12 < frequency_months < 24 and frequency_months == int(frequency_months):
            months = int(frequency_months)
            return f"Every {months} months"
        # Otherwise show in years
        else:
            years = self.frequency_years
            if years == int(years):
                years = int(years)
            return f"Every {years} year{'s' if years != 1 else ''}"

    @property
    def display_name(self):
        """Return the display name including variant if applicable"""
        if self.variant_name:
            return f"{self.name} ({self.variant_name})"
        return self.name

    @property
    def variant_name(self):
        """Return the variant name (for compatibility - not implemented yet)"""
        return None

    @property
    def base_name(self):
        """Return the base screening name without variant"""
        return self.name

    @classmethod
    def get_variants(cls, base_name):
        """Get all variants for a given base screening name"""
        return cls.query.filter_by(name=base_name).order_by(cls.variant_name.asc()).all()

    @classmethod
    def get_variant_count(cls, base_name):
        """Get the count of variants for a given base screening name"""
        return cls.query.filter_by(name=base_name).count()

    @classmethod
    def get_base_names_with_counts(cls):
        """Get all unique base names with their variant counts"""
        from sqlalchemy import func
        
        results = db.session.query(
            cls.name,
            func.count(cls.id).label('variant_count'),
            func.min(cls.is_active).label('all_active')
        ).group_by(cls.name).order_by(cls.name).all()
        
        return [(name, int(count), bool(all_active)) for name, count, all_active in results]

    def sync_status_to_variants(self):
        """Sync the is_active status to all other variants of the same base name"""
        # Get the base name (everything before ' - ' if it exists)
        base_name = self.name.split(' - ')[0] if ' - ' in self.name else self.name
        
        # Find all screening types that share the same base name
        variants = ScreeningType.query.filter(
            db.or_(
                ScreeningType.name == base_name,
                ScreeningType.name.like(f"{base_name} - %")
            )
        ).all()
        
        # Update all variants to match this screening type's status
        for variant in variants:
            if variant.id != self.id:
                variant.is_active = self.is_active
        
        db.session.commit()

    def __repr__(self):
        if self.variant_name:
            return f'<ScreeningType {self.name} ({self.variant_name})>'
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
    ocr_text = db.Column(db.Text)  # OCR extracted text (primary field)
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
    """Admin action logging"""
    __tablename__ = 'admin_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('admin_logs', lazy=True))

    def __repr__(self):
        return f'<AdminLog {self.action} by {self.user_id}>'

class ScreeningSettings(db.Model):
    """Settings for screening data cutoffs and configuration"""
    __tablename__ = 'screening_settings'

    id = db.Column(db.Integer, primary_key=True)
    lab_cutoff_months = db.Column(db.Integer, default=12, nullable=False)
    imaging_cutoff_months = db.Column(db.Integer, default=12, nullable=False)
    consult_cutoff_months = db.Column(db.Integer, default=12, nullable=False)
    hospital_cutoff_months = db.Column(db.Integer, default=12, nullable=False)
    default_status_options = db.Column(db.Text, default="Due\nDue Soon\nComplete\nOverdue")
    default_checklist_items = db.Column(db.Text, default="Review screening results\nDiscuss recommendations\nSchedule follow-up\nUpdate care plan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<ScreeningSettings lab:{self.lab_cutoff_months}m imaging:{self.imaging_cutoff_months}m>'

# Keep ChecklistSettings as an alias for backward compatibility
ChecklistSettings = ScreeningSettings

# Additional models for system functionality
class PrepSheetSettings(db.Model):
    """Prep sheet configuration"""
    __tablename__ = 'prep_sheet_settings'

    id = db.Column(db.Integer, primary_key=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    imaging_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    consults_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    hospital_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_cutoff_description(self, data_type):
        """Get human-readable description of cutoff setting"""
        cutoff_value = getattr(self, f'{data_type}_cutoff_months', 0)
        if cutoff_value == 0:
            return "To Last Appointment"
        elif cutoff_value == 1:
            return "1 month"
        else:
            return f"{cutoff_value} months"

    def get_effective_cutoff_date(self, data_type, patient_id=None):
        """Calculate the effective cutoff date for a data type"""
        from datetime import datetime, timedelta
        
        cutoff_months = getattr(self, f'{data_type}_cutoff_months', 6)
        
        # If cutoff is 0, use last appointment logic
        if cutoff_months == 0 and patient_id:
            # Find patient's most recent appointment before today
            from models import Patient  # Import here to avoid circular imports
            patient = Patient.query.get(patient_id)
            if patient:
                # This would need to be implemented when appointment model exists
                # For now, fallback to 6 months
                pass
            # Fallback to 6 months if no appointments or patient not found
            cutoff_months = 6
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=cutoff_months * 30)
        return cutoff_date

    @classmethod
    def apply_preset(cls, preset_name):
        """Apply a preset configuration"""
        presets = {
            'conservative': {'labs': 3, 'imaging': 3, 'consults': 3, 'hospital': 3},
            'standard': {'labs': 6, 'imaging': 6, 'consults': 6, 'hospital': 6},
            'extended': {'labs': 12, 'imaging': 12, 'consults': 12, 'hospital': 12},
            'last_appointment': {'labs': 0, 'imaging': 0, 'consults': 0, 'hospital': 0}
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            return {
                'labs_cutoff_months': preset['labs'],
                'imaging_cutoff_months': preset['imaging'],
                'consults_cutoff_months': preset['consults'],
                'hospital_cutoff_months': preset['hospital']
            }
        return None



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