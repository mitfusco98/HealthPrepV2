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
        
        # Activate all users in this organization
        org_users = User.query.filter_by(org_id=org_id).all()
        for user in org_users:
            user.is_active_user = True
        
        # Handle billing based on creation method
        if org.creation_method == 'manual':
            # Manual billing org - activate immediately (no trial period)
            logger.info(f"Approving manual billing organization {org_id}")
            org.onboarding_status = 'approved'
            org.setup_status = 'live'  # Go straight to live status (no trial)
            org.subscription_status = 'manual_billing'
            org.approved_at = datetime.utcnow()
            org.approved_by = current_user.id
            db.session.commit()
            flash('Organization approved with manual billing. System activated.', 'info')
        else:
            # Self-service org - start Stripe subscription with immediate charge (no trial)
            # Payment method must be on file before approval
            if not org.stripe_customer_id:
                logger.error(f"Cannot approve organization {org_id} - no Stripe customer ID (payment method required)")
                flash('Cannot approve: Organization has no payment method on file.', 'error')
                return redirect(url_for('root_admin.dashboard'))
            
            # Start paid subscription (immediate charge)
            subscription_started = StripeService.start_paid_subscription(org)
            
            if subscription_started:
                # Subscription successful - activate organization
                org.onboarding_status = 'approved'
                org.setup_status = 'live'  # Go straight to live (no trial)
                org.approved_at = datetime.utcnow()
                org.approved_by = current_user.id
                db.session.commit()
                
                logger.info(f"Organization {org_id} approved and subscription started successfully")
                flash(f'Organization "{org.name}" approved and first payment processed!', 'success')
            else:
                # Payment failed - do not approve
                logger.error(f"Failed to start Stripe subscription for organization {org_id}")
                flash('Cannot approve: Payment processing failed. Please verify payment method is valid.', 'error')
                return redirect(url_for('root_admin.dashboard'))
        
        # Send approval notification to admin user
        admin_user = User.query.filter_by(org_id=org_id, role='admin').first()
        if admin_user:
            logger.info(f"Sending approval email to {admin_user.email} for org {org.name}")
            email_sent = EmailService.send_organization_approved_email(
                email=admin_user.email,
                username=admin_user.username,
                org_name=org.name
            )
            if email_sent:
                logger.info(f"Approval email sent successfully to {admin_user.email}")
            else:
                logger.warning(f"Failed to send approval email to {admin_user.email}")
        else:
            logger.warning(f"No admin user found for organization {org_id} to send approval email")
        
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
                           ScreeningVariant, ScreeningProtocol, PatientCondition, FHIRImmunization)
        
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
            logger.info(f"Sending rejection email to {admin_user.email} for org {org_name}")
            email_sent = EmailService.send_organization_rejected_email(
                email=admin_user.email,
                username=admin_user.username,
                org_name=org_name,
                rejection_reason=rejection_reason
            )
            if email_sent:
                logger.info(f"Rejection email sent successfully to {admin_user.email}")
            else:
                logger.warning(f"Failed to send rejection email to {admin_user.email}")
        
        # Cleanup Stripe resources before deletion
        if org.stripe_customer_id:
            try:
                # Cancel any active subscriptions
                if org.stripe_subscription_id:
                    logger.info(f"Cancelling Stripe subscription {org.stripe_subscription_id} for rejected org {org_id}")
                    StripeService.cancel_subscription(org.stripe_subscription_id)
                
                # Archive the customer (mark as deleted in metadata, don't actually delete for audit trail)
                logger.info(f"Archiving Stripe customer {org.stripe_customer_id} for rejected org {org_id}")
                import stripe
                stripe.Customer.modify(
                    org.stripe_customer_id,
                    metadata={
                        'archived': 'true',
                        'archived_at': datetime.utcnow().isoformat(),
                        'rejection_reason': rejection_reason,
                        'original_org_name': org_name
                    }
                )
            except Exception as stripe_error:
                logger.error(f"Error cleaning up Stripe resources for org {org_id}: {str(stripe_error)}")
        
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
        
        # Delete patient-scoped data before patients (these tables have patient_id FK, not org_id)
        patient_ids = [p.id for p in Patient.query.filter_by(org_id=org_id).all()]
        if patient_ids:
            PatientCondition.query.filter(PatientCondition.patient_id.in_(patient_ids)).delete(synchronize_session=False)
            FHIRImmunization.query.filter(FHIRImmunization.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        
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
