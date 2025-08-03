"""
Prep sheet generation and viewing routes
Handles patient prep sheet creation and display
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user

from models import Patient, ChecklistSettings
from routes.auth_routes import user_required
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import AdminLogger

logger = logging.getLogger(__name__)
prep_sheet_bp = Blueprint('prep_sheet', __name__)
admin_logger = AdminLogger()

@prep_sheet_bp.route('/patient/<int:patient_id>')
@user_required
def view_prep_sheet(patient_id):
    """View prep sheet for a specific patient"""
    # Get patient
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate prep sheet
    generator = PrepSheetGenerator()
    
    try:
        prep_data = generator.get_prep_sheet_template_data(patient_id)
        
        if 'error' in prep_data:
            flash(f'Error generating prep sheet: {prep_data["error"]}', 'error')
            return redirect(url_for('screening.screening_list'))
        
        # Log the prep sheet view
        admin_logger.log_action(
            user_id=current_user.id,
            action='prep_sheet_viewed',
            resource_type='prep_sheet',
            resource_id=patient_id,
            details={
                'patient_name': patient.name,
                'patient_mrn': patient.mrn
            },
            ip_address=request.remote_addr
        )
        
        return render_template('prep_sheet/prep_sheet.html',
                             patient=patient,
                             prep_data=prep_data)
    
    except Exception as e:
        logger.error(f"Error viewing prep sheet for patient {patient_id}: {str(e)}")
        flash('An error occurred while generating the prep sheet.', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/patient/<int:patient_id>/generate', methods=['POST'])
@user_required
def generate_prep_sheet(patient_id):
    """Generate/regenerate prep sheet for a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Get custom settings from form if provided
    custom_settings = {}
    
    if request.form.get('lab_cutoff_months'):
        custom_settings['lab_cutoff_months'] = int(request.form.get('lab_cutoff_months'))
    
    if request.form.get('imaging_cutoff_months'):
        custom_settings['imaging_cutoff_months'] = int(request.form.get('imaging_cutoff_months'))
    
    if request.form.get('consult_cutoff_months'):
        custom_settings['consult_cutoff_months'] = int(request.form.get('consult_cutoff_months'))
    
    if request.form.get('hospital_cutoff_months'):
        custom_settings['hospital_cutoff_months'] = int(request.form.get('hospital_cutoff_months'))
    
    # Generate prep sheet
    generator = PrepSheetGenerator()
    
    try:
        result = generator.generate_prep_sheet(patient_id, custom_settings)
        
        if result.get('success'):
            # Log the generation
            admin_logger.log_action(
                user_id=current_user.id,
                action='prep_sheet_generated',
                resource_type='prep_sheet',
                resource_id=patient_id,
                details={
                    'patient_name': patient.name,
                    'patient_mrn': patient.mrn,
                    'custom_settings': custom_settings
                },
                ip_address=request.remote_addr
            )
            
            flash('Prep sheet generated successfully!', 'success')
        else:
            flash(f'Error generating prep sheet: {result.get("error", "Unknown error")}', 'error')
    
    except Exception as e:
        logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
        flash('An error occurred while generating the prep sheet.', 'error')
    
    return redirect(url_for('prep_sheet.view_prep_sheet', patient_id=patient_id))

@prep_sheet_bp.route('/patient/<int:patient_id>/print')
@user_required
def print_prep_sheet(patient_id):
    """Print-friendly version of prep sheet"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate prep sheet
    generator = PrepSheetGenerator()
    
    try:
        prep_data = generator.get_prep_sheet_template_data(patient_id)
        
        if 'error' in prep_data:
            flash(f'Error generating prep sheet: {prep_data["error"]}', 'error')
            return redirect(url_for('prep_sheet.view_prep_sheet', patient_id=patient_id))
        
        # Log the print action
        admin_logger.log_action(
            user_id=current_user.id,
            action='prep_sheet_printed',
            resource_type='prep_sheet',
            resource_id=patient_id,
            details={
                'patient_name': patient.name,
                'patient_mrn': patient.mrn
            },
            ip_address=request.remote_addr
        )
        
        return render_template('prep_sheet/prep_sheet_print.html',
                             patient=patient,
                             prep_data=prep_data)
    
    except Exception as e:
        logger.error(f"Error printing prep sheet for patient {patient_id}: {str(e)}")
        flash('An error occurred while preparing the prep sheet for printing.', 'error')
        return redirect(url_for('prep_sheet.view_prep_sheet', patient_id=patient_id))

@prep_sheet_bp.route('/settings')
@user_required
def prep_sheet_settings():
    """Prep sheet settings configuration"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
    
    return render_template('prep_sheet/settings.html', settings=settings)

