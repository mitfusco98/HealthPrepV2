"""
Organization Approval Routes for Root Admin
Handles approval/rejection of new organization signups
"""
import logging
from flask import Blueprint, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from models import User, Organization, db, log_admin_event
from services.email_service import EmailService

logger = logging.getLogger(__name__)

org_approval_bp = Blueprint('org_approval', __name__)


def root_admin_required(f):
    """Decorator to require root admin role"""
    import functools
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_root_admin_user():
            flash('Root admin access required', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@org_approval_bp.route('/root-admin/organizations/<int:org_id>/approve', methods=['POST'])
@login_required
@root_admin_required
def approve_organization(org_id):
    """Approve a pending organization and activate its users"""
    try:
        org = Organization.query.get_or_404(org_id)
        
        # Check if already approved
        if org.onboarding_status == 'approved':
            flash(f'{org.name} is already approved.', 'info')
            return redirect(url_for('root_admin.dashboard'))
        
        # Update organization status
        org.onboarding_status = 'approved'
        org.setup_status = 'trial'  # Activate trial (is_active @property will return True)
        org.approved_at = datetime.utcnow()
        org.approved_by = current_user.id
        
        # Activate all users in this organization
        org_users = User.query.filter_by(org_id=org_id).all()
        for user in org_users:
            user.is_active_user = True
        
        db.session.commit()
        
        # Send approval notification to admin user
        admin_user = User.query.filter_by(org_id=org_id, role='admin').first()
        if admin_user:
            EmailService.send_organization_approved_email(
                email=admin_user.email,
                username=admin_user.username,
                org_name=org.name
            )
        
        # Log the approval
        log_admin_event(
            event_type='organization_approved',
            user_id=current_user.id,
            org_id=org_id,
            ip=request.remote_addr,
            data={
                'org_name': org.name,
                'approved_by': current_user.username,
                'activated_users': len(org_users)
            }
        )
        
        logger.info(f"Organization {org.name} (ID: {org_id}) approved by {current_user.username}")
        flash(f'Organization "{org.name}" has been approved and activated!', 'success')
        
        return redirect(url_for('root_admin.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving organization {org_id}: {str(e)}")
        flash('Error approving organization. Please try again.', 'error')
        return redirect(url_for('root_admin.dashboard'))


@org_approval_bp.route('/root-admin/organizations/<int:org_id>/reject', methods=['POST'])
@login_required
@root_admin_required
def reject_organization(org_id):
    """Reject a pending organization"""
    try:
        org = Organization.query.get_or_404(org_id)
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')
        
        # Check if already processed
        if org.onboarding_status in ['approved', 'suspended']:
            flash(f'{org.name} has already been processed.', 'info')
            return redirect(url_for('root_admin.dashboard'))
        
        # Update organization status (use 'suspended' instead of 'rejected')
        org.onboarding_status = 'suspended'
        org.setup_status = 'suspended'  # Suspend org (is_active @property will return False)
        
        # Deactivate all users in this organization
        org_users = User.query.filter_by(org_id=org_id).all()
        for user in org_users:
            user.is_active_user = False
        
        db.session.commit()
        
        # Send rejection notification to admin user
        admin_user = User.query.filter_by(org_id=org_id, role='admin').first()
        if admin_user:
            EmailService.send_organization_rejected_email(
                email=admin_user.email,
                username=admin_user.username,
                org_name=org.name,
                rejection_reason=rejection_reason
            )
        
        # Log the rejection
        log_admin_event(
            event_type='organization_rejected',
            user_id=current_user.id,
            org_id=org_id,
            ip=request.remote_addr,
            data={
                'org_name': org.name,
                'rejected_by': current_user.username,
                'reason': rejection_reason
            }
        )
        
        logger.info(f"Organization {org.name} (ID: {org_id}) rejected by {current_user.username}")
        flash(f'Organization "{org.name}" has been rejected.', 'warning')
        
        return redirect(url_for('root_admin.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting organization {org_id}: {str(e)}")
        flash('Error rejecting organization. Please try again.', 'error')
        return redirect(url_for('root_admin.dashboard'))
