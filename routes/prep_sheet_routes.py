"""
Prep sheet generation and management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
from routes.auth_routes import non_admin_required
from datetime import datetime
import logging

from models import Patient, Appointment, PrepSheetSettings
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import AdminLogger
from forms import PrepSheetSettingsForm
from app import db

logger = logging.getLogger(__name__)

prep_sheet_bp = Blueprint('prep_sheet', __name__)

@prep_sheet_bp.route('/patient/<int:patient_id>')
@login_required
@non_admin_required
def generate_for_patient(patient_id):
    """Generate prep sheet for a specific patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        appointment_id = request.args.get('appointment_id', type=int)
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id, appointment_id)
        
        if result['success']:
            # Log the generation
            AdminLogger.log(
                user_id=current_user.id,
                action='generate_prep_sheet',
                details=f'Generated prep sheet for patient {patient.mrn}, appointment {appointment_id}'
            )
            
            return render_template('prep_sheet/prep_sheet.html', 
                                 **result['data'])
        else:
            flash(f'Error generating prep sheet: {result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        
    except Exception as e:
        logger.error(f"Error generating prep sheet: {str(e)}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

@prep_sheet_bp.route('/appointment/<int:appointment_id>')
@login_required
def generate_for_appointment(appointment_id):
    """Generate prep sheet for a specific appointment"""
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(appointment.patient_id, appointment_id)
        
        if result['success']:
            # Log the generation
            AdminLogger.log(
                user_id=current_user.id,
                action='generate_prep_sheet',
                details=f'Generated prep sheet for appointment {appointment_id}, patient {appointment.patient.mrn}'
            )
            
            return render_template('prep_sheet/prep_sheet.html', 
                                 **result['data'])
        else:
            flash(f'Error generating prep sheet: {result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=appointment.patient_id))
        
    except Exception as e:
        logger.error(f"Error generating prep sheet for appointment: {str(e)}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('main.dashboard'))

@prep_sheet_bp.route('/batch-generate', methods=['GET', 'POST'])
@login_required
@non_admin_required
def batch_generate():
    """Batch generate prep sheets for multiple patients"""
    try:
        if request.method == 'GET':
            # Show batch generation interface
            upcoming_appointments = Appointment.query.filter(
                Appointment.appointment_date >= datetime.now(),
                Appointment.status == 'Scheduled'
            ).order_by(Appointment.appointment_date).limit(50).all()
            
            return render_template('prep_sheet/batch_generate.html',
                                 appointments=upcoming_appointments)
        
        # Handle POST request
        appointment_ids = request.form.getlist('appointment_ids')
        if not appointment_ids:
            flash('No appointments selected', 'error')
            return redirect(url_for('prep_sheet.batch_generate'))
        
        # Generate prep sheets for selected appointments
        generator = PrepSheetGenerator()
        generated_count = 0
        error_count = 0
        results = []
        
        for apt_id in appointment_ids:
            try:
                appointment = Appointment.query.get(int(apt_id))
                if appointment:
                    result = generator.generate_prep_sheet(
                        appointment.patient_id, 
                        appointment.id
                    )
                    
                    if result['success']:
                        generated_count += 1
                        results.append({
                            'patient_mrn': appointment.patient.mrn,
                            'appointment_date': appointment.appointment_date,
                            'success': True
                        })
                    else:
                        error_count += 1
                        results.append({
                            'patient_mrn': appointment.patient.mrn,
                            'appointment_date': appointment.appointment_date,
                            'success': False,
                            'error': result['error']
                        })
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error generating prep sheet for appointment {apt_id}: {str(e)}")
        
        # Log the batch generation
        AdminLogger.log(
            user_id=current_user.id,
            action='batch_generate_prep_sheets',
            details=f'Batch generated {generated_count} prep sheets, {error_count} errors, {len(appointment_ids)} total requested'
        )
        
        if generated_count > 0:
            flash(f'Successfully generated {generated_count} prep sheets', 'success')
        if error_count > 0:
            flash(f'{error_count} prep sheets failed generation', 'warning')
        
        return render_template('prep_sheet/batch_results.html',
                             results=results,
                             generated_count=generated_count,
                             error_count=error_count)
        
    except Exception as e:
        logger.error(f"Error in batch prep sheet generation: {str(e)}")
        flash('Error in batch generation', 'error')
        return redirect(url_for('prep_sheet.batch_generate'))

@prep_sheet_bp.route('/regenerate/<int:patient_id>')
@login_required
def regenerate(patient_id):
    """Regenerate prep sheet for a patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        appointment_id = request.args.get('appointment_id', type=int)
        
        # Generate fresh prep sheet
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id, appointment_id)
        
        if result['success']:
            # Log the regeneration
            AdminLogger.log(
                user_id=current_user.id,
                action='regenerate_prep_sheet',
                details=f'Regenerated prep sheet for patient {patient.mrn}'
            )
            
            return render_template('prep_sheet/prep_sheet.html', 
                                 **result['data'])
        else:
            flash(f'Error regenerating prep sheet: {result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        
    except Exception as e:
        logger.error(f"Error regenerating prep sheet: {str(e)}")
        flash('Error regenerating prep sheet', 'error')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

@prep_sheet_bp.route('/export/<int:patient_id>')
@login_required
def export_prep_sheet(patient_id):
    """Export prep sheet in various formats"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        format_type = request.args.get('format', 'json')
        appointment_id = request.args.get('appointment_id', type=int)
        
        # Generate prep sheet data
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id, appointment_id)
        
        if not result['success']:
            flash(f'Error generating prep sheet: {result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        
        # Export in requested format
        export_result = generator.export_prep_sheet_data(result['data'], format_type)
        
        if export_result['success']:
            if format_type == 'json':
                import json
                response = make_response(json.dumps(export_result['data'], indent=2))
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = f'attachment; filename="{export_result["filename"]}"'
                
                # Log the export
                AdminLogger.log(
                    user_id=current_user.id,
                    action='export_prep_sheet',
                    details=f'Exported prep sheet for patient {patient.mrn} in {format_type} format'
                )
                
                return response
            else:
                flash(f'Export format {format_type} not supported yet', 'error')
                return redirect(url_for('main.patient_detail', patient_id=patient_id))
        else:
            flash(f'Error exporting prep sheet: {export_result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        
    except Exception as e:
        logger.error(f"Error exporting prep sheet: {str(e)}")
        flash('Error exporting prep sheet', 'error')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

@prep_sheet_bp.route('/api/validate/<int:patient_id>')
@login_required
def api_validate_prep_sheet(patient_id):
    """API endpoint to validate prep sheet data completeness"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id)
        
        if result['success']:
            # Validate the data
            validation_result = generator.validate_prep_sheet_data(result['data'])
            
            return jsonify({
                'success': True,
                'validation': validation_result,
                'patient_mrn': patient.mrn
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            })
        
    except Exception as e:
        logger.error(f"Error validating prep sheet: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prep_sheet_bp.route('/api/preview/<int:patient_id>')
@login_required
def api_preview_prep_sheet(patient_id):
    """API endpoint to get prep sheet preview data"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        appointment_id = request.args.get('appointment_id', type=int)
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id, appointment_id)
        
        if result['success']:
            # Return preview data (subset of full prep sheet)
            preview_data = {
                'patient_header': result['data']['patient_header'],
                'screening_summary': {
                    'total_screenings': result['data']['quality_checklist']['total_screenings'],
                    'due_count': result['data']['quality_checklist']['due_count'],
                    'due_soon_count': result['data']['quality_checklist']['due_soon_count'],
                    'complete_count': result['data']['quality_checklist']['complete_count']
                },
                'document_summary': {
                    category: {
                        'count': data['count'],
                        'cutoff_months': data['cutoff_months']
                    }
                    for category, data in result['data']['medical_data'].items()
                }
            }
            
            return jsonify({
                'success': True,
                'preview': preview_data
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            })
        
    except Exception as e:
        logger.error(f"Error generating prep sheet preview: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prep_sheet_bp.route('/templates')
@login_required
def manage_templates():
    """Manage prep sheet templates"""
    try:
        # This would implement template management
        # For now, show a placeholder page
        
        templates = [
            {
                'name': 'Standard Prep Sheet',
                'description': 'Default comprehensive prep sheet',
                'active': True
            },
            {
                'name': 'Cardiology Focused',
                'description': 'Focused on cardiac screenings',
                'active': False
            }
        ]
        
        return render_template('prep_sheet/templates.html',
                             templates=templates)
        
    except Exception as e:
        logger.error(f"Error loading prep sheet templates: {str(e)}")
        flash('Error loading templates', 'error')
        return render_template('error/500.html'), 500

@prep_sheet_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@non_admin_required
def prep_sheet_settings():
    """Prep sheet generation settings"""
    try:
        if request.method == 'POST':
            # Update prep sheet settings
            settings = PrepSheetSettings.query.first()
            if not settings:
                settings = PrepSheetSettings()
                db.session.add(settings)
            
            # Update cutoff settings
            settings.labs_cutoff_months = request.form.get('labs_cutoff_months', type=int) or 12
            settings.imaging_cutoff_months = request.form.get('imaging_cutoff_months', type=int) or 12
            settings.consults_cutoff_months = request.form.get('consults_cutoff_months', type=int) or 12
            settings.hospital_cutoff_months = request.form.get('hospital_cutoff_months', type=int) or 24
            
            db.session.commit()
            
            # Log the change
            AdminLogger.log(
                user_id=current_user.id,
                action='update_prep_sheet_settings',
                details=f'Updated prep sheet settings - Labs: {settings.labs_cutoff_months}, Imaging: {settings.imaging_cutoff_months}, Consults: {settings.consults_cutoff_months}, Hospital: {settings.hospital_cutoff_months}'
            )
            
            flash('Prep sheet settings updated successfully', 'success')
            return redirect(url_for('prep_sheet.prep_sheet_settings'))
        
        # GET request - show current settings
        settings = PrepSheetSettings.query.first()
        if not settings:
            settings = PrepSheetSettings()
        
        form = PrepSheetSettingsForm(obj=settings)
        
        return render_template('prep_sheet/settings.html',
                             form=form,
                             settings=settings)
        
    except Exception as e:
        logger.error(f"Error in prep sheet settings: {str(e)}")
        flash('Error loading prep sheet settings', 'error')
        return render_template('error/500.html'), 500
