"""
Async Processing Routes for HealthPrepV2
Handles background job management and status monitoring.

NOTE: Batch patient sync functionality has been consolidated into
comprehensive_emr_sync.py which is the authoritative EMR ingestion path.
The async batch sync routes were removed as they had no UI templates
and used a legacy sync path.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from models import db, Patient, Organization, ScreeningType, AsyncJob
from services.async_processing import get_async_processing_service
from services.enhanced_audit_logging import log_fhir_access, audit_logger
from routes.auth_routes import admin_required

async_bp = Blueprint('async', __name__, url_prefix='/async')


# NOTE: The following routes were removed as they had no UI templates:
# - /async/dashboard - rendered async/dashboard.html (does not exist)
# - /async/batch-sync - rendered async/batch_sync.html (does not exist)
# - /async/jobs - rendered async/job_list.html (does not exist)
# - /async/job/<job_id> - rendered async/job_detail.html (does not exist)
# - /async/settings - rendered async/settings.html (does not exist)
# 
# The batch patient sync also used a legacy sync path that has been
# superseded by comprehensive_emr_sync.py.


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


@async_bp.route('/api/jobs')
@login_required
def api_list_jobs():
    """API endpoint to list jobs for the organization (JSON response)"""
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
        
        return jsonify({
            'success': True,
            'jobs': [{'job_id': j.job_id, 'status': j.status, 'job_type': j.job_type, 
                     'created_at': j.created_at.isoformat() if j.created_at else None} for j in jobs.items],
            'total': jobs.total,
            'page': page,
            'per_page': per_page
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to list jobs: {str(e)}'}), 500


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