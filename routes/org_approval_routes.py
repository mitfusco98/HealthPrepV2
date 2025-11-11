"""
Organization Approval Routes for Root Admin
Handles approval/rejection of new organization signups
"""
import logging
from flask import Blueprint, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from models import User, Organization, db, log_admin_event
from services.email_service import EmailService
from services.stripe_service import StripeService

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
        
        # Start Stripe subscription with 14-day trial (trial starts NOW, on approval)
        if org.stripe_customer_id:
            subscription_started = StripeService.start_trial_subscription(org)
            if not subscription_started:
                logger.warning(f"Failed to start Stripe subscription for organization {org_id}")
                flash('Organization approved but Stripe subscription failed. Please check billing manually.', 'warning')
        else:
            logger.warning(f"Organization {org_id} approved without Stripe customer ID")
            flash('Organization approved but no payment method on file. Trial dates set manually.', 'warning')
            # Set trial dates manually if no Stripe
            org.trial_start_date = datetime.utcnow()
            org.trial_expires = datetime.utcnow() + timedelta(days=14)
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
            org_id=0,  # System Organization - all root admin actions
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
    """Reject and automatically delete a pending organization"""
    try:
        from models import (AdminLog, ScreeningPreset, Patient, Screening, PrepSheetSettings,
                           ScreeningType, Document, FHIRDocument, AsyncJob, FHIRApiCall,
                           Appointment, DismissedDocumentMatch, EpicCredentials,
                           ScreeningVariant, ScreeningProtocol)
        
        org = Organization.query.get_or_404(org_id)
        org_name = org.name
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')
        
        # Check if already processed
        if org.onboarding_status in ['approved', 'suspended']:
            flash(f'{org.name} has already been processed.', 'info')
            return redirect(url_for('root_admin.dashboard'))
        
        # Prevent deletion of System Organization (org_id=0)
        if org_id == 0:
            flash('Cannot reject System Organization', 'error')
            return redirect(url_for('root_admin.dashboard'))
        
        # Get admin user for rejection email before deletion
        admin_user = User.query.filter_by(org_id=org_id, role='admin').first()
        org_users = User.query.filter_by(org_id=org_id).all()
        user_count = len(org_users)
        
        # Send rejection notification before deletion
        if admin_user:
            EmailService.send_organization_rejected_email(
                email=admin_user.email,
                username=admin_user.username,
                org_name=org_name,
                rejection_reason=rejection_reason
            )
        
        # CRITICAL: Reassign admin_logs to System Organization (org_id=0) for audit trail preservation
        admin_logs = AdminLog.query.filter_by(org_id=org_id).all()
        for log in admin_logs:
            log.org_id = 0  # Reassign to System Organization context
            log.action_details = f"[ORG REJECTED & DELETED: {org_name}] " + (log.action_details or "")
        
        # Delete organization-scoped data (order matters for foreign key constraints)
        DismissedDocumentMatch.query.filter_by(org_id=org_id).delete()
        Appointment.query.filter_by(org_id=org_id).delete()
        FHIRApiCall.query.filter_by(org_id=org_id).delete()
        AsyncJob.query.filter_by(org_id=org_id).delete()
        PrepSheetSettings.query.filter_by(org_id=org_id).delete()
        ScreeningPreset.query.filter_by(org_id=org_id).delete()
        ScreeningVariant.query.filter_by(org_id=org_id).delete()
        ScreeningProtocol.query.filter_by(org_id=org_id).delete()
        Screening.query.filter_by(org_id=org_id).delete()
        ScreeningType.query.filter_by(org_id=org_id).delete()
        FHIRDocument.query.filter_by(org_id=org_id).delete()
        Document.query.filter_by(org_id=org_id).delete()
        Patient.query.filter_by(org_id=org_id).delete()
        EpicCredentials.query.filter_by(org_id=org_id).delete()
        
        # Delete all users in this organization
        for user in org_users:
            db.session.delete(user)
        
        # Log the rejection and deletion to System Organization
        log_admin_event(
            event_type='organization_rejected_deleted',
            user_id=current_user.id,
            org_id=0,  # System Organization - all root admin actions
            ip=request.remote_addr,
            data={
                'organization_name': org_name,
                'organization_id': org_id,
                'rejected_by': current_user.username,
                'rejection_reason': rejection_reason,
                'users_deleted': user_count,
                'audit_logs_preserved': len(admin_logs),
                'description': f'Rejected and deleted organization: {org_name} ({user_count} users, {len(admin_logs)} audit logs preserved). Reason: {rejection_reason}'
            }
        )
        
        # Delete organization
        db.session.delete(org)
        db.session.commit()
        
        logger.info(f"Organization {org_name} (ID: {org_id}) rejected and deleted by {current_user.username}")
        flash(f'Organization "{org_name}" has been rejected and deleted.', 'warning')
        
        return redirect(url_for('root_admin.dashboard'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting organization {org_id}: {str(e)}")
        flash('Error rejecting organization. Please try again.', 'error')
        return redirect(url_for('root_admin.dashboard'))
