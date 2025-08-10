"""
Database models for HealthPrep Medical Screening System
"""
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property

# Import db from app module
from app import db


class Organization(db.Model):
    """Organization model for multi-tenancy"""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150))  # Friendly display name
    address = db.Column(db.Text)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    
    # Epic FHIR Configuration
    epic_client_id = db.Column(db.String(100))  # Epic client ID
    epic_client_secret = db.Column(db.String(255))  # Encrypted Epic client secret
    epic_fhir_url = db.Column(db.String(255))  # Epic FHIR base URL
    epic_environment = db.Column(db.String(20), default='sandbox')  # sandbox, production
    
    # Organizational Settings
    setup_status = db.Column(db.String(20), default='incomplete')  # incomplete, live, trial, suspended
    custom_presets_enabled = db.Column(db.Boolean, default=True)
    auto_sync_enabled = db.Column(db.Boolean, default=False)
    max_users = db.Column(db.Integer, default=10)  # User limit for this org
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    trial_expires = db.Column(db.DateTime)  # For trial accounts
    
    # Relationships
    users = db.relationship('User', backref='organization', lazy=True)
    epic_credentials = db.relationship('EpicCredentials', backref='organization', lazy=True, cascade='all, delete-orphan')
    
    @property
    def is_active(self):
        """Check if organization is active"""
        if self.setup_status == 'suspended':
            return False
        if self.setup_status == 'trial' and self.trial_expires and self.trial_expires < datetime.utcnow():
            return False
        return True
    
    @property
    def user_count(self):
        """Get current user count"""
        from sqlalchemy import func
        return db.session.query(func.count(User.id)).filter(User.org_id == self.id).scalar() or 0
    
    @property
    def can_add_users(self):
        """Check if organization can add more users"""
        return self.user_count < self.max_users
    
    def get_epic_config(self):
        """Get Epic configuration for this organization"""
        return {
            'client_id': self.epic_client_id,
            'fhir_url': self.epic_fhir_url,
            'environment': self.epic_environment,
            'has_credentials': bool(self.epic_client_id and self.epic_client_secret)
        }
    
    def __repr__(self):
        return f'<Organization {self.name}>'


class EpicCredentials(db.Model):
    """Encrypted storage for Epic FHIR credentials per organization"""
    __tablename__ = 'epic_credentials'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Token storage (encrypted at rest)
    access_token = db.Column(db.Text)  # Encrypted access token
    refresh_token = db.Column(db.Text)  # Encrypted refresh token
    token_expires_at = db.Column(db.DateTime)
    token_scope = db.Column(db.String(255))  # FHIR scopes granted
    
    # Epic user context (if user-specific tokens)
    epic_user_id = db.Column(db.String(100))  # Epic user ID if token is user-specific
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Internal user if mapped
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='epic_credentials')
    
    @property
    def is_expired(self):
        """Check if token is expired"""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() >= self.token_expires_at
    
    @property
    def expires_soon(self):
        """Check if token expires within 30 minutes"""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() >= (self.token_expires_at - timedelta(minutes=30))
    
    def __repr__(self):
        return f'<EpicCredentials for org {self.org_id}>'


