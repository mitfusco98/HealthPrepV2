"""
Preparation sheet routes for generating and viewing patient prep sheets.
Handles prep sheet generation, batch processing, and template management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
import json
import logging
from datetime import datetime
from io import StringIO

from models import Patient, MedicalDocument, Screening, ScreeningType, db
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import AdminLogger

logger = logging.getLogger(__name__)
prep_sheet_bp = Blueprint('prep_sheet', __name__)
admin_logger = AdminLogger()

@prep_sheet_bp.route('/generate/<int:patient_id>')
@login_required
def generate_prep_sheet(patient_id):
    """Generate and display preparation sheet for a patient."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Get appointment date if provided
        appointment_date_str = request.args.get('appointment_date')
        appointment_date = None
        
        if appointment_date_str:
            try:
                from dateutil import parser as date_parser
                appointment_date = date_parser.parse(appointment_date_str)
            except:
                flash('Invalid appointment date format', 'warning')
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        prep_sheet_data = generator.generate_prep_sheet(patient_id, appointment_date)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='generate_prep_sheet',
            details=f'Generated prep sheet for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        if not prep_sheet_data['success']:
            flash(f'Error generating prep sheet: {prep_sheet_data.get("error", "Unknown error")}', 'error')
            return redirect(url_for('screening.screening_list'))
        
        return render_template('prep_sheet/prep_sheet.html',
                             patient=patient,
                             prep_sheet=prep_sheet_data,
                             appointment_date=appointment_date)
        
    except Exception as e:
        logger.error(f"Error generating prep sheet for patient {patient_id}: {e}")
        flash('Error generating preparation sheet', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/preview/<int:patient_id>')
@login_required
def preview_prep_sheet(patient_id):
    """Preview prep sheet summary without full generation."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        generator = PrepSheetGenerator()
        summary = generator.get_prep_sheet_summary(patient_id)
        
        if not summary['success']:
            return jsonify(summary), 400
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting prep sheet preview: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@prep_sheet_bp.route('/batch')
@login_required
def batch_prep_sheets():
    """Interface for generating multiple prep sheets."""
    try:
        # Get all patients for selection
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        return render_template('prep_sheet/batch_generation.html', patients=patients)
        
    except Exception as e:
        logger.error(f"Error loading batch prep sheets interface: {e}")
        flash('Error loading batch generation interface', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/batch/generate', methods=['POST'])
@login_required
def generate_batch_prep_sheets():
    """Generate prep sheets for multiple patients."""
    try:
        # Get selected patient IDs
        patient_ids = request.form.getlist('patient_ids', type=int)
        
        if not patient_ids:
            flash('Please select at least one patient', 'error')
            return redirect(url_for('prep_sheet.batch_prep_sheets'))
        
        # Get appointment date if provided
        appointment_date_str = request.form.get('appointment_date')
        appointment_date = None
        
        if appointment_date_str:
            try:
                from dateutil import parser as date_parser
                appointment_date = date_parser.parse(appointment_date_str)
            except:
                flash('Invalid appointment date format', 'warning')
        
        # Generate batch prep sheets
        generator = PrepSheetGenerator()
        batch_result = generator.generate_batch_prep_sheets(patient_ids, appointment_date)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='generate_batch_prep_sheets',
            details=f'Generated batch prep sheets for {len(patient_ids)} patients: {batch_result["successful_generations"]} successful, {batch_result["failed_generations"]} failed',
            ip_address=request.remote_addr
        )
        
        if batch_result['success']:
            flash(f'Successfully generated {batch_result["successful_generations"]} prep sheets', 'success')
            
            if batch_result['failed_generations'] > 0:
                flash(f'{batch_result["failed_generations"]} prep sheets failed to generate', 'warning')
                
                # Show errors if any
                for error in batch_result.get('errors', []):
                    flash(error, 'error')
        else:
            flash(f'Batch generation failed: {batch_result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('prep_sheet.batch_prep_sheets'))
        
        # Store results in session for viewing
        from flask import session
        session['batch_prep_results'] = batch_result
        
        return redirect(url_for('prep_sheet.view_batch_results'))
        
    except Exception as e:
        logger.error(f"Error generating batch prep sheets: {e}")
        flash('Error generating batch prep sheets', 'error')
        return redirect(url_for('prep_sheet.batch_prep_sheets'))

@prep_sheet_bp.route('/batch/results')
@login_required
def view_batch_results():
    """View results of batch prep sheet generation."""
    try:
        from flask import session
        
        batch_results = session.get('batch_prep_results')
        
        if not batch_results:
            flash('No batch results found', 'error')
            return redirect(url_for('prep_sheet.batch_prep_sheets'))
        
        # Get patient information for results
        successful_patients = []
        if 'prep_sheets' in batch_results:
            for patient_id_str, prep_sheet in batch_results['prep_sheets'].items():
                patient_id = int(patient_id_str)
                patient = Patient.query.get(patient_id)
                if patient:
                    successful_patients.append({
                        'patient': patient,
                        'prep_sheet': prep_sheet
                    })
        
        return render_template('prep_sheet/batch_results.html',
                             batch_results=batch_results,
                             successful_patients=successful_patients)
        
    except Exception as e:
        logger.error(f"Error viewing batch results: {e}")
        flash('Error loading batch results', 'error')
        return redirect(url_for('prep_sheet.batch_prep_sheets'))

@prep_sheet_bp.route('/export/<int:patient_id>')
@login_required
def export_prep_sheet(patient_id):
    """Export prep sheet as JSON."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        generator = PrepSheetGenerator()
        prep_sheet_data = generator.generate_prep_sheet(patient_id)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='export_prep_sheet',
            details=f'Exported prep sheet for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        if not prep_sheet_data['success']:
            flash(f'Error generating prep sheet for export: {prep_sheet_data.get("error")}', 'error')
            return redirect(url_for('screening.screening_list'))
        
        # Create JSON response
        filename = f"prep_sheet_{patient.mrn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        response = Response(
            json.dumps(prep_sheet_data, indent=2, default=str),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting prep sheet: {e}")
        flash('Error exporting preparation sheet', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/print/<int:patient_id>')
@login_required
def print_prep_sheet(patient_id):
    """Generate print-friendly version of prep sheet."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        generator = PrepSheetGenerator()
        prep_sheet_data = generator.generate_prep_sheet(patient_id)
        
        if not prep_sheet_data['success']:
            flash(f'Error generating prep sheet: {prep_sheet_data.get("error")}', 'error')
            return redirect(url_for('screening.screening_list'))
        
        return render_template('prep_sheet/print_prep_sheet.html',
                             patient=patient,
                             prep_sheet=prep_sheet_data,
                             print_view=True)
        
    except Exception as e:
        logger.error(f"Error generating print prep sheet: {e}")
        flash('Error generating print version', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/api/quick-generate/<int:patient_id>')
@login_required
def api_quick_generate(patient_id):
    """Quick API endpoint for prep sheet generation status."""
    try:
        generator = PrepSheetGenerator()
        summary = generator.get_prep_sheet_summary(patient_id)
        
        if summary['success']:
            # Add quick generation flag
            summary['can_generate'] = True
            summary['has_documents'] = summary['total_documents'] > 0
            summary['has_screenings'] = summary['total_screenings'] > 0
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error in quick generate API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@prep_sheet_bp.route('/settings')
@login_required
def prep_sheet_settings():
    """Preparation sheet template and generation settings."""
    try:
        from models import ChecklistSettings
        
        # Get current settings
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
            db.session.commit()
        
        # Get template information
        template_info = {
            'available_templates': ['prep_sheet.html', 'print_prep_sheet.html'],
            'current_template': 'prep_sheet.html',
            'last_updated': settings.updated_at.isoformat() if settings.updated_at else None
        }
        
        return render_template('prep_sheet/settings.html',
                             settings=settings,
                             template_info=template_info)
        
    except Exception as e:
        logger.error(f"Error loading prep sheet settings: {e}")
        flash('Error loading prep sheet settings', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/settings/update', methods=['POST'])
@login_required
def update_prep_sheet_settings():
    """Update preparation sheet settings."""
    try:
        from models import ChecklistSettings
        
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        # Update settings
        settings.lab_cutoff_months = request.form.get('lab_cutoff_months', type=int) or 12
        settings.imaging_cutoff_months = request.form.get('imaging_cutoff_months', type=int) or 24
        settings.consult_cutoff_months = request.form.get('consult_cutoff_months', type=int) or 12
        settings.hospital_cutoff_months = request.form.get('hospital_cutoff_months', type=int) or 12
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='update_prep_sheet_settings',
            details='Updated prep sheet generation settings',
            ip_address=request.remote_addr
        )
        
        flash('Prep sheet settings updated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error updating prep sheet settings: {e}")
        db.session.rollback()
        flash('Error updating prep sheet settings', 'error')
    
    return redirect(url_for('prep_sheet.prep_sheet_settings'))

@prep_sheet_bp.route('/document/<int:document_id>')
@login_required
def view_document(document_id):
    """View a specific medical document."""
    try:
        document = MedicalDocument.query.get_or_404(document_id)
        
        # Check if user has access to this patient's documents
        # In a real implementation, you'd have proper access controls
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_document',
            details=f'Viewed document {document.filename} for patient {document.patient_id}',
            ip_address=request.remote_addr
        )
        
        return render_template('prep_sheet/view_document.html', document=document)
        
    except Exception as e:
        logger.error(f"Error viewing document {document_id}: {e}")
        flash('Error loading document', 'error')
        return redirect(url_for('screening.screening_list'))

@prep_sheet_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Upload a new medical document."""
    if request.method == 'POST':
        try:
            # Get form data
            patient_id = request.form.get('patient_id', type=int)
            document_type = request.form.get('document_type')
            uploaded_file = request.files.get('document_file')
            
            if not all([patient_id, document_type, uploaded_file]):
                flash('All fields are required', 'error')
                return redirect(url_for('prep_sheet.upload_document'))
            
            # Verify patient exists
            patient = Patient.query.get(patient_id)
            if not patient:
                flash('Patient not found', 'error')
                return redirect(url_for('prep_sheet.upload_document'))
            
            # Save uploaded file (in production, use proper file storage)
            import os
            import tempfile
            
            temp_dir = tempfile.gettempdir()
            filename = uploaded_file.filename
            file_path = os.path.join(temp_dir, filename)
            uploaded_file.save(file_path)
            
            # Create document record
            document = MedicalDocument(
                patient_id=patient_id,
                filename=filename,
                document_type=document_type,
                upload_date=datetime.utcnow(),
                document_date=datetime.utcnow(),  # Could be extracted from form
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                ocr_processed=False
            )
            
            db.session.add(document)
            db.session.commit()
            
            # Process OCR in background (simplified for this example)
            from ocr.processor import OCRProcessor
            processor = OCRProcessor()
            
            try:
                ocr_result = processor.process_document(file_path, document_type)
                
                if ocr_result['success']:
                    document.ocr_text = ocr_result['text']
                    document.ocr_confidence = ocr_result['confidence']
                    document.ocr_processed = True
                    
                    # Apply PHI filtering
                    from ocr.phi_filter import PHIFilter
                    phi_filter = PHIFilter()
                    
                    # Get PHI settings
                    phi_settings = PHIFilterSettings.query.first()
                    if phi_settings and phi_settings.enabled:
                        filter_settings = {
                            'filter_ssn': phi_settings.filter_ssn,
                            'filter_phone': phi_settings.filter_phone,
                            'filter_mrn': phi_settings.filter_mrn,
                            'filter_insurance': phi_settings.filter_insurance,
                            'filter_addresses': phi_settings.filter_addresses,
                            'filter_names': phi_settings.filter_names,
                            'filter_dates': phi_settings.filter_dates,
                            'filter_emails': True
                        }
                        
                        filter_result = phi_filter.filter_text(document.ocr_text, filter_settings)
                        if filter_result['success']:
                            document.ocr_text = filter_result['filtered_text']
                            document.phi_filtered = True
                    
                    db.session.commit()
                
            except Exception as ocr_error:
                logger.error(f"OCR processing error: {ocr_error}")
                # Document is still saved, just without OCR
            
            admin_logger.log_action(
                user_id=current_user.id,
                action='upload_document',
                details=f'Uploaded document {filename} for patient {patient.full_name}',
                ip_address=request.remote_addr
            )
            
            flash(f'Document "{filename}" uploaded successfully', 'success')
            return redirect(url_for('prep_sheet.generate_prep_sheet', patient_id=patient_id))
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            db.session.rollback()
            flash('Error uploading document', 'error')
    
    # GET request - show upload form
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    return render_template('prep_sheet/upload_document.html', patients=patients)
