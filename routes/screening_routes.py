"""
Screening management routes
Handles screening lists, types, and checklist settings
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import Patient, ScreeningType, Screening, ChecklistSettings
from forms import ScreeningTypeForm, ChecklistSettingsForm
from core.engine import ScreeningEngine
from core.matcher import FuzzyMatcher
from admin.logs import AdminLogger
from routes.auth_routes import user_required, has_permission
from app import db

logger = logging.getLogger(__name__)
screening_bp = Blueprint('screening', __name__)
admin_logger = AdminLogger()

@screening_bp.route('/list')
@user_required
def screening_list():
    """Main screening list view with multiple modes"""
    mode = request.args.get('mode', 'list')
    patient_filter = request.args.get('patient', '')
    status_filter = request.args.get('status', '')
    screening_type_filter = request.args.get('screening_type', '')
    
    # Get screening data based on mode
    if mode == 'types':
        return render_screening_types()
    elif mode == 'checklist':
        return render_checklist_settings()
    else:
        return render_screening_list(patient_filter, status_filter, screening_type_filter)

def render_screening_list(patient_filter, status_filter, screening_type_filter):
    """Render the main screening list"""
    # Build query for screenings
    query = db.session.query(Screening).join(Screening.patient).join(Screening.screening_type)
    
    # Apply filters
    if patient_filter:
        query = query.filter(Patient.name.ilike(f'%{patient_filter}%'))
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if screening_type_filter:
        query = query.filter(ScreeningType.name.ilike(f'%{screening_type_filter}%'))
    
    # Get results
    screenings = query.order_by(Screening.status, Screening.next_due_date).all()
    
    # Get filter options
    patients = db.session.query(Patient).order_by(Patient.name).all()
    screening_types = db.session.query(ScreeningType).filter_by(is_active=True).order_by(ScreeningType.name).all()
    
    # Calculate summary statistics
    total_screenings = len(screenings)
    status_counts = {}
    for screening in screenings:
        status_counts[screening.status] = status_counts.get(screening.status, 0) + 1
    
    return render_template('screening/screening_list.html',
                         mode='list',
                         screenings=screenings,
                         patients=patients,
                         screening_types=screening_types,
                         filters={
                             'patient': patient_filter,
                             'status': status_filter,
                             'screening_type': screening_type_filter
                         },
                         summary={
                             'total': total_screenings,
                             'status_counts': status_counts
                         })

def render_screening_types():
    """Render screening types management"""
    screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
    
    return render_template('screening/screening_list.html',
                         mode='types',
                         screening_types=screening_types)

def render_checklist_settings():
    """Render checklist settings"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
    
    form = ChecklistSettingsForm(obj=settings)
    
    return render_template('screening/screening_list.html',
                         mode='checklist',
                         settings=settings,
                         form=form)

@screening_bp.route('/types')
@user_required
def screening_types():
    """Screening types management page"""
    screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
    
    return render_template('screening/screening_types.html',
                         screening_types=screening_types)

@screening_bp.route('/types/add', methods=['GET', 'POST'])
@user_required
def add_screening_type():
    """Add new screening type"""
    if not has_permission('manage_screening_types'):
        flash('Permission denied.', 'error')
        return redirect(url_for('screening.screening_types'))
    
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        # Create new screening type
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            keywords=form.keywords.data.split('\n') if form.keywords.data else [],
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            gender=form.gender.data if form.gender.data else None,
            frequency_number=form.frequency_number.data,
            frequency_unit=form.frequency_unit.data,
            trigger_conditions=form.trigger_conditions.data.split('\n') if form.trigger_conditions.data else [],
            is_active=form.is_active.data
        )
        
        db.session.add(screening_type)
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='screening_type_created',
            resource_type='screening_type',
            resource_id=screening_type.id,
            details={'name': screening_type.name},
            ip_address=request.remote_addr
        )
        
        flash('Screening type created successfully!', 'success')
        return redirect(url_for('screening.screening_types'))
    
    return render_template('screening/add_screening_type.html', form=form)

@screening_bp.route('/types/<int:screening_type_id>/edit', methods=['GET', 'POST'])
@user_required
def edit_screening_type(screening_type_id):
    """Edit existing screening type"""
    if not has_permission('manage_screening_types'):
        flash('Permission denied.', 'error')
        return redirect(url_for('screening.screening_types'))
    
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    form = ScreeningTypeForm(obj=screening_type)
    
    # Pre-populate form fields
    if screening_type.keywords:
        form.keywords.data = '\n'.join(screening_type.keywords)
    if screening_type.trigger_conditions:
        form.trigger_conditions.data = '\n'.join(screening_type.trigger_conditions)
    
    if form.validate_on_submit():
        # Update screening type
        screening_type.name = form.name.data
        screening_type.description = form.description.data
        screening_type.keywords = form.keywords.data.split('\n') if form.keywords.data else []
        screening_type.min_age = form.min_age.data
        screening_type.max_age = form.max_age.data
        screening_type.gender = form.gender.data if form.gender.data else None
        screening_type.frequency_number = form.frequency_number.data
        screening_type.frequency_unit = form.frequency_unit.data
        screening_type.trigger_conditions = form.trigger_conditions.data.split('\n') if form.trigger_conditions.data else []
        screening_type.is_active = form.is_active.data
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='screening_type_updated',
            resource_type='screening_type',
            resource_id=screening_type.id,
            details={'name': screening_type.name},
            ip_address=request.remote_addr
        )
        
        flash('Screening type updated successfully!', 'success')
        return redirect(url_for('screening.screening_types'))
    
    return render_template('screening/edit_screening_type.html', 
                         form=form, screening_type=screening_type)

