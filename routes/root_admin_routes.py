"""
Root Admin routes - Super admin functionality for managing all organizations
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging
import functools
import uuid
from werkzeug.security import generate_password_hash

from models import User, Organization, AdminLog, log_admin_event, EpicCredentials, ScreeningPreset, Provider, UserProviderAssignment
from app import db
from app import csrf
from flask import request as flask_request

logger = logging.getLogger(__name__)

root_admin_bp = Blueprint('root_admin', __name__)

def root_admin_required(f):
    """Decorator to require root admin role"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_root_admin_user():
            flash('Root admin access required', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@root_admin_bp.route('/dashboard')
@login_required
@root_admin_required
def dashboard():
    """Root admin dashboard - manage all organizations"""
    try:
        # Get all organizations
        organizations = Organization.query.order_by(Organization.created_at.desc()).all()
        
        # Get pending organizations for approval
        pending_orgs = Organization.query.filter_by(onboarding_status='pending_approval').order_by(Organization.created_at.desc()).all()

        # Get system-wide statistics
        total_orgs = len(organizations)
        active_orgs = sum(1 for org in organizations if org.is_active)
        trial_orgs = sum(1 for org in organizations if org.setup_status == 'trial')
        pending_orgs_count = len(pending_orgs)

        # Get user statistics across all organizations
        total_users = User.query.filter(User.org_id != None).count()
        admin_users = User.query.filter(User.role == 'admin').count()

        # Get recent activities across all organizations
        recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(20).all()

        # Get preset statistics
        total_presets = ScreeningPreset.query.count()
        global_presets = ScreeningPreset.query.filter_by(preset_scope='global').count()

        stats = {
            'total_organizations': total_orgs,
            'active_organizations': active_orgs,
            'trial_organizations': trial_orgs,
            'pending_organizations': pending_orgs_count,
            'total_users': total_users,
            'admin_users': admin_users,
            'total_presets': total_presets,
            'global_presets': global_presets
        }

        return render_template('root_admin/dashboard.html', 
                             organizations=organizations,
                             pending_orgs=pending_orgs,
                             stats=stats,
                             recent_logs=recent_logs)

    except Exception as e:
        logger.error(f"Error in root admin dashboard: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/presets')
@login_required
@root_admin_required
def presets():
    """Root admin presets management page"""
    try:
        # Get all presets from all organizations
        all_presets = ScreeningPreset.query.order_by(ScreeningPreset.created_at.desc()).all()

        # Get global presets - check both preset_scope='global' AND shared=True for compatibility
        global_presets = ScreeningPreset.query.filter(
            (ScreeningPreset.preset_scope == 'global') | 
            (ScreeningPreset.shared == True)
        ).order_by(ScreeningPreset.updated_at.desc()).all()

        # Organize presets by organization for better display
        org_presets = {}
        for preset in all_presets:
            if preset.preset_scope != 'global':  # Don't duplicate global presets in org sections
                org_name = preset.organization.name if preset.organization else 'Unknown Organization'
                if org_name not in org_presets:
                    org_presets[org_name] = []
                org_presets[org_name].append(preset)

        # Get statistics
        stats = {
            'total_presets': len(all_presets),
            'global_presets': len(global_presets),
            'org_presets': sum(len(presets) for presets in org_presets.values()),
            'organizations_with_presets': len(org_presets)
        }

        return render_template('root_admin/presets.html', 
                             global_presets=global_presets,
                             org_presets=org_presets,
                             stats=stats)

    except Exception as e:
        logger.error(f"Error loading root admin presets: {str(e)}")
        flash('Error loading presets', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/presets/<int:preset_id>/make-global', methods=['POST'])
@login_required
@root_admin_required
def make_preset_global(preset_id):
    """Make a preset globally available to all organizations"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        # Store original org info before making it global
        original_org_id = preset.org_id
        original_org_name = preset.organization.name if preset.organization else 'System'
        original_creator = preset.creator.username if preset.creator else 'System'

        # Preserve original information in metadata
        if not preset.preset_metadata:
            preset.preset_metadata = {}

        preset.preset_metadata.update({
            'original_org_id': original_org_id,
            'original_org_name': original_org_name,
            'original_creator_username': original_creator,
            'made_global_at': datetime.utcnow().isoformat(),
            'made_global_by': current_user.username
        })

        # Make preset global
        preset.shared = True
        preset.preset_scope = 'global'
        preset.org_id = None  # Make it available to all organizations

        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='preset_made_global',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset.name,
                'original_org': original_org_name,
                'description': f'Made preset "{preset.name}" globally available'
            }
        )

        flash(f'Preset "{preset.name}" is now globally available to all organizations', 'success')
        return redirect(url_for('root_admin.presets'))

    except Exception as e:
        logger.error(f"Error making preset global: {str(e)}")
        flash('Error making preset global', 'error')
        return redirect(url_for('root_admin.presets'))

@root_admin_bp.route('/presets/<int:preset_id>/remove-global', methods=['POST'])
@login_required
@root_admin_required
def remove_global_preset(preset_id):
    """Remove global availability from a preset"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        # Remove global status and assign back to original organization
        # Note: We need to handle org assignment properly
        if not preset.organization and preset.creator and preset.creator.org_id:
            preset.org_id = preset.creator.org_id

        preset.shared = False
        preset.preset_scope = 'organization'

        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='preset_global_removed',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset.name,
                'description': f'Removed global availability from preset "{preset.name}"'
            }
        )

        flash(f'Preset "{preset.name}" is no longer globally available', 'success')
        return redirect(url_for('root_admin.presets'))

    except Exception as e:
        logger.error(f"Error removing global preset: {str(e)}")
        flash('Error removing global preset', 'error')
        return redirect(url_for('root_admin.presets'))

@root_admin_bp.route('/presets/<int:preset_id>/delete', methods=['POST'])
@login_required
@root_admin_required
def delete_universal_preset(preset_id):
    """Delete a universal preset completely"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)
        preset_name = preset.name

        # Log the action before deletion
        log_admin_event(
            event_type='universal_preset_deleted',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset_name,
                'description': f'Deleted universal preset "{preset_name}"'
            }
        )

        # Delete the preset
        db.session.delete(preset)
        db.session.commit()

        flash(f'Universal preset "{preset_name}" has been deleted', 'success')
        return redirect(url_for('root_admin.presets'))

    except Exception as e:
        logger.error(f"Error deleting universal preset: {str(e)}")
        flash('Error deleting preset', 'error')
        return redirect(url_for('root_admin.presets'))

@root_admin_bp.route('/presets/<int:preset_id>/view')
@login_required
@root_admin_required
def view_preset(preset_id):
    """View detailed preset information for root admin review"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        # Get detailed screening type information
        screening_types = []
        screening_data_list = preset.get_screening_types()

        if screening_data_list:
            for st_data in screening_data_list:
                # Handle different data formats
                screening_types.append({
                    'name': st_data.get('name', 'Unknown'),
                    'description': st_data.get('description', ''),
                    'keywords': st_data.get('keywords', []),
                    'trigger_conditions': st_data.get('trigger_conditions', []),
                    'eligible_genders': st_data.get('gender_criteria', st_data.get('eligible_genders', 'both')),
                    'min_age': st_data.get('age_min', st_data.get('min_age')),
                    'max_age': st_data.get('age_max', st_data.get('max_age')),
                    'frequency_years': st_data.get('frequency_years'),
                    'frequency_months': st_data.get('frequency_months'),
                    'frequency_number': st_data.get('frequency_number'),
                    'frequency_unit': st_data.get('frequency_unit'),
                    'variants': st_data.get('variants', [])
                })

        # Get organization context
        org_context = {
            'name': preset.organization.name if preset.organization else 'System',
            'setup_status': preset.organization.setup_status if preset.organization else 'active',
            'user_count': preset.organization.user_count if preset.organization else 0,
            'created_at': preset.organization.created_at if preset.organization else None
        }

        # Get creator information
        creator_info = {
            'username': preset.creator.username if preset.creator else 'System',
            'role': preset.creator.role if preset.creator else 'system',
            'email': preset.creator.email if preset.creator else None
        }

        return render_template('root_admin/view_preset.html',
                             preset=preset,
                             screening_types=screening_types,
                             org_context=org_context,
                             creator_info=creator_info)

    except Exception as e:
        logger.error(f"Error viewing preset {preset_id}: {str(e)}")
        flash('Error loading preset details', 'error')
        return redirect(url_for('root_admin.presets'))

@root_admin_bp.route('/presets')
@login_required
@root_admin_required
def manage_presets():
    """Root admin preset management"""
    try:
        # Get all presets for global management
        pending_presets = ScreeningPreset.query.filter(
            db.func.json_extract(ScreeningPreset.preset_metadata, '$.approval_status') == 'pending'
        ).order_by(ScreeningPreset.updated_at.desc()).all()

        global_presets = ScreeningPreset.query.filter_by(shared=True).order_by(
            ScreeningPreset.updated_at.desc()
        ).all()

        organization_presets = ScreeningPreset.query.filter(
            ScreeningPreset.shared == False,
            ScreeningPreset.org_id != None
        ).order_by(ScreeningPreset.updated_at.desc()).limit(20).all()

        return render_template('root_admin/presets.html',
                             pending_presets=pending_presets,
                             global_presets=global_presets,
                             organization_presets=organization_presets)

    except Exception as e:
        logger.error(f"Error in root admin preset management: {str(e)}")
        flash('Error loading preset management', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/presets/<int:preset_id>/approve', methods=['POST'])
@login_required
@root_admin_required
def approve_preset(preset_id):
    """Approve preset for global sharing"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        if not preset.is_pending_approval():
            flash('This preset is not pending approval', 'error')
            return redirect(url_for('root_admin.manage_presets'))

        # Approve the preset
        preset.approve_for_global_sharing(current_user.id)
        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='approve_preset_global',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'preset_name': preset.name,
                'preset_id': preset_id,
                'source_org_id': preset.preset_metadata.get('source_org_id') if preset.preset_metadata else None,
                'description': f'Approved preset "{preset.name}" for global sharing'
            }
        )

        flash(f'Preset "{preset.name}" approved for global sharing', 'success')
        return redirect(url_for('root_admin.manage_presets'))

    except Exception as e:
        logger.error(f"Error approving preset: {str(e)}")
        flash('Error approving preset', 'error')
        return redirect(url_for('root_admin.manage_presets'))

@root_admin_bp.route('/presets/<int:preset_id>/reject', methods=['POST'])
@login_required
@root_admin_required
def reject_preset(preset_id):
    """Reject preset for global sharing"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)
        reason = request.form.get('rejection_reason', '').strip()

        if not preset.is_pending_approval():
            flash('This preset is not pending approval', 'error')
            return redirect(url_for('root_admin.manage_presets'))

        # Reject the preset
        preset.reject_global_approval(current_user.id, reason)
        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='reject_preset_global',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'preset_name': preset.name,
                'preset_id': preset_id,
                'rejection_reason': reason,
                'source_org_id': preset.preset_metadata.get('source_org_id') if preset.preset_metadata else None,
                'description': f'Rejected preset "{preset.name}" for global sharing: {reason}'
            }
        )

        flash(f'Preset "{preset.name}" rejected for global sharing', 'success')
        return redirect(url_for('root_admin.manage_presets'))

    except Exception as e:
        logger.error(f"Error rejecting preset: {str(e)}")
        flash('Error rejecting preset', 'error')
        return redirect(url_for('root_admin.manage_presets'))