class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)  # Unique within organization
    email = db.Column(db.String(120), nullable=False)  # Unique within organization  
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='nurse', nullable=False)  # 'root_admin', 'admin', 'MA', 'nurse'
    is_admin = db.Column(db.Boolean, default=False, nullable=False)  # Kept for backward compatibility
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    is_root_admin = db.Column(db.Boolean, default=False, nullable=False)  # Super admin for managing all organizations
    
    # Multi-tenancy fields
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)  # Nullable for root admins
    epic_user_id = db.Column(db.String(100))  # Epic user ID for mapping
    
    # Security and session management
    two_factor_enabled = db.Column(db.Boolean, default=False)
    session_timeout_minutes = db.Column(db.Integer, default=30)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Create unique constraints within organization
    __table_args__ = (
        db.UniqueConstraint('username', 'org_id', name='unique_username_per_org'),
        db.UniqueConstraint('email', 'org_id', name='unique_email_per_org'),
    )

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    def is_admin_user(self):
        """Check if user has admin privileges"""
        return self.role == 'admin' or self.is_admin or self.is_root_admin
    
    def is_root_admin_user(self):
        """Check if user has root admin privileges"""
        return self.is_root_admin or self.role == 'root_admin'

    def has_role(self, role):
        """Check if user has specific role"""
        return self.role == role

    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.role == 'admin' or self.is_root_admin
    
    def can_manage_organizations(self):
        """Check if user can manage organizations"""
        return self.is_root_admin
    
    def can_access_data(self, org_id):
        """Check if user can access data for a specific organization"""
        return self.org_id == org_id or self.is_root_admin
    
    def is_session_expired(self):
        """Check if user session is expired based on activity"""
        if not self.last_activity:
            return True
        timeout_delta = timedelta(minutes=self.session_timeout_minutes)
        return datetime.utcnow() > (self.last_activity + timeout_delta)
    
    def is_account_locked(self):
        """Check if account is temporarily locked"""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def record_login_attempt(self, success=True):
        """Record login attempt and handle account locking"""
        if success:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.last_login = datetime.utcnow()
            self.last_activity = datetime.utcnow()
        else:
            self.failed_login_attempts += 1
            # Lock account after 5 failed attempts for 30 minutes
            if self.failed_login_attempts >= 5:
                self.locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

    @property
    def is_active(self):
        """Check if user is active (Flask-Login requirement)"""
        return self.is_active_user

    @property
    def role_display(self):
        """Get display name for role"""
        role_names = {
            'root_admin': 'Root Administrator',
            'admin': 'Administrator',
            'MA': 'Medical Assistant',
            'nurse': 'Nurse'
        }
        return role_names.get(self.role, self.role.title())

    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    """Patient model with organization scope"""
    __tablename__ = 'patient'

    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), nullable=False)  # Unique within organization
    name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    
    # Multi-tenancy
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Epic integration
    epic_patient_id = db.Column(db.String(100))  # Epic patient ID for FHIR sync
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique MRN within organization
    __table_args__ = (
        db.UniqueConstraint('mrn', 'org_id', name='unique_mrn_per_org'),
    )

    # Relationships
    organization = db.relationship('Organization', backref='patients')
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
    """Screening type configuration with organization scope"""
    __tablename__ = 'screening_type'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)  # Organization scope
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
    organization = db.relationship('Organization', backref='screening_types')
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
        return cls.query.filter_by(name=base_name).order_by(cls.name.asc()).all()

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
    
    def to_preset_format(self):
        """Convert screening type to preset format for export"""
        # Convert frequency_years to number and unit that PresetLoader expects
        frequency_years = self.frequency_years or 1.0
        
        if frequency_years >= 1.0 and frequency_years == int(frequency_years):
            # Whole years
            frequency_number = int(frequency_years)
            frequency_unit = 'years'
        elif frequency_years < 1.0:
            # Convert to months
            frequency_months = frequency_years * 12
            if frequency_months == int(frequency_months):
                frequency_number = int(frequency_months)
                frequency_unit = 'months'
            else:
                # Use fractional years
                frequency_number = frequency_years
                frequency_unit = 'years'
        else:
            # Fractional years
            frequency_number = frequency_years
            frequency_unit = 'years'
        
        return {
            'name': self.name,
            'description': '',  # ScreeningType doesn't have description field yet
            'keywords': self.keywords_list,
            'gender_criteria': self.eligible_genders or 'both',  # Map to expected field name
            'age_min': self.min_age,  # Map to expected field name
            'age_max': self.max_age,  # Map to expected field name
            'frequency_number': frequency_number,
            'frequency_unit': frequency_unit,
            'trigger_conditions': self.trigger_conditions_list,
            'is_active': self.is_active,
            'org_id': self.org_id
        }
    
    @classmethod
    def create_preset_from_types(cls, screening_type_ids, preset_name, description='', specialty='Custom', created_by=None, org_id=None):
        """Create a ScreeningPreset from selected screening types"""
        from datetime import datetime
        
        # Get the screening types with organization scope
        if org_id:
            screening_types = cls.query.filter(
                cls.id.in_(screening_type_ids),
                cls.org_id == org_id
            ).all()
        else:
            screening_types = cls.query.filter(cls.id.in_(screening_type_ids)).all()
        
        if not screening_types:
            return None
        
        # Convert to preset format
        screening_data = []
        for st in screening_types:
            screening_data.append(st.to_preset_format())
        
        # Create preset data structure for the screening_data field
        preset_data = {
            'name': preset_name,
            'description': description,
            'specialty': specialty,
            'version': '2.0',
            'created_date': datetime.utcnow().isoformat(),
            'screening_types': screening_data
        }
        
        # Create ScreeningPreset record
        preset = ScreeningPreset(
            name=preset_name,
            description=description,
            specialty=specialty,
            org_id=org_id,
            shared=False,  # Start as organization-specific
            preset_scope='organization',
            screening_data=preset_data,
            preset_metadata={
                'source_org_id': org_id,
                'source_screening_type_ids': screening_type_ids,
                'extracted_at': datetime.utcnow().isoformat(),
                'extraction_method': 'from_existing_types'
            },
            created_by=created_by
        )
        
        return preset

    def __repr__(self):
        if self.variant_name:
            return f'<ScreeningType {self.name} ({self.variant_name})>'
        return f'<ScreeningType {self.name}>'

