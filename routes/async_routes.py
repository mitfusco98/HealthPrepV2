"""
Async Processing Routes for HealthPrepV2
Handles background job management, status monitoring, and batch operations
"""

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json

from models import db, Patient, Organization, ScreeningType, AsyncJob
from services.async_processing import get_async_processing_service
from services.enhanced_audit_logging import log_fhir_access, audit_logger
from utils.auth_utils import admin_required

async_bp = Blueprint('async', __name__, url_prefix='/async')


@async_bp.route('/dashboard')
@login_required
@admin_required
def async_dashboard():
    """Dashboard for managing asynchronous jobs"""
    try:
        async_service = get_async_processing_service()
        
        # Get active jobs for this organization
        active_jobs = async_service.get_organization_active_jobs(current_user.org_id)
        
        # Get recent completed jobs
        recent_jobs = AsyncJob.query.filter_by(
            org_id=current_user.org_id
        ).order_by(AsyncJob.created_at.desc()).limit(10).all()
        
        # Get organization settings
        organization = Organization.query.get(current_user.org_id)
        
        return render_template('async/dashboard.html',
                             active_jobs=active_jobs,
                             recent_jobs=recent_jobs,
                             organization=organization)
    
    except Exception as e:
        flash(f'Error loading async dashboard: {str(e)}', 'error')
        return redirect(url_for('ui.dashboard'))


@async_bp.route('/batch-sync', methods=['GET', 'POST'])
@login_required
@admin_required
def batch_patient_sync():
    """Initiate batch patient synchronization from Epic"""
    if request.method == 'GET':
        return render_template('async/batch_sync.html')
    
    try:
        data = request.get_json() or request.form.to_dict()
        patient_mrns = data.get('patient_mrns', '').strip().split('\n')
        patient_mrns = [mrn.strip() for mrn in patient_mrns if mrn.strip()]
        priority = data.get('priority', 'normal')
        
        if not patient_mrns:
            return jsonify({'error': 'No patient MRNs provided'}), 400
        
        # Check organization batch size limits
        organization = Organization.query.get(current_user.org_id)
        if not organization.async_processing_enabled:
            return jsonify({'error': 'Async processing is disabled for this organization'}), 403
        
        max_batch = organization.get_max_batch_size()
        if len(patient_mrns) > max_batch:
            return jsonify({
                'error': f'Batch size ({len(patient_mrns)}) exceeds organization limit ({max_batch})'
            }), 400
        
        # Check rate limits
        from models import FHIRApiCall
        current_hour_calls = FHIRApiCall.get_hourly_call_count(current_user.org_id)
        estimated_calls = len(patient_mrns) * 5  # Estimated API calls per patient
        
        if not organization.is_within_rate_limit(current_hour_calls + estimated_calls):
            return jsonify({
                'error': f'This batch would exceed your hourly rate limit ({organization.fhir_rate_limit_per_hour} calls/hour)'
            }), 429
        
        # Enqueue batch job
        async_service = get_async_processing_service()
        job_id = async_service.enqueue_batch_patient_sync(
            organization_id=current_user.org_id,
            patient_mrns=patient_mrns,
            user_id=current_user.id,
            priority=priority
        )
        
        # Log the batch sync initiation
        log_fhir_access(
            organization_id=current_user.org_id,
            action='batch_sync_initiated',
            resource_type='Patient',
            resource_count=len(patient_mrns),
            additional_data={
                'job_id': job_id,
                'priority': priority,
                'patient_count': len(patient_mrns)
            }
        )
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'patient_count': len(patient_mrns),
            'message': f'Batch sync initiated for {len(patient_mrns)} patients'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to initiate batch sync: {str(e)}'}), 500