@root_admin_bp.route('/presets/<int:preset_id>/view')
@login_required
@root_admin_required
def view_preset_details(preset_id):
    """View detailed preset information for approval"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        # Get organization context
        organization = None
        if preset.org_id:
            organization = Organization.query.get(preset.org_id)

        # Get creator information
        creator = None
        if preset.created_by:
            creator = User.query.get(preset.created_by)

        return render_template('root_admin/preset_details.html',
                             preset=preset,
                             organization=organization,
                             creator=creator)

    except Exception as e:
        logger.error(f"Error viewing preset details: {str(e)}")
        flash('Error loading preset details', 'error')
        return redirect(url_for('root_admin.manage_presets'))

@root_admin_bp.route('/organizations')
@login_required
@root_admin_required
def organizations():
    """List all organizations with filtering and pagination"""
    try:
        # Get filter parameter
        status_filter = request.args.get('status', 'all')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Build query based on filter
        query = Organization.query
        
        if status_filter == 'pending':
            query = query.filter(Organization.onboarding_status == 'pending_approval')
        elif status_filter == 'active':
            # Active includes both 'live' and legacy 'trial' organizations
            query = query.filter(
                db.or_(
                    Organization.setup_status == 'live',
                    Organization.setup_status == 'trial'  # Legacy trial orgs are now treated as active
                )
            )
        elif status_filter == 'suspended':
            query = query.filter(Organization.setup_status == 'suspended')
        
        # Paginate results
        pagination = query.order_by(Organization.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('root_admin/organizations.html', 
                             organizations=pagination.items,
                             pagination=pagination,
                             status_filter=status_filter)
    except Exception as e:
        logger.error(f"Error loading organizations: {str(e)}")
        flash('Error loading organizations', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/organizations/create', methods=['GET', 'POST'])
@login_required
@root_admin_required
def create_organization():
    """Manually create organization for enterprise/custom billing"""
    from utils.onboarding_helpers import (
        generate_username_from_email,
        create_password_reset_token,
        get_password_reset_expiry,
        generate_dummy_password_hash
    )
    from services.email_service import EmailService
    from flask import url_for as flask_url_for
    
    if request.method == 'GET':
        return render_template('root_admin/create_organization.html')
    
    try:
        # Collect organization information
        org_name = request.form.get('org_name', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        site = request.form.get('site', '').strip()
        specialty = request.form.get('specialty', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        billing_email = request.form.get('billing_email', '').strip() or contact_email
        notes = request.form.get('notes', '').strip()
        
        # Validate required fields
        if not org_name or not contact_email:
            flash('Organization name and admin email are required', 'error')
            return render_template('root_admin/create_organization.html')
        
        # Check if organization name already exists
        existing_org = Organization.query.filter_by(name=org_name).first()
        if existing_org:
            flash('An organization with this name already exists', 'error')
            return render_template('root_admin/create_organization.html')
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=contact_email).first()
        if existing_user:
            flash('This email is already registered', 'error')
            return render_template('root_admin/create_organization.html')
        
        # Get Epic and system settings from form
        epic_client_id = request.form.get('epic_client_id', '').strip()
        epic_client_secret = request.form.get('epic_client_secret', '').strip()
        epic_fhir_url = request.form.get('epic_fhir_url', '').strip()
        epic_environment = request.form.get('epic_environment', 'sandbox')
        max_users = request.form.get('max_users', 10, type=int)
        display_name = request.form.get('display_name', '').strip()
        custom_presets_enabled = request.form.get('custom_presets_enabled') == 'on'
        auto_sync_enabled = request.form.get('auto_sync_enabled') == 'on'
        notes = request.form.get('notes', '').strip()
        
        # Epic credentials: all or nothing - if any provided, all must be provided
        epic_fields_provided = [bool(epic_client_id), bool(epic_client_secret), bool(epic_fhir_url)]
        if any(epic_fields_provided) and not all(epic_fields_provided):
            flash('All Epic FHIR credentials (Client ID, Client Secret, and FHIR URL) must be provided together', 'error')
            return render_template('root_admin/create_organization.html')
        
        # Validate Epic FHIR URL if provided
        if epic_fhir_url:
            # Check URL format
            if not epic_fhir_url.startswith(('http://', 'https://')) or len(epic_fhir_url.split('://')) < 2:
                flash('Invalid Epic FHIR URL format. Must be a valid URL starting with http:// or https://', 'error')
                return render_template('root_admin/create_organization.html')
            
            # Production organizations cannot use sandbox URL
            sandbox_url = 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
            if epic_environment == 'production' and epic_fhir_url == sandbox_url:
                flash('Production organizations cannot use the sandbox FHIR URL. Please provide your organization\'s unique Epic FHIR endpoint.', 'error')
                return render_template('root_admin/create_organization.html')
        
        # Create organization with manual billing
        org = Organization(
            name=org_name,
            display_name=display_name or org_name,
            site=site,
            specialty=specialty,
            address=address,
            phone=phone,
            contact_email=contact_email,
            billing_email=billing_email,
            creation_method='manual',
            setup_status='incomplete',
            onboarding_status='pending_approval',
            subscription_status='manual_billing',
            max_users=max_users,
            custom_presets_enabled=custom_presets_enabled,
            auto_sync_enabled=auto_sync_enabled,
            epic_client_id=epic_client_id or None,
            epic_fhir_url=epic_fhir_url or None,
            epic_environment=epic_environment
        )
        
        # Set encrypted secret if provided
        if epic_client_secret:
            org.epic_client_secret = epic_client_secret
        
        db.session.add(org)
        db.session.flush()
        
        # Generate admin user credentials
        username = generate_username_from_email(contact_email)
        
        # Create admin user
        admin_user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_admin=True,
            org_id=org.id,
            is_temp_password=True,
            is_active_user=True,
            email_verified=False,
            password_hash=generate_dummy_password_hash()  # Dummy hash until user sets real password via reset link
        )
        
        db.session.add(admin_user)
        db.session.flush()
        
        # Create a default provider for the organization (matches signup flow)
        default_provider = Provider(
            name=f"Provider - {org_name}",
            specialty=specialty or 'General Practice',
            org_id=org.id,
            is_active=True
        )
        db.session.add(default_provider)
        db.session.flush()
        
        # Create assignment linking admin to the default provider
        admin_assignment = UserProviderAssignment(
            user_id=admin_user.id,
            provider_id=default_provider.id,
            org_id=org.id,
            can_view_patients=True,
            can_edit_screenings=True,
            can_generate_prep_sheets=True,
            can_sync_epic=True
        )
        db.session.add(admin_assignment)
        
        logger.info(f"Created default provider {default_provider.id} for manual organization {org.id}")
        
        # Generate password reset token for welcome email
        reset_token = create_password_reset_token()
        admin_user.password_reset_token = reset_token
        admin_user.password_reset_expires = get_password_reset_expiry(hours=48)
        
        db.session.commit()
        
        # Seed organization with sample data for demonstration
        try:
            from scripts.seed_org_sample_data import seed_organization_data
            seed_results = seed_organization_data(org.id, default_provider.id)
            if seed_results:
                logger.info(f"Seeded sample data for new organization {org.id}: {seed_results}")
        except Exception as seed_error:
            logger.warning(f"Could not seed sample data for org {org.id}: {seed_error}")
        
        # Send welcome email with password setup link
        password_setup_url = flask_url_for('password_reset.reset_password', token=reset_token, _external=True)
        
        EmailService.send_admin_welcome_email(
            email=contact_email,
            username=username,
            org_name=org_name,
            password_setup_url=password_setup_url
        )
        
        # Log the action
        log_admin_event(
            event_type='create_manual_organization',
            user_id=current_user.id,
            org_id=0,
            ip=flask_request.remote_addr,
            data={
                'organization_name': org_name,
                'target_org_id': org.id,
                'admin_email': contact_email,
                'notes': notes,
                'description': f'Manually created organization: {org_name} (custom billing)'
            }
        )
        
        logger.info(f"Manual organization created by root admin: {org_name} (ID: {org.id})")
        
        flash(f'Organization "{org_name}" created successfully. Welcome email sent to {contact_email}.', 'success')
        flash('Organization is pending approval. Admin can configure while awaiting activation.', 'info')
        
        return redirect(url_for('root_admin.view_organization', org_id=org.id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating manual organization: {str(e)}")
        flash('Error creating organization. Please try again.', 'error')
        return render_template('root_admin/create_organization.html')

@root_admin_bp.route('/organizations/<int:org_id>')
@login_required
@root_admin_required
def view_organization(org_id):
    """View organization details"""
    try:
        org = Organization.query.get_or_404(org_id)

        # Get organization users
        users = User.query.filter_by(org_id=org_id).order_by(User.username).all()

        # Get organization statistics
        stats = {
            'total_users': len(users),
            'admin_users': sum(1 for user in users if user.is_admin_user()),
            'active_users': sum(1 for user in users if user.is_active_user),
            'epic_configured': bool(org.epic_client_id)
        }

        # Get Epic credentials
        epic_creds = EpicCredentials.query.filter_by(org_id=org_id).first()

        return render_template('root_admin/view_organization.html', 
                             organization=org,
                             users=users,
                             stats=stats,
                             epic_creds=epic_creds)

    except Exception as e:
        logger.error(f"Error viewing organization {org_id}: {str(e)}")
        flash('Error loading organization', 'error')
        return redirect(url_for('root_admin.organizations'))

@root_admin_bp.route('/organizations/<int:org_id>/edit', methods=['GET', 'POST'])
@login_required
@root_admin_required
def edit_organization(org_id):
    """Edit organization details"""
    try:
        org = Organization.query.get_or_404(org_id)

        if request.method == 'POST':
            # Don't update name - it's readonly and causes NULL constraint issues
            org.display_name = request.form.get('display_name')
            org.site = request.form.get('site')
            org.specialty = request.form.get('specialty')
            org.contact_email = request.form.get('contact_email')
            org.billing_email = request.form.get('billing_email')
            org.address = request.form.get('address')
            org.phone = request.form.get('phone')
            org.max_users = request.form.get('max_users', type=int)
            org.setup_status = request.form.get('setup_status')
            org.custom_presets_enabled = request.form.get('custom_presets_enabled') == 'on'
            org.auto_sync_enabled = request.form.get('auto_sync_enabled') == 'on'

            # Epic configuration
            org.epic_client_id = request.form.get('epic_client_id')
            org.epic_fhir_url = request.form.get('epic_fhir_url')
            org.epic_environment = request.form.get('epic_environment')

            # Only update secret if provided
            epic_secret = request.form.get('epic_client_secret')
            if epic_secret:
                org.epic_client_secret = epic_secret  # Encrypted by model

            db.session.commit()

            # Log the action (use root admin's org_id, not target org)
            log_admin_event(
                event_type='edit_organization',
                user_id=current_user.id,
                org_id=0,  # System Organization - all root admin actions
                ip=flask_request.remote_addr,
                data={
                    'organization_name': org.name,
                    'target_org_id': org_id,
                    'description': f'Updated organization: {org.name}'
                }
            )

            flash(f'Organization "{org.name}" updated successfully', 'success')
            return redirect(url_for('root_admin.view_organization', org_id=org_id))

        return render_template('root_admin/edit_organization.html', organization=org)

    except Exception as e:
        logger.error(f"Error editing organization {org_id}: {str(e)}")
        flash('Error updating organization', 'error')
        return redirect(url_for('root_admin.organizations'))

@root_admin_bp.route('/organizations/<int:org_id>/delete', methods=['POST'])
@login_required
@root_admin_required
def delete_organization(org_id):
    """Delete organization with cascade deletion of users and data cleanup"""
    try:
        from models import (AdminLog, ScreeningPreset, Patient, Screening, PrepSheetSettings,
                           ScreeningType, Document, FHIRDocument, AsyncJob, FHIRApiCall,
                           Appointment, DismissedDocumentMatch, EpicCredentials,
                           ScreeningVariant, ScreeningProtocol, Provider, UserProviderAssignment,
                           PatientCondition, ScreeningDocumentMatch)
        
        org = Organization.query.get_or_404(org_id)
        org_name = org.name
        
        # Prevent deletion of System Organization (org_id=0)
        if org_id == 0:
            return jsonify({'success': False, 'error': 'Cannot delete System Organization'}), 400
        
        # Get user count for logging
        org_users = User.query.filter_by(org_id=org_id).all()
        user_count = len(org_users)
        
        # CRITICAL: Reassign admin_logs to System Organization (org_id=0) for audit trail preservation
        # This prevents NOT NULL constraint violation and maintains HIPAA compliance
        admin_logs = AdminLog.query.filter_by(org_id=org_id).all()
        for log in admin_logs:
            log.org_id = 0  # Reassign to System Organization context
            log.action_details = f"[ORG DELETED: {org_name}] " + (log.action_details or "")
        
        logger.info(f"Reassigned {len(admin_logs)} audit log entries from org {org_id} to System Organization context")
        
        # CRITICAL: Clear patient_id references in admin_logs before deleting patients
        # This prevents FK constraint violation on admin_logs.patient_id_fkey
        org_patient_ids = [p.id for p in Patient.query.filter_by(org_id=org_id).all()]
        if org_patient_ids:
            patient_logs = AdminLog.query.filter(AdminLog.patient_id.in_(org_patient_ids)).all()
            for log in patient_logs:
                log.patient_id = None  # Clear patient reference
            logger.info(f"Cleared patient_id from {len(patient_logs)} admin log entries for org {org_id}")
        
        # Commit changes to persist admin_log updates before deleting patients
        # This ensures FK constraints are cleared before patient deletion
        db.session.commit()
        
        # Delete organization-scoped data (order matters for foreign key constraints)
        # 1. User-Provider assignments (before users and providers)
        UserProviderAssignment.query.filter_by(org_id=org_id).delete()
        
        # 2. Dismissed document matches (depends on screenings)
        DismissedDocumentMatch.query.filter_by(org_id=org_id).delete()
        
        # 3. Screening document matches (depends on screenings)
        screening_ids = [s.id for s in Screening.query.filter_by(org_id=org_id).all()]
        if screening_ids:
            ScreeningDocumentMatch.query.filter(ScreeningDocumentMatch.screening_id.in_(screening_ids)).delete(synchronize_session=False)
            
            # 3b. Clear screening_fhir_documents association table (depends on screenings)
            from models import screening_fhir_documents, screening_immunizations
            db.session.execute(
                screening_fhir_documents.delete().where(
                    screening_fhir_documents.c.screening_id.in_(screening_ids)
                )
            )
            
            # 3c. Clear screening_immunizations association table (depends on screenings)
            db.session.execute(
                screening_immunizations.delete().where(
                    screening_immunizations.c.screening_id.in_(screening_ids)
                )
            )
        
        # 4. Appointments
        Appointment.query.filter_by(org_id=org_id).delete()
        
        # 5. FHIR API calls
        FHIRApiCall.query.filter_by(org_id=org_id).delete()
        
        # 6. Async jobs
        AsyncJob.query.filter_by(org_id=org_id).delete()
        
        # 7. Prep sheet settings
        PrepSheetSettings.query.filter_by(org_id=org_id).delete()
        
        # 8. Screening presets (delete ONLY org-scoped presets, preserve global ones)
        # Global presets (org_id=0 or preset_scope='global') should NEVER be deleted
        # Only delete presets that belong to this specific organization
        ScreeningPreset.query.filter(
            ScreeningPreset.org_id == org_id,
            ScreeningPreset.org_id != 0,  # Never delete system org presets
            ScreeningPreset.preset_scope != 'global'  # Never delete global presets
        ).delete(synchronize_session=False)
        
        # 9. Screening variants (depends on screening types)
        ScreeningVariant.query.filter_by(org_id=org_id).delete()
        
        # 10. Screening protocols (may reference org_id - nullable)
        ScreeningProtocol.query.filter_by(org_id=org_id).delete()
        
        # 11. Screenings (depends on screening_type and patient)
        Screening.query.filter_by(org_id=org_id).delete()
        
        # 12. Screening types
        ScreeningType.query.filter_by(org_id=org_id).delete()
        
        # 13. FHIR documents
        FHIRDocument.query.filter_by(org_id=org_id).delete()
        
        # 13b. FHIR immunizations (depends on patients, must be before patients)
        from models import FHIRImmunization
        FHIRImmunization.query.filter_by(org_id=org_id).delete()
        
        # 14. Documents
        Document.query.filter_by(org_id=org_id).delete()
        
        # 15. Patient conditions (before patients)
        if org_patient_ids:
            PatientCondition.query.filter(PatientCondition.patient_id.in_(org_patient_ids)).delete(synchronize_session=False)
        
        # 16. Patients
        Patient.query.filter_by(org_id=org_id).delete()
        
        # 17. Providers (before organization)
        Provider.query.filter_by(org_id=org_id).delete()
        
        # 18. Epic credentials
        EpicCredentials.query.filter_by(org_id=org_id).delete()
        
        # 19. Delete all users in this organization
        for user in org_users:
            db.session.delete(user)
        
        # Log before deletion (this log will go to root admin org)
        log_admin_event(
            event_type='delete_organization',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'organization_name': org_name,
                'organization_id': org_id,
                'users_deleted': user_count,
                'audit_logs_preserved': len(admin_logs),
                'description': f'Deleted organization: {org_name} ({user_count} users, {len(admin_logs)} audit logs preserved)'
            }
        )
        
        # Delete organization
        db.session.delete(org)
        db.session.commit()
        
        logger.info(f"Successfully deleted organization {org_name} (ID: {org_id})")
        
        return jsonify({
            'success': True, 
            'message': f'Organization "{org_name}" and {user_count} associated user(s) deleted successfully. {len(admin_logs)} audit logs preserved.'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting organization {org_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Error deleting organization'}), 500

@root_admin_bp.route('/organizations/<int:org_id>/users')
@login_required
@root_admin_required
def organization_users(org_id):
    """View users in an organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        users = User.query.filter_by(org_id=org_id).order_by(User.username).all()

        return render_template('root_admin/organization_users.html', 
                             organization=org,
                             users=users)

    except Exception as e:
        logger.error(f"Error loading organization users: {str(e)}")
        flash('Error loading users', 'error')
        return redirect(url_for('root_admin.view_organization', org_id=org_id))

