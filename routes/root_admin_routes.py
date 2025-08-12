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

from models import User, Organization, AdminLog, log_admin_event, EpicCredentials, ScreeningPreset, ExportRequest
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
        
        # Get pending export requests
        pending_export_requests = ExportRequest.query.filter_by(status='pending').order_by(ExportRequest.created_at.desc()).limit(10).all()
        
        # Get recent activities across all organizations
        recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(20).all()
        
        stats = {
            'total_organizations': total_orgs,
            'active_organizations': active_orgs,
            'trial_organizations': trial_orgs,
            'total_users': total_users,
            'admin_users': admin_users,
            'pending_export_requests': len(pending_export_requests)
        }
        
        return render_template('root_admin/dashboard.html', 
                             organizations=organizations,
                             stats=stats,
                             recent_logs=recent_logs,
                             pending_export_requests=pending_export_requests)
        
    except Exception as e:
        logger.error(f"Error in root admin dashboard: {str(e)}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

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
                             logs=logs_pagination.items,
                             pagination=logs_pagination,
                             organizations=organizations,
                             event_types=event_types,
                             filters={'org_id': org_id, 'event_type': event_type})
        
    except Exception as e:
        logger.error(f"Error loading system logs: {str(e)}")
        flash('Error loading logs', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/export-requests')
@login_required
@root_admin_required
def export_requests():
    """View all export requests from organization admins"""
    try:
        # Get filter parameters
        status = request.args.get('status', 'pending')
        org_id = request.args.get('org_id', type=int)
        
        # Build query
        query = ExportRequest.query
        
        if status != 'all':
            query = query.filter(ExportRequest.status == status)
        if org_id:
            query = query.filter(ExportRequest.org_id == org_id)
        
        export_requests = query.order_by(ExportRequest.created_at.desc()).all()
        
        # Get organizations for filter
        organizations = Organization.query.order_by(Organization.name).all()
        
        return render_template('root_admin/export_requests.html',
                             export_requests=export_requests,
                             organizations=organizations,
                             filters={'status': status, 'org_id': org_id})
        
    except Exception as e:
        logger.error(f"Error loading export requests: {str(e)}")
        flash('Error loading export requests', 'error')
        return render_template('error/500.html'), 500

@root_admin_bp.route('/export-requests/<string:request_id>')
@login_required
@root_admin_required
def view_export_request(request_id):
    """View detailed export request"""
    try:
        export_request = ExportRequest.query.get_or_404(request_id)
        return render_template('root_admin/view_export_request.html',
                             export_request=export_request)
        
    except Exception as e:
        logger.error(f"Error viewing export request {request_id}: {str(e)}")
        flash('Error loading export request', 'error')
        return redirect(url_for('root_admin.export_requests'))

@root_admin_bp.route('/export-requests/<string:request_id>/approve', methods=['POST'])
@login_required
@root_admin_required
def approve_export_request(request_id):
    """Approve export request and create universal type"""
    try:
        export_request = ExportRequest.query.get_or_404(request_id)
        
        if not export_request.is_pending:
            flash('This export request has already been reviewed', 'error')
            return redirect(url_for('root_admin.export_requests'))
        
        review_notes = request.form.get('review_notes', '').strip()
        
        # Approve the request
        export_request.approve(current_user, review_notes)
        
        flash(f'Export request for "{export_request.proposed_universal_name}" approved successfully', 'success')
        return redirect(url_for('root_admin.export_requests'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving export request {request_id}: {str(e)}")
        flash('Error approving export request', 'error')
        return redirect(url_for('root_admin.export_requests'))

@root_admin_bp.route('/export-requests/<string:request_id>/reject', methods=['POST'])
@login_required
@root_admin_required
def reject_export_request(request_id):
    """Reject export request"""
    try:
        export_request = ExportRequest.query.get_or_404(request_id)
        
        if not export_request.is_pending:
            flash('This export request has already been reviewed', 'error')
            return redirect(url_for('root_admin.export_requests'))
        
        review_notes = request.form.get('review_notes', '').strip()
        
        if not review_notes:
            flash('Please provide a reason for rejection', 'error')
            return redirect(url_for('root_admin.view_export_request', request_id=request_id))
        
        # Reject the request
        export_request.reject(current_user, review_notes)
        
        flash(f'Export request for "{export_request.proposed_universal_name}" rejected', 'warning')
        return redirect(url_for('root_admin.export_requests'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting export request {request_id}: {str(e)}")
        flash('Error rejecting export request', 'error')
        return redirect(url_for('root_admin.export_requests'))