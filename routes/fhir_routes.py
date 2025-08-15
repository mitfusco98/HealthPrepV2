"""
FHIR Integration Routes
Handles Epic interoperability and FHIR mapping functionality
"""
import json
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, ScreeningType, Organization
from utils.fhir_mapping import FHIRResourceMapper, ScreeningTypeFHIREnhancer
from emr.epic_integration import EpicScreeningIntegration

logger = logging.getLogger(__name__)
fhir_bp = Blueprint('fhir', __name__, url_prefix='/fhir')


@fhir_bp.route('/screening-mapping', methods=['GET'])
@login_required
def screening_mapping():
    """Display FHIR mapping for screening types"""
    try:
        screening_types = ScreeningType.query.filter_by(org_id=current_user.org_id, is_active=True).all()
        
        # Get FHIR mapping statistics
        total_screenings = len(screening_types)
        mapped_screenings = sum(1 for st in screening_types if st.fhir_search_params)
        
        mapping_stats = {
            'total_screenings': total_screenings,
            'mapped_screenings': mapped_screenings,
            'mapping_percentage': round((mapped_screenings / total_screenings * 100) if total_screenings > 0 else 0)
        }
        
        return render_template('fhir/screening_mapping.html', 
                             screening_types=screening_types,
                             mapping_stats=mapping_stats)
        
    except Exception as e:
        logger.error(f"Error in screening mapping view: {str(e)}")
        flash(f"Error loading FHIR mapping: {str(e)}", 'error')
        return redirect(url_for('admin.admin_dashboard'))


@fhir_bp.route('/generate-mappings', methods=['POST'])
@login_required
def generate_mappings():
    """Generate FHIR mappings for screening types"""
    try:
        screening_type_ids = request.json.get('screening_type_ids', [])
        
        if not screening_type_ids:
            # Generate for all active screening types
            screening_types = ScreeningType.query.filter_by(
                org_id=current_user.org_id, 
                is_active=True
            ).all()
        else:
            # Generate for specific screening types
            screening_types = ScreeningType.query.filter(
                ScreeningType.id.in_(screening_type_ids),
                ScreeningType.org_id == current_user.org_id
            ).all()
        
        updated_count = 0
        errors = []
        
        for screening_type in screening_types:
            try:
                enhanced_data = screening_type.generate_fhir_mappings()
                db.session.add(screening_type)
                updated_count += 1
                
                logger.info(f"Generated FHIR mappings for: {screening_type.name}")
                
            except Exception as e:
                error_msg = f"Error generating FHIR mappings for {screening_type.name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        db.session.commit()
        
        response_data = {
            'success': True,
            'updated_count': updated_count,
            'total_count': len(screening_types),
            'errors': errors
        }
        
        if errors:
            response_data['message'] = f"Generated FHIR mappings for {updated_count} screening types with {len(errors)} errors"
        else:
            response_data['message'] = f"Successfully generated FHIR mappings for {updated_count} screening types"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error generating FHIR mappings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@fhir_bp.route('/screening-type/<int:screening_type_id>/mapping', methods=['GET'])