@screening_bp.route('/types/<int:screening_type_id>/delete', methods=['POST'])
@user_required
def delete_screening_type(screening_type_id):
    """Delete screening type"""
    if not has_permission('manage_screening_types'):
        flash('Permission denied.', 'error')
        return redirect(url_for('screening.screening_types'))
    
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    # Check if screening type is in use
    screening_count = Screening.query.filter_by(screening_type_id=screening_type_id).count()
    
    if screening_count > 0:
        flash(f'Cannot delete screening type. It is used by {screening_count} screening(s).', 'error')
        return redirect(url_for('screening.screening_types'))
    
    # Log the action before deletion
    admin_logger.log_action(
        user_id=current_user.id,
        action='screening_type_deleted',
        resource_type='screening_type',
        resource_id=screening_type.id,
        details={'name': screening_type.name},
        ip_address=request.remote_addr
    )
    
    db.session.delete(screening_type)
    db.session.commit()
    
    flash('Screening type deleted successfully!', 'success')
    return redirect(url_for('screening.screening_types'))

@screening_bp.route('/settings', methods=['GET', 'POST'])
@user_required
def checklist_settings():
    """Checklist settings page"""
    settings = ChecklistSettings.query.first()
    if not settings:
        settings = ChecklistSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = ChecklistSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        # Update settings
        settings.lab_cutoff_months = form.lab_cutoff_months.data
        settings.imaging_cutoff_months = form.imaging_cutoff_months.data
        settings.consult_cutoff_months = form.consult_cutoff_months.data
        settings.hospital_cutoff_months = form.hospital_cutoff_months.data
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='checklist_settings_updated',
            resource_type='settings',
            resource_id=settings.id,
            details={
                'lab_cutoff': settings.lab_cutoff_months,
                'imaging_cutoff': settings.imaging_cutoff_months,
                'consult_cutoff': settings.consult_cutoff_months,
                'hospital_cutoff': settings.hospital_cutoff_months
            },
            ip_address=request.remote_addr
        )
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('screening.checklist_settings'))
    
    return render_template('screening/checklist_settings.html', 
                         form=form, settings=settings)

@screening_bp.route('/refresh', methods=['POST'])
@user_required
def refresh_screenings():
    """Refresh screening analysis"""
    try:
        engine = ScreeningEngine()
        patient_id = request.form.get('patient_id')
        
        if patient_id:
            # Refresh specific patient
            results = engine.run_screening_analysis(int(patient_id))
        else:
            # Refresh all patients
            results = engine.run_screening_analysis()
        
        if 'error' in results:
            flash(f'Error refreshing screenings: {results["error"]}', 'error')
        else:
            flash(f'Refreshed {results["updated_screenings"]} screenings for {results["processed_patients"]} patients.', 'success')
            
            # Log the action
            admin_logger.log_action(
                user_id=current_user.id,
                action='screenings_refreshed',
                resource_type='screening',
                details=results,
                ip_address=request.remote_addr
            )
    
    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        flash('An error occurred while refreshing screenings.', 'error')
    
    return redirect(url_for('screening.screening_list'))

# API endpoints for AJAX requests

@screening_bp.route('/api/keywords/<int:screening_type_id>')
@user_required
def get_screening_keywords(screening_type_id):
    """Get keywords for a screening type (AJAX endpoint)"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    return jsonify({
        'success': True,
        'screening_type_id': screening_type_id,
        'keywords': screening_type.keywords or []
    })

@screening_bp.route('/api/suggest-keywords')
@user_required
def suggest_keywords():
    """Suggest keywords based on partial input"""
    partial = request.args.get('q', '')
    
    if len(partial) < 2:
        return jsonify({'suggestions': []})
    
    matcher = FuzzyMatcher()
    suggestions = matcher.suggest_keywords(partial, limit=10)
    
    return jsonify({'suggestions': suggestions})

@screening_bp.route('/api/suggest-conditions')
@user_required
def suggest_conditions():
    """Suggest medical conditions based on partial input"""
    partial = request.args.get('q', '')
    
    if len(partial) < 2:
        return jsonify({'suggestions': []})
    
    matcher = FuzzyMatcher()
    suggestions = matcher.suggest_conditions(partial, limit=10)
    
    return jsonify({'suggestions': suggestions})

@screening_bp.route('/api/screening-status/<int:screening_id>')
@user_required
def get_screening_status(screening_id):
    """Get detailed status for a specific screening"""
    screening = Screening.query.get_or_404(screening_id)
    
    return jsonify({
        'success': True,
        'screening': {
            'id': screening.id,
            'name': screening.screening_type.name,
            'status': screening.status,
            'last_completed': screening.last_completed_date.isoformat() if screening.last_completed_date else None,
            'next_due': screening.next_due_date.isoformat() if screening.next_due_date else None,
            'matched_documents': len(screening.matched_documents) if screening.matched_documents else 0
        }
    })
