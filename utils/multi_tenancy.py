"""
Multi-tenancy utilities for HealthPrepV2
Provides organization-scoped data access and security enforcement
"""
from functools import wraps
from flask import request, abort, current_app
from flask_login import current_user
from sqlalchemy import and_
from models import db, Organization, User, Patient, Screening, Document, ScreeningType, AdminLog


class OrganizationScope:
    """Utility class for enforcing organization-scoped data access"""
    
    @staticmethod
    def get_user_org_id():
        """Get the current user's organization ID"""
        if not current_user or not current_user.is_authenticated:
            return None
        return getattr(current_user, 'org_id', None)
    
    @staticmethod
    def filter_by_org(query, model_class, org_id=None):
        """Apply organization filter to a query"""
        if org_id is None:
            org_id = OrganizationScope.get_user_org_id()
        
        if org_id is None:
            return query.filter(False)  # Return empty result if no org context
        
        # Apply org filter if the model has org_id
        if hasattr(model_class, 'org_id'):
            return query.filter(model_class.org_id == org_id)
        
        return query
    
    @staticmethod
    def get_org_patients(org_id=None):
        """Get all patients for an organization"""
        org_id = org_id or OrganizationScope.get_user_org_id()
        return Patient.query.filter(Patient.org_id == org_id)
    
    @staticmethod
    def get_org_screenings(org_id=None):
        """Get all screenings for an organization"""
        org_id = org_id or OrganizationScope.get_user_org_id()
        return Screening.query.filter(Screening.org_id == org_id)
    
    @staticmethod
    def get_org_documents(org_id=None):
        """Get all documents for an organization"""
        org_id = org_id or OrganizationScope.get_user_org_id()
        return Document.query.filter(Document.org_id == org_id)
    
    @staticmethod
    def get_org_screening_types(org_id=None):
        """Get all screening types for an organization"""
        org_id = org_id or OrganizationScope.get_user_org_id()
        return ScreeningType.query.filter(ScreeningType.org_id == org_id)
    
    @staticmethod
    def get_org_users(org_id=None):
        """Get all users for an organization"""
        org_id = org_id or OrganizationScope.get_user_org_id()
        return User.query.filter(User.org_id == org_id)


def require_organization_access(org_id_param='org_id'):
    """Decorator to enforce organization access control"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                abort(401)
            
            # Get org_id from URL parameter, form data, or JSON
            requested_org_id = None
            if org_id_param in kwargs:
                requested_org_id = kwargs[org_id_param]
            elif request.method in ['POST', 'PUT', 'PATCH']:
                if request.is_json and request.json:
                    requested_org_id = request.json.get(org_id_param)
                elif request.form:
                    requested_org_id = request.form.get(org_id_param)
            
            # If no org_id specified, use user's org
            if requested_org_id is None:
                requested_org_id = current_user.org_id
            else:
                requested_org_id = int(requested_org_id)
            
            # Check if user can access this organization
            if current_user.org_id != requested_org_id:
                current_app.logger.warning(
                    f"User {current_user.id} attempted to access org {requested_org_id} "
                    f"but belongs to org {current_user.org_id}"
                )
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(required_role):
    """Decorator to enforce role-based access control"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                abort(401)
            
            if not current_user.has_role(required_role) and not current_user.is_admin_user():
                current_app.logger.warning(
                    f"User {current_user.id} with role {current_user.role} "
                    f"attempted to access {required_role}-only resource"
                )
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