@async_bp.route('/batch-prep-sheets', methods=['POST'])
@login_required
@admin_required
def batch_prep_sheet_generation():
    """Initiate batch preparation sheet generation"""
    try:
        data = request.get_json()
        patient_ids = data.get('patient_ids', [])
        screening_type_ids = data.get('screening_types', [])
        priority = data.get('priority', 'normal')
        
        if not patient_ids:
            return jsonify({'error': 'No patients selected'}), 400
        
        if not screening_type_ids:
            return jsonify({'error': 'No screening types selected'}), 400
        
        # Validate patients belong to this organization
        valid_patients = Patient.query.filter(
            Patient.id.in_(patient_ids),
            Patient.org_id == current_user.org_id
        ).all()
        
        if len(valid_patients) != len(patient_ids):
            return jsonify({'error': 'Some patients do not belong to your organization'}), 403
        
        # Validate screening types belong to this organization
        valid_screening_types = ScreeningType.query.filter(
            ScreeningType.id.in_(screening_type_ids),
            ScreeningType.org_id == current_user.org_id
        ).all()
        
        if len(valid_screening_types) != len(screening_type_ids):
            return jsonify({'error': 'Some screening types do not belong to your organization'}), 403
        
        # Check organization limits
        organization = Organization.query.get(current_user.org_id)
        max_batch = organization.get_max_batch_size()
        
        if len(patient_ids) > max_batch:
            return jsonify({
                'error': f'Batch size ({len(patient_ids)}) exceeds organization limit ({max_batch})'
            }), 400
        
        # Enqueue batch job
        async_service = get_async_processing_service()
        job_id = async_service.enqueue_batch_prep_sheet_generation(
            organization_id=current_user.org_id,
            patient_ids=patient_ids,
            screening_types=screening_type_ids,
            user_id=current_user.id,
            priority=priority
        )
        
        # Log the batch generation initiation
        log_fhir_access(
            organization_id=current_user.org_id,
            action='batch_prep_sheet_generation_initiated',
            resource_type='PrepSheet',
            resource_count=len(patient_ids),
            additional_data={
                'job_id': job_id,
                'screening_types': len(screening_type_ids),
                'priority': priority
            }
        )
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'patient_count': len(patient_ids),
            'screening_type_count': len(screening_type_ids),
            'message': f'Batch prep sheet generation initiated for {len(patient_ids)} patients'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to initiate batch generation: {str(e)}'}), 500


