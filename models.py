"""
Database models for HealthPrep Medical Screening System
"""
from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
import logging
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property
from typing import Optional

# Import db from app module
from app import db

# Import encryption utilities
from utils.encryption import encrypt_field, decrypt_field, is_encryption_enabled

logger = logging.getLogger(__name__)


class Organization(db.Model):
    """Organization model for multi-tenancy"""
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150))  # Friendly display name
    address = db.Column(db.Text)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))

    # Epic FHIR Configuration - Enhanced for multi-tenant production support
    epic_client_id = db.Column(db.String(100))  # Epic client ID
    _epic_client_secret = db.Column('epic_client_secret', db.String(500))  # Encrypted Epic client secret
    epic_fhir_url = db.Column(db.String(255), nullable=True)  # Epic FHIR base URL (optional - required only if Epic credentials provided)
    epic_environment = db.Column(db.String(20), default='sandbox')  # sandbox, production
    
    # Production Epic Configuration (varies per organization)
    epic_production_base_url = db.Column(db.String(500))  # Production FHIR URL (unique per Epic customer)
    epic_endpoint_id = db.Column(db.String(100))  # Epic endpoint identifier from open.epic.com
    epic_organization_id = db.Column(db.String(100))  # Epic organization identifier
    epic_oauth_url = db.Column(db.String(500))  # Epic OAuth2 authorization URL
    epic_token_url = db.Column(db.String(500))  # Epic OAuth2 token URL
    
    # Rate limiting and batch processing settings
    fhir_rate_limit_per_hour = db.Column(db.Integer, default=1000)  # FHIR API calls per hour limit
    max_batch_size = db.Column(db.Integer, default=100)  # Maximum batch size for async processing
    async_processing_enabled = db.Column(db.Boolean, default=True)  # Enable async background jobs
    
    # Audit and compliance settings
    audit_retention_days = db.Column(db.Integer, default=2555)  # 7 years for HIPAA compliance
    phi_logging_level = db.Column(db.String(20), default='minimal')  # minimal, standard, detailed

    # Epic Connection Status & Retry Logic (per blueprint)
    is_epic_connected = db.Column(db.Boolean, default=False)  # Current Epic connection status
    last_epic_sync = db.Column(db.DateTime)  # Last successful Epic data fetch
    last_epic_error = db.Column(db.Text)  # Last Epic connection/API error for troubleshooting
    epic_token_expiry = db.Column(db.DateTime)  # Current token expiry for status display
    connection_retry_count = db.Column(db.Integer, default=0)  # Failed retry attempts counter
    next_token_check = db.Column(db.DateTime)  # When to check token expiry next
    
    # Epic App Registration Fields
    epic_app_name = db.Column(db.String(200))  # Epic app name for registration
    epic_app_description = db.Column(db.Text)  # Epic app description
    epic_registration_status = db.Column(db.String(50), default='not_started')  # not_started, in_progress, pending_approval, approved, active
    epic_registration_date = db.Column(db.DateTime)  # When Epic registration was completed

    # Organizational Settings
    setup_status = db.Column(db.String(20), default='incomplete')  # incomplete, live, trial, suspended
    custom_presets_enabled = db.Column(db.Boolean, default=True)
    auto_sync_enabled = db.Column(db.Boolean, default=False)
    max_users = db.Column(db.Integer, default=10)  # User limit for this org
    
    # Appointment-Based Prioritization Settings
    appointment_based_prioritization = db.Column(db.Boolean, default=False)  # Enable appointment-based screening prioritization
    prioritization_window_days = db.Column(db.Integer, default=14)  # Number of days to look ahead for appointments
    process_non_scheduled_patients = db.Column(db.Boolean, default=False)  # Process patients without appointments after priority patients
    last_appointment_sync = db.Column(db.DateTime)  # Last time appointments were synced from Epic

    # Organization Details for Onboarding
    site = db.Column(db.String(200))  # Specific site/location name
    specialty = db.Column(db.String(100))  # Medical specialty (e.g., "Family Practice", "Internal Medicine")
    
    # Stripe Billing Integration
    stripe_customer_id = db.Column(db.String(100), unique=True)  # Stripe customer ID
    stripe_subscription_id = db.Column(db.String(100))  # Stripe subscription ID
    subscription_status = db.Column(db.String(20), default='trialing')  # trialing, active, past_due, canceled, incomplete
    trial_start_date = db.Column(db.DateTime)  # When trial period started
    billing_email = db.Column(db.String(120))  # Email for billing notifications (can differ from contact_email)
    
    # Onboarding Status Management
    creation_method = db.Column(db.String(20), default='self_service')  # self_service, manual (for enterprise/custom billing)
    onboarding_status = db.Column(db.String(30), default='pending_approval')  # pending_approval, approved, active, suspended
    signup_completion_token = db.Column(db.String(100), unique=True)  # One-time token for completing signup (API flow)
    signup_completion_token_expires = db.Column(db.DateTime)  # Token expiry (24 hours)
    approved_at = db.Column(db.DateTime)  # When organization was approved
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Root admin who approved

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    trial_expires = db.Column(db.DateTime)  # For trial accounts (14 days from trial_start_date)

    # Relationships
    users = db.relationship('User', foreign_keys='User.org_id', backref='organization', lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_organizations', lazy=True)
    epic_credentials = db.relationship('EpicCredentials', backref='organization', lazy=True, cascade='all, delete-orphan')

    @property
    def is_active(self):
        """Check if organization is active"""
        # Check setup status
        if self.setup_status == 'suspended':
            return False
        
        # Manual billing organizations are active if approved (no trial expiration check)
        if self.creation_method == 'manual' and self.subscription_status == 'manual_billing':
            return True
        
        # Check trial expiration for non-manual orgs
        if self.setup_status == 'trial' and self.trial_expires and self.trial_expires < datetime.utcnow():
            return False
        
        # Check subscription status - block canceled or terminated subscriptions
        if self.subscription_status in ['canceled', 'incomplete_expired', 'unpaid']:
            return False
        
        return True

    @property
    def user_count(self):
        """Get current user count"""
        from sqlalchemy import func
        # Ensure User is imported before use, or use a forward reference if necessary
        # For simplicity here, assuming User is accessible in this scope or imported earlier
        return db.session.query(func.count(User.id)).filter(User.org_id == self.id).scalar() or 0

    @property
    def can_add_users(self):
        """Check if organization can add more users"""
        return self.user_count < self.max_users
    
    @property
    def has_payment_info(self):
        """Check if organization has provided payment information"""
        return bool(self.stripe_customer_id)
    
    @property
    def has_epic_credentials(self):
        """Check if organization has configured Epic credentials"""
        return bool(self.epic_client_id)
    
    @property
    def has_epic_oauth_connected(self):
        """Check if organization has completed Epic OAuth and has valid connection"""
        return bool(self.is_epic_connected)
    
    @property
    def live_user_count(self):
        """Get count of users with permanent passwords (not temp passwords)"""
        from sqlalchemy import func
        return db.session.query(func.count(User.id)).filter(
            User.org_id == self.id,
            User.is_temp_password == False
        ).scalar() or 0
    
    @hybrid_property
    def epic_client_secret(self):
        """Get decrypted Epic client secret"""
        if not self._epic_client_secret:
            return None
        try:
            return decrypt_field(self._epic_client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt epic_client_secret for org {self.id}: {e}")
            return None
    
    @epic_client_secret.expression
    def epic_client_secret(cls):
        """Class-level expression for epic_client_secret (for queries)"""
        return cls._epic_client_secret
    
    @epic_client_secret.setter
    def epic_client_secret(self, value):
        """Set and encrypt Epic client secret"""
        # Treat None and empty strings as None (no encryption needed)
        if not value or (isinstance(value, str) and not value.strip()):
            self._epic_client_secret = None
        else:
            try:
                self._epic_client_secret = encrypt_field(value)
            except Exception as e:
                logger.error(f"Failed to encrypt epic_client_secret for org {self.id}: {e}")
                self._epic_client_secret = value

    def get_epic_config(self):
        """Get Epic configuration for this organization"""
        return {
            'client_id': self.epic_client_id,
            'fhir_url': self.epic_fhir_url,
            'environment': self.epic_environment,
            'has_credentials': bool(self.epic_client_id and self.epic_client_secret)
        }
    
    def get_epic_fhir_config(self) -> dict:
        """Get Epic FHIR configuration for this organization"""
        if self.epic_environment == 'sandbox':
            # Sandbox configuration (shared Epic sandbox)
            return {
                'client_id': self.epic_client_id,
                'fhir_url': self.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/',
                'oauth_url': self.epic_oauth_url or 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize',
                'token_url': self.epic_token_url or 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token',
                'is_sandbox': True
            }
        else:
            # Production configuration (organization-specific Epic instance)
            return {
                'client_id': self.epic_client_id,
                'fhir_url': self.epic_production_base_url,
                'oauth_url': self.epic_oauth_url,
                'token_url': self.epic_token_url,
                'endpoint_id': self.epic_endpoint_id,
                'organization_id': self.epic_organization_id,
                'is_sandbox': False
            }
    
    def is_within_rate_limit(self, current_hour_calls: int) -> bool:
        """Check if organization is within FHIR API rate limits"""
        return current_hour_calls < self.fhir_rate_limit_per_hour
    
    def get_max_batch_size(self) -> int:
        """Get maximum batch size for async processing"""
        return min(self.max_batch_size, 500)  # Hard cap at 500 for performance
    
    def should_log_phi(self) -> bool:
        """Check if PHI should be logged based on organization settings"""
        return self.phi_logging_level != 'none'
    
    # Epic Connection Status Methods (per blueprint)
    def get_epic_connection_status(self) -> dict:
        """Get comprehensive Epic connection status for admin display"""
        status = {
            'is_connected': self.is_epic_connected,
            'last_sync': self.last_epic_sync,
            'last_error': self.last_epic_error,
            'token_expiry': self.epic_token_expiry,
            'retry_count': self.connection_retry_count,
            'status_class': '',
            'status_message': '',
            'action_required': False
        }
        
        # Determine visual status indicators
        if self.is_epic_connected and self.epic_token_expiry:
            if datetime.utcnow() < self.epic_token_expiry:
                time_until_expiry = self.epic_token_expiry - datetime.utcnow()
                if time_until_expiry.total_seconds() < 3600:  # Less than 1 hour
                    status.update({
                        'status_class': 'warning',
                        'status_message': f'⚠️ Connected (expires in {int(time_until_expiry.total_seconds()//60)} min)',
                        'action_required': True
                    })
                else:
                    status.update({
                        'status_class': 'success',
                        'status_message': '✅ Connected to Epic',
                        'action_required': False
                    })
            else:
                status.update({
                    'status_class': 'danger',
                    'status_message': '❌ Token Expired',
                    'action_required': True
                })
        else:
            status.update({
                'status_class': 'danger',
                'status_message': '❌ Not Connected - Action Required',
                'action_required': True
            })
        
        return status
    
    def update_epic_connection_status(self, is_connected: bool, error_message: Optional[str] = None, token_expiry: Optional[datetime] = None):
        """Update Epic connection status after API operations"""
        self.is_epic_connected = is_connected
        
        if is_connected:
            self.last_epic_sync = datetime.utcnow()
            self.last_epic_error = None
            self.connection_retry_count = 0
            if token_expiry:
                self.epic_token_expiry = token_expiry
        else:
            if error_message:
                self.last_epic_error = error_message
            self.connection_retry_count += 1
        
        # Schedule next token check
        if token_expiry:
            # Check 30 minutes before expiry
            self.next_token_check = token_expiry - timedelta(minutes=30)
        else:
            # Check in 1 hour if no expiry known
            self.next_token_check = datetime.utcnow() + timedelta(hours=1)
        
        db.session.commit()
    
    def needs_token_check(self) -> bool:
        """Check if organization needs token expiry check"""
        if not self.next_token_check:
            return True
        return datetime.utcnow() >= self.next_token_check
    
    def clear_epic_connection_error(self):
        """Clear connection error (for manual retry)"""
        self.last_epic_error = None
        self.connection_retry_count = 0
        db.session.commit()

    def __repr__(self):
        return f'<Organization {self.name}>'


class EpicCredentials(db.Model):
    """Encrypted storage for Epic FHIR credentials per organization"""
    __tablename__ = 'epic_credentials'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)

    # Token storage (encrypted at rest)
    _access_token = db.Column('access_token', db.Text)  # Encrypted access token
    _refresh_token = db.Column('refresh_token', db.Text)  # Encrypted refresh token
    token_expires_at = db.Column(db.DateTime)
    token_scope = db.Column(db.Text)  # FHIR scopes granted

    # Epic user context (if user-specific tokens)
    epic_user_id = db.Column(db.String(100))  # Epic user ID if token is user-specific
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Internal user if mapped

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime)

    # Relationships
    user = db.relationship('User', backref='epic_credentials')
    
    @hybrid_property
    def access_token(self):
        """Get decrypted access token"""
        if not self._access_token:
            return None
        try:
            return decrypt_field(self._access_token)
        except Exception as e:
            logger.error(f"Failed to decrypt access_token for epic_credentials {self.id}: {e}")
            return None
    
    @access_token.setter
    def access_token(self, value):
        """Set and encrypt access token"""
        if value is None:
            self._access_token = None
        else:
            try:
                self._access_token = encrypt_field(value)
            except Exception as e:
                logger.error(f"Failed to encrypt access_token for epic_credentials {self.id}: {e}")
                self._access_token = value
    
    @hybrid_property
    def refresh_token(self):
        """Get decrypted refresh token"""
        if not self._refresh_token:
            return None
        try:
            return decrypt_field(self._refresh_token)
        except Exception as e:
            logger.error(f"Failed to decrypt refresh_token for epic_credentials {self.id}: {e}")
            return None
    
    @refresh_token.setter
    def refresh_token(self, value):
        """Set and encrypt refresh token"""
        if value is None:
            self._refresh_token = None
        else:
            try:
                self._refresh_token = encrypt_field(value)
            except Exception as e:
                logger.error(f"Failed to encrypt refresh_token for epic_credentials {self.id}: {e}")
                self._refresh_token = value

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
    
    # Security Questions (Admin 2FA)
    security_question_1 = db.Column(db.String(200))  # "What year did you graduate high school?"
    security_answer_1_hash = db.Column(db.String(255))  # Hashed answer
    security_question_2 = db.Column(db.String(200))  # "What is your mother's maiden name?"
    security_answer_2_hash = db.Column(db.String(255))  # Hashed answer
    
    # Password Management
    is_temp_password = db.Column(db.Boolean, default=False)  # Force password change on login
    password_reset_token = db.Column(db.String(100))  # Token for password reset link
    password_reset_expires = db.Column(db.DateTime)  # Expiry time for reset token
    email_verified = db.Column(db.Boolean, default=False)  # Email verification status

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
    
    # Security Question Methods
    def set_security_answer_1(self, answer):
        """Set and hash security answer 1"""
        if answer:
            self.security_answer_1_hash = generate_password_hash(answer.strip().lower())
    
    def set_security_answer_2(self, answer):
        """Set and hash security answer 2"""
        if answer:
            self.security_answer_2_hash = generate_password_hash(answer.strip().lower())
    
    def check_security_answer_1(self, answer):
        """Check security answer 1"""
        if not self.security_answer_1_hash or not answer:
            return False
        return check_password_hash(self.security_answer_1_hash, answer.strip().lower())
    
    def check_security_answer_2(self, answer):
        """Check security answer 2"""
        if not self.security_answer_2_hash or not answer:
            return False
        return check_password_hash(self.security_answer_2_hash, answer.strip().lower())
    
    def has_security_questions(self):
        """Check if user has set up security questions"""
        return bool(self.security_question_1 and self.security_answer_1_hash and 
                   self.security_question_2 and self.security_answer_2_hash)
    
    # Password Reset Methods
    def generate_password_reset_token(self):
        """Generate password reset token with 1 hour expiry"""
        import secrets
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        return self.password_reset_token
    
    def check_password_reset_token(self, token):
        """Check if reset token is valid and not expired"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        if self.password_reset_token != token:
            return False
        if datetime.utcnow() > self.password_reset_expires:
            return False
        return True
    
    def clear_password_reset_token(self):
        """Clear password reset token after use"""
        self.password_reset_token = None
        self.password_reset_expires = None

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
    
    @property
    def user_status(self):
        """Get user onboarding/activation status"""
        if not self.is_active_user:
            return 'inactive'
        elif self.is_temp_password:
            return 'pending'
        else:
            return 'active'
    
    @property
    def status_display(self):
        """Get display name for user status"""
        status_names = {
            'pending': 'Pending Setup',
            'active': 'Active',
            'inactive': 'Inactive'
        }
        return status_names.get(self.user_status, 'Unknown')

    def __repr__(self):
        return f'<User {self.username}>'

class Patient(db.Model):
    """Patient model with organization scope"""
    __tablename__ = 'patient'

    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), nullable=True)  # Unique within organization, nullable for Epic imports
    name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)

    # Multi-tenancy
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)

    # Epic FHIR integration fields
    epic_patient_id = db.Column(db.String(100))  # Epic Patient.id from FHIR
    fhir_patient_resource = db.Column(db.Text)  # Full FHIR Patient resource (JSON)
    last_fhir_sync = db.Column(db.DateTime)  # Last time data was synced from Epic
    fhir_version_id = db.Column(db.String(50))  # FHIR resource version for change detection

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique MRN within organization (if MRN exists) and indexing for FHIR sync
    __table_args__ = (
        # Only enforce unique constraint when MRN is not null
        db.Index('idx_patient_mrn_org', 'mrn', 'org_id', unique=True, 
                postgresql_where=db.text('mrn IS NOT NULL')),
        db.Index('idx_patient_epic_id', 'epic_patient_id'),
        db.Index('idx_patient_fhir_sync', 'last_fhir_sync'),
    )

    # Relationships
    organization = db.relationship('Organization', backref='patients')
    screenings = db.relationship('Screening', backref='patient', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='patient', lazy=True, cascade='all, delete-orphan')
    fhir_documents = db.relationship('FHIRDocument', backref='patient', lazy=True, cascade='all, delete-orphan')
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

    def update_from_fhir(self, fhir_patient_resource):
        """Update patient data from FHIR Patient resource"""
        import json
        
        if isinstance(fhir_patient_resource, dict):
            self.fhir_patient_resource = json.dumps(fhir_patient_resource)
            
            # Update basic demographics from FHIR if available
            if 'name' in fhir_patient_resource and fhir_patient_resource['name']:
                name_data = fhir_patient_resource['name'][0]
                if 'given' in name_data and 'family' in name_data:
                    self.name = f"{' '.join(name_data['given'])} {name_data['family']}"
            
            if 'gender' in fhir_patient_resource:
                gender_map = {'male': 'M', 'female': 'F', 'other': 'Other'}
                self.gender = gender_map.get(fhir_patient_resource['gender'], 'Other')
            
            if 'birthDate' in fhir_patient_resource:
                try:
                    birth_date = datetime.strptime(fhir_patient_resource['birthDate'], '%Y-%m-%d').date()
                    self.date_of_birth = birth_date
                except ValueError:
                    pass
            
            # Update contact information
            if 'telecom' in fhir_patient_resource:
                for contact in fhir_patient_resource['telecom']:
                    if contact.get('system') == 'phone':
                        self.phone = contact.get('value')
                    elif contact.get('system') == 'email':
                        self.email = contact.get('value')
            
            # Update version tracking
            if 'meta' in fhir_patient_resource and 'versionId' in fhir_patient_resource['meta']:
                self.fhir_version_id = fhir_patient_resource['meta']['versionId']
        
        self.last_fhir_sync = datetime.utcnow()
    
    def needs_fhir_sync(self, sync_interval_hours=24):
        """Check if patient data needs to be synced from FHIR"""
        if not self.last_fhir_sync:
            return True
        
        sync_threshold = datetime.utcnow() - timedelta(hours=sync_interval_hours)
        return self.last_fhir_sync < sync_threshold
    
    def __repr__(self):
        epic_info = f" [Epic: {self.epic_patient_id}]" if self.epic_patient_id else ""
        return f'<Patient {self.name} ({self.mrn}){epic_info}>'

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
    frequency_value = db.Column(db.Float, nullable=False)  # Frequency value (numeric)
    frequency_unit = db.Column(db.String(10), default='years')  # Unit: 'years', 'months', etc.
    trigger_conditions = db.Column(db.Text)  # JSON string of conditions that modify screening protocols
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # User who created this screening type
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # FHIR Mapping Fields for Epic Interoperability
    fhir_search_params = db.Column(db.Text)  # JSON string of FHIR search parameters
    epic_query_context = db.Column(db.Text)  # JSON string of Epic-specific query context
    fhir_condition_codes = db.Column(db.Text)  # JSON string of standardized condition codes (ICD-10/SNOMED CT)
    fhir_observation_codes = db.Column(db.Text)  # JSON string of standardized observation codes (LOINC)
    fhir_document_types = db.Column(db.Text)  # JSON string of FHIR document type mappings

    # Relationships
    organization = db.relationship('Organization', backref='screening_types')
    screenings = db.relationship('Screening', backref='screening_type', lazy=True)
    created_by_user = db.relationship('User', backref='created_screening_types', foreign_keys=[created_by])

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

        # Handle case where JSON loads to None
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
    def frequency_years(self):
        """Return frequency in years as a float"""
        if not self.frequency_value:
            return 1.0  # Default to 1 year
        
        if self.frequency_unit == 'months':
            return self.frequency_value / 12.0
        elif self.frequency_unit == 'years':
            return float(self.frequency_value)
        else:
            # Default to years for unknown units
            return float(self.frequency_value)

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
    def get_base_names_with_counts(cls, org_id=None):
        """Get unique base names with their variant counts for a specific organization"""
        from sqlalchemy import func, cast, Integer
        
        # Get all screening types for the organization
        query = cls.query
        if org_id is not None:
            query = query.filter(cls.org_id == org_id)
        
        screening_types = query.all()
        
        # Group by base name (extracted from full name)
        base_name_groups = {}
        
        for st in screening_types:
            base_name = cls._extract_base_name(st.name)
            
            if base_name not in base_name_groups:
                base_name_groups[base_name] = {
                    'variants': [],
                    'all_active': True
                }
            
            base_name_groups[base_name]['variants'].append(st)
            
            # Check if all variants are active
            if not st.is_active:
                base_name_groups[base_name]['all_active'] = False
        
        # Convert to the expected format
        results = []
        for base_name, group_data in sorted(base_name_groups.items()):
            variant_count = len(group_data['variants'])
            all_active = group_data['all_active']
            results.append((base_name, variant_count, all_active))
        
        return results
    
    @classmethod
    def _extract_base_name(cls, name):
        """Extract base screening name from variant name with connecting descriptors"""
        if not name:
            return name
        
        # Handle connecting descriptors like "Pulmonary Function Test - COPD Monitoring"
        # Split on common delimiters and take the first part as the base name
        delimiters = [' - ', ' – ', ' — ', ' (', ':']
        
        base_name = name
        for delimiter in delimiters:
            if delimiter in name:
                base_name = name.split(delimiter)[0].strip()
                break
        
        return base_name
    
    def generate_fhir_mappings(self):
        """Generate and store FHIR mappings for this screening type"""
        from utils.fhir_mapping import ScreeningTypeFHIREnhancer
        
        enhancer = ScreeningTypeFHIREnhancer()
        screening_data = {
            'name': self.name,
            'keywords': self.keywords_list,
            'trigger_conditions': self.trigger_conditions_list,
            'eligible_genders': self.eligible_genders,
            'min_age': self.min_age,
            'max_age': self.max_age,
            'frequency_years': self.frequency_years
        }
        
        enhanced_data = enhancer.add_fhir_mapping_to_screening_type(screening_data)
        
        # Update FHIR mapping fields
        self.fhir_search_params = enhanced_data.get('fhir_search_params')
        self.epic_query_context = enhanced_data.get('epic_query_context')
        self.fhir_condition_codes = enhanced_data.get('fhir_condition_codes')
        self.fhir_observation_codes = enhanced_data.get('fhir_observation_codes')
        
        return enhanced_data
    
    def get_fhir_search_params(self):
        """Get parsed FHIR search parameters"""
        if not self.fhir_search_params:
            return {}
        try:
            return json.loads(self.fhir_search_params)
        except:
            return {}
    
    def get_epic_query_context(self):
        """Get parsed Epic query context"""
        if not self.epic_query_context:
            return {}
        try:
            return json.loads(self.epic_query_context)
        except:
            return {}
    
    def get_fhir_condition_codes(self):
        """Get standardized condition codes for FHIR queries"""
        if not self.fhir_condition_codes:
            return []
        try:
            return json.loads(self.fhir_condition_codes)
        except:
            return []
    
    def get_fhir_observation_codes(self):
        """Get standardized observation codes for FHIR queries"""
        if not self.fhir_observation_codes:
            return []
        try:
            return json.loads(self.fhir_observation_codes)
        except:
            return []

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
        preset = ScreeningPreset()
        preset.name = preset_name
        preset.description = description
        preset.specialty = specialty
        preset.org_id = org_id
        preset.shared = False  # Start as organization-specific
        preset.preset_scope = 'organization'
        preset.screening_data = preset_data
        preset.preset_metadata = {
            'source_org_id': org_id,
            'source_screening_type_ids': screening_type_ids,
            'extracted_at': datetime.utcnow().isoformat(),
            'extraction_method': 'from_existing_types'
        }
        preset.created_by = created_by

        return preset

    def __repr__(self):
        if self.variant_name:
            return f'<ScreeningType {self.name} ({self.variant_name})>'
        return f'<ScreeningType {self.name}>'


# Association table for FHIR documents and screenings  
screening_fhir_documents = db.Table('screening_fhir_documents',
    db.Column('screening_id', db.Integer, db.ForeignKey('screening.id'), primary_key=True),
    db.Column('fhir_document_id', db.Integer, db.ForeignKey('fhir_documents.id'), primary_key=True)
)


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
    fhir_documents = db.relationship('FHIRDocument', secondary=screening_fhir_documents, back_populates='screenings')

    @property
    def matched_documents_list(self):
        """Return matched documents as a list"""
        if not self.matched_documents:
            return []
        try:
            return json.loads(self.matched_documents)
        except:
            return []
    
    def get_active_document_matches(self):
        """Get document matches excluding dismissed ones"""
        from models import DismissedDocumentMatch
        
        # Get all dismissed document IDs for this screening
        dismissed_ids = set(
            row[0] for row in db.session.query(DismissedDocumentMatch.document_id).filter(
                DismissedDocumentMatch.screening_id == self.id,
                DismissedDocumentMatch.is_active == True,
                DismissedDocumentMatch.document_id.isnot(None)
            ).all()
        )
        
        # Filter out dismissed matches
        return [match for match in self.document_matches if match.document_id not in dismissed_ids]
    
    def get_active_fhir_documents(self):
        """Get FHIR documents excluding dismissed ones"""
        from models import DismissedDocumentMatch
        
        # Get all dismissed FHIR document IDs for this screening
        dismissed_ids = set(
            row[0] for row in db.session.query(DismissedDocumentMatch.fhir_document_id).filter(
                DismissedDocumentMatch.screening_id == self.id,
                DismissedDocumentMatch.is_active == True,
                DismissedDocumentMatch.fhir_document_id.isnot(None)
            ).all()
        )
        
        # Filter out dismissed documents
        return [doc for doc in self.fhir_documents if doc.id not in dismissed_ids]

    def __repr__(self):
        return f'<Screening {self.screening_type_id} for patient {self.patient_id}>'

class Document(db.Model):
    """Document model with organization scope and EMR sync tracking"""
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New fields for EMR sync architecture separation
    external_system = db.Column(db.String(50))  # 'epic', 'allscripts', etc.
    external_id = db.Column(db.String(100))  # External system document ID
    external_hash = db.Column(db.String(64))  # SHA-256 hash for change detection
    ingested_at = db.Column(db.DateTime)  # When document was pulled from EMR
    binary_fetched_at = db.Column(db.DateTime)  # When document binary was downloaded
    processing_version = db.Column(db.Integer, default=1)  # OCR/processing version
    
    # Document date from EMR vs local creation date
    document_date = db.Column(db.Date)  # Date from EMR system (preferred for screening logic)

    # Relationships
    organization = db.relationship('Organization', backref='documents')
    
    # Add indexes for performance
    __table_args__ = (
        db.Index('idx_document_org_external', 'org_id', 'external_system', 'external_id'),
        db.Index('idx_document_patient_date', 'patient_id', 'document_date'),
        db.Index('idx_document_ingested', 'ingested_at'),
    )

    def __repr__(self):
        return f'<Document {self.filename}>'


class FHIRDocument(db.Model):
    """FHIR DocumentReference model for Epic integration"""
    __tablename__ = 'fhir_documents'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # FHIR DocumentReference fields
    epic_document_id = db.Column(db.String(100), nullable=False)  # Epic DocumentReference.id
    fhir_document_reference = db.Column(db.Text)  # Full FHIR DocumentReference resource (JSON)
    document_type_code = db.Column(db.String(50))  # LOINC code for document type
    document_type_display = db.Column(db.String(200))  # Human readable document type
    
    # Document metadata
    title = db.Column(db.String(300))
    description = db.Column(db.Text)
    creation_date = db.Column(db.DateTime)  # When document was created in Epic
    document_date = db.Column(db.Date)  # Actual date from FHIR resource (preferred for screening logic)
    author_name = db.Column(db.String(200))  # Document author from Epic
    
    # Content handling
    content_url = db.Column(db.Text)  # Epic Binary resource URL for document content
    content_type = db.Column(db.String(100))  # MIME type (application/pdf, text/plain, etc.)
    content_size = db.Column(db.Integer)  # Size in bytes
    content_hash = db.Column(db.String(64))  # SHA-256 hash of content for change detection
    
    # Local processing status
    is_processed = db.Column(db.Boolean, default=False)  # Has been processed by screening engine
    processing_status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    processing_error = db.Column(db.Text)  # Error message if processing failed
    ocr_text = db.Column(db.Text)  # Extracted text content from OCR
    relevance_score = db.Column(db.Float)  # Relevance score for screening (0.0-1.0)
    
    # System fields
    last_accessed = db.Column(db.DateTime)  # Last time document was accessed from Epic
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = db.relationship('Organization', backref='fhir_documents')
    screenings = db.relationship('Screening', secondary=screening_fhir_documents, back_populates='fhir_documents')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_fhir_doc_epic_id', 'epic_document_id'),
        db.Index('idx_fhir_doc_patient', 'patient_id'),
        db.Index('idx_fhir_doc_type', 'document_type_code'),
        db.Index('idx_fhir_doc_processing', 'processing_status'),
        db.UniqueConstraint('epic_document_id', 'org_id', name='unique_epic_doc_per_org'),
    )
    
    def update_from_fhir(self, fhir_document_reference):
        """Update document metadata from FHIR DocumentReference resource"""
        import json
        from hashlib import sha256
        
        if isinstance(fhir_document_reference, dict):
            self.fhir_document_reference = json.dumps(fhir_document_reference)
            
            # Extract document type information
            if 'type' in fhir_document_reference and 'coding' in fhir_document_reference['type']:
                type_coding = fhir_document_reference['type']['coding'][0]
                self.document_type_code = type_coding.get('code')
                self.document_type_display = type_coding.get('display')
            
            # Extract title and description
            self.title = fhir_document_reference.get('description')
            
            # Extract creation date
            if 'date' in fhir_document_reference:
                try:
                    self.creation_date = datetime.fromisoformat(fhir_document_reference['date'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            
            # Extract author information
            if 'author' in fhir_document_reference and fhir_document_reference['author']:
                author = fhir_document_reference['author'][0]
                if 'display' in author:
                    self.author_name = author['display']
            
            # Extract content information
            if 'content' in fhir_document_reference and fhir_document_reference['content']:
                content = fhir_document_reference['content'][0]
                attachment = content.get('attachment', {})
                
                self.content_url = attachment.get('url')
                self.content_type = attachment.get('contentType')
                self.content_size = attachment.get('size')
                
                # Generate content hash if data is available
                if 'data' in attachment:
                    import base64
                    content_bytes = base64.b64decode(attachment['data'])
                    self.content_hash = sha256(content_bytes).hexdigest()
        
        self.updated_at = datetime.utcnow()
    
    def is_relevant_for_screening(self, screening_type):
        """Check if document is relevant for a specific screening type"""
        if not screening_type or not self.document_type_code:
            return False
        
        # Get FHIR document type mappings for screening type
        try:
            doc_type_mappings = screening_type.get_fhir_document_type_mappings()
            if not doc_type_mappings:
                return False
            
            # Check if document type matches any mapping
            return self.document_type_code in doc_type_mappings
        except AttributeError:
            # Fallback: simple keyword matching if method doesn't exist
            if hasattr(screening_type, 'keywords_list') and screening_type.keywords_list:
                return any(keyword.lower() in (self.document_type_display or '').lower() 
                          for keyword in screening_type.keywords_list)
            return False
    
    def mark_processed(self, status='completed', error=None, ocr_text=None, relevance_score=None):
        """Mark document as processed with results"""
        self.is_processed = True
        self.processing_status = status
        self.processing_error = error
        if ocr_text:
            self.ocr_text = ocr_text
        if relevance_score is not None:
            self.relevance_score = relevance_score
        self.updated_at = datetime.utcnow()
    
    @property
    def is_pdf(self):
        """Check if document is a PDF"""
        return self.content_type == 'application/pdf'
    
    @property
    def display_name(self):
        """Get display name for document"""
        return self.title or f"Document {self.epic_document_id}"
    
    def __repr__(self):
        return f'<FHIRDocument {self.epic_document_id} - {self.document_type_display or "Unknown Type"}>'


class AsyncJob(db.Model):
    """Model for tracking asynchronous background jobs"""
    __tablename__ = 'async_jobs'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(100), nullable=False, unique=True)  # RQ job ID
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Job details
    job_type = db.Column(db.String(50), nullable=False)  # batch_patient_sync, prep_sheet_generation, etc.
    status = db.Column(db.String(20), default='queued')  # queued, running, completed, failed, cancelled
    priority = db.Column(db.String(20), default='normal')  # normal, high
    
    # Progress tracking
    total_items = db.Column(db.Integer, default=0)
    completed_items = db.Column(db.Integer, default=0)
    failed_items = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Job metadata
    job_data = db.Column(db.JSON)  # Input parameters and metadata
    result_data = db.Column(db.JSON)  # Job results and output
    error_message = db.Column(db.Text)  # Error details if failed
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    organization = db.relationship('Organization', backref='async_jobs')
    user = db.relationship('User', backref='initiated_jobs')
    
    @property
    def duration_seconds(self):
        """Calculate job duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0
    
    @property
    def is_active(self):
        """Check if job is currently active"""
        return self.status in ['queued', 'running']
    
    def update_progress(self, completed: int, failed: int = 0, error_message: Optional[str] = None):
        """Update job progress"""
        self.completed_items = completed
        self.failed_items = failed
        if self.total_items > 0:
            self.progress_percentage = (completed + failed) / self.total_items * 100
        if error_message:
            self.error_message = error_message
        db.session.commit()
    
    def mark_started(self):
        """Mark job as started"""
        self.status = 'running'
        self.started_at = datetime.utcnow()
        db.session.commit()
    
    def mark_completed(self, result_data: Optional[dict] = None):
        """Mark job as completed"""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.progress_percentage = 100.0
        if result_data:
            self.result_data = result_data
        db.session.commit()
    
    def mark_failed(self, error_message: str):
        """Mark job as failed"""
        self.status = 'failed'
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        db.session.commit()
    
    def __repr__(self):
        return f'<AsyncJob {self.job_type} - {self.status}>'


