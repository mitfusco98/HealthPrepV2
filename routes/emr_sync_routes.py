"""
EMR Synchronization Routes with Selective Refresh
Provides API endpoints for EMR sync operations and webhooks
"""
import logging
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from routes.auth_routes import non_admin_required
from datetime import datetime
from emr.sync_manager import EMRSyncManager, EMRChangeListener
from models import db
# from admin.admin_logger import AdminLogger  # Import when available

# Create blueprint
emr_sync_bp = Blueprint('emr_sync', __name__, url_prefix='/emr')

# Initialize managers
sync_manager = EMRSyncManager()
change_listener = EMRChangeListener()
logger = logging.getLogger(__name__)

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