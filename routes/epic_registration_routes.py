"""
Epic App Registration Management Routes
Handles Epic app registration, configuration, and testing
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import Forbidden

from models import db, Organization
from functools import wraps
from flask import abort

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin_user():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

logger = logging.getLogger(__name__)
epic_registration_bp = Blueprint('epic_registration', __name__, url_prefix='/admin/epic')


@epic_registration_bp.route('/registration')
@login_required
@admin_required
def epic_registration():
    """Epic App Registration Management Interface"""
    try:
        # Ensure user has organization context
        if not current_user.organization:
            flash('Organization context required for Epic registration', 'error')
            return redirect(url_for('admin.dashboard'))
        
        return render_template('admin/epic_registration.html')
        
    except Exception as e:
        logger.error(f"Error loading Epic registration page: {str(e)}")
        flash('Error loading Epic registration page', 'error')
        return redirect(url_for('admin.dashboard'))


@epic_registration_bp.route('/update-registration', methods=['POST'])
@login_required
@admin_required
def update_epic_registration():
    """Update Epic App Registration Details"""
    try:
        organization = current_user.organization
        if not organization:
            flash('Organization context required', 'error')
            return redirect(url_for('admin.dashboard'))
        
        # Update Epic app registration fields
        organization.epic_app_name = request.form.get('epic_app_name', '').strip()
        organization.epic_app_description = request.form.get('epic_app_description', '').strip()
        organization.epic_client_id = request.form.get('epic_client_id', '').strip()
        organization.epic_environment = request.form.get('epic_environment', 'sandbox')
        organization.epic_registration_status = request.form.get('epic_registration_status', 'not_started')
        
        # Handle redirect URIs (convert textarea to JSON list)
        redirect_uris_text = request.form.get('epic_redirect_uris', '').strip()
        if redirect_uris_text:
            redirect_uris = [uri.strip() for uri in redirect_uris_text.split('\n') if uri.strip()]
            organization.epic_redirect_uris = json.dumps(redirect_uris)
        else:
            organization.epic_redirect_uris = None
        
        # Update registration date if status changed to pending/approved
        if organization.epic_registration_status in ['pending', 'approved'] and not organization.epic_registration_date:
            organization.epic_registration_date = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Updated Epic registration for organization {organization.name}")
        flash('Epic registration details updated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error updating Epic registration: {str(e)}")
        db.session.rollback()
        flash('Error updating Epic registration details', 'error')
    
    return redirect(url_for('epic_registration.epic_registration'))


@epic_registration_bp.route('/test-connection', methods=['POST'])
@login_required
@admin_required
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
        from services.epic_fhir_service import EpicFHIRService
        
        # Initialize Epic service
        epic_service = EpicFHIRService(organization.id)
        
        if not epic_service.fhir_client:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize Epic FHIR client'
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
            
    except Exception as e:
        logger.error(f"Epic connection test failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        })


@epic_registration_bp.route('/registration-guide')
@login_required
@admin_required
def registration_guide():
    """Epic App Registration Step-by-Step Guide"""
    try:
        # Get current organization's Epic configuration
        organization = current_user.organization
        
        # Prepare guide data based on organization's current status
        guide_data = {
            'organization': organization,
            'required_scopes': [
                'openid',
                'fhirUser', 
                'patient/Patient.read',
                'patient/Condition.read',
                'patient/Observation.read',
                'patient/DocumentReference.read',
                'patient/DocumentReference.write',
                'user/DocumentReference.write',
                'offline_access'
            ],
            'redirect_uris': [
                f"{request.host_url}fhir/epic-callback",
                f"{request.host_url}fhir/oauth-callback"
            ]
        }
        
        return render_template('admin/epic_registration_guide.html', **guide_data)
        
    except Exception as e:
        logger.error(f"Error loading Epic registration guide: {str(e)}")
        flash('Error loading registration guide', 'error')
        return redirect(url_for('epic_registration.epic_registration'))


@epic_registration_bp.route('/scope-validator', methods=['POST'])
@login_required
@admin_required
def validate_epic_scopes():
    """Validate Epic Scopes Against HealthPrep Requirements"""
    try:
        json_data = request.get_json() or {}
        provided_scopes = json_data.get('scopes', [])
        
        # Required scopes for HealthPrep functionality
        required_scopes = [
            'openid',
            'fhirUser',
            'patient/Patient.read',
            'patient/Condition.read', 
            'patient/Observation.read',
            'patient/DocumentReference.read',
            'patient/DocumentReference.write',  # Critical for writing prep sheets
            'offline_access'  # For refresh tokens
        ]
        
        # Recommended additional scopes
        recommended_scopes = [
            'user/Patient.read',
            'user/Condition.read',
            'user/Observation.read',
            'user/DocumentReference.read',
            'user/DocumentReference.write',
            'user/Encounter.read'
        ]
        
        # Validate scopes
        missing_required = [scope for scope in required_scopes if scope not in provided_scopes]
        missing_recommended = [scope for scope in recommended_scopes if scope not in provided_scopes]
        extra_scopes = [scope for scope in provided_scopes if scope not in required_scopes + recommended_scopes]
        
        validation_result = {
            'is_valid': len(missing_required) == 0,
            'missing_required': missing_required,
            'missing_recommended': missing_recommended,
            'extra_scopes': extra_scopes,
            'total_score': max(0, 100 - (len(missing_required) * 20) - (len(missing_recommended) * 5))
        }
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating Epic scopes: {str(e)}")
        return jsonify({
            'is_valid': False,
            'error': str(e)
        }), 500