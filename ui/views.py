"""
User interface views for patient-facing functionality
"""

import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Patient, Screening, ScreeningType, MedicalDocument, ChecklistSettings, db
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator

logger = logging.getLogger(__name__)

class UIViews:
    """Handles user interface views and interactions"""
    
    def __init__(self):
        self.screening_engine = ScreeningEngine()
        self.prep_generator = PrepSheetGenerator()
    
    @login_required
    def screening_list(self):
        """
        Display screening list with multiple tabs (list, types, checklist)
        """
        # Get current tab from URL parameter
        active_tab = request.args.get('tab', 'list')
        
        # Get filter parameters
        patient_filter = request.args.get('patient', '')
        status_filter = request.args.get('status', '')
        screening_type_filter = request.args.get('screening_type', '')
        
        # Base data for all tabs
        context = {
            'active_tab': active_tab,
            'filters': {
                'patient': patient_filter,
                'status': status_filter,
                'screening_type': screening_type_filter
            }
        }
        
        if active_tab == 'list':
            context.update(self._get_screening_list_data(patient_filter, status_filter, screening_type_filter))
        elif active_tab == 'types':
            context.update(self._get_screening_types_data())
        elif active_tab == 'checklist':
            context.update(self._get_checklist_settings_data())
        
        return render_template('screening/screening_list.html', **context)
    
    def _get_screening_list_data(self, patient_filter: str, status_filter: str, screening_type_filter: str):
        """Get data for screening list tab"""
        
        # Build query for screenings
        query = Screening.query.join(Patient).join(ScreeningType)
        
        # Apply filters
        if patient_filter:
            query = query.filter(
                (Patient.first_name.contains(patient_filter)) | 
                (Patient.last_name.contains(patient_filter)) |
                (Patient.mrn.contains(patient_filter))
            )
        
        if status_filter:
            query = query.filter(Screening.status == status_filter)
        
        if screening_type_filter:
            query = query.filter(ScreeningType.name.contains(screening_type_filter))
        
        # Get screenings with ordering
        screenings = query.order_by(
            Patient.last_name.asc(),
            Patient.first_name.asc(),
            ScreeningType.name.asc()
        ).all()
        
        # Get filter options
        all_patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        all_screening_types = ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
        
        return {
            'screenings': screenings,
            'patients': all_patients,
            'screening_types': all_screening_types,
            'status_options': ['Complete', 'Due', 'Due Soon'],
            'total_screenings': len(screenings)
        }
    
    def _get_screening_types_data(self):
        """Get data for screening types management tab"""
        
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        
        return {
            'screening_types': screening_types,
            'total_types': len(screening_types),
            'active_types': len([st for st in screening_types if st.is_active])
        }
    
    def _get_checklist_settings_data(self):
        """Get data for checklist settings tab"""
        
        settings = ChecklistSettings.get_current()
        
        return {
            'settings': settings,
            'last_updated': settings.updated_at.strftime('%m/%d/%Y %I:%M %p') if settings.updated_at else 'Never'
        }
    
    @login_required
    def patient_detail(self, patient_id: int):
        """
        Display detailed patient information with prep sheet
        """
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet
        prep_sheet = self.prep_generator.generate_prep_sheet(patient)
        
        # Get patient's screenings
        screenings = Screening.query.filter_by(patient_id=patient_id).all()
        
        context = {
            'patient': patient,
            'prep_sheet': prep_sheet,
            'screenings': screenings
        }
        
        return render_template('patient/patient_detail.html', **context)
    
    @login_required
    def prep_sheet_view(self, patient_id: int):
        """
        Display standalone prep sheet for a patient
        """
        patient = Patient.query.get_or_404(patient_id)
        
        # Get appointment date if provided
        appointment_date_str = request.args.get('appointment_date')
        appointment_date = datetime.utcnow()
        
        if appointment_date_str:
            try:
                appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid appointment date format', 'error')
        
        # Generate prep sheet
        prep_sheet = self.prep_generator.generate_prep_sheet(patient, appointment_date)
        
        context = {
            'patient': patient,
            'prep_sheet': prep_sheet,
            'appointment_date': appointment_date,
            'print_mode': request.args.get('print', '') == 'true'
        }
        
        return render_template('prep_sheet/prep_sheet.html', **context)
    
    @login_required
    def refresh_screenings(self):
        """
        Refresh screening engine for all patients
        """
        try:
            # Run screening engine
            result = self.screening_engine.process_all_patients()
            
            flash(f'Screenings refreshed: {result["patients_processed"]} patients processed, {result["total_screenings"]} screenings updated', 'success')
            
        except Exception as e:
            logger.error(f"Error refreshing screenings: {str(e)}")
            flash('Error refreshing screenings. Please try again.', 'error')
        
        return redirect(url_for('ui.screening_list'))
    
    @login_required
    def refresh_screening_type(self, screening_type_id: int):
        """
        Refresh screenings for a specific screening type
        """
        try:
            result = self.screening_engine.refresh_screening_type(screening_type_id)
            
            flash(f'Screening type "{result["screening_type"]}" refreshed: {result["updated_screenings"]} screenings updated', 'success')
            
        except Exception as e:
            logger.error(f"Error refreshing screening type {screening_type_id}: {str(e)}")
            flash('Error refreshing screening type. Please try again.', 'error')
        
        return redirect(url_for('ui.screening_list', tab='types'))
    
    @login_required
    def update_checklist_settings(self):
        """
        Update checklist settings from form submission
        """
        if request.method == 'POST':
            try:
                settings = ChecklistSettings.get_current()
                
                # Update settings from form
                settings.lab_cutoff_months = int(request.form.get('lab_cutoff_months', 12))
                settings.imaging_cutoff_months = int(request.form.get('imaging_cutoff_months', 24))
                settings.consult_cutoff_months = int(request.form.get('consult_cutoff_months', 12))
                settings.hospital_cutoff_months = int(request.form.get('hospital_cutoff_months', 24))
                settings.updated_by = current_user.id
                settings.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                flash('Checklist settings updated successfully', 'success')
                
            except ValueError as e:
                flash('Invalid input values. Please check your entries.', 'error')
            except Exception as e:
                logger.error(f"Error updating checklist settings: {str(e)}")
                flash('Error updating settings. Please try again.', 'error')
                db.session.rollback()
        
        return redirect(url_for('ui.screening_list', tab='checklist'))
    
    @login_required
    def document_viewer(self, document_id: int):
        """
        View a specific medical document
        """
        document = MedicalDocument.query.get_or_404(document_id)
        
        # Security check - ensure user has access to this patient's documents
        if not current_user.is_admin:
            # Add additional security checks here based on your access control model
            pass
        
        context = {
            'document': document,
            'patient': document.patient,
            'ocr_available': document.ocr_processed,
            'confidence_level': self._get_confidence_level(document.ocr_confidence)
        }
        
        return render_template('document/document_viewer.html', **context)
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level for display"""
        if not confidence:
            return 'unknown'
        elif confidence >= 0.85:
            return 'high'
        elif confidence >= 0.70:
            return 'medium'
        else:
            return 'low'
    
    @login_required
    def search_patients(self):
        """
        Search for patients (AJAX endpoint)
        """
        query = request.args.get('q', '').strip()
        
        if len(query) < 2:
            return jsonify({'patients': []})
        
        # Search patients by name or MRN
        patients = Patient.query.filter(
            (Patient.first_name.contains(query)) |
            (Patient.last_name.contains(query)) |
            (Patient.mrn.contains(query))
        ).limit(20).all()
        
        patient_list = []
        for patient in patients:
            patient_list.append({
                'id': patient.id,
                'mrn': patient.mrn,
                'name': patient.full_name,
                'age': patient.age,
                'gender': patient.gender
            })
        
        return jsonify({'patients': patient_list})
    
    @login_required
    def screening_keywords_api(self, screening_type_id: int):
        """
        API endpoint to get keywords for a screening type
        """
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        
        return jsonify({
            'success': True,
            'keywords': screening_type.keywords_list,
            'screening_type': screening_type.name
        })
    
    @login_required
    def batch_prep_sheets(self):
        """
        Generate prep sheets for multiple patients
        """
        if request.method == 'POST':
            try:
                # Get patient IDs from form
                patient_ids = request.form.getlist('patient_ids')
                patient_ids = [int(pid) for pid in patient_ids if pid.isdigit()]
                
                if not patient_ids:
                    flash('No patients selected', 'error')
                    return redirect(url_for('ui.screening_list'))
                
                # Get appointment date
                appointment_date_str = request.form.get('appointment_date')
                appointment_date = datetime.utcnow()
                
                if appointment_date_str:
                    try:
                        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d')
                    except ValueError:
                        flash('Invalid appointment date format', 'error')
                        return redirect(url_for('ui.screening_list'))
                
                # Generate batch prep sheets
                result = self.prep_generator.generate_batch_prep_sheets(patient_ids, appointment_date)
                
                flash(f'Batch prep sheets generated: {result["successful"]} successful, {result["failed"]} failed', 'success')
                
                # Return the batch result for display/download
                context = {
                    'batch_result': result,
                    'appointment_date': appointment_date
                }
                
                return render_template('prep_sheet/batch_prep_sheets.html', **context)
                
            except Exception as e:
                logger.error(f"Error generating batch prep sheets: {str(e)}")
                flash('Error generating batch prep sheets. Please try again.', 'error')
        
        return redirect(url_for('ui.screening_list'))

