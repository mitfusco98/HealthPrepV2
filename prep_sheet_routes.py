"""
Prep sheet generation and management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from datetime import datetime
import logging

from app import db
from models import Patient, PrepSheet
from forms import PrepSheetGenerationForm
from prep_sheet.generator import PrepSheetGenerator
from prep_sheet.filters import PrepSheetFilters

prep_sheet_bp = Blueprint('prep_sheet', __name__)
logger = logging.getLogger(__name__)

@prep_sheet_bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate():
    """Generate prep sheet for a patient"""
    form = PrepSheetGenerationForm()
    
    # Populate patient choices
    form.patient_id.choices = [
        (p.id, f"{p.full_name} ({p.mrn})")
        for p in Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    ]
    
    if form.validate_on_submit():
        try:
            patient = Patient.query.get_or_404(form.patient_id.data)
            
            # Generate prep sheet
            generator = PrepSheetGenerator()
            
            generation_options = {
                'include_labs': form.include_labs.data,
                'include_imaging': form.include_imaging.data,
                'include_consults': form.include_consults.data,
                'include_hospital': form.include_hospital.data,
                'appointment_date': form.appointment_date.data
            }
            
            prep_sheet_data = generator.generate_prep_sheet(patient.id, generation_options)
            
            # Save prep sheet to database
            prep_sheet = PrepSheet(
                patient_id=patient.id,
                generated_by=current_user.id,
                appointment_date=form.appointment_date.data,
                content=prep_sheet_data['html_content'],
                settings_snapshot=prep_sheet_data['settings_snapshot'],
                generation_time_seconds=prep_sheet_data['generation_time'],
                documents_processed=prep_sheet_data['documents_processed'],
                screenings_included=prep_sheet_data['screenings_included']
            )
            
            db.session.add(prep_sheet)
            db.session.commit()
            
            flash('Prep sheet generated successfully', 'success')
            return redirect(url_for('prep_sheet.view', prep_sheet_id=prep_sheet.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Prep sheet generation error: {str(e)}")
            flash('Error generating prep sheet', 'error')
    
    return render_template('prep_sheet/generate.html', form=form)

@prep_sheet_bp.route('/view/<int:prep_sheet_id>')
@login_required
def view(prep_sheet_id):
    """View generated prep sheet"""
    try:
        prep_sheet = PrepSheet.query.get_or_404(prep_sheet_id)
        
        return render_template('prep_sheet/prep_sheet.html', 
                             prep_sheet=prep_sheet,
                             patient=prep_sheet.patient)
        
    except Exception as e:
        logger.error(f"Prep sheet view error: {str(e)}")
        flash('Error loading prep sheet', 'error')
        return redirect(url_for('prep_sheet.list'))

@prep_sheet_bp.route('/list')
@login_required
def list():
    """List all prep sheets"""
    try:
        page = request.args.get('page', 1, type=int)
        patient_id = request.args.get('patient_id', type=int)
        
        query = PrepSheet.query.join(Patient)
        
        if patient_id:
            query = query.filter(PrepSheet.patient_id == patient_id)
        
        prep_sheets = query.order_by(PrepSheet.generated_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Get patients for filter
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        return render_template('prep_sheet/list.html',
                             prep_sheets=prep_sheets,
                             patients=patients,
                             selected_patient=patient_id)
        
    except Exception as e:
        logger.error(f"Prep sheet list error: {str(e)}")
        flash('Error loading prep sheets', 'error')
        return render_template('prep_sheet/list.html')

@prep_sheet_bp.route('/print/<int:prep_sheet_id>')
@login_required
def print_prep_sheet(prep_sheet_id):
    """Print-friendly version of prep sheet"""
    try:
        prep_sheet = PrepSheet.query.get_or_404(prep_sheet_id)
        
        response = make_response(render_template('prep_sheet/print.html',
                                               prep_sheet=prep_sheet,
                                               patient=prep_sheet.patient))
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as e:
        logger.error(f"Prep sheet print error: {str(e)}")
        flash('Error loading prep sheet for printing', 'error')
        return redirect(url_for('prep_sheet.view', prep_sheet_id=prep_sheet_id))

@prep_sheet_bp.route('/delete/<int:prep_sheet_id>', methods=['POST'])
@login_required
def delete(prep_sheet_id):
    """Delete prep sheet"""
    try:
        prep_sheet = PrepSheet.query.get_or_404(prep_sheet_id)
        
        # Check if user can delete (admin or creator)
        if not current_user.is_admin() and prep_sheet.generated_by != current_user.id:
            flash('You do not have permission to delete this prep sheet', 'error')
            return redirect(url_for('prep_sheet.list'))
        
        db.session.delete(prep_sheet)
        db.session.commit()
        
        flash('Prep sheet deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Prep sheet delete error: {str(e)}")
        flash('Error deleting prep sheet', 'error')
    
    return redirect(url_for('prep_sheet.list'))

@prep_sheet_bp.route('/regenerate/<int:patient_id>')
@login_required
def regenerate(patient_id):
    """Regenerate prep sheet for patient with current settings"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Generate prep sheet with default settings
        generator = PrepSheetGenerator()
        
        generation_options = {
            'include_labs': True,
            'include_imaging': True,
            'include_consults': True,
            'include_hospital': True,
            'appointment_date': None
        }
        
        prep_sheet_data = generator.generate_prep_sheet(patient.id, generation_options)
        
        # Save prep sheet to database
        prep_sheet = PrepSheet(
            patient_id=patient.id,
            generated_by=current_user.id,
            content=prep_sheet_data['html_content'],
            settings_snapshot=prep_sheet_data['settings_snapshot'],
            generation_time_seconds=prep_sheet_data['generation_time'],
            documents_processed=prep_sheet_data['documents_processed'],
            screenings_included=prep_sheet_data['screenings_included']
        )
        
        db.session.add(prep_sheet)
        db.session.commit()
        
        flash(f'Prep sheet regenerated for {patient.full_name}', 'success')
        return redirect(url_for('prep_sheet.view', prep_sheet_id=prep_sheet.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Prep sheet regeneration error: {str(e)}")
        flash('Error regenerating prep sheet', 'error')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