@prep_sheet_bp.route('/settings/update', methods=['POST'])
@user_required
def update_prep_sheet_settings():
    """Update prep sheet settings"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
        from app import db
        db.session.add(settings)
    
    try:
        # Update settings from form
        settings.lab_cutoff_months = int(request.form.get('lab_cutoff_months', 12))
        settings.imaging_cutoff_months = int(request.form.get('imaging_cutoff_months', 24))
        settings.consult_cutoff_months = int(request.form.get('consult_cutoff_months', 12))
        settings.hospital_cutoff_months = int(request.form.get('hospital_cutoff_months', 24))
        
        # Handle default items (JSON array)
        default_items = request.form.getlist('default_items')
        settings.default_items = default_items
        
        from app import db
        db.session.commit()
        
        # Log the update
        admin_logger.log_action(
            user_id=current_user.id,
            action='prep_sheet_settings_updated',
            resource_type='prep_sheet_settings',
            resource_id=settings.id,
            details={
                'lab_cutoff_months': settings.lab_cutoff_months,
                'imaging_cutoff_months': settings.imaging_cutoff_months,
                'consult_cutoff_months': settings.consult_cutoff_months,
                'hospital_cutoff_months': settings.hospital_cutoff_months,
                'default_items_count': len(settings.default_items) if settings.default_items else 0
            },
            ip_address=request.remote_addr
        )
        
        flash('Prep sheet settings updated successfully!', 'success')
    
    except ValueError as e:
        flash('Invalid input values. Please check your entries.', 'error')
    except Exception as e:
        logger.error(f"Error updating prep sheet settings: {str(e)}")
        flash('An error occurred while updating settings.', 'error')
    
    return redirect(url_for('prep_sheet.prep_sheet_settings'))

# API endpoints for AJAX requests

@prep_sheet_bp.route('/api/patient/<int:patient_id>/preview')
@user_required
def api_prep_sheet_preview(patient_id):
    """Get prep sheet preview data via API"""
    generator = PrepSheetGenerator()
    
    try:
        # Get custom settings from query parameters
        custom_settings = {}
        
        for setting in ['lab_cutoff_months', 'imaging_cutoff_months', 
                       'consult_cutoff_months', 'hospital_cutoff_months']:
            value = request.args.get(setting)
            if value:
                custom_settings[setting] = int(value)
        
        prep_data = generator.generate_prep_sheet(patient_id, custom_settings)
        
        if prep_data.get('success'):
            return jsonify({
                'success': True,
                'data': prep_data['prep_data']
            })
        else:
            return jsonify({
                'success': False,
                'error': prep_data.get('error', 'Unknown error')
            })
    
    except Exception as e:
        logger.error(f"Error generating prep sheet preview for patient {patient_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prep_sheet_bp.route('/api/patient/<int:patient_id>/summary')
@user_required
def api_prep_sheet_summary(patient_id):
    """Get prep sheet summary statistics via API"""
    generator = PrepSheetGenerator()
    
    try:
        prep_data = generator.get_prep_sheet_template_data(patient_id)
        
        if 'error' in prep_data:
            return jsonify({
                'success': False,
                'error': prep_data['error']
            })
        
        # Extract summary statistics
        quality_checklist = prep_data.get('quality_checklist', {})
        medical_data = prep_data.get('medical_data', {})
        
        summary = {
            'total_screenings': quality_checklist.get('total_screenings', 0),
            'compliance_rate': quality_checklist.get('compliance_rate', 0),
            'status_counts': quality_checklist.get('status_summary', {}),
            'document_counts': {
                'lab': medical_data.get('lab', {}).get('count', 0),
                'imaging': medical_data.get('imaging', {}).get('count', 0),
                'consult': medical_data.get('consult', {}).get('count', 0),
                'hospital': medical_data.get('hospital', {}).get('count', 0)
            },
            'total_documents': sum([
                medical_data.get('lab', {}).get('count', 0),
                medical_data.get('imaging', {}).get('count', 0),
                medical_data.get('consult', {}).get('count', 0),
                medical_data.get('hospital', {}).get('count', 0)
            ])
        }
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    
    except Exception as e:
        logger.error(f"Error generating prep sheet summary for patient {patient_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prep_sheet_bp.route('/api/document/<int:document_id>')
@user_required
def api_document_details(document_id):
    """Get document details via API"""
    from models import MedicalDocument
    
    document = MedicalDocument.query.get_or_404(document_id)
    
    # Check if user has access to this patient's data
    # For now, allow all authenticated users
    
    return jsonify({
        'success': True,
        'document': {
            'id': document.id,
            'filename': document.filename,
            'document_type': document.document_type,
            'date_created': document.date_created.isoformat() if document.date_created else None,
            'ocr_confidence': document.ocr_confidence,
            'has_ocr_text': document.ocr_text is not None,
            'patient_name': document.patient.name if document.patient else None
        }
    })
"""
Prep sheet generation routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

prep_sheet_bp = Blueprint('prep_sheet', __name__)

@prep_sheet_bp.route('/generate/<int:patient_id>')
@login_required
def generate_prep_sheet(patient_id):
    """Generate prep sheet for a patient"""
    from models import Patient
    patient = Patient.query.get_or_404(patient_id)
    return render_template('prep_sheet/prep_sheet.html', patient=patient)

@prep_sheet_bp.route('/settings')
@login_required
def settings():
    """Prep sheet settings"""
    return render_template('settings/checklist_settings.html')
