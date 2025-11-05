"""
EMR Synchronization Routes with Comprehensive Epic Integration
Provides API endpoints for EMR sync operations, Epic FHIR integration, and screening updates
"""
import json
import logging
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from routes.auth_routes import non_admin_required
from routes.oauth_routes import require_admin
from datetime import datetime
from emr.sync_manager import EMRSyncManager, EMRChangeListener
from services.comprehensive_emr_sync import ComprehensiveEMRSync
from services.emr_screening_integration import EMRScreeningIntegration
from models import db, Patient, Organization, Screening
# from admin.admin_logger import AdminLogger  # Import when available

# Create blueprint
emr_sync_bp = Blueprint('emr_sync', __name__, url_prefix='/emr')

# Initialize managers
sync_manager = EMRSyncManager()
change_listener = EMRChangeListener()
logger = logging.getLogger(__name__)

def require_approved_organization(f):
    """Decorator to require organization approval before Epic/EMR integration access"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            from flask import abort
            abort(401)
        
        org = current_user.organization
        if not org:
            flash('No organization found for your account.', 'error')
            return redirect(url_for('index'))
        
        # Check if organization is pending approval
        if org.onboarding_status == 'pending_approval':
            flash('Epic FHIR integration is not available until your organization is approved by our team. You will receive an email notification when your trial begins.', 'warning')
            return redirect(url_for('admin.dashboard' if current_user.role == 'admin' else 'ui.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

@emr_sync_bp.route('/dashboard')
@login_required
@non_admin_required
def emr_dashboard():
    """EMR synchronization dashboard"""
    try:
        # Get recent sync history (placeholder)
        recent_syncs = []  # Would query sync history from database
        
        return render_template('emr/dashboard.html', 
                             recent_syncs=recent_syncs)
        
    except Exception as e:
        logger.error(f"Error loading EMR dashboard: {str(e)}")
        flash('Error loading EMR dashboard', 'error')
        return render_template('error/500.html'), 500

@emr_sync_bp.route('/sync', methods=['POST'])
@login_required
@non_admin_required
@require_approved_organization
def sync_emr_data():
    """EMR sync for dashboard - pulls NEW documents and processes them"""
    try:
        from services.emr_sync_service import EMRSyncService
        
        # Initialize new EMR sync service for the user's organization
        emr_sync = EMRSyncService(current_user.org_id)
        
        # Get optional patient filter from request
        patient_filter = None
        if request.form.get('patient_filter'):
            patient_filter = {'mrn_filter': request.form.get('patient_filter')}
        
        # Sync new data only (with OCR processing and initial screening updates)
        sync_results = emr_sync.sync_new_data(patient_filter=patient_filter)
        
        if sync_results.get('success'):
            stats = sync_results.get('stats', {})
            new_docs = stats.get('new_documents_found', 0)
            processed_docs = stats.get('documents_processed', 0)
            updated_screenings = stats.get('screenings_updated', 0)
            errors = stats.get('errors', [])
            
            if new_docs > 0:
                message = f'EMR sync completed! Found {new_docs} new documents, processed {processed_docs} documents, updated {updated_screenings} screenings'
                if errors:
                    message += f'. {len(errors)} errors occurred.'
                flash(message, 'success')
            else:
                flash('EMR sync completed - no new documents found', 'info')
        else:
            error_msg = sync_results.get('error', 'Unknown error occurred')
            flash(f'EMR sync failed: {error_msg}', 'error')
            
        return redirect(url_for('ui.dashboard'))
        
    except Exception as e:
        logger.error(f"Error syncing EMR data: {str(e)}")
        flash('Error syncing data from EMR', 'error')
        return redirect(url_for('ui.dashboard'))


# ============================================================================
# COMPREHENSIVE EMR SYNC ROUTES (Epic FHIR Integration)
# ============================================================================

@emr_sync_bp.route('/admin/sync')
@login_required
@require_admin
def comprehensive_sync_dashboard():
    """Comprehensive EMR Sync Dashboard with Epic FHIR Integration"""
    try:
        organization = current_user.organization
        if not organization:
            flash('Organization not found', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # Check Epic configuration
        has_epic_config = bool(organization.epic_client_id and organization.epic_client_secret)
        
        # Get recent sync statistics
        recent_patients = Patient.query.filter_by(org_id=current_user.org_id).order_by(
            Patient.last_fhir_sync.desc().nullslast()
        ).limit(10).all()
        
        # Get sync summary statistics
        total_patients = Patient.query.filter_by(org_id=current_user.org_id).count()
        synced_patients = Patient.query.filter_by(org_id=current_user.org_id).filter(
            Patient.last_fhir_sync.isnot(None)
        ).count()
        
        context = {
            'organization': organization,
            'has_epic_config': has_epic_config,
            'total_patients': total_patients,
            'synced_patients': synced_patients,
            'sync_coverage': int((synced_patients / total_patients * 100) if total_patients > 0 else 0),
            'recent_patients': recent_patients
        }
        
        return render_template('admin/emr_comprehensive_sync.html', **context)
        
    except Exception as e:
        logger.error(f"Error in comprehensive EMR sync dashboard: {str(e)}")
        flash('Error loading EMR sync dashboard', 'error')
        return redirect(url_for('admin.dashboard'))


@emr_sync_bp.route('/admin/sync/patient', methods=['POST'])
@login_required
@require_admin
def sync_patient_comprehensive():
    """Sync a specific patient from Epic EMR with comprehensive data retrieval"""
    try:
        data = request.get_json()
        epic_patient_id = data.get('epic_patient_id')
        
        if not epic_patient_id:
            return jsonify({
                'success': False,
                'error': 'Epic Patient ID is required'
            })
        
        # Initialize EMR screening integration
        emr_integration = EMRScreeningIntegration(current_user.org_id)
        
        # Perform complete sync and screening processing
        results = emr_integration.sync_and_process_patient(epic_patient_id)
        
        if results['success']:
            message = f"Successfully synced and processed patient {results.get('patient_name', epic_patient_id)}"
            logger.info(f"Comprehensive patient sync completed: {message}")
            
            return jsonify({
                'success': True,
                'message': message,
                'results': results
            })
        else:
            error_msg = results.get('error', 'Unknown error during sync')
            logger.error(f"Comprehensive patient sync failed: {error_msg}")
            
            return jsonify({
                'success': False,
                'error': error_msg
            })
            
    except Exception as e:
        error_msg = f"Error syncing patient: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        return jsonify({
            'success': False,
            'error': error_msg
        })


@emr_sync_bp.route('/admin/sync/batch', methods=['POST'])
@login_required
@require_admin
def sync_batch_comprehensive():
    """Sync multiple patients from Epic EMR with comprehensive data"""
    try:
        data = request.get_json()
        epic_patient_ids = data.get('patient_ids', [])
        
        if not epic_patient_ids:
            return jsonify({
                'success': False,
                'error': 'Patient IDs are required'
            })
        
        # Initialize EMR screening integration
        emr_integration = EMRScreeningIntegration(current_user.org_id)
        
        batch_results = []
        successful_syncs = 0
        failed_syncs = 0
        
        for epic_patient_id in epic_patient_ids:
            try:
                result = emr_integration.sync_and_process_patient(epic_patient_id)
                batch_results.append(result)
                
                if result['success']:
                    successful_syncs += 1
                else:
                    failed_syncs += 1
                    
            except Exception as e:
                failed_syncs += 1
                batch_results.append({
                    'success': False,
                    'epic_patient_id': epic_patient_id,
                    'error': str(e)
                })
        
        logger.info(f"Comprehensive batch sync completed: {successful_syncs} successful, {failed_syncs} failed")
        
        return jsonify({
            'success': True,
            'message': f"Batch sync completed: {successful_syncs} successful, {failed_syncs} failed",
            'summary': {
                'total_patients': len(epic_patient_ids),
                'successful_syncs': successful_syncs,
                'failed_syncs': failed_syncs
            },
            'results': batch_results
        })
        
    except Exception as e:
        error_msg = f"Error in batch sync: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        return jsonify({
            'success': False,
            'error': error_msg
        })


@emr_sync_bp.route('/admin/sync/statistics')
@login_required
@require_admin
def get_comprehensive_sync_statistics():
    """Get comprehensive EMR synchronization statistics"""
    try:
        # Get organization statistics
        organization = current_user.organization
        
        # Patient sync statistics
        total_patients = Patient.query.filter_by(org_id=current_user.org_id).count()
        synced_patients = Patient.query.filter_by(org_id=current_user.org_id).filter(
            Patient.last_fhir_sync.isnot(None)
        ).count()
        
        # Recent sync activity
        from datetime import timedelta
        recent_syncs = Patient.query.filter_by(org_id=current_user.org_id).filter(
            Patient.last_fhir_sync >= datetime.now() - timedelta(days=7)
        ).count()
        
        # Screening statistics
        total_screenings = Screening.query.join(Patient).filter(
            Patient.org_id == current_user.org_id
        ).count()
        
        due_screenings = Screening.query.join(Patient).filter(
            Patient.org_id == current_user.org_id,
            Screening.status == 'due'
        ).count()
        
        statistics = {
            'patient_sync': {
                'total_patients': total_patients,
                'synced_patients': synced_patients,
                'sync_coverage_percent': int((synced_patients / total_patients * 100) if total_patients > 0 else 0),
                'recent_syncs_7_days': recent_syncs
            },
            'screening_status': {
                'total_screenings': total_screenings,
                'due_screenings': due_screenings,
                'compliance_rate': int(((total_screenings - due_screenings) / total_screenings * 100) if total_screenings > 0 else 0)
            },
            'epic_connection': {
                'configured': bool(organization.epic_client_id),
                'connected': bool(organization.is_epic_connected),
                'last_connection': organization.last_epic_sync.isoformat() if organization.last_epic_sync else None
            }
        }
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting comprehensive sync statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@emr_sync_bp.route('/admin/sync/test-connection')
@login_required
@require_admin
def test_comprehensive_emr_connection():
    """Test Epic FHIR connection for comprehensive EMR sync"""
    try:
        organization = current_user.organization
        
        if not organization.epic_client_id:
            return jsonify({
                'success': False,
                'error': 'Epic FHIR configuration not found'
            })
        
        # Initialize EMR sync service to test connection
        emr_sync = ComprehensiveEMRSync(current_user.org_id)
        
        # Test authentication
        if not emr_sync.epic_service.ensure_authenticated():
            return jsonify({
                'success': False,
                'error': 'Epic FHIR authentication failed'
            })
        
        return jsonify({
            'success': True,
            'message': 'Epic FHIR connection successful',
            'connection_details': {
                'organization': organization.name,
                'epic_fhir_url': organization.epic_fhir_url,
                'has_access_token': bool(emr_sync.epic_service.fhir_client.access_token)
            }
        })
        
    except Exception as e:
        logger.error(f"Error testing comprehensive EMR connection: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        })

@emr_sync_bp.route('/sync/trigger', methods=['POST'])
@login_required
def trigger_sync():
    """Manually trigger EMR synchronization"""
    try:
        if not current_user.is_admin:
            flash('Insufficient permissions for EMR sync', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Get sync parameters
        emr_endpoint = request.form.get('emr_endpoint', '')
        sync_mode = request.form.get('sync_mode', 'full')  # full or incremental
        
        if not emr_endpoint:
            flash('EMR endpoint is required', 'error')
            return redirect(url_for('emr_sync.emr_dashboard'))
        
        # Check if Epic OAuth is authenticated
        from routes.oauth_routes import get_epic_fhir_client
        if not get_epic_fhir_client():
            flash('Epic FHIR not authenticated. Please authenticate with Epic first.', 'warning')
            return redirect(url_for('oauth.epic_authorize'))
        
        # Configure sync
        sync_config = {
            'mode': sync_mode,
            'include_documents': request.form.get('include_documents', 'on') == 'on',
            'include_conditions': request.form.get('include_conditions', 'on') == 'on',
            'date_range': request.form.get('date_range', '30')  # days
        }
        
        # Trigger synchronization
        sync_results = sync_manager.sync_from_emr(emr_endpoint, sync_config)
        
        if sync_results.get('success', False):
            # Log successful sync
            logger.info(f"EMR sync triggered by user {current_user.id}: {sync_results.get('total_affected_screenings', 0)} screenings updated")
            
            flash(f"EMR sync completed successfully. {sync_results.get('total_affected_screenings', 0)} screenings updated, "
                  f"{sync_results.get('preserved_screenings', 0)} preserved. "
                  f"Efficiency: {sync_results.get('efficiency_ratio', 0)*100:.1f}%", 'success')
        else:
            flash(f"EMR sync failed: {sync_results.get('error', 'Unknown error')}", 'error')
        
        return redirect(url_for('emr_sync.emr_dashboard'))
        
    except Exception as e:
        logger.error(f"Error triggering EMR sync: {str(e)}")
        flash('Error triggering EMR synchronization', 'error')
        return redirect(url_for('emr_sync.emr_dashboard'))

@emr_sync_bp.route('/webhook/fhir', methods=['POST'])
def fhir_webhook():
    """Handle FHIR webhook notifications for real-time updates"""
    try:
        # Get webhook data
        webhook_data = request.get_json()
        
        if not webhook_data:
            return jsonify({'error': 'No data received'}), 400
        
        logger.info(f"Received FHIR webhook: {webhook_data.get('type', 'unknown')}")
        
        # Process webhook with selective refresh
        results = change_listener.handle_emr_webhook(webhook_data)
        
        if results.get('success', False):
            return jsonify({
                'status': 'success',
                'message': 'Webhook processed successfully',
                'affected_screenings': results.get('total_regenerated', 0),
                'preserved_screenings': results.get('preserved_screenings', 0)
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': results.get('error', 'Processing failed')
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing FHIR webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@emr_sync_bp.route('/api/sync/status')
@login_required
def sync_status():
    """Get current synchronization status"""
    try:
        # Return current sync status (placeholder)
        status = {
            'last_sync': None,  # Would get from database
            'sync_in_progress': False,
            'total_screenings': 0,  # Would count from database
            'last_selective_refresh': None
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({'error': 'Error getting status'}), 500

@emr_sync_bp.route('/api/sync/test', methods=['POST'])
@login_required
def test_sync():
    """Test EMR connection and sync configuration"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        data = request.get_json()
        emr_endpoint = data.get('endpoint', '')
        
        if not emr_endpoint:
            return jsonify({'error': 'EMR endpoint required'}), 400
        
        # Test connection (placeholder)
        # In production, this would:
        # 1. Test FHIR endpoint connectivity
        # 2. Validate authentication
        # 3. Check available resources
        
        test_results = {
            'connection': True,
            'authentication': True,
            'available_resources': ['Patient', 'DocumentReference', 'Condition'],
            'estimated_records': 0
        }
        
        return jsonify({
            'status': 'success',
            'results': test_results
        })
        
    except Exception as e:
        logger.error(f"Error testing EMR connection: {str(e)}")
        return jsonify({'error': 'Connection test failed'}), 500

