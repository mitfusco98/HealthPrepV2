"""
Main user interface views for screening management and prep sheets
"""
import logging
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument, ChecklistSettings
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator

logger = logging.getLogger(__name__)

@login_required
def screening_list():
    """Main screening list interface with multiple modes"""
    try:
        # Get all patients for dropdown
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        # Get active screening types
        screening_types = ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
        
        # Get current tab from query params
        tab = request.args.get('tab', 'list')
        
        if tab == 'list':
            # Screening list mode
            patient_id = request.args.get('patient_id')
            status_filter = request.args.get('status')
            type_filter = request.args.get('type_id')
            
            screenings_query = db.session.query(Screening).join(ScreeningType).filter(ScreeningType.is_active == True)
            
            if patient_id:
                screenings_query = screenings_query.filter(Screening.patient_id == patient_id)
            if status_filter:
                screenings_query = screenings_query.filter(Screening.status == status_filter)
            if type_filter:
                screenings_query = screenings_query.filter(Screening.screening_type_id == type_filter)
            
            screenings = screenings_query.order_by(Screening.status.desc(), ScreeningType.name).all()
            
            # Add matched documents info
            for screening in screenings:
                if screening.matched_documents:
                    screening.documents = MedicalDocument.query.filter(
                        MedicalDocument.id.in_(screening.matched_documents)
                    ).all()
                else:
                    screening.documents = []
            
            context = {
                'screenings': screenings,
                'patients': patients,
                'screening_types': screening_types,
                'current_patient_id': int(patient_id) if patient_id else None,
                'current_status': status_filter,
                'current_type_id': int(type_filter) if type_filter else None
            }
            
        elif tab == 'types':
            # Screening types management mode
            context = {
                'screening_types': screening_types,
                'patients': patients
            }
            
        elif tab == 'checklist':
            # Checklist settings mode
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
            
            context = {
                'settings': settings,
                'patients': patients
            }
        
        else:
            # Default to list view
            tab = 'list'
            context = {
                'screenings': [],
                'patients': patients,
                'screening_types': screening_types
            }
        
        context['current_tab'] = tab
        return render_template('screening/screening_list.html', **context)
        
    except Exception as e:
        logger.error(f"Error in screening list view: {e}")
        flash('Error loading screening list', 'error')
        return render_template('screening/screening_list.html', 
                             screenings=[], patients=[], screening_types=[], current_tab='list')

@login_required
def refresh_screenings():
    """Refresh screening data for all or specific patients"""
    try:
        patient_id = request.form.get('patient_id')
        screening_type_ids = request.form.getlist('screening_type_ids')
        
        engine = ScreeningEngine()
        
        if patient_id:
            # Refresh specific patient
            if screening_type_ids:
                engine.refresh_patient_screenings(int(patient_id), [int(id) for id in screening_type_ids])
            else:
                engine.process_patient_screenings(int(patient_id))
            flash(f'Screenings refreshed for patient', 'success')
        else:
            # Refresh all patients
            patients = Patient.query.all()
            for patient in patients:
                try:
                    engine.process_patient_screenings(patient.id)
                except Exception as e:
                    logger.error(f"Error refreshing patient {patient.id}: {e}")
            
            flash(f'Screenings refreshed for {len(patients)} patients', 'success')
        
        return redirect(url_for('ui.screening_list'))
        
    except Exception as e:
        logger.error(f"Error refreshing screenings: {e}")
        flash('Error refreshing screenings', 'error')
        return redirect(url_for('ui.screening_list'))

@login_required
def generate_prep_sheet():
    """Generate prep sheet for a patient"""
    try:
        patient_id = request.args.get('patient_id')
        if not patient_id:
            flash('Patient ID is required', 'error')
            return redirect(url_for('ui.screening_list'))
        
        patient = Patient.query.get(int(patient_id))
        if not patient:
            flash('Patient not found', 'error')
            return redirect(url_for('ui.screening_list'))
        
        # Generate prep sheet
        generator = PrepSheetGenerator()
        prep_data = generator.generate_prep_sheet(int(patient_id))
        
        return render_template('prep_sheet/prep_sheet.html', **prep_data)
        
    except Exception as e:
        logger.error(f"Error generating prep sheet: {e}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('ui.screening_list'))

@login_required
def manage_screening_types():
    """Manage screening types (CRUD operations)"""
    try:
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'create':
                return create_screening_type()
            elif action == 'update':
                return update_screening_type()
            elif action == 'delete':
                return delete_screening_type()
            elif action == 'toggle_status':
                return toggle_screening_type_status()
        
        # GET request - show management interface
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        return render_template('screening/screening_types.html', screening_types=screening_types)
        
    except Exception as e:
        logger.error(f"Error in screening types management: {e}")
        flash('Error managing screening types', 'error')
        return redirect(url_for('ui.screening_list', tab='types'))

def create_screening_type():
    """Create new screening type"""
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        keywords = request.form.get('keywords', '').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        
        # Eligibility criteria
        min_age = request.form.get('min_age')
        max_age = request.form.get('max_age')
        gender = request.form.get('gender')
        
        eligibility_criteria = {}
        if min_age:
            eligibility_criteria['min_age'] = int(min_age)
        if max_age:
            eligibility_criteria['max_age'] = int(max_age)
        if gender and gender != 'any':
            eligibility_criteria['gender'] = gender
        
        # Frequency
        frequency_number = int(request.form.get('frequency_number', 1))
        frequency_unit = request.form.get('frequency_unit', 'years')
        
        # Trigger conditions
        trigger_conditions = request.form.get('trigger_conditions', '').split(',')
        trigger_conditions = [c.strip() for c in trigger_conditions if c.strip()]
        
        # Create screening type
        screening_type = ScreeningType(
            name=name,
            description=description,
            keywords=keywords,
            eligibility_criteria=eligibility_criteria,
            frequency_number=frequency_number,
            frequency_unit=frequency_unit,
            trigger_conditions=trigger_conditions,
            is_active=True
        )
        
        db.session.add(screening_type)
        db.session.commit()
        
        flash(f'Screening type "{name}" created successfully', 'success')
        return redirect(url_for('ui.screening_list', tab='types'))
        
    except Exception as e:
        logger.error(f"Error creating screening type: {e}")
        flash('Error creating screening type', 'error')
        return redirect(url_for('ui.screening_list', tab='types'))

def update_screening_type():
    """Update existing screening type"""
    try:
        screening_type_id = request.form.get('screening_type_id')
        screening_type = ScreeningType.query.get(int(screening_type_id))
        
        if not screening_type:
            flash('Screening type not found', 'error')
            return redirect(url_for('ui.screening_list', tab='types'))
        
        # Update fields
        screening_type.name = request.form.get('name', '').strip()
        screening_type.description = request.form.get('description', '').strip()
        
        keywords = request.form.get('keywords', '').split(',')
        screening_type.keywords = [k.strip() for k in keywords if k.strip()]
        
        # Update eligibility criteria
        min_age = request.form.get('min_age')
        max_age = request.form.get('max_age')
        gender = request.form.get('gender')
        
        eligibility_criteria = {}
        if min_age:
            eligibility_criteria['min_age'] = int(min_age)
        if max_age:
            eligibility_criteria['max_age'] = int(max_age)
        if gender and gender != 'any':
            eligibility_criteria['gender'] = gender
        
        screening_type.eligibility_criteria = eligibility_criteria
        
        # Update frequency
        screening_type.frequency_number = int(request.form.get('frequency_number', 1))
        screening_type.frequency_unit = request.form.get('frequency_unit', 'years')
        
        # Update trigger conditions
        trigger_conditions = request.form.get('trigger_conditions', '').split(',')
        screening_type.trigger_conditions = [c.strip() for c in trigger_conditions if c.strip()]
        
        db.session.commit()
        
        flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
        return redirect(url_for('ui.screening_list', tab='types'))
        
    except Exception as e:
        logger.error(f"Error updating screening type: {e}")
        flash('Error updating screening type', 'error')
        return redirect(url_for('ui.screening_list', tab='types'))

def delete_screening_type():
    """Delete screening type"""
    try:
        screening_type_id = request.form.get('screening_type_id')
        screening_type = ScreeningType.query.get(int(screening_type_id))
        
        if not screening_type:
            flash('Screening type not found', 'error')
            return redirect(url_for('ui.screening_list', tab='types'))
        
        # Check if there are associated screenings
        associated_screenings = Screening.query.filter_by(screening_type_id=screening_type.id).count()
        
        if associated_screenings > 0:
            flash(f'Cannot delete screening type. It has {associated_screenings} associated screenings.', 'error')
            return redirect(url_for('ui.screening_list', tab='types'))
        
        name = screening_type.name
        db.session.delete(screening_type)
        db.session.commit()
        
        flash(f'Screening type "{name}" deleted successfully', 'success')
        return redirect(url_for('ui.screening_list', tab='types'))
        
    except Exception as e:
        logger.error(f"Error deleting screening type: {e}")
        flash('Error deleting screening type', 'error')
        return redirect(url_for('ui.screening_list', tab='types'))

def toggle_screening_type_status():
    """Toggle screening type active status"""
    try:
        screening_type_id = request.form.get('screening_type_id')
        screening_type = ScreeningType.query.get(int(screening_type_id))
        
        if not screening_type:
            flash('Screening type not found', 'error')
            return redirect(url_for('ui.screening_list', tab='types'))
        
        screening_type.is_active = not screening_type.is_active
        db.session.commit()
        
        status = 'activated' if screening_type.is_active else 'deactivated'
        flash(f'Screening type "{screening_type.name}" {status} successfully', 'success')
        return redirect(url_for('ui.screening_list', tab='types'))
        
    except Exception as e:
        logger.error(f"Error toggling screening type status: {e}")
        flash('Error updating screening type status', 'error')
        return redirect(url_for('ui.screening_list', tab='types'))

@login_required
def update_checklist_settings():
    """Update checklist settings"""
    try:
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        # Update cutoff months
        settings.labs_cutoff_months = int(request.form.get('labs_cutoff_months', 12))
        settings.imaging_cutoff_months = int(request.form.get('imaging_cutoff_months', 24))
        settings.consults_cutoff_months = int(request.form.get('consults_cutoff_months', 12))
        settings.hospital_cutoff_months = int(request.form.get('hospital_cutoff_months', 12))
        
        # Update OCR threshold
        settings.ocr_confidence_threshold = float(request.form.get('ocr_confidence_threshold', 70.0))
        
        # Update PHI filtering
        settings.phi_filtering_enabled = bool(request.form.get('phi_filtering_enabled'))
        
        db.session.commit()
        
        flash('Checklist settings updated successfully', 'success')
        return redirect(url_for('ui.screening_list', tab='checklist'))
        
    except Exception as e:
        logger.error(f"Error updating checklist settings: {e}")
        flash('Error updating checklist settings', 'error')
        return redirect(url_for('ui.screening_list', tab='checklist'))

@login_required
def get_screening_keywords():
    """API endpoint to get keywords for a screening type"""
    try:
        screening_type_id = request.args.get('screening_type_id')
        if not screening_type_id:
            return jsonify({'success': False, 'error': 'Missing screening type ID'})
        
        screening_type = ScreeningType.query.get(int(screening_type_id))
        if not screening_type:
            return jsonify({'success': False, 'error': 'Screening type not found'})
        
        return jsonify({
            'success': True,
            'keywords': screening_type.keywords or []
        })
        
    except Exception as e:
        logger.error(f"Error getting screening keywords: {e}")
        return jsonify({'success': False, 'error': 'Internal error'})

