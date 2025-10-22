"""
Epic Registration Routes
Handles Epic SMART on FHIR app registration workflow
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import logging

# Create blueprint
epic_registration_bp = Blueprint('epic_registration', __name__)

logger = logging.getLogger(__name__)

@epic_registration_bp.route('/admin/epic/registration')
@login_required
def epic_registration():
    """Epic Registration Management Page"""
    try:
        organization = current_user.organization
        if not organization:
            flash('Organization not found', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # Get current Epic registration status
        registration_status = organization.epic_registration_status or 'not_started'
        
        context = {
            'organization': organization,
            'registration_status': registration_status,
            'epic_scopes': [
                'patient/Patient.read',
                'patient/Observation.read',
                'patient/Condition.read',
                'patient/MedicationRequest.read',
                'patient/DocumentReference.read',
                'patient/DocumentReference.write',
                'patient/Appointment.read',
                'offline_access'
            ]
        }
        
        return render_template('admin/epic_registration.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading Epic registration page: {str(e)}")
        flash('Error loading Epic registration page', 'error')
        return redirect(url_for('admin.dashboard'))

@epic_registration_bp.route('/admin/epic/registration/update', methods=['POST'])
@login_required
def update_epic_registration():
    """Update Epic Registration Information"""
    try:
        organization = current_user.organization
        if not organization:
            return jsonify({'success': False, 'error': 'Organization not found'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Update Epic registration fields
        if 'epic_client_id' in data:
            organization.epic_client_id = data['epic_client_id']
        if 'epic_client_secret' in data:
            organization.epic_client_secret = data['epic_client_secret']
        if 'epic_fhir_url' in data:
            organization.epic_fhir_url = data['epic_fhir_url']
        if 'epic_registration_status' in data:
            organization.epic_registration_status = data['epic_registration_status']
            if data['epic_registration_status'] == 'approved':
                organization.epic_registration_date = datetime.utcnow()
        
        # Import here to avoid circular imports
        from app import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Epic registration information updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating Epic registration: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to update registration: {str(e)}'
        })

@epic_registration_bp.route('/admin/epic/registration/test-connection', methods=['POST'])
@login_required
def test_epic_connection():
    """Test Epic FHIR Connection"""
    try:
        organization = current_user.organization
        if not organization or not organization.epic_client_id:
            return jsonify({
                'success': False,
                'error': 'Epic Client ID required for connection testing'
            })
        
        # Import here to avoid circular imports
        try:
            from services.epic_fhir_service import EpicFHIRService
            
            # Check if Epic is configured first
            if not organization.epic_client_id:
                return jsonify({
                    'success': False,
                    'error': 'Epic Client ID not configured. Please enter your Epic credentials first.'
                })
            
            if not organization.epic_fhir_url:
                return jsonify({
                    'success': False,
                    'error': 'Epic FHIR URL not configured. Please enter your Epic FHIR Base URL.'
                })
            
            # Initialize Epic service
            epic_service = EpicFHIRService(organization.id)
            
            if not epic_service.fhir_client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize Epic FHIR client. Please check your Epic configuration and try again.'
                })
            
            # Test basic connection (without full OAuth for now)
            # In a real implementation, this would test the authorization URL generation
            auth_url, state = epic_service.fhir_client.get_authorization_url()
            
            if auth_url and 'epic.com' in auth_url:
                logger.info(f"Epic connection test successful for organization {organization.name}")
                return jsonify({
                    'success': True,
                    'message': 'Epic connection configuration appears valid',
                    'auth_url': auth_url[:100] + '...'  # Truncated for security
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate valid Epic authorization URL'
                })
                
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Epic FHIR service not available'
            })
            
    except Exception as e:
        logger.error(f"Epic connection test failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        })

@epic_registration_bp.route('/admin/epic/registration/appointment-prioritization', methods=['POST'])
@login_required
def update_appointment_prioritization():
    """Update Appointment Prioritization Settings"""
    try:
        organization = current_user.organization
        if not organization:
            return jsonify({'success': False, 'error': 'Organization not found'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Update appointment prioritization settings
        if 'appointment_based_prioritization' in data:
            organization.appointment_based_prioritization = bool(data['appointment_based_prioritization'])
        
        if 'prioritization_window_days' in data:
            window_days = int(data['prioritization_window_days'])
            if window_days < 1 or window_days > 90:
                return jsonify({'success': False, 'error': 'Window days must be between 1 and 90'})
            organization.prioritization_window_days = window_days
        
        if 'process_non_scheduled_patients' in data:
            organization.process_non_scheduled_patients = bool(data['process_non_scheduled_patients'])
        
        # Import here to avoid circular imports
        from app import db
        db.session.commit()
        
        logger.info(f"Appointment prioritization settings updated for organization {organization.name}")
        
        return jsonify({
            'success': True,
            'message': 'Appointment prioritization settings updated successfully',
            'settings': {
                'appointment_based_prioritization': organization.appointment_based_prioritization,
                'prioritization_window_days': organization.prioritization_window_days,
                'process_non_scheduled_patients': organization.process_non_scheduled_patients,
                'last_appointment_sync': organization.last_appointment_sync.isoformat() if organization.last_appointment_sync else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating appointment prioritization: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to update settings: {str(e)}'
        })

@epic_registration_bp.route('/admin/epic/registration/prioritization-stats', methods=['GET'])
@login_required
def get_prioritization_stats():
    """Get Appointment Prioritization Statistics"""
    try:
        organization = current_user.organization
        if not organization:
            return jsonify({'success': False, 'error': 'Organization not found'})
        
        from services.appointment_prioritization import AppointmentBasedPrioritization
        
        prioritization_service = AppointmentBasedPrioritization(organization.id)
        stats = prioritization_service.get_prioritization_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting prioritization stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@epic_registration_bp.route('/admin/epic/reset-credentials', methods=['POST'])
@login_required
def reset_epic_credentials():
    """
    Reset corrupted Epic credentials
    Clears epic_client_secret and epic_credentials tokens that cannot be decrypted
    """
    try:
        organization = current_user.organization
        if not organization:
            return jsonify({'success': False, 'error': 'Organization not found'})
        
        # Import here to avoid circular imports
        from app import db
        from models import EpicCredentials
        
        # Clear epic_client_secret (will be re-entered by user)
        organization._epic_client_secret = None
        
        # Clear all epic_credentials tokens for this organization
        EpicCredentials.query.filter_by(org_id=organization.id).delete()
        
        # Reset Epic connection status
        organization.is_epic_connected = False
        organization.last_epic_error = 'Credentials reset due to decryption failure'
        organization.epic_token_expiry = None
        
        db.session.commit()
        
        logger.info(f"Epic credentials reset for organization {organization.name}")
        
        return jsonify({
            'success': True,
            'message': 'Epic credentials have been reset. Please re-enter your Epic Client ID and Client Secret to reconnect.'
        })
        
    except Exception as e:
        logger.error(f"Error resetting Epic credentials: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to reset credentials: {str(e)}'
        })