@login_required
def screening_type_mapping(screening_type_id):
    """Get detailed FHIR mapping for a specific screening type"""
    try:
        screening_type = ScreeningType.query.filter_by(
            id=screening_type_id,
            org_id=current_user.org_id
        ).first_or_404()
        
        # Generate FHIR mappings if not already present
        if not screening_type.fhir_search_params:
            enhanced_data = screening_type.generate_fhir_mappings()
            db.session.add(screening_type)
            db.session.commit()
        
        # Get parsed mappings
        fhir_params = screening_type.get_fhir_search_params()
        epic_context = screening_type.get_epic_query_context()
        condition_codes = screening_type.get_fhir_condition_codes()
        observation_codes = screening_type.get_fhir_observation_codes()
        
        mapping_data = {
            'screening_type': {
                'id': screening_type.id,
                'name': screening_type.name,
                'keywords': screening_type.keywords_list,
                'trigger_conditions': screening_type.trigger_conditions_list,
                'eligible_genders': screening_type.eligible_genders,
                'min_age': screening_type.min_age,
                'max_age': screening_type.max_age,
                'frequency_years': screening_type.frequency_years
            },
            'fhir_mappings': {
                'search_params': fhir_params,
                'epic_context': epic_context,
                'condition_codes': condition_codes,
                'observation_codes': observation_codes
            }
        }
        
        return jsonify(mapping_data)
        
    except Exception as e:
        logger.error(f"Error getting screening type mapping: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@fhir_bp.route('/epic-config', methods=['GET'])
@login_required
def epic_config():
    """Display Epic FHIR configuration for organization"""
    try:
        if not current_user.org_id:
            flash("No organization associated with user", 'error')
            return redirect(url_for('admin.admin_dashboard'))
            
        organization = Organization.query.get(current_user.org_id)
        
        if not organization:
            flash("Organization not found", 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        epic_config = organization.get_epic_config()
        
        return render_template('fhir/epic_config.html',
                             organization=organization,
                             epic_config=epic_config)
        
    except Exception as e:
        logger.error(f"Error in epic config view: {str(e)}")
        flash(f"Error loading Epic configuration: {str(e)}", 'error')
        return redirect(url_for('admin.admin_dashboard'))


@fhir_bp.route('/epic-config', methods=['POST'])
@login_required
def update_epic_config():
    """Update Epic FHIR configuration"""
    try:
        organization = Organization.query.get(current_user.org_id)
        
        if not organization:
            return jsonify({
                'success': False,
                'error': 'Organization not found'
            }), 404
        
        # Update Epic configuration
        organization.epic_client_id = request.form.get('epic_client_id', '').strip()
        organization.epic_fhir_url = request.form.get('epic_fhir_url', '').strip()
        organization.epic_environment = request.form.get('epic_environment', 'sandbox')
        
        # Note: Client secret would be handled securely in production
        # For now, we'll store it in the organization record
        epic_client_secret = request.form.get('epic_client_secret', '').strip()
        if epic_client_secret:
            organization.epic_client_secret = epic_client_secret
        
        db.session.commit()
        
        flash("Epic FHIR configuration updated successfully", 'success')
        return redirect(url_for('fhir.epic_config'))
        
    except Exception as e:
        logger.error(f"Error updating Epic configuration: {str(e)}")
        flash(f"Error updating Epic configuration: {str(e)}", 'error')
        return redirect(url_for('fhir.epic_config'))


@fhir_bp.route('/test-epic-connection', methods=['POST'])
@login_required
def test_epic_connection():
    """Test Epic FHIR connection"""
    try:
        integration = EpicScreeningIntegration(current_user.org_id)
        
        # Test authentication
        if integration.fhir_client.authenticate():
            return jsonify({
                'success': True,
                'message': 'Successfully connected to Epic FHIR',
                'epic_url': integration.fhir_client.base_url,
                'environment': integration.epic_environment
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to authenticate with Epic FHIR'
            })
        
    except Exception as e:
        logger.error(f"Error testing Epic connection: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@fhir_bp.route('/screening-data/<patient_mrn>', methods=['GET'])
@login_required
def get_screening_data(patient_mrn):
    """Get Epic screening data for a patient"""
    try:
        screening_type_ids = request.args.getlist('screening_types')
        
        if not screening_type_ids:
            return jsonify({
                'success': False,
                'error': 'No screening types specified'
            }), 400
        
        # Get screening types
        screening_types = ScreeningType.query.filter(
            ScreeningType.id.in_(screening_type_ids),
            ScreeningType.org_id == current_user.org_id
        ).all()
        
        # Convert to dict format for Epic integration
        screening_data = []
        for st in screening_types:
            screening_data.append({
                'name': st.name,
                'keywords': st.keywords_list,
                'trigger_conditions': st.trigger_conditions_list,
                'eligible_genders': st.eligible_genders,
                'min_age': st.min_age,
                'max_age': st.max_age,
                'frequency_years': st.frequency_years,
                'fhir_search_params': st.fhir_search_params
            })
        
        # Get Epic data
        integration = EpicScreeningIntegration(current_user.org_id)
        epic_data = integration.get_screening_relevant_data(patient_mrn, screening_data)
        
        if not epic_data:
            return jsonify({
                'success': False,
                'error': 'No data found or Epic connection failed'
            })
        
        return jsonify({
            'success': True,
            'patient_mrn': patient_mrn,
            'epic_data': epic_data,
            'data_summary': {
                'conditions_count': len(epic_data.get('conditions', [])),
                'observations_count': len(epic_data.get('observations', [])),
                'documents_count': len(epic_data.get('documents', [])),
                'encounters_count': len(epic_data.get('encounters', []))
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Epic screening data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500