@root_admin_bp.route('/users')
@login_required
@root_admin_required
def all_users():
    """View all users across all organizations with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Get users with organization info and paginate
        pagination = db.session.query(User, Organization).join(
            Organization, User.org_id == Organization.id
        ).order_by(Organization.name, User.username).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return render_template('root_admin/all_users.html', 
                             users=pagination.items,
                             pagination=pagination)

    except Exception as e:
        logger.error(f"Error loading all users: {str(e)}")
        flash('Error loading users', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/system/logs')
@login_required
@root_admin_required
def system_logs():
    """View system-wide logs"""
    try:
        # Get filter parameters
        page = request.args.get('page', 1, type=int)
        org_id = request.args.get('org_id', type=int)
        event_type = request.args.get('event_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        # Build query
        query = AdminLog.query

        if org_id:
            query = query.filter(AdminLog.org_id == org_id)
        if event_type:
            query = query.filter(AdminLog.event_type == event_type)
        if date_from:
            try:
                from datetime import datetime
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(AdminLog.timestamp >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                from datetime import datetime
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(AdminLog.timestamp <= to_date)
            except ValueError:
                pass

        logs_pagination = query.order_by(AdminLog.timestamp.desc()).paginate(
            page=page, per_page=100, error_out=False
        )

        # Get filter options
        organizations = Organization.query.order_by(Organization.name).all()
        event_types = db.session.query(AdminLog.event_type).distinct().all()
        event_types = [event.event_type for event in event_types if event.event_type]

        return render_template('root_admin/system_logs.html',
                             logs=logs_pagination,
                             organizations=organizations,
                             event_types=event_types,
                             filters={'org_id': org_id, 'event_type': event_type, 'date_from': date_from, 'date_to': date_to})

    except Exception as e:
        logger.error(f"Error loading system logs: {str(e)}")
        flash('Error loading logs', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/logs/export')
@login_required
@root_admin_required
def export_logs():
    """Export audit logs to CSV for HIPAA compliance"""
    try:
        import csv
        from io import StringIO
        from datetime import datetime
        
        # Get filter parameters (same as system_logs view)
        org_id = request.args.get('org_id', type=int)
        event_type = request.args.get('event_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Build query
        query = AdminLog.query
        
        if org_id:
            query = query.filter(AdminLog.org_id == org_id)
        if event_type:
            query = query.filter(AdminLog.event_type == event_type)
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(AdminLog.timestamp >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(AdminLog.timestamp <= to_date)
            except ValueError:
                pass
        
        # Get all matching logs
        logs = query.order_by(AdminLog.timestamp.desc()).all()
        
        # Create CSV in memory
        si = StringIO()
        writer = csv.writer(si)
        
        # Write header
        writer.writerow([
            'Timestamp',
            'Event Type',
            'User ID',
            'Username',
            'Organization ID',
            'Organization Name',
            'IP Address',
            'Patient ID',
            'Resource Type',
            'Resource ID',
            'Action Details',
            'Event Data'
        ])
        
        # Write data rows
        for log in logs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.event_type or '',
                log.user_id or '',
                log.user.username if log.user else '',
                log.org_id or '',
                log.organization.name if log.organization else '',
                log.ip_address or '',
                log.patient_id or '',
                log.resource_type or '',
                log.resource_id or '',
                log.action_details or '',
                str(log.data) if log.data else ''
            ])
        
        # Log the export action
        log_admin_event(
            event_type='export_audit_logs',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'logs_exported': len(logs),
                'filter_org_id': org_id,
                'filter_event_type': event_type,
                'description': f'Exported {len(logs)} audit log entries to CSV'
            }
        )
        
        # Prepare response
        output = si.getvalue()
        si.close()
        
        # Generate filename with timestamp
        filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from flask import make_response
        response = make_response(output)
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv'
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting logs: {str(e)}")
        flash('Error exporting logs', 'error')
        return redirect(url_for('root_admin.system_logs'))

@root_admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@root_admin_required
def create_user():
    """Create new user for any organization"""
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            org_id = request.form.get('org_id', type=int)

            # Validate input
            if not username or not email or not password or not role or not org_id:
                flash('All fields are required', 'error')
                return render_template('root_admin/create_user.html', 
                                     organizations=Organization.query.order_by(Organization.name).all())

            # Check if username/email already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            if existing_user:
                flash('Username or email already exists', 'error')
                return render_template('root_admin/create_user.html', 
                                     organizations=Organization.query.order_by(Organization.name).all())

            # Get organization and check user limit
            org = Organization.query.get_or_404(org_id)
            current_user_count = User.query.filter_by(org_id=org_id).count()
            if current_user_count >= org.max_users:
                flash(f'Organization "{org.name}" has reached its user limit ({org.max_users})', 'error')
                return render_template('root_admin/create_user.html', 
                                     organizations=Organization.query.order_by(Organization.name).all())

            # Create user
            user = User(
                username=username,
                email=email,
                role=role,
                org_id=org_id,
                created_by=current_user.id,
                is_active_user=True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Auto-assign new user to all active providers in the organization
            org_providers = Provider.query.filter_by(org_id=org_id, is_active=True).all()
            for provider in org_providers:
                assignment = UserProviderAssignment(
                    user_id=user.id,
                    provider_id=provider.id,
                    org_id=org_id,
                    can_view_patients=True,
                    can_edit_screenings=(role in ['admin', 'nurse']),
                    can_generate_prep_sheets=True,
                    can_sync_epic=(role == 'admin')
                )
                db.session.add(assignment)
            db.session.commit()

            # Log the action
            log_admin_event(
                event_type='create_user',
                user_id=current_user.id,
                org_id=0,  # System Organization - all root admin actions
                ip=flask_request.remote_addr,
                data={
                    'created_user_id': user.id,
                    'created_username': username,
                    'target_org_id': org_id,
                    'target_org_name': org.name,
                    'user_role': role,
                    'description': f'Created user {username} for organization {org.name}'
                }
            )

            flash(f'User "{username}" created successfully in organization "{org.name}"', 'success')
            return redirect(url_for('root_admin.all_users'))

        # GET request - show create form
        organizations = Organization.query.filter_by(is_active=True).order_by(Organization.name).all()
        return render_template('root_admin/create_user.html', organizations=organizations)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {str(e)}")
        flash('Error creating user', 'error')
        return redirect(url_for('root_admin.all_users'))

# DEPRECATED: /users/<id>/edit route removed - users managed through organization admin dashboard

@root_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@root_admin_required
def delete_user(user_id):
    """Delete user with safety checks"""
    try:
        user = User.query.get_or_404(user_id)

        # Safety check - don't delete if it's the only admin in the organization
        if user.role == 'admin':
            admin_count = User.query.filter_by(org_id=user.org_id, role='admin').count()
            if admin_count == 1:
                return jsonify({
                    'success': False,
                    'error': 'Cannot delete the last admin user of an organization'
                }), 400

        # Safety check - don't delete root admin users
        if user.is_root_admin_user():
            return jsonify({
                'success': False,
                'error': 'Cannot delete root admin users'
            }), 400

        username = user.username
        org_name = user.organization.name if user.organization else 'Unknown'

        # Log before deletion
        log_admin_event(
            event_type='delete_user',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'deleted_user_id': user_id,
                'deleted_username': username,
                'target_org_name': org_name,
                'description': f'Deleted user {username} from organization {org.name}'
            }
        )

        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'User "{username}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Error deleting user'}), 500

@root_admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@root_admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)

        # Safety check - don't deactivate root admin users
        if user.is_root_admin_user():
            return jsonify({
                'success': False,
                'error': 'Cannot deactivate root admin users'
            }), 400

        user.is_active_user = not user.is_active_user
        db.session.commit()

        action = 'activated' if user.is_active_user else 'deactivated'

        # Log the action
        log_admin_event(
            event_type='toggle_user_status',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'target_user_id': user.id,
                'target_username': user.username,
                'new_status': 'active' if user.is_active_user else 'inactive',
                'description': f'{action.title()} user {user.username}'
            }
        )

        return jsonify({
            'success': True,
            'message': f'User "{user.username}" {action} successfully',
            'new_status': 'active' if user.is_active_user else 'inactive'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user status {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Error updating user status'}), 500

@root_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@root_admin_required
def delete_user_route(user_id):
    """Delete user route - calls the existing delete_user function"""
    return delete_user(user_id)

@root_admin_bp.route('/users/<int:user_id>/reset-security-questions', methods=['POST'])
@login_required
@root_admin_required
def reset_security_questions(user_id):
    """Reset security questions for a user (admin users only)"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Only allow resetting for admin users
        if not user.is_admin_user():
            return jsonify({
                'success': False,
                'error': 'Security questions can only be reset for administrator users'
            }), 400
        
        # Clear security question hashes
        user.security_answer_1_hash = None
        user.security_answer_2_hash = None
        
        db.session.commit()
        
        # Log the action
        log_admin_event(
            event_type='reset_security_questions',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=flask_request.remote_addr,
            data={
                'target_user_id': user.id,
                'target_username': user.username,
                'target_org_id': user.org_id,
                'description': f'Reset security questions for admin user: {user.username}'
            }
        )
        
        logger.info(f"Root admin {current_user.username} reset security questions for user {user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Security questions reset for {user.username}. They will be prompted to set new questions on next login.'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting security questions for user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Error resetting security questions'}), 500

# Duplicate edit_organization route removed - keeping only the one added at the end

# Duplicate delete_organization route removed - keeping only the one added at the end

@root_admin_bp.route('/presets/<int:preset_id>/promote', methods=['POST'])
@login_required
@root_admin_required
@csrf.exempt
def promote_preset_globally(preset_id):
    """Make a preset globally available to all organizations"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        # Store original org info before making it global
        original_org_id = preset.org_id
        original_org_name = preset.organization.name if preset.organization else 'Unknown'
        original_creator = preset.creator.username if preset.creator else 'Unknown'

        # Preserve original information in metadata
        if not preset.preset_metadata:
            preset.preset_metadata = {}

        preset.preset_metadata.update({
            'original_org_id': original_org_id,
            'original_org_name': original_org_name,
            'original_creator_username': original_creator,
            'made_global_at': datetime.utcnow().isoformat(),
            'made_global_by': current_user.username
        })

        # Make preset global
        preset.shared = True
        preset.preset_scope = 'global'
        preset.org_id = None  # Make it available to all organizations

        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='preset_made_global',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset.name,
                'original_org': original_org_name,
                'description': f'Made preset "{preset.name}" globally available'
            }
        )

        flash(f'Preset "{preset.name}" is now globally available to all organizations', 'success')
        return redirect(url_for('root_admin.presets'))

    except Exception as e:
        logger.error(f"Error making preset global: {str(e)}")
        flash('Error making preset global', 'error')
        return redirect(url_for('root_admin.presets'))

@root_admin_bp.route('/api/presets/<int:preset_id>/promote', methods=['POST'])
@csrf.exempt
@login_required
@root_admin_required
def api_promote_preset_globally(preset_id):
    """API endpoint for promoting presets globally (CSRF exempt)"""
    try:
        preset = ScreeningPreset.query.get_or_404(preset_id)

        if preset.preset_scope == 'global':
            return jsonify({'error': 'Preset is already globally available'}), 400

        # Store original org info before making it global
        original_org_id = preset.org_id
        original_org_name = preset.organization.name if preset.organization else 'Unknown'
        original_creator = preset.creator.username if preset.creator else 'Unknown'

        # Preserve original information in metadata
        if not preset.preset_metadata:
            preset.preset_metadata = {}

        preset.preset_metadata.update({
            'original_org_id': original_org_id,
            'original_org_name': original_org_name,
            'original_creator_username': original_creator,
            'made_global_at': datetime.utcnow().isoformat(),
            'made_global_by': current_user.username
        })

        preset.shared = True
        preset.preset_scope = 'global'
        preset.org_id = None

        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='preset_promoted',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset.name,
                'promoted_by': current_user.username
            }
        )

        return jsonify({
            'success': True,
            'message': f'Preset "{preset.name}" has been promoted globally'
        })

    except Exception as e:
        logger.error(f"Error promoting preset globally: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to promote preset globally'}), 500