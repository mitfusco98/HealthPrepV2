"""
Prep sheet generation and display routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
import logging
from models import Patient
from prep_sheet.generator import prep_sheet_generator
from admin.logs import admin_logger

logger = logging.getLogger(__name__)

prep_sheet_bp = Blueprint('prep_sheet', __name__)

@prep_sheet_bp.route('/patient/<int:patient_id>')
@login_required
def generate_prep_sheet(patient_id):
    """Generate and display prep sheet for a patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet
        result = prep_sheet_generator.generate_prep_sheet(patient_id)
        
        if not result['success']:
            flash(f'Error generating prep sheet: {result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('screening.screening_list'))
        
        prep_data = result['prep_data']
        
        # Generate summary statistics
        summary_stats = prep_sheet_generator.generate_summary_stats(prep_data)
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='generate_prep_sheet',
            resource_type='Patient',
            resource_id=patient_id,
            details=f'Generated prep sheet for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        return render_template('prep_sheet/prep_sheet.html',
                             patient=patient,
                             prep_data=prep_data,
                             summary_stats=summary_stats,
                             generated_at=result['generated_at'])
        
    except Exception as e:
        logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
        flash('Error generating prep sheet. Please try again.', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/patient/<int:patient_id>/print')
@login_required
def print_prep_sheet(patient_id):
    """Print-friendly version of prep sheet"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet
        result = prep_sheet_generator.generate_prep_sheet(patient_id)
        
        if not result['success']:
            flash(f'Error generating prep sheet: {result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('prep_sheet.generate_prep_sheet', patient_id=patient_id))
        
        prep_data = result['prep_data']
        summary_stats = prep_sheet_generator.generate_summary_stats(prep_data)
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='print_prep_sheet',
            resource_type='Patient',
            resource_id=patient_id,
            details=f'Printed prep sheet for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        response = make_response(render_template('prep_sheet/prep_sheet_print.html',
                                               patient=patient,
                                               prep_data=prep_data,
                                               summary_stats=summary_stats,
                                               generated_at=result['generated_at']))
        
        # Set headers for printing
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as e:
        logger.error(f"Error generating print prep sheet for patient {patient_id}: {str(e)}")
        flash('Error generating print version. Please try again.', 'error')
        return redirect(url_for('prep_sheet.generate_prep_sheet', patient_id=patient_id))

@prep_sheet_bp.route('/patient/<int:patient_id>/export')
@login_required
def export_prep_sheet(patient_id):
    """Export prep sheet data as JSON"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet
        result = prep_sheet_generator.generate_prep_sheet(patient_id)
        
        if not result['success']:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
        
        prep_data = result['prep_data']
        
        # Export data
        export_data = prep_sheet_generator.export_prep_sheet_data(prep_data)
        export_data['generated_at'] = result['generated_at'].isoformat()
        export_data['exported_by'] = current_user.username
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='export_prep_sheet',
            resource_type='Patient',
            resource_id=patient_id,
            details=f'Exported prep sheet data for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        response = make_response(jsonify(export_data))
        response.headers['Content-Disposition'] = f'attachment; filename=prep_sheet_{patient.mrn}_{prep_data.prep_date}.json'
        response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting prep sheet for patient {patient_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@prep_sheet_bp.route('/batch')
@login_required
def batch_prep_sheets():
    """Batch prep sheet generation interface"""
    try:
        # Get all patients for selection
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        return render_template('prep_sheet/batch_generation.html', patients=patients)
        
    except Exception as e:
        logger.error(f"Error loading batch prep sheets page: {str(e)}")
        flash('Error loading page. Please try again.', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/batch/generate', methods=['POST'])
@login_required
def generate_batch_prep_sheets():
    """Generate prep sheets for multiple patients"""
    try:
        patient_ids = request.form.getlist('patient_ids')
        
        if not patient_ids:
            flash('Please select at least one patient.', 'error')
            return redirect(url_for('prep_sheet.batch_prep_sheets'))
        
        # Convert to integers
        patient_ids = [int(pid) for pid in patient_ids]
        
        generated_sheets = []
        errors = []
        
        for patient_id in patient_ids:
            try:
                result = prep_sheet_generator.generate_prep_sheet(patient_id)
                
                if result['success']:
                    patient = Patient.query.get(patient_id)
                    generated_sheets.append({
                        'patient_id': patient_id,
                        'patient_name': patient.full_name if patient else 'Unknown',
                        'prep_data': result['prep_data'],
                        'generated_at': result['generated_at']
                    })
                else:
                    patient = Patient.query.get(patient_id)
                    errors.append({
                        'patient_id': patient_id,
                        'patient_name': patient.full_name if patient else 'Unknown',
                        'error': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                patient = Patient.query.get(patient_id)
                errors.append({
                    'patient_id': patient_id,
                    'patient_name': patient.full_name if patient else 'Unknown',
                    'error': str(e)
                })
        
        # Log the batch action
        admin_logger.log_action(
            user_id=current_user.id,
            action='batch_generate_prep_sheets',
            details=f'Generated {len(generated_sheets)} prep sheets, {len(errors)} errors',
            ip_address=request.remote_addr
        )
        
        if errors:
            flash(f'Generated {len(generated_sheets)} prep sheets with {len(errors)} errors.', 'warning')
        else:
            flash(f'Successfully generated {len(generated_sheets)} prep sheets.', 'success')
        
        return render_template('prep_sheet/batch_results.html',
                             generated_sheets=generated_sheets,
                             errors=errors)
        
    except Exception as e:
        logger.error(f"Error generating batch prep sheets: {str(e)}")
        flash('Error generating batch prep sheets. Please try again.', 'error')
        return redirect(url_for('prep_sheet.batch_prep_sheets'))

@prep_sheet_bp.route('/api/patient/<int:patient_id>/summary')
@login_required
def get_patient_summary(patient_id):
    """API endpoint to get patient summary for prep sheet"""
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Generate basic prep sheet data
        result = prep_sheet_generator.generate_prep_sheet(patient_id)
        
        if not result['success']:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
        
        prep_data = result['prep_data']
        summary_stats = prep_sheet_generator.generate_summary_stats(prep_data)
        
        summary = {
            'patient_id': patient_id,
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'age': patient.age,
            'gender': patient.gender,
            'total_documents': summary_stats['total_documents'],
            'total_conditions': summary_stats['total_conditions'],
            'screening_stats': summary_stats['screening_stats'],
            'data_quality_score': summary_stats['data_quality_score']
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting patient summary for {patient_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@prep_sheet_bp.route('/templates')
@login_required
def prep_sheet_templates():
    """Prep sheet template management"""
    try:
        # This would be expanded to support custom templates
        return render_template('prep_sheet/templates.html')
        
    except Exception as e:
        logger.error(f"Error loading prep sheet templates: {str(e)}")
        flash('Error loading templates. Please try again.', 'error')
        return redirect(url_for('screening.screening_list'))