class Screening(db.Model):
    """Patient screening record with organization scope"""
    __tablename__ = 'screening'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    screening_type_id = db.Column(db.Integer, db.ForeignKey('screening_type.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)  # Data isolation
    status = db.Column(db.String(20), nullable=False)  # 'due', 'due_soon', 'complete'
    last_completed = db.Column(db.Date)
    next_due = db.Column(db.Date)
    matched_documents = db.Column(db.Text)  # JSON string of document IDs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = db.relationship('Organization', backref='screenings')
    
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
        return f'<Screening {self.screening_type_id} for patient {self.patient_id}>'

class Document(db.Model):
    """Document model with organization scope"""
    __tablename__ = 'document'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)  # Data isolation
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    document_type = db.Column(db.String(50))  # 'lab', 'imaging', 'consult', 'hospital'
    content = db.Column(db.Text)  # OCR extracted text
    ocr_text = db.Column(db.Text)  # OCR extracted text (primary field)
    ocr_confidence = db.Column(db.Float)
    phi_filtered = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    organization = db.relationship('Organization', backref='documents')

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
        return f'<Condition {self.condition_name} for patient {self.patient_id}>'

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
        return f'<Appointment {self.appointment_date} for patient {self.patient_id}>'

class AdminLog(db.Model):
    """Admin action logging with organization scope"""
    __tablename__ = 'admin_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    event_type = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)  # Organization scope
    ip_address = db.Column(db.String(45))
    
    # Enhanced logging fields for HIPAA compliance
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))  # Patient accessed (if applicable)
    resource_type = db.Column(db.String(50))  # Type of resource accessed (patient, document, screening)
    resource_id = db.Column(db.Integer)  # ID of specific resource
    action_details = db.Column(db.Text)  # Human-readable action description
    
    data = db.Column(db.JSON)  # Additional structured data
    
    # Security tracking
    session_id = db.Column(db.String(100))  # Session identifier
    user_agent = db.Column(db.Text)  # Browser/client information
    
    # Relationships
    user = db.relationship('User', backref=db.backref('admin_logs', lazy=True))
    organization = db.relationship('Organization', backref=db.backref('admin_logs', lazy=True))
    patient = db.relationship('Patient', backref=db.backref('access_logs', lazy=True))

    def __repr__(self):
        return f'<AdminLog {self.event_type} by {self.user_id}>'

def log_admin_event(event_type, user_id, org_id, ip, data=None, patient_id=None, resource_type=None, resource_id=None, action_details=None, session_id=None, user_agent=None):
    """Enhanced utility function to log admin events with organization scope"""
    log = AdminLog()
    log.event_type = event_type
    log.user_id = user_id
    log.org_id = org_id
    log.patient_id = patient_id
    log.resource_type = resource_type
    log.resource_id = resource_id
    log.action_details = action_details
    log.session_id = session_id
    log.user_agent = user_agent
    log.ip_address = ip
    log.data = data or {}
    db.session.add(log)
    db.session.commit()

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