@async_bp.route('/job/<job_id>/status')
@login_required
def job_status(job_id):
    """Get status of a specific job"""
    try:
        # Verify job belongs to user's organization
        job = AsyncJob.query.filter_by(
            job_id=job_id,
            org_id=current_user.org_id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Get detailed status from async service
        async_service = get_async_processing_service()
        status_info = async_service.get_job_status(job_id)
        
        # Add database job info
        status_info.update({
            'job_type': job.job_type,
            'total_items': job.total_items,
            'completed_items': job.completed_items,
            'failed_items': job.failed_items,
            'progress_percentage': job.progress_percentage,
            'duration_seconds': job.duration_seconds,
            'error_message': job.error_message
        })
        
        return jsonify(status_info)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get job status: {str(e)}'}), 500


@async_bp.route('/job/<job_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_job(job_id):
    """Cancel a running job"""
    try:
        # Verify job belongs to user's organization
        job = AsyncJob.query.filter_by(
            job_id=job_id,
            org_id=current_user.org_id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if not job.is_active:
            return jsonify({'error': 'Job is not active'}), 400
        
        # Cancel the job
        async_service = get_async_processing_service()
        success = async_service.cancel_job(job_id, current_user.id, current_user.org_id)
        
        if success:
            # Update database record
            job.status = 'cancelled'
            job.completed_at = datetime.utcnow()
            job.error_message = f'Cancelled by user {current_user.username}'
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Job cancelled successfully'
            })
        else:
            return jsonify({'error': 'Failed to cancel job'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Failed to cancel job: {str(e)}'}), 500


@async_bp.route('/jobs')
@login_required
def list_jobs():
    """List jobs for the organization"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status_filter = request.args.get('status')
        job_type_filter = request.args.get('job_type')
        
        query = AsyncJob.query.filter_by(org_id=current_user.org_id)
        
        if status_filter:
            query = query.filter(AsyncJob.status == status_filter)
        
        if job_type_filter:
            query = query.filter(AsyncJob.job_type == job_type_filter)
        
        jobs = query.order_by(AsyncJob.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('async/job_list.html', jobs=jobs)
    
    except Exception as e:
        flash(f'Error loading jobs: {str(e)}', 'error')
        return redirect(url_for('async.async_dashboard'))


@async_bp.route('/job/<job_id>')
@login_required
def job_detail(job_id):
    """Show detailed information about a job"""
    try:
        job = AsyncJob.query.filter_by(
            job_id=job_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        # Get live status from async service
        async_service = get_async_processing_service()
        live_status = async_service.get_job_status(job_id)
        
        return render_template('async/job_detail.html', 
                             job=job, 
                             live_status=live_status)
    
    except Exception as e:
        flash(f'Error loading job details: {str(e)}', 'error')
        return redirect(url_for('async.async_dashboard'))


@async_bp.route('/rate-limit/status')
@login_required
def rate_limit_status():
    """Get current rate limit status for the organization"""
    try:
        organization = Organization.query.get(current_user.org_id)
        
        from models import FHIRApiCall
        current_hour_calls = FHIRApiCall.get_hourly_call_count(current_user.org_id)
        
        rate_limit_info = {
            'current_hour_calls': current_hour_calls,
            'hourly_limit': organization.fhir_rate_limit_per_hour,
            'remaining_calls': organization.fhir_rate_limit_per_hour - current_hour_calls,
            'percentage_used': (current_hour_calls / organization.fhir_rate_limit_per_hour) * 100,
            'max_batch_size': organization.get_max_batch_size(),
            'async_processing_enabled': organization.async_processing_enabled
        }
        
        return jsonify(rate_limit_info)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get rate limit status: {str(e)}'}), 500


@async_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def async_settings():
    """Manage async processing settings for the organization"""
    organization = Organization.query.get(current_user.org_id)
    
    if request.method == 'POST':
        try:
            # Update async processing settings
            organization.async_processing_enabled = request.form.get('async_processing_enabled') == 'on'
            organization.max_batch_size = min(int(request.form.get('max_batch_size', 100)), 500)
            organization.fhir_rate_limit_per_hour = int(request.form.get('fhir_rate_limit_per_hour', 1000))
            organization.phi_logging_level = request.form.get('phi_logging_level', 'minimal')
            
            db.session.commit()
            
            # Log the settings change
            log_fhir_access(
                organization_id=current_user.org_id,
                action='async_settings_updated',
                additional_data={
                    'async_enabled': organization.async_processing_enabled,
                    'max_batch_size': organization.max_batch_size,
                    'rate_limit': organization.fhir_rate_limit_per_hour,
                    'phi_level': organization.phi_logging_level
                }
            )
            
            flash('Async processing settings updated successfully', 'success')
            return redirect(url_for('async.async_settings'))
        
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
    
    return render_template('async/settings.html', organization=organization)


# API endpoints for real-time job monitoring

@async_bp.route('/api/jobs/active')
@login_required
def api_active_jobs():
    """API endpoint to get active jobs with real-time status"""
    try:
        async_service = get_async_processing_service()
        active_jobs = async_service.get_organization_active_jobs(current_user.org_id)
        
        return jsonify({
            'success': True,
            'active_jobs': active_jobs,
            'total_active': len(active_jobs)
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get active jobs: {str(e)}'}), 500


@async_bp.route('/api/stats')
@login_required
def api_async_stats():
    """API endpoint to get async processing statistics"""
    try:
        # Get job statistics for the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        stats = db.session.query(
            AsyncJob.status,
            db.func.count(AsyncJob.id).label('count')
        ).filter(
            AsyncJob.org_id == current_user.org_id,
            AsyncJob.created_at >= thirty_days_ago
        ).group_by(AsyncJob.status).all()
        
        # Get FHIR API call statistics
        from models import FHIRApiCall
        api_stats = db.session.query(
            db.func.date_trunc('day', FHIRApiCall.called_at).label('day'),
            db.func.count(FHIRApiCall.id).label('calls')
        ).filter(
            FHIRApiCall.org_id == current_user.org_id,
            FHIRApiCall.called_at >= thirty_days_ago
        ).group_by(db.func.date_trunc('day', FHIRApiCall.called_at)).all()
        
        return jsonify({
            'success': True,
            'job_stats': {status: count for status, count in stats},
            'api_call_stats': [
                {'date': day.isoformat(), 'calls': calls} 
                for day, calls in api_stats
            ]
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get statistics: {str(e)}'}), 500