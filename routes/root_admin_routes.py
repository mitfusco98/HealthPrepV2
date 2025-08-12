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

from models import User, Organization, AdminLog, log_admin_event, EpicCredentials, ScreeningPreset
from app import db
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
        
        # Get system-wide statistics
        total_orgs = len(organizations)
        active_orgs = sum(1 for org in organizations if org.is_active)
        trial_orgs = sum(1 for org in organizations if org.setup_status == 'trial')
        
        # Get user statistics across all organizations
        total_users = User.query.filter(User.org_id != None).count()
        admin_users = User.query.filter(User.role == 'admin').count()
        
        # Get recent activities across all organizations
        recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(20).all()
        
        # Get preset statistics
        total_presets = ScreeningPreset.query.count()
        global_presets = ScreeningPreset.query.filter_by(shared=True).count()
        
        stats = {
            'total_organizations': total_orgs,
            'active_organizations': active_orgs,
            'trial_organizations': trial_orgs,
            'total_users': total_users,
            'admin_users': admin_users,
            'total_presets': total_presets,
            'global_presets': global_presets
        }
        
        return render_template('root_admin/dashboard.html', 
                             organizations=organizations,
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
        
        # Get global presets (universally available)
        global_presets = ScreeningPreset.query.filter_by(shared=True).order_by(ScreeningPreset.updated_at.desc()).all()
        
        # Organize presets by organization for better display
        org_presets = {}
        for preset in all_presets:
            if not preset.shared:  # Don't duplicate global presets in org sections
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
        
        # Make preset global
        preset.shared = True
        preset.preset_scope = 'global'
        preset.org_id = None  # Make it available to all organizations
        
        db.session.commit()
        
        # Log the action
        log_admin_event(
            event_type='preset_made_global',
            user_id=current_user.id,
            org_id=1,  # Root admin org
            ip=request.remote_addr,
            data={
                'preset_id': preset_id,
                'preset_name': preset.name,
                'original_org': preset.organization.name if preset.organization else 'Unknown',
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
        
        # Remove global status
        preset.shared = False
        preset.preset_scope = 'organization'
        
        db.session.commit()
        
        # Log the action
        log_admin_event(
            event_type='preset_global_removed',
            user_id=current_user.id,
            org_id=1,  # Root admin org
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
            org_id=1,  # Root admin org
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

@root_admin_bp.route('/presets/view/<int:preset_id>')
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
            org_id=None,  # Root admin action
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
            org_id=None,  # Root admin action
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
    """List all organizations"""
    try:
        organizations = Organization.query.order_by(Organization.created_at.desc()).all()
        return render_template('root_admin/organizations.html', organizations=organizations)
    except Exception as e:
        logger.error(f"Error loading organizations: {str(e)}")
        flash('Error loading organizations', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/organizations/create', methods=['GET', 'POST'])
@login_required
@root_admin_required
def create_organization():
    """Create new organization"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            display_name = request.form.get('display_name')
            contact_email = request.form.get('contact_email')
            address = request.form.get('address')
            phone = request.form.get('phone')
            max_users = request.form.get('max_users', 10, type=int)
            
            # Admin user details
            admin_username = request.form.get('admin_username')
            admin_email = request.form.get('admin_email')
            admin_password = request.form.get('admin_password')
            
            # Validate input
            if not name or not admin_username or not admin_email or not admin_password:
                flash('Organization name and admin details are required', 'error')
                return render_template('root_admin/create_organization.html')
            
            # Check if organization name already exists
            existing_org = Organization.query.filter_by(name=name).first()
            if existing_org:
                flash('Organization name already exists', 'error')
                return render_template('root_admin/create_organization.html')
            
            # Create organization
            org = Organization(
                name=name,
                display_name=display_name or name,
                contact_email=contact_email,
                address=address,
                phone=phone,
                max_users=max_users,
                setup_status='incomplete'
            )
            db.session.add(org)
            db.session.flush()  # Get the org.id
            
            # Create admin user for the organization
            admin_user = User(
                username=admin_username,
                email=admin_email,
                role='admin',
                is_admin=True,
                org_id=org.id,
                created_by=current_user.id
            )
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            
            db.session.commit()
            
            # Log the action
            log_admin_event(
                event_type='create_organization',
                user_id=current_user.id,
                org_id=org.id,
                ip=flask_request.remote_addr,
                data={
                    'organization_name': name,
                    'admin_username': admin_username,
                    'description': f'Created organization: {name} with admin: {admin_username}'
                }
            )
            
            flash(f'Organization "{name}" created successfully with admin user "{admin_username}"', 'success')
            return redirect(url_for('root_admin.organizations'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating organization: {str(e)}")
            flash('Error creating organization', 'error')
            return render_template('root_admin/create_organization.html')
    
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
            org.name = request.form.get('name')
            org.display_name = request.form.get('display_name')
            org.contact_email = request.form.get('contact_email')
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
                org.epic_client_secret = epic_secret  # In production, this should be encrypted
            
            db.session.commit()
            
            # Log the action
            log_admin_event(
                event_type='edit_organization',
                user_id=current_user.id,
                org_id=org_id,
                ip=flask_request.remote_addr,
                data={
                    'organization_name': org.name,
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
    """Delete organization (with safety checks)"""
    try:
        org = Organization.query.get_or_404(org_id)
        
        # Safety check - don't delete if has users
        user_count = User.query.filter_by(org_id=org_id).count()
        if user_count > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete organization with {user_count} users. Remove users first.'
            }), 400
        
        org_name = org.name
        
        # Log before deletion
        log_admin_event(
            event_type='delete_organization',
            user_id=current_user.id,
            org_id=org_id,
            ip=flask_request.remote_addr,
            data={
                'organization_name': org_name,
                'description': f'Deleted organization: {org_name}'
            }
        )
        
        db.session.delete(org)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Organization "{org_name}" deleted successfully'
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
    """View all users across all organizations"""
    try:
        # Get users with organization info
        users = db.session.query(User, Organization).join(
            Organization, User.org_id == Organization.id
        ).order_by(Organization.name, User.username).all()
        
        return render_template('root_admin/all_users.html', users=users)
        
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
        
        # Build query
        query = AdminLog.query
        
        if org_id:
            query = query.filter(AdminLog.org_id == org_id)
        if event_type:
            query = query.filter(AdminLog.event_type == event_type)
        
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
                             filters={'org_id': org_id, 'event_type': event_type})
        
    except Exception as e:
        logger.error(f"Error loading system logs: {str(e)}")
        flash('Error loading logs', 'error')
        return render_template('error/500.html'), 500

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
            
            # Log the action
            log_admin_event(
                event_type='create_user',
                user_id=current_user.id,
                org_id=None,  # Root admin action
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

@root_admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@root_admin_required
def edit_user(user_id):
    """Edit user details"""
    try:
        user = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            # Update user details
            user.email = request.form.get('email')
            user.role = request.form.get('role')
            user.is_active_user = request.form.get('is_active') == 'on'
            
            # Handle organization change
            new_org_id = request.form.get('org_id', type=int)
            if new_org_id != user.org_id:
                new_org = Organization.query.get_or_404(new_org_id)
                current_user_count = User.query.filter_by(org_id=new_org_id).count()
                if current_user_count >= new_org.max_users:
                    flash(f'Target organization "{new_org.name}" has reached its user limit ({new_org.max_users})', 'error')
                    return render_template('root_admin/edit_user.html', 
                                         user=user, 
                                         organizations=Organization.query.order_by(Organization.name).all())
                user.org_id = new_org_id
            
            # Handle password change
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            db.session.commit()
            
            # Log the action
            log_admin_event(
                event_type='edit_user',
                user_id=current_user.id,
                org_id=None,  # Root admin action
                ip=flask_request.remote_addr,
                data={
                    'target_user_id': user.id,
                    'target_username': user.username,
                    'target_org_id': user.org_id,
                    'description': f'Updated user {user.username}'
                }
            )
            
            flash(f'User "{user.username}" updated successfully', 'success')
            return redirect(url_for('root_admin.all_users'))
        
        # GET request - show edit form
        organizations = Organization.query.order_by(Organization.name).all()
        return render_template('root_admin/edit_user.html', user=user, organizations=organizations)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing user {user_id}: {str(e)}")
        flash('Error updating user', 'error')
        return redirect(url_for('root_admin.all_users'))

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
            org_id=None,  # Root admin action
            ip=flask_request.remote_addr,
            data={
                'deleted_user_id': user_id,
                'deleted_username': username,
                'target_org_name': org_name,
                'description': f'Deleted user {username} from organization {org_name}'
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
        
        # Safety check - don't deactivate if it's the only admin in the organization
        if user.role == 'admin' and user.is_active_user:
            active_admin_count = User.query.filter_by(
                org_id=user.org_id, 
                role='admin', 
                is_active_user=True
            ).count()
            if active_admin_count == 1:
                return jsonify({
                    'success': False,
                    'error': 'Cannot deactivate the last active admin user of an organization'
                }), 400
        
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
            org_id=None,  # Root admin action
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

# Duplicate edit_organization route removed - keeping only the one added at the end

# Duplicate delete_organization route removed - keeping only the one added at the end

