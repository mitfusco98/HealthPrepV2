"""
Epic Admin Routes - Connection Status & Management
Implements blueprint admin interface for Epic connection management
"""

from flask import Blueprint, request, jsonify, render_template, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging

from models import Organization, db
from services.epic_connection_monitor import get_connection_monitor
from emr.fhir_client import FHIRClient

# Create blueprint
epic_admin_bp = Blueprint('epic_admin', __name__, url_prefix='/admin/epic')
logger = logging.getLogger(__name__)

@epic_admin_bp.route('/check-connection/<int:user_id>')
@login_required
def check_connection(user_id):
    """
    Manual connection check endpoint (per blueprint)
    Allows admin to trigger connection status refresh
    """
    try:
        # Ensure user can access this organization
        if not current_user.is_root_admin and current_user.id != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get user's organization
        user_org = current_user.organization if not current_user.is_root_admin else Organization.query.get(user_id)
        if not user_org:
            return jsonify({'success': False, 'error': 'Organization not found'}), 404
        
        # Use connection monitor to check status
        monitor = get_connection_monitor()
        action_taken = monitor.check_organization_connection(user_org)
        
        # Get updated status
        status = user_org.get_epic_connection_status()
        
        logger.info(f"Manual connection check for org {user_org.name}: {status['status_message']}")
        
        return jsonify({
            'success': True,
            'action_taken': action_taken,
            'status': status,
            'message': f"Connection check completed: {status['status_message']}"
        })
        
    except Exception as e:
        logger.error(f"Error checking connection for user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@epic_admin_bp.route('/test-connection/<int:user_id>')
@login_required
def test_connection(user_id):
    """
    Test Epic FHIR connection with actual API call
    Provides real connectivity verification beyond token status
    """
    try:
        # Ensure user can access this organization
        if not current_user.is_root_admin and current_user.id != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get user's organization
        user_org = current_user.organization if not current_user.is_root_admin else Organization.query.get(user_id)
        if not user_org:
            return jsonify({'success': False, 'error': 'Organization not found'}), 404
        
        # Get Epic credentials
        epic_creds = user_org.epic_credentials
        if not epic_creds:
            return jsonify({'success': False, 'error': 'No Epic credentials configured'}), 400
        
        latest_cred = max(epic_creds, key=lambda c: c.updated_at) if epic_creds else None
        if not latest_cred or latest_cred.is_expired:
            return jsonify({'success': False, 'error': 'Epic credentials expired'}), 400
        
        # Create FHIR client and test connection
        epic_config = user_org.get_epic_fhir_config()
        fhir_client = FHIRClient(
            organization_config=epic_config,
            organization=user_org
        )
        
        # Set current tokens
        fhir_client.set_tokens(
            access_token=latest_cred.access_token,
            refresh_token=latest_cred.refresh_token,
            expires_in=(latest_cred.token_expires_at - datetime.utcnow()).total_seconds() if latest_cred.token_expires_at else 0
        )
        
        # Test with a simple Patient search (should work with minimal scopes)
        test_result = fhir_client._api_get_with_retry(
            url=f"{fhir_client.base_url}Patient",
            params={'_count': '1'}  # Just get 1 record for testing
        )
        
        if test_result:
            logger.info(f"Epic connection test successful for org {user_org.name}")
            return jsonify({
                'success': True,
                'message': 'Epic FHIR connection test successful',
                'endpoint': fhir_client.base_url,
                'records_available': test_result.get('total', 0) if 'total' in test_result else 'unknown'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Connection test failed - no response from Epic FHIR endpoint'
            })
        
    except Exception as e:
        logger.error(f"Error testing connection for user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@epic_admin_bp.route('/clear-error/<int:user_id>', methods=['POST'])
@login_required
def clear_error(user_id):
    """
    Clear Epic connection error (per blueprint)
    Allows admin to manually clear error state for retry
    """
    try:
        # Ensure user can access this organization
        if not current_user.is_root_admin and current_user.id != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get user's organization
        user_org = current_user.organization if not current_user.is_root_admin else Organization.query.get(user_id)
        if not user_org:
            return jsonify({'success': False, 'error': 'Organization not found'}), 404
        
        # Clear connection error
        user_org.clear_epic_connection_error()
        
        logger.info(f"Cleared Epic connection error for org {user_org.name}")
        
        return jsonify({
            'success': True,
            'message': 'Epic connection error cleared successfully'
        })
        
    except Exception as e:
        logger.error(f"Error clearing connection error for user {user_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@epic_admin_bp.route('/connection-report')
@login_required
def connection_report():
    """
    Generate comprehensive Epic connection status report
    For root admin monitoring across all organizations
    """
    try:
        if not current_user.is_root_admin:
            return jsonify({'success': False, 'error': 'Root admin access required'}), 403
        
        # Generate connection report
        monitor = get_connection_monitor()
        report = monitor.generate_connection_report()
        
        logger.info(f"Generated Epic connection report: {report.get('summary', {})}")
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"Error generating connection report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@epic_admin_bp.route('/organizations-needing-attention')
@login_required
def organizations_needing_attention():
    """
    Get list of organizations that need admin attention
    For proactive notification system
    """
    try:
        if not current_user.is_root_admin:
            return jsonify({'success': False, 'error': 'Root admin access required'}), 403
        
        monitor = get_connection_monitor()
        attention_needed = monitor.get_organizations_needing_attention()
        
        return jsonify({
            'success': True,
            'organizations': attention_needed,
            'count': len(attention_needed)
        })
        
    except Exception as e:
        logger.error(f"Error getting organizations needing attention: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper function to get Epic status for templates
def get_epic_status_for_template(organization):
    """Get Epic connection status formatted for template display"""
    if not organization:
        return {
            'is_connected': False,
            'status_class': 'danger',
            'status_message': 'No organization found',
            'action_required': True,
            'last_sync': None,
            'last_error': 'Organization not found',
            'token_expiry': None,
            'retry_count': 0
        }
    
    return organization.get_epic_connection_status()