class FHIRApiCall(db.Model):
    """Model for tracking FHIR API calls for rate limiting and audit"""
    __tablename__ = 'fhir_api_calls'
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # API call details
    endpoint = db.Column(db.String(200), nullable=False)  # FHIR endpoint called
    method = db.Column(db.String(10), nullable=False)  # GET, POST, PUT, DELETE
    resource_type = db.Column(db.String(50))  # Patient, Observation, DocumentReference, etc.
    resource_id = db.Column(db.String(100))  # Specific resource ID if applicable
    
    # Request metadata
    request_params = db.Column(db.JSON)  # Query parameters
    response_status = db.Column(db.Integer)  # HTTP response status
    response_time_ms = db.Column(db.Integer)  # Response time in milliseconds
    
    # Patient context (for audit)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))  # Local patient ID
    epic_patient_id = db.Column(db.String(100))  # Epic patient ID from API call
    
    # Timestamps
    called_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    organization = db.relationship('Organization')
    user = db.relationship('User')
    patient = db.relationship('Patient')
    
    @classmethod
    def get_hourly_call_count(cls, org_id: int, hour_offset: int = 0) -> int:
        """Get FHIR API call count for specific hour"""
        from sqlalchemy import func
        
        target_hour = datetime.utcnow() - timedelta(hours=hour_offset)
        start_time = target_hour.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        return db.session.query(func.count(cls.id)).filter(
            cls.org_id == org_id,
            cls.called_at >= start_time,
            cls.called_at < end_time
        ).scalar() or 0
    
    @classmethod
    def log_api_call(cls, org_id: int, endpoint: str, method: str, 
                    user_id: Optional[int] = None, resource_type: Optional[str] = None, 
                    resource_id: Optional[str] = None, epic_patient_id: Optional[str] = None,
                    response_status: Optional[int] = None, response_time_ms: Optional[int] = None,
                    request_params: Optional[dict] = None):
        """Log an API call for audit and rate limiting"""
        api_call = cls(
            org_id=org_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            resource_type=resource_type,
            resource_id=resource_id,
            epic_patient_id=epic_patient_id,
            response_status=response_status,
            response_time_ms=response_time_ms,
            request_params=request_params
        )
        
        db.session.add(api_call)
        db.session.commit()
        return api_call
    
    def __repr__(self):
        return f'<FHIRApiCall {self.method} {self.endpoint}>'

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
    """Patient appointments with Epic FHIR integration"""
    __tablename__ = 'appointment'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_type = db.Column(db.String(100))
    provider = db.Column(db.String(100))
    status = db.Column(db.String(20), default='scheduled')
    notes = db.Column(db.Text)
    
    # Epic FHIR integration fields
    epic_appointment_id = db.Column(db.String(100))
    fhir_appointment_resource = db.Column(db.Text)
    last_fhir_sync = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = db.relationship('Organization', backref='appointments')
    
    # Indexes for performance and uniqueness
    __table_args__ = (
        db.Index('idx_appointment_date', 'appointment_date'),
        db.Index('idx_appointment_patient', 'patient_id'),
        db.Index('idx_appointment_epic_id', 'epic_appointment_id'),
        db.UniqueConstraint('epic_appointment_id', 'org_id', name='unique_epic_appointment_per_org'),
    )

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
    """Prep sheet configuration - organization-scoped for multi-tenancy"""
    __tablename__ = 'prep_sheet_settings'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)
    labs_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    imaging_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    consults_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    hospital_cutoff_months = db.Column(db.Integer, default=12)  # 0 = To Last Appointment
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = db.relationship('Organization', backref='prep_sheet_settings')

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
    def is_global(self):
        """Check if preset is globally accessible"""
        return self.preset_scope == 'global'

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

    def check_application_conflicts(self):
        """Check for conflicts when applying this preset"""
        conflicts = {
            'existing_types': [],
            'modified_types': [],
            'missing_types': [],
            'has_conflicts': False
        }
        
        # Get the target organization from the user making the request
        from flask_login import current_user
        target_org_id = current_user.org_id
        
        try:
            screening_types_data = self.get_screening_types()
            
            # Handle case where no screening types in preset
            if not screening_types_data:
                return conflicts
            
            for st_data in screening_types_data:
                existing = ScreeningType.query.filter_by(
                    name=st_data['name'],
                    org_id=target_org_id
                ).first()
                
                if existing:
                    conflicts['existing_types'].append({
                        'name': existing.name,
                        'id': existing.id,
                        'modified_date': existing.updated_at.strftime('%Y-%m-%d %H:%M') if existing.updated_at else 'Unknown'
                    })
                    
                    # Check if existing type differs from preset
                    is_modified = False
                    
                    try:
                        # Compare keywords
                        preset_keywords = set(st_data.get('keywords', []))
                        existing_keywords = set(existing.keywords_list)
                        
                        # Handle different field name formats for compatibility
                        preset_genders = st_data.get('eligible_genders') or st_data.get('gender_criteria', 'both')
                        
                        # Handle frequency - check for both formats
                        if 'frequency_years' in st_data:
                            preset_freq = float(st_data.get('frequency_years', 1.0))
                        else:
                            # Convert from frequency_number/frequency_unit format
                            freq_number = st_data.get('frequency_number', 1)
                            freq_unit = st_data.get('frequency_unit', 'years')
                            if freq_unit == 'months':
                                preset_freq = float(freq_number) / 12.0
                            elif freq_unit == 'weeks':
                                preset_freq = float(freq_number) / 52.0
                            else:  # years
                                preset_freq = float(freq_number)
                        
                        # Handle different age field names
                        preset_min_age = st_data.get('min_age') or st_data.get('age_min')
                        preset_max_age = st_data.get('max_age') or st_data.get('age_max')
                        
                        # Check for actual differences
                        if (preset_keywords != existing_keywords or
                            preset_genders != (existing.eligible_genders or 'both') or
                            abs(preset_freq - (existing.frequency_years or 1.0)) > 0.001 or  # Float comparison
                            preset_min_age != existing.min_age or
                            preset_max_age != existing.max_age):
                            is_modified = True
                            
                        # Also compare trigger conditions
                        preset_conditions = set(st_data.get('trigger_conditions', []))
                        existing_conditions = set(existing.trigger_conditions_list)
                        
                        if preset_conditions != existing_conditions:
                            is_modified = True
                            
                        if is_modified:
                            conflicts['modified_types'].append({
                                'name': existing.name,
                                'id': existing.id,
                                'modified_date': existing.updated_at.strftime('%Y-%m-%d %H:%M') if existing.updated_at else 'Unknown'
                            })
                            
                    except Exception as detail_error:
                        logger.warning(f"Error comparing screening type {st_data.get('name', 'Unknown')}: {str(detail_error)}")
                        # If we can't compare properly, treat as potential conflict to be safe
                        conflicts['modified_types'].append({
                            'name': existing.name,
                            'id': existing.id,
                            'modified_date': existing.updated_at.strftime('%Y-%m-%d %H:%M') if existing.updated_at else 'Unknown'
                        })
                else:
                    # This screening type is missing from the organization
                    conflicts['missing_types'].append({
                        'name': st_data['name']
                    })
            
            # Only flag conflicts for types that would be modified, not missing ones
            conflicts['has_conflicts'] = len(conflicts['modified_types']) > 0
            return conflicts
            
        except Exception as e:
            logger.error(f"Error checking preset conflicts: {str(e)}")
            # Return safe default that allows application to proceed for empty orgs
            return {
                'existing_types': [],
                'modified_types': [],
                'missing_types': [{'name': st_data.get('name', 'Unknown')} for st_data in self.get_screening_types()],
                'has_conflicts': False,
                'error': f'Could not verify conflicts: {str(e)}'
            }

    def import_to_screening_types(self, overwrite_existing=False, replace_entire_set=False, created_by=None):
        """Import this preset's screening types to the database"""
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        # Get the target organization from the user making the request
        from flask_login import current_user
        target_org_id = current_user.org_id

        if not target_org_id:
            return {
                'success': False,
                'error': 'No organization ID found for current user',
                'imported_count': 0,
                'updated_count': 0,
                'skipped_count': 0,
                'errors': ['User must belong to an organization']
            }

        try:
            screening_types_data = self.get_screening_types()
            
            # Handle case where preset has no screening types
            if not screening_types_data:
                return {
                    'success': True,
                    'imported_count': 0,
                    'updated_count': 0,
                    'skipped_count': 0,
                    'errors': ['No screening types found in preset']
                }
            
            # If replace_entire_set is True, delete all existing screening types first
            if replace_entire_set:
                try:
                    existing_types = ScreeningType.query.filter_by(org_id=target_org_id).all()
                    deleted_count = len(existing_types)
                    
                    # For each screening type, delete all associated records first to avoid orphans
                    for existing_type in existing_types:
                        # Get all screenings for this type
                        screenings = Screening.query.filter_by(screening_type_id=existing_type.id).all()
                        
                        # Delete all related records for each screening
                        for screening in screenings:
                            with db.session.no_autoflush:
                                # Delete ScreeningDocumentMatch records
                                ScreeningDocumentMatch.query.filter_by(screening_id=screening.id).delete(synchronize_session='fetch')
                                
                                # Delete DismissedDocumentMatch records  
                                DismissedDocumentMatch.query.filter_by(screening_id=screening.id).delete(synchronize_session='fetch')
                                
                                # Clear FHIR document associations
                                screening.fhir_documents.clear()
                            
                            # Delete the screening
                            db.session.delete(screening)
                        
                        # Now safe to delete the screening type
                        db.session.delete(existing_type)
                    
                    logger.info(f"Deleted {deleted_count} existing screening types and all associated screenings for complete replacement")
                    
                    # Commit the deletions before importing new ones to prevent rollback issues
                    db.session.commit()
                    logger.info("Committed deletion of existing screening types")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error deleting existing screening types for replacement: {str(e)}")
                    return {
                        'success': False,
                        'error': f'Failed to clear existing screening types: {str(e)}',
                        'imported_count': 0,
                        'updated_count': 0,
                        'skipped_count': 0,
                        'errors': [f'Failed to clear existing screening types: {str(e)}']
                    }
            
            # Helper function to safely convert frequency data
            def get_frequency_years(data):
                # Handle different frequency formats from preset data
                freq_years = data.get('frequency_years')
                if freq_years is not None:
                    try:
                        return float(freq_years)
                    except (ValueError, TypeError):
                        pass
                
                freq_number = data.get('frequency_number', 1)
                freq_unit = data.get('frequency_unit', 'years')
                
                try:
                    freq_number = float(freq_number)
                except (ValueError, TypeError):
                    freq_number = 1.0
                
                if freq_unit == 'months':
                    return freq_number / 12.0
                elif freq_unit == 'weeks':
                    return freq_number / 52.0
                else:  # assume years
                    return freq_number

            # Helper function to safely get integer age values
            def get_age_value(data, field_names):
                for field_name in field_names:
                    value = data.get(field_name)
                    if value is not None:
                        try:
                            return int(value)
                        except (ValueError, TypeError):
                            continue
                return None
            
            # Helper function to normalize gender values to match form standards
            def normalize_gender(data):
                """
                Normalize gender values to match ScreeningTypeForm standards:
                - 'both' (default for null/empty)
                - 'M' (Male Only)
                - 'F' (Female Only)
                """
                # Check multiple possible field names used in different preset formats
                gender = (data.get('eligible_genders') or 
                         data.get('gender_criteria') or 
                         data.get('gender_restriction') or 
                         'both')
                
                if not gender or gender == '':
                    return 'both'
                
                # Normalize to uppercase for comparison
                gender_upper = str(gender).upper().strip()
                
                # Handle various female formats
                if gender_upper in ('F', 'FEMALE', 'FEM', 'WOMEN', 'WOMAN'):
                    return 'F'
                
                # Handle various male formats
                if gender_upper in ('M', 'MALE', 'MEN', 'MAN'):
                    return 'M'
                
                # Default to both for any other value
                return 'both'
            
            for st_data in screening_types_data:
                try:
                    # Validate required fields
                    screening_name = st_data.get('name')
                    if not screening_name or not screening_name.strip():
                        errors.append("Screening type missing required 'name' field")
                        continue
                    
                    screening_name = screening_name.strip()
                    logger.info(f"Processing screening type: '{screening_name}' for org {target_org_id}")
                    
                    # VARIANT SUPPORT: Check if EXACT duplicate exists (same name AND same criteria)
                    # Only skip if the screening type is IDENTICAL in every way
                    # This allows variants (same name, different criteria) to be created
                    keywords_json = json.dumps(st_data.get('keywords', []))
                    trigger_conditions_json = json.dumps(st_data.get('trigger_conditions', []))
                    eligible_genders = normalize_gender(st_data)  # Normalize to 'F', 'M', or 'both'
                    min_age = get_age_value(st_data, ['min_age', 'age_min'])
                    max_age = get_age_value(st_data, ['max_age', 'age_max'])
                    frequency_years = get_frequency_years(st_data)
                    
                    # Convert frequency_years to frequency_value and frequency_unit
                    if frequency_years:
                        frequency_months = frequency_years * 12
                        if frequency_months < 24 and frequency_months == int(frequency_months):
                            frequency_value = int(frequency_months)
                            frequency_unit = 'months'
                        elif frequency_years == int(frequency_years):
                            frequency_value = int(frequency_years)
                            frequency_unit = 'years'
                        else:
                            frequency_value = frequency_years
                            frequency_unit = 'years'
                    else:
                        frequency_value = 1.0
                        frequency_unit = 'years'
                    
                    # When replace_entire_set is True, skip duplicate checking since we cleared everything
                    if replace_entire_set:
                        existing = None
                    else:
                        # Check for exact match: same name AND same criteria (for variant support)
                        existing = ScreeningType.query.filter_by(
                        name=screening_name,
                        org_id=target_org_id,
                        keywords=keywords_json,
                        eligible_genders=eligible_genders,
                        min_age=min_age,
                        max_age=max_age,
                        frequency_value=frequency_value,
                        frequency_unit=frequency_unit,
                        trigger_conditions=trigger_conditions_json
                    ).first()

                    if existing and not overwrite_existing:
                        logger.info(f"Skipping exact duplicate screening type: '{screening_name}' (same name and criteria)")
                        skipped_count += 1
                        continue



                    if existing and overwrite_existing:
                        # Update existing screening type (exact match found)
                        logger.info(f"Updating exact duplicate screening type: '{screening_name}'")
                        existing.keywords = keywords_json
                        existing.eligible_genders = eligible_genders
                        existing.min_age = min_age
                        existing.max_age = max_age
                        existing.frequency_value = frequency_value
                        existing.frequency_unit = frequency_unit
                        existing.trigger_conditions = trigger_conditions_json
                        existing.is_active = st_data.get('is_active', True)
                        existing.updated_at = datetime.utcnow()
                        updated_count += 1
                    else:
                        # Create new screening type in target organization (variant support enabled)
                        # Check if this is a variant (same name, different criteria exists)
                        variant_check = ScreeningType.query.filter_by(
                            name=screening_name,
                            org_id=target_org_id
                        ).first()
                        
                        if variant_check:
                            logger.info(f"Creating VARIANT of '{screening_name}' for org {target_org_id} (different criteria)")
                        else:
                            logger.info(f"Creating new screening type: '{screening_name}' for org {target_org_id}")
                            
                        new_st = ScreeningType()
                        new_st.name = screening_name
                        new_st.org_id = target_org_id  # CRITICAL: Set organization ID
                        new_st.keywords = keywords_json
                        new_st.eligible_genders = eligible_genders
                        new_st.min_age = min_age
                        new_st.max_age = max_age
                        new_st.frequency_value = frequency_value
                        new_st.frequency_unit = frequency_unit
                        new_st.trigger_conditions = trigger_conditions_json
                        new_st.is_active = st_data.get('is_active', True)
                        new_st.created_by = created_by
                        new_st.created_at = datetime.utcnow()
                        new_st.updated_at = datetime.utcnow()
                        db.session.add(new_st)
                        imported_count += 1

                except Exception as e:
                    # Rollback this individual screening type to prevent session pollution
                    db.session.rollback()
                    error_msg = f"Error processing '{st_data.get('name', 'Unknown')}': {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error processing screening type {st_data.get('name', 'Unknown')}: {str(e)}")
                    continue

            # Attempt to commit changes
            try:
                if imported_count > 0 or updated_count > 0:
                    db.session.commit()
                    logger.info(f"Successfully imported {imported_count} and updated {updated_count} screening types")
                
                return {
                    'success': True,
                    'imported_count': imported_count,
                    'updated_count': updated_count,
                    'skipped_count': skipped_count,
                    'errors': errors
                }
            except Exception as commit_error:
                db.session.rollback()
                error_msg = f"Database commit failed: {str(commit_error)}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'imported_count': 0,
                    'updated_count': 0,
                    'skipped_count': 0,
                    'errors': errors + [error_msg]
                }

        except Exception as e:
            db.session.rollback()
            error_msg = f"Failed to import screening types: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
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
        """Check if preset is pending approval"""
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
        try:
            return [alias.alias for alias in self.aliases] if self.aliases else []
        except Exception:
            return []

    def add_alias(self, alias_text, source='system', confidence=1.0):
        """Add an alias for this universal type"""
        existing = UniversalTypeAlias.query.filter_by(
            universal_type_id=self.id,
            alias=alias_text
        ).first()

        if not existing:
            alias = UniversalTypeAlias()
            alias.universal_type_id = self.id
            alias.alias = alias_text
            alias.source = source
            alias.confidence = confidence
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
        try:
            variants_list = list(self.variants) if self.variants else []
            return [v for v in variants_list if v.is_published]
        except Exception:
            return []

    @property
    def variant_count(self):
        """Total number of variants"""
        try:
            return len(list(self.variants)) if self.variants else 0
        except Exception:
            return 0

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
        from sqlalchemy.orm import sessionmaker
        universal_type = UniversalType.query.get(self.universal_type_id)
        if universal_type:
            alias = universal_type.add_alias(
                alias_text=self.label,
                source='system',
                confidence=confidence
            )
            return alias
        return None

    def __repr__(self):
        return f'<TypeLabelAssociation {self.label} -> {self.universal_type_id}>'


class DismissedDocumentMatch(db.Model):
    """Track dismissed document-screening matches to handle false positives"""
    __tablename__ = 'dismissed_document_matches'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Support both local documents and FHIR documents
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    fhir_document_id = db.Column(db.Integer, db.ForeignKey('fhir_documents.id'), nullable=True)
    
    # Screening this document was incorrectly matched to
    screening_id = db.Column(db.Integer, db.ForeignKey('screening.id'), nullable=False)
    
    # Multi-tenancy
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    
    # Audit trail
    dismissed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dismissed_at = db.Column(db.DateTime, default=datetime.utcnow)
    dismissal_reason = db.Column(db.Text)  # Optional reason for dismissal
    
    # Allow restoration
    is_active = db.Column(db.Boolean, default=True)
    restored_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    restored_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    document = db.relationship('Document', backref='dismissals')
    fhir_document = db.relationship('FHIRDocument', backref='dismissals')
    screening = db.relationship('Screening', backref='dismissed_matches')
    dismisser = db.relationship('User', foreign_keys=[dismissed_by], backref='dismissed_matches')
    restorer = db.relationship('User', foreign_keys=[restored_by], backref='restored_matches')
    organization = db.relationship('Organization', backref='dismissed_matches')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_dismissed_doc_screening', 'document_id', 'screening_id', 'is_active'),
        db.Index('idx_dismissed_fhir_screening', 'fhir_document_id', 'screening_id', 'is_active'),
        db.Index('idx_dismissed_org', 'org_id', 'is_active'),
    )
    
    def __repr__(self):
        doc_ref = f"Doc:{self.document_id}" if self.document_id else f"FHIR:{self.fhir_document_id}"
        return f'<DismissedDocumentMatch {doc_ref} -> Screening:{self.screening_id}>'


# Note: ExportRequest model removed - global preset management handled directly by root admin