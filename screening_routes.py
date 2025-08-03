from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import ScreeningType, PatientScreening, Patient, MedicalDocument, ChecklistSettings
from forms import ScreeningTypeForm, ChecklistSettingsForm
from core.engine import ScreeningEngine
from utils import cache_timestamp
import logging
import json

screening_bp = Blueprint('screening', __name__)

@screening_bp.route('/')
@screening_bp.route('/list')
@login_required
def screening_list():
    """Main screening list page with multiple tabs"""
    # Get all patients with their screenings
    patients = Patient.query.all()
    screening_data = []
    
    for patient in patients:
        screenings = PatientScreening.query.filter_by(patient_id=patient.id).all()
        for screening in screenings:
            screening_data.append({
                'patient': patient,
                'screening': screening,
                'screening_type': screening.screening_type
            })
    
    # Get all screening types for the types tab
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    # Get checklist settings
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('screening/screening_list.html',
                         screening_data=screening_data,
                         screening_types=screening_types,
                         settings=settings,
                         cache_timestamp=cache_timestamp())

@screening_bp.route('/add-type', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add new screening type"""
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            gender_eligibility=form.gender_eligibility.data,
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            frequency_value=form.frequency_value.data,
            frequency_unit=form.frequency_unit.data
        )
        
        # Handle keywords
        keywords = []
        if form.keywords.data:
            keywords = [k.strip() for k in form.keywords.data.split(',') if k.strip()]
        screening_type.set_keywords_list(keywords)
        
        # Handle trigger conditions
        conditions = []
        if form.trigger_conditions.data:
            conditions = [c.strip() for c in form.trigger_conditions.data.split(',') if c.strip()]
        screening_type.set_trigger_conditions_list(conditions)
        
        db.session.add(screening_type)
        db.session.commit()
        
        # Log the action
        from models import AdminLog
        log_entry = AdminLog(
            user_id=current_user.id,
            action='screening_type_created',
            details=f'Created screening type: {screening_type.name}',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash(f'Screening type "{screening_type.name}" created successfully', 'success')
        return redirect(url_for('screening.screening_list'))
    
    return render_template('screening/add_screening_type.html', form=form)

@screening_bp.route('/edit-type/<int:screening_type_id>', methods=['GET', 'POST'])
@login_required
def edit_screening_type(screening_type_id):
    """Edit existing screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    form = ScreeningTypeForm(obj=screening_type)
    
    if form.validate_on_submit():
        screening_type.name = form.name.data
        screening_type.description = form.description.data
        screening_type.gender_eligibility = form.gender_eligibility.data
        screening_type.min_age = form.min_age.data
        screening_type.max_age = form.max_age.data
        screening_type.frequency_value = form.frequency_value.data
        screening_type.frequency_unit = form.frequency_unit.data
        
        # Handle keywords
        keywords = []
        if form.keywords.data:
            keywords = [k.strip() for k in form.keywords.data.split(',') if k.strip()]
        screening_type.set_keywords_list(keywords)
        
        # Handle trigger conditions
        conditions = []
        if form.trigger_conditions.data:
            conditions = [c.strip() for c in form.trigger_conditions.data.split(',') if c.strip()]
        screening_type.set_trigger_conditions_list(conditions)
        
        db.session.commit()
        
        # Log the action
        from models import AdminLog
        log_entry = AdminLog(
            user_id=current_user.id,
            action='screening_type_updated',
            details=f'Updated screening type: {screening_type.name}',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
        return redirect(url_for('screening.screening_list'))
    
    # Pre-populate form fields
    if request.method == 'GET':
        keywords = screening_type.get_keywords_list()
        form.keywords.data = ', '.join(keywords) if keywords else ''
        
        conditions = screening_type.get_trigger_conditions_list()
        form.trigger_conditions.data = ', '.join(conditions) if conditions else ''
    
    return render_template('screening/add_screening_type.html', 
                         form=form, 
                         editing=True, 
                         screening_type=screening_type)

@screening_bp.route('/toggle-type/<int:screening_type_id>')
@login_required
def toggle_screening_type(screening_type_id):
    """Toggle screening type active status"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    screening_type.is_active = not screening_type.is_active
    db.session.commit()
    
    # Log the action
    from models import AdminLog
    status = 'activated' if screening_type.is_active else 'deactivated'
    log_entry = AdminLog(
        user_id=current_user.id,
        action='screening_type_toggled',
        details=f'{status.capitalize()} screening type: {screening_type.name}',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash(f'Screening type "{screening_type.name}" {status}', 'success')
    return redirect(url_for('screening.screening_list'))

@screening_bp.route('/delete-type/<int:screening_type_id>')
@login_required
def delete_screening_type(screening_type_id):
    """Delete screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    # Check if there are associated screenings
    associated_screenings = PatientScreening.query.filter_by(screening_type_id=screening_type_id).count()
    
    if associated_screenings > 0:
        flash(f'Cannot delete screening type "{screening_type.name}" - it has {associated_screenings} associated patient screenings', 'error')
        return redirect(url_for('screening.screening_list'))
    
    screening_name = screening_type.name
    db.session.delete(screening_type)
    db.session.commit()
    
    # Log the action
    from models import AdminLog
    log_entry = AdminLog(
        user_id=current_user.id,
        action='screening_type_deleted',
        details=f'Deleted screening type: {screening_name}',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash(f'Screening type "{screening_name}" deleted successfully', 'success')
    return redirect(url_for('screening.screening_list'))

@screening_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def checklist_settings():
    """Checklist settings page"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = ChecklistSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        settings.lab_cutoff_months = form.lab_cutoff_months.data
        settings.imaging_cutoff_months = form.imaging_cutoff_months.data
        settings.consult_cutoff_months = form.consult_cutoff_months.data
        settings.hospital_cutoff_months = form.hospital_cutoff_months.data
        
        # Handle default items
        default_items = []
        if form.default_items.data:
            default_items = [item.strip() for item in form.default_items.data.split('\n') if item.strip()]
        settings.default_items = json.dumps(default_items) if default_items else None
        
        # Handle status options
        status_options = []
        if form.status_options.data:
            status_options = [option.strip() for option in form.status_options.data.split('\n') if option.strip()]
        settings.status_options = json.dumps(status_options) if status_options else None
        
        db.session.commit()
        
        # Log the action
        from models import AdminLog
        log_entry = AdminLog(
            user_id=current_user.id,
            action='checklist_settings_updated',
            details='Updated checklist settings',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash('Checklist settings updated successfully', 'success')
        return redirect(url_for('screening.screening_list'))
    
    # Pre-populate form fields
    if request.method == 'GET':
        if settings.default_items:
            try:
                default_items = json.loads(settings.default_items)
                form.default_items.data = '\n'.join(default_items)
            except:
                pass
        
        if settings.status_options:
            try:
                status_options = json.loads(settings.status_options)
                form.status_options.data = '\n'.join(status_options)
            except:
                pass
    
    return render_template('screening/checklist_settings.html', form=form, settings=settings)

@screening_bp.route('/refresh', methods=['POST'])
@login_required  
def refresh_screenings():
    """Refresh all screenings using the screening engine"""
    try:
        engine = ScreeningEngine()
        updated_count = engine.refresh_all_screenings()
        
        # Log the action
        from models import AdminLog
        log_entry = AdminLog(
            user_id=current_user.id,
            action='screenings_refreshed',
            details=f'Refreshed {updated_count} screenings',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash(f'Successfully refreshed {updated_count} screenings', 'success')
    except Exception as e:
        logging.error(f"Error refreshing screenings: {str(e)}")
        flash('Error refreshing screenings. Please try again.', 'error')
    
    return redirect(url_for('screening.screening_list'))