class ScreeningPreset(db.Model):
    """Screening preset templates with multi-tenant support"""
    __tablename__ = 'screening_preset'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    specialty = db.Column(db.String(50))  # e.g., 'cardiology', 'primary_care', 'oncology'
    
    # Multi-tenancy support
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))  # NULL = global/shared preset
    shared = db.Column(db.Boolean, default=False, nullable=False)  # Shared across tenants/organizations
    preset_scope = db.Column(db.String(20), default='organization')  # 'global', 'organization', 'user'
    
    screening_data = db.Column(db.JSON, nullable=False)  # Complete screening type data
    preset_metadata = db.Column(db.JSON)  # Additional metadata (version, tags, etc.)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    creator = db.relationship('User', backref='created_presets')
    organization = db.relationship('Organization', backref='screening_presets')

    @property
    def screening_count(self):
        """Get number of screening types in this preset"""
        if not self.screening_data:
            return 0
        
        # Handle new format: screening_data is a dict with 'screening_types' key
        if isinstance(self.screening_data, dict):
            if 'screening_types' in self.screening_data:
                screening_types = self.screening_data['screening_types']
                return len(screening_types) if isinstance(screening_types, list) else 0
            # If it's a dict but no 'screening_types' key, it's probably a single screening
            return 1
        
        # Handle legacy format: screening_data is directly a list of screening types  
        if isinstance(self.screening_data, list):
            return len(self.screening_data)
        
        return 1 if self.screening_data else 0

    @property
    def specialty_display(self):
        """Get formatted specialty name"""
        if not self.specialty:
            return 'General'
        return self.specialty.replace('_', ' ').title()

    def get_screening_types(self):
        """Get all screening types in this preset"""
        if not self.screening_data:
            return []
        
        # Handle new format: screening_data is a dict with 'screening_types' key
        if isinstance(self.screening_data, dict):
            if 'screening_types' in self.screening_data:
                screening_types = self.screening_data['screening_types']
                return screening_types if isinstance(screening_types, list) else []
            # If it's a dict but no 'screening_types' key, treat the whole dict as one screening
            return [self.screening_data]
        
        # Handle legacy format: screening_data is directly a list of screening types
        if isinstance(self.screening_data, list):
            return self.screening_data
        else:
            return [self.screening_data]

    def add_screening_type(self, screening_type_data):
        """Add a screening type to this preset"""
        current_data = self.get_screening_types()
        current_data.append(screening_type_data)
        self.screening_data = current_data
        self.updated_at = datetime.utcnow()

    def remove_screening_type(self, index):
        """Remove a screening type by index"""
        current_data = self.get_screening_types()
        if 0 <= index < len(current_data):
            current_data.pop(index)
            self.screening_data = current_data if current_data else []
            self.updated_at = datetime.utcnow()
            return True
        return False

    def update_screening_type(self, index, screening_type_data):
        """Update a screening type by index"""
        current_data = self.get_screening_types()
        if 0 <= index < len(current_data):
            current_data[index] = screening_type_data
            self.screening_data = current_data
            self.updated_at = datetime.utcnow()
            return True
        return False

    @classmethod
    def from_screening_types(cls, screening_types, name, description='', specialty='', shared=False, created_by=None):
        """Create a preset from existing ScreeningType objects"""
        screening_data = []
        
        for st in screening_types:
            screening_data.append({
                'name': st.name,
                'keywords': st.keywords_list,
                'eligible_genders': st.eligible_genders,
                'min_age': st.min_age,
                'max_age': st.max_age,
                'frequency_years': st.frequency_years,
                'trigger_conditions': st.trigger_conditions_list,
                'is_active': st.is_active
            })
        
        preset = cls(
            name=name,
            description=description,
            specialty=specialty,
            shared=shared,
            screening_data=screening_data,
            created_by=created_by
        )
        
        return preset

    def import_to_screening_types(self, overwrite_existing=False, created_by=None):
        """Import this preset's screening types to the database"""
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        try:
            for st_data in self.get_screening_types():
                try:
                    # Check if screening type already exists
                    existing = ScreeningType.query.filter_by(name=st_data['name']).first()
                    
                    if existing and not overwrite_existing:
                        skipped_count += 1
                        continue
                    
                    if existing and overwrite_existing:
                        # Update existing screening type
                        existing.keywords = json.dumps(st_data.get('keywords', []))
                        existing.eligible_genders = st_data.get('eligible_genders', 'both')
                        existing.min_age = st_data.get('min_age')
                        existing.max_age = st_data.get('max_age')
                        existing.frequency_years = st_data.get('frequency_years', 1.0)
                        existing.trigger_conditions = json.dumps(st_data.get('trigger_conditions', []))
                        existing.is_active = st_data.get('is_active', True)
                        existing.updated_at = datetime.utcnow()
                        updated_count += 1
                    else:
                        # Create new screening type
                        new_st = ScreeningType()
                        new_st.name = st_data['name']
                        new_st.keywords = json.dumps(st_data.get('keywords', []))
                        new_st.eligible_genders = st_data.get('eligible_genders', 'both')
                        new_st.min_age = st_data.get('min_age')
                        new_st.max_age = st_data.get('max_age')
                        new_st.frequency_years = st_data.get('frequency_years', 1.0)
                        new_st.trigger_conditions = json.dumps(st_data.get('trigger_conditions', []))
                        new_st.is_active = st_data.get('is_active', True)
                        db.session.add(new_st)
                        imported_count += 1
                        
                except Exception as e:
                    errors.append(f"Error processing '{st_data.get('name', 'Unknown')}': {str(e)}")
                    continue
            
            db.session.commit()
            
            return {
                'success': True,
                'imported_count': imported_count,
                'updated_count': updated_count,
                'skipped_count': skipped_count,
                'errors': errors
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'imported_count': 0,
                'updated_count': 0,
                'skipped_count': 0,
                'errors': errors + [str(e)]
            }

    def to_export_dict(self):
        """Export preset data for file download"""
        return {
            'preset_info': {
                'name': self.name,
                'description': self.description,
                'specialty': self.specialty,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'creator': self.creator.username if self.creator else None,
                'version': self.preset_metadata.get('version', '1.0') if self.preset_metadata and isinstance(self.preset_metadata, dict) else '1.0'
            },
            'screening_types': self.get_screening_types(),
            'metadata': self.preset_metadata or {}
        }

    @classmethod
    def from_import_dict(cls, data, created_by):
        """Create preset from imported data"""
        preset_info = data.get('preset_info', {})
        
        return cls(
            name=preset_info.get('name', 'Imported Preset'),
            description=preset_info.get('description', ''),
            specialty=preset_info.get('specialty', ''),
            shared=False,  # Imported presets are not shared by default
            screening_data=data.get('screening_types', []),
            preset_metadata=data.get('metadata', {}),
            created_by=created_by
        )

    def is_accessible_by_user(self, user):
        """Check if preset is accessible by a specific user"""
        # Global/shared presets are accessible to all users
        if self.shared or self.preset_scope == 'global':
            return True
        
        # Organization-specific presets are accessible to users in the same org
        if self.org_id and user.org_id == self.org_id:
            return True
        
        # User can access their own presets
        if self.created_by == user.id:
            return True
        
        return False
    
    def can_be_edited_by_user(self, user):
        """Check if preset can be edited by a specific user"""
        # Global presets can only be edited by super admins (future feature)
        if self.preset_scope == 'global':
            return False  # Reserved for future super admin role
        
        # User can edit their own presets
        if self.created_by == user.id:
            return True
        
        # Admin users can edit organization presets
        if user.is_admin_user() and self.org_id == user.org_id:
            return True
        
        return False

    def request_global_approval(self, requested_by):
        """Request approval for global sharing by root admin"""
        if not self.preset_metadata:
            self.preset_metadata = {}
        
        self.preset_metadata.update({
            'approval_requested': True,
            'approval_requested_by': requested_by,
            'approval_requested_at': datetime.utcnow().isoformat(),
            'approval_status': 'pending'
        })
        self.updated_at = datetime.utcnow()
    
    def approve_for_global_sharing(self, approved_by):
        """Approve preset for global sharing (root admin function)"""
        self.shared = True
        self.preset_scope = 'global'
        self.org_id = None  # Make it available to all organizations
        
        if not self.preset_metadata:
            self.preset_metadata = {}
        
        self.preset_metadata.update({
            'approval_status': 'approved',
            'approved_by': approved_by,
            'approved_at': datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow()
    
    def reject_global_approval(self, rejected_by, reason=''):
        """Reject preset for global sharing (root admin function)"""
        if not self.preset_metadata:
            self.preset_metadata = {}
        
        self.preset_metadata.update({
            'approval_status': 'rejected',
            'rejected_by': rejected_by,
            'rejected_at': datetime.utcnow().isoformat(),
            'rejection_reason': reason
        })
        self.updated_at = datetime.utcnow()
    
    def is_pending_approval(self):
        """Check if preset is pending global approval"""
        if not self.preset_metadata:
            return False
        return self.preset_metadata.get('approval_status') == 'pending'
    
    def get_approval_status(self):
        """Get current approval status"""
        if not self.preset_metadata:
            return 'none'
        return self.preset_metadata.get('approval_status', 'none')
    
    def can_request_approval(self):
        """Check if preset can request global approval"""
        # Must be organization-scoped and not already shared
        if self.shared or self.preset_scope == 'global':
            return False
        
        # Must not already be pending or approved
        status = self.get_approval_status()
        return status not in ['pending', 'approved']
    
    def get_screening_type_count(self):
        """Get number of screening types in preset (compatible with existing code)"""
        if not self.screening_data:
            return 0
        if isinstance(self.screening_data, dict) and 'screening_types' in self.screening_data:
            return len(self.screening_data['screening_types'])
        elif isinstance(self.screening_data, list):
            return len(self.screening_data)
        return 0
    
    def get_screening_type_names(self):
        """Get list of screening type names in this preset"""
        names = []
        if self.screening_data:
            if isinstance(self.screening_data, dict) and 'screening_types' in self.screening_data:
                for st in self.screening_data['screening_types']:
                    names.append(st.get('name', 'Unknown'))
            elif isinstance(self.screening_data, list):
                for st in self.screening_data:
                    names.append(st.get('name', 'Unknown'))
        return names
    
    def __repr__(self):
        return f'<ScreeningPreset {self.name} ({self.screening_count} types)>'


# ================================
# Universal Screening Type System
# ================================

import uuid
import hashlib

class UniversalType(db.Model):
    """Universal screening type for standardized naming and grouping"""
    __tablename__ = 'universal_types'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_name = db.Column(db.String(200), unique=True, nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False)
    status = db.Column(db.Enum('active', 'deprecated', name='universal_type_status'), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    aliases = db.relationship('UniversalTypeAlias', backref='universal_type', lazy=True, cascade='all, delete-orphan')
    protocols = db.relationship('ScreeningProtocol', backref='universal_type', lazy=True, cascade='all, delete-orphan')
    label_associations = db.relationship('TypeLabelAssociation', backref='universal_type', lazy=True)
    
    @classmethod
    def create_slug(cls, name):
        """Create deterministic slug from canonical name"""
        import re
        slug = name.lower().strip()
        # Replace punctuation and spaces with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        # Remove multiple hyphens
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')
    
    @property
    def all_aliases(self):
        """Get all aliases as a list"""
        return [alias.alias for alias in self.aliases] if self.aliases else []
    
    def add_alias(self, alias_text, source='system', confidence=1.0):
        """Add an alias for this universal type"""
        existing = UniversalTypeAlias.query.filter_by(
            universal_type_id=self.id,
            alias=alias_text
        ).first()
        
        if not existing:
            alias = UniversalTypeAlias(
                universal_type_id=self.id,
                alias=alias_text,
                source=source,
                confidence=confidence
            )
            db.session.add(alias)
            return alias
        return existing
    
    def __repr__(self):
        return f'<UniversalType {self.canonical_name}>'


class UniversalTypeAlias(db.Model):
    """Aliases for universal screening types"""
    __tablename__ = 'universal_type_aliases'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    universal_type_id = db.Column(db.String(36), db.ForeignKey('universal_types.id'), nullable=False)
    alias = db.Column(db.String(200), nullable=False)
    source = db.Column(db.Enum('system', 'org', 'user', name='alias_source'), default='system')
    confidence = db.Column(db.Float, default=1.0)  # 0-1 confidence score
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('universal_type_id', 'alias'),)
    
    def __repr__(self):
        return f'<UniversalTypeAlias {self.alias} -> {self.universal_type_id}>'


class ScreeningProtocol(db.Model):
    """Groups related variants that represent the same type across users/orgs"""
    __tablename__ = 'screening_protocols'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    universal_type_id = db.Column(db.String(36), db.ForeignKey('universal_types.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    scope = db.Column(db.Enum('system', 'org', name='protocol_scope'), default='system')
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    variants = db.relationship('ScreeningVariant', backref='protocol', lazy=True, cascade='all, delete-orphan')
    organization = db.relationship('Organization', backref='protocols')
    
    @property
    def published_variants(self):
        """Get only published variants"""
        return [v for v in self.variants if v.is_published] if self.variants else []
    
    @property
    def variant_count(self):
        """Total number of variants"""
        return len(self.variants) if self.variants else 0
    
    @property
    def published_count(self):
        """Number of published variants"""
        return len(self.published_variants)
    
    def __repr__(self):
        return f'<ScreeningProtocol {self.name} ({self.variant_count} variants)>'


class ScreeningVariant(db.Model):
    """A specific set of criteria created by a user; tied to a protocol"""
    __tablename__ = 'screening_variants'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    protocol_id = db.Column(db.String(36), db.ForeignKey('screening_protocols.id'), nullable=False)
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    label = db.Column(db.String(200), nullable=False)  # e.g., "MA template v2", "Endo clinic protocol"
    criteria_json = db.Column(db.JSON, nullable=False)
    criteria_hash = db.Column(db.String(64), nullable=False)  # SHA256 of normalized criteria
    derived_from_variant_id = db.Column(db.String(36), db.ForeignKey('screening_variants.id'), nullable=True)
    is_published = db.Column(db.Boolean, default=False)  # Available to admins for preset creation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='created_variants')
    organization = db.relationship('Organization', backref='variants')
    derived_from = db.relationship('ScreeningVariant', remote_side=[id], backref='derivatives')
    
    @classmethod
    def compute_criteria_hash(cls, criteria_json):
        """Compute SHA256 hash of normalized criteria for duplicate detection"""
        import json
        # Normalize JSON by sorting keys
        normalized = json.dumps(criteria_json, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    @property
    def criteria_summary(self):
        """Get a summary of the criteria for display"""
        if not self.criteria_json:
            return "No criteria defined"
        
        summary = []
        if self.criteria_json.get('keywords'):
            summary.append(f"{len(self.criteria_json['keywords'])} keywords")
        if self.criteria_json.get('trigger_conditions'):
            summary.append(f"{len(self.criteria_json['trigger_conditions'])} conditions")
        if self.criteria_json.get('frequency_number'):
            unit = self.criteria_json.get('frequency_unit', 'years')
            summary.append(f"Every {self.criteria_json['frequency_number']} {unit}")
        
        return ", ".join(summary) if summary else "Basic criteria"
    
    @property
    def is_duplicate(self):
        """Check if this variant has identical criteria to another variant"""
        duplicate = ScreeningVariant.query.filter(
            ScreeningVariant.criteria_hash == self.criteria_hash,
            ScreeningVariant.id != self.id
        ).first()
        return duplicate is not None
    
    def get_duplicate_variants(self):
        """Get all variants with identical criteria"""
        return ScreeningVariant.query.filter(
            ScreeningVariant.criteria_hash == self.criteria_hash,
            ScreeningVariant.id != self.id
        ).all()
    
    def __repr__(self):
        return f'<ScreeningVariant {self.label} (by {self.author.username if self.author else "Unknown"})>'


class TypeSynonymGroup(db.Model):
    """Explicit admin-controlled mappings of synonymous labels"""
    __tablename__ = 'type_synonym_groups'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    universal_type_id = db.Column(db.String(36), db.ForeignKey('universal_types.id'), nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TypeSynonymGroup for {self.universal_type_id}>'


class TypeLabelAssociation(db.Model):
    """Connects free-text labels found in the wild to a universal type"""
    __tablename__ = 'type_label_associations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label = db.Column(db.String(200), nullable=False)
    universal_type_id = db.Column(db.String(36), db.ForeignKey('universal_types.id'), nullable=False)
    source = db.Column(db.Enum('system', 'root_admin', 'org_admin', 'user', name='association_source'), default='user')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('label', 'universal_type_id'),)
    
    def promote_to_alias(self, confidence=0.9):
        """Promote this association to a first-class alias"""
        alias = self.universal_type.add_alias(
            alias_text=self.label,
            source='system',
            confidence=confidence
        )
        return alias
    
    def __repr__(self):
        return f'<TypeLabelAssociation {self.label} -> {self.universal_type_id}>'