class AuditLogger:
    """Enhanced audit logging with organization scope"""
    
    @staticmethod
    def log_user_action(event_type, details=None, patient_id=None, resource_type=None, 
                       resource_id=None, session_id=None):
        """Log user action with full audit context"""
        if not current_user or not current_user.is_authenticated:
            return
        
        # Get request context
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '') if request else ''
        
        # Create audit log entry
        log_entry = AdminLog()
        log_entry.event_type = event_type
        log_entry.user_id = current_user.id
        log_entry.org_id = current_user.org_id
        log_entry.patient_id = patient_id
        log_entry.resource_type = resource_type
        log_entry.resource_id = resource_id
        log_entry.action_details = details
        log_entry.ip_address = ip_address
        log_entry.session_id = session_id
        log_entry.user_agent = user_agent
        log_entry.data = {'timestamp': 'system_generated'}
        
        try:
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to log audit event: {e}")
            db.session.rollback()
    
    @staticmethod
    def log_patient_access(patient_id, action_type='view'):
        """Log patient data access for HIPAA compliance"""
        AuditLogger.log_user_action(
            event_type=f'patient_{action_type}',
            details=f'Patient {action_type} action',
            patient_id=patient_id,
            resource_type='patient',
            resource_id=patient_id
        )
    
    @staticmethod
    def log_document_access(document_id, action_type='view'):
        """Log document access for HIPAA compliance"""
        AuditLogger.log_user_action(
            event_type=f'document_{action_type}',
            details=f'Document {action_type} action',
            resource_type='document',
            resource_id=document_id
        )
    
    @staticmethod
    def log_screening_action(screening_id, action_type='view'):
        """Log screening-related actions"""
        AuditLogger.log_user_action(
            event_type=f'screening_{action_type}',
            details=f'Screening {action_type} action',
            resource_type='screening',
            resource_id=screening_id
        )


class OrganizationOnboarding:
    """Utilities for onboarding new organizations"""
    
    @staticmethod
    def create_organization(name, contact_email, admin_user_data):
        """Create a new organization with initial admin user"""
        try:
            # Create organization
            org = Organization()
            org.name = name
            org.contact_email = contact_email
            org.setup_status = 'incomplete'
            db.session.add(org)
            db.session.flush()  # Get org.id
            
            # Create admin user
            admin_user = User()
            admin_user.username = admin_user_data['username']
            admin_user.email = admin_user_data['email']
            admin_user.role = 'admin'
            admin_user.org_id = org.id
            admin_user.is_active_user = True
            admin_user.set_password(admin_user_data['password'])
            db.session.add(admin_user)
            
            # Log the creation
            db.session.commit()
            
            return org, admin_user
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create organization: {e}")
    
    @staticmethod
    def setup_epic_credentials(org_id, client_id, client_secret, fhir_url, environment='sandbox'):
        """Configure Epic FHIR credentials for an organization"""
        org = Organization.query.get(org_id)
        if not org:
            raise ValueError("Organization not found")
        
        org.epic_client_id = client_id
        org.epic_client_secret = client_secret  # Should be encrypted in production
        org.epic_fhir_url = fhir_url
        org.epic_environment = environment
        
        if org.setup_status == 'incomplete':
            org.setup_status = 'live'
        
        db.session.commit()
        return org
    
    @staticmethod
    def activate_organization(org_id):
        """Activate an organization and enable sync"""
        org = Organization.query.get(org_id)
        if not org:
            raise ValueError("Organization not found")
        
        # Validate that Epic credentials are configured
        if not org.epic_client_id or not org.epic_fhir_url:
            raise ValueError("Epic credentials must be configured before activation")
        
        org.setup_status = 'live'
        org.auto_sync_enabled = True
        
        db.session.commit()
        return org


# Session management utilities
class SessionManager:
    """Utilities for managing user sessions and security"""
    
    @staticmethod
    def check_session_timeout(user):
        """Check if user session has timed out"""
        if user.is_session_expired():
            return True
        return False
    
    @staticmethod
    def update_user_activity(user):
        """Update user's last activity timestamp"""
        user.update_activity()
        db.session.commit()
    
    @staticmethod
    def handle_failed_login(user):
        """Handle failed login attempt"""
        user.record_login_attempt(success=False)
        db.session.commit()
    
    @staticmethod
    def handle_successful_login(user):
        """Handle successful login"""
        user.record_login_attempt(success=True)
        db.session.commit()