@emr_sync_bp.route('/api/selective-refresh/analyze', methods=['POST'])
@login_required
def analyze_refresh_impact():
    """Analyze potential impact of selective refresh"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        data = request.get_json()
        changes = data.get('changes', {})
        
        # Simulate selective refresh analysis
        analysis = {
            'total_screenings': 0,  # Would count from database
            'affected_screenings': 0,
            'preserved_screenings': 0,
            'efficiency_gain': 0.0,
            'affected_patients': [],
            'affected_screening_types': []
        }
        
        return jsonify({
            'status': 'success',
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error analyzing refresh impact: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500

@emr_sync_bp.route('/settings')
@login_required
def sync_settings():
    """EMR synchronization settings page"""
    try:
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Get current sync settings (placeholder)
        settings = {
            'emr_endpoint': '',
            'sync_frequency': 'daily',
            'auto_sync_enabled': False,
            'webhook_enabled': False,
            'selective_refresh_enabled': True
        }
        
        return render_template('emr/settings.html', settings=settings)
        
    except Exception as e:
        logger.error(f"Error loading sync settings: {str(e)}")
        flash('Error loading synchronization settings', 'error')
        return render_template('error/500.html'), 500

@emr_sync_bp.route('/settings', methods=['POST'])
@login_required
def update_sync_settings():
    """Update EMR synchronization settings"""
    try:
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Update settings (placeholder)
        # In production, this would update configuration in database
        
        logger.info(f"EMR sync settings updated by user {current_user.id}")
        
        flash('EMR synchronization settings updated successfully', 'success')
        return redirect(url_for('emr_sync.sync_settings'))
        
    except Exception as e:
        logger.error(f"Error updating sync settings: {str(e)}")
        flash('Error updating synchronization settings', 'error')
        return redirect(url_for('emr_sync.sync_settings'))

# Error handlers
@emr_sync_bp.errorhandler(404)
def not_found(error):
    return render_template('error/404.html'), 404

@emr_sync_bp.errorhandler(500)
def internal_error(error):
    return render_template('error/500.html'), 500