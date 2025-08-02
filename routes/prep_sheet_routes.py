from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Patient, PrepSheet, PrepSheetSettings
from prep_sheet.generator import PrepSheetGenerator
from prep_sheet.filters import apply_cutoff_filters
from admin.logs import log_admin_action
from app import db
from datetime import datetime

prep_sheet_bp = Blueprint('prep_sheet', __name__)

@prep_sheet_bp.route('/generate/<int:patient_id>')
@login_required
def generate_prep_sheet(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Get prep sheet settings
    settings = PrepSheetSettings.query.first()
    if not settings:
        settings = PrepSheetSettings()
        db.session.add(settings)
        db.session.commit()
    
    # Generate prep sheet
    generator = PrepSheetGenerator()
    prep_data = generator.generate_for_patient(patient, settings)
    
    # Save prep sheet
    prep_sheet = PrepSheet(
        patient_id=patient.id,
        prep_data=prep_data,
        cutoff_months=settings.lab_cutoff_months
    )
    db.session.add(prep_sheet)
    db.session.commit()
    
    log_admin_action(current_user.id, 'Prep Sheet Generated',
                    f'Generated prep sheet for patient: {patient.full_name}', request.remote_addr)
    
    return render_template('prep_sheet/prep_sheet.html',
                         patient=patient,
                         prep_data=prep_data,
                         settings=settings)

@prep_sheet_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def prep_sheet_settings():
    settings = PrepSheetSettings.query.first()
    if not settings:
        settings = PrepSheetSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        settings.lab_cutoff_months = request.form.get('lab_cutoff_months', type=int)
        settings.imaging_cutoff_months = request.form.get('imaging_cutoff_months', type=int)
        settings.consult_cutoff_months = request.form.get('consult_cutoff_months', type=int)
        settings.hospital_cutoff_months = request.form.get('hospital_cutoff_months', type=int)
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        log_admin_action(current_user.id, 'Prep Sheet Settings Updated',
                        'Updated prep sheet cutoff settings', request.remote_addr)
        
        flash('Prep sheet settings updated successfully', 'success')
        return redirect(url_for('prep_sheet.prep_sheet_settings'))
    
    return render_template('prep_sheet/prep_sheet_settings.html', settings=settings)

@prep_sheet_bp.route('/list')
@login_required
def prep_sheet_list():
    """Display all generated prep sheets"""
    prep_sheets = PrepSheet.query.order_by(PrepSheet.generated_date.desc()).all()
    return render_template('prep_sheet/prep_sheet_list.html', prep_sheets=prep_sheets)

@prep_sheet_bp.route('/view/<int:prep_sheet_id>')
@login_required 
def view_prep_sheet(prep_sheet_id):
    """View a specific prep sheet"""
    prep_sheet = PrepSheet.query.get_or_404(prep_sheet_id)
    return render_template('prep_sheet/prep_sheet.html', 
                         patient=prep_sheet.patient,
                         prep_data=prep_sheet.prep_data,
                         prep_sheet=prep_sheet)
