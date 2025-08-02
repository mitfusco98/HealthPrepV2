"""
Screening management routes for main user interface
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import json
import logging
from models import Patient, ScreeningType, Screening, MedicalDocument
from core.engine import screening_engine
from admin.logs import admin_logger

logger = logging.getLogger(__name__)

screening_bp = Blueprint('screening', __name__)

@screening_bp.route('/list')
@screening_bp.route('/')
@login_required
def screening_list():
    """Main screening list interface with multi-modal tabs"""
    try:
        # Get filter parameters
        patient_filter = request.args.get('patient', '').strip()
        status_filter = request.args.get('status', '').strip()
        screening_type_filter = request.args.get('screening_type', '').strip()
        
        # Get all patients for dropdown
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        # Get all screening types for dropdown
        screening_types = ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
        
        # Base query for screenings
        screenings_query = Screening.query.join(Patient).join(ScreeningType)
        
        # Apply filters
        if patient_filter:
            try:
                patient_id = int(patient_filter)
                screenings_query = screenings_query.filter(Screening.patient_id == patient_id)
            except ValueError:
                # Filter by name if not a valid ID
                screenings_query = screenings_query.filter(
                    (Patient.first_name.ilike(f'%{patient_filter}%')) |
                    (Patient.last_name.ilike(f'%{patient_filter}%'))
                )
        
        if status_filter:
            screenings_query = screenings_query.filter(Screening.status == status_filter)
        
        if screening_type_filter:
            try:
                screening_type_id = int(screening_type_filter)
                screenings_query = screenings_query.filter(Screening.screening_type_id == screening_type_id)
            except ValueError:
                pass
        
        # Get filtered screenings
        screenings = screenings_query.order_by(
            Screening.status.desc(),  # Due first
            Patient.last_name,
            Patient.first_name
        ).all()
        
        # Get screening statistics
        stats = {
            'total': len(screenings),
            'due': len([s for s in screenings if s.status == 'Due']),
            'due_soon': len([s for s in screenings if s.status == 'Due Soon']),
            'complete': len([s for s in screenings if s.status == 'Complete'])
        }
        
        return render_template('screening/screening_list.html',
                             screenings=screenings,
                             patients=patients,
                             screening_types=screening_types,
                             stats=stats,
                             filters={
                                 'patient': patient_filter,
                                 'status': status_filter,
                                 'screening_type': screening_type_filter
                             })
        
    except Exception as e:
        logger.error(f"Error loading screening list: {str(e)}")
        flash('Error loading screening list. Please try again.', 'error')
        return render_template('screening/screening_list.html',
                             screenings=[],
                             patients=[],
                             screening_types=[],
                             stats={'total': 0, 'due': 0, 'due_soon': 0, 'complete': 0},
                             filters={})

@screening_bp.route('/types')
@login_required
def screening_types():
    """Screening types management"""
    try:
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        
        return render_template('screening/screening_types.html',
                             screening_types=screening_types)
        
    except Exception as e:
        logger.error(f"Error loading screening types: {str(e)}")
        flash('Error loading screening types. Please try again.', 'error')
        return render_template('screening/screening_types.html', screening_types=[])

@screening_bp.route('/types/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add new screening type"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            keywords_raw = request.form.get('keywords', '').strip()
            frequency_months = request.form.get('frequency_months', type=int)
            frequency_unit = request.form.get('frequency_unit', 'months').strip()
            min_age = request.form.get('min_age', type=int)
            max_age = request.form.get('max_age', type=int)
            gender_restrictions = request.form.get('gender_restrictions', '').strip()
            trigger_conditions_raw = request.form.get('trigger_conditions', '').strip()
            
            if not name:
                flash('Screening type name is required.', 'error')
                return render_template('screening/add_screening_type.html')
            
            # Check if name already exists
            existing = ScreeningType.query.filter_by(name=name).first()
            if existing:
                flash('A screening type with this name already exists.', 'error')
                return render_template('screening/add_screening_type.html')
            
            # Process keywords
            keywords = []
            if keywords_raw:
                keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
            
            # Process trigger conditions
            trigger_conditions = []
            if trigger_conditions_raw:
                trigger_conditions = [t.strip() for t in trigger_conditions_raw.split(',') if t.strip()]
            
            # Create new screening type
            screening_type = ScreeningType(
                name=name,
                description=description,
                keywords=json.dumps(keywords),
                frequency_months=frequency_months or 12,
                frequency_unit=frequency_unit,
                min_age=min_age,
                max_age=max_age,
                gender_restrictions=gender_restrictions if gender_restrictions else None,
                trigger_conditions=json.dumps(trigger_conditions),
                is_active=True
            )
            
            from app import db
            db.session.add(screening_type)
            db.session.commit()
            
            # Log the action
            admin_logger.log_action(
                user_id=current_user.id,
                action='create_screening_type',
                resource_type='ScreeningType',
                resource_id=screening_type.id,
                details=f'Created screening type: {name}',
                ip_address=request.remote_addr
            )
            
            flash(f'Screening type "{name}" created successfully.', 'success')
            return redirect(url_for('screening.screening_types'))
            
        except Exception as e:
            logger.error(f"Error creating screening type: {str(e)}")
            flash('Error creating screening type. Please try again.', 'error')
    
    return render_template('screening/add_screening_type.html')

@screening_bp.route('/types/<int:screening_type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(screening_type_id):
    """Edit existing screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        
        if request.method == 'POST':
            # Update screening type
            original_name = screening_type.name
            
            screening_type.name = request.form.get('name', '').strip()
            screening_type.description = request.form.get('description', '').strip()
            
            keywords_raw = request.form.get('keywords', '').strip()
            keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()] if keywords_raw else []
            screening_type.keywords = json.dumps(keywords)
            
            screening_type.frequency_months = request.form.get('frequency_months', type=int) or 12
            screening_type.frequency_unit = request.form.get('frequency_unit', 'months').strip()
            screening_type.min_age = request.form.get('min_age', type=int)
            screening_type.max_age = request.form.get('max_age', type=int)
            
            gender_restrictions = request.form.get('gender_restrictions', '').strip()
            screening_type.gender_restrictions = gender_restrictions if gender_restrictions else None
            
            trigger_conditions_raw = request.form.get('trigger_conditions', '').strip()
            trigger_conditions = [t.strip() for t in trigger_conditions_raw.split(',') if t.strip()] if trigger_conditions_raw else []
            screening_type.trigger_conditions = json.dumps(trigger_conditions)
            
            screening_type.is_active = bool(request.form.get('is_active'))
            
            from app import db
            db.session.commit()
            
            # Log the action
            admin_logger.log_action(
                user_id=current_user.id,
                action='update_screening_type',
                resource_type='ScreeningType',
                resource_id=screening_type.id,
                details=f'Updated screening type: {original_name} -> {screening_type.name}',
                ip_address=request.remote_addr
            )
            
            flash(f'Screening type "{screening_type.name}" updated successfully.', 'success')
            return redirect(url_for('screening.screening_types'))
        
        # Prepare data for form
        keywords_list = json.loads(screening_type.keywords) if screening_type.keywords else []
        trigger_conditions_list = json.loads(screening_type.trigger_conditions) if screening_type.trigger_conditions else []
        
        return render_template('screening/edit_screening_type.html',
                             screening_type=screening_type,
                             keywords_text=', '.join(keywords_list),
                             trigger_conditions_text=', '.join(trigger_conditions_list))
        
    except Exception as e:
        logger.error(f"Error editing screening type {screening_type_id}: {str(e)}")
        flash('Error loading screening type. Please try again.', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/refresh')
@login_required
def refresh_screenings():
    """Refresh all patient screenings"""
    try:
        results = screening_engine.refresh_all_screenings()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='refresh_screenings',
            details=f'Refreshed screenings: {results["success"]} successful, {results["errors"]} errors',
            ip_address=request.remote_addr
        )
        
        if results['errors'] > 0:
            flash(f'Screenings refreshed with {results["errors"]} errors. {results["success"]} patients processed successfully.', 'warning')
        else:
            flash(f'Successfully refreshed screenings for {results["success"]} patients.', 'success')
        
    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        flash('Error refreshing screenings. Please try again.', 'error')
    
    return redirect(url_for('screening.screening_list'))

@screening_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """API endpoint to get keywords for a screening type"""
    try:
        screening_type = ScreeningType.query.get(screening_type_id)
        if not screening_type:
            return jsonify({'success': False, 'error': 'Screening type not found'}), 404
        
        keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
        
        return jsonify({
            'success': True,
            'keywords': keywords,
            'screening_type': screening_type.name
        })
        
    except Exception as e:
        logger.error(f"Error getting keywords for screening type {screening_type_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@screening_bp.route('/settings')
@login_required
def checklist_settings():
    """Checklist settings page"""
    try:
        from models import ChecklistSettings
        settings = ChecklistSettings.query.first()
        
        if not settings:
            # Create default settings
            settings = ChecklistSettings()
            from app import db
            db.session.add(settings)
            db.session.commit()
        
        return render_template('screening/checklist_settings.html', settings=settings)
        
    except Exception as e:
        logger.error(f"Error loading checklist settings: {str(e)}")
        flash('Error loading settings. Please try again.', 'error')
        return redirect(url_for('screening.screening_list'))

@screening_bp.route('/settings', methods=['POST'])
@login_required
def update_checklist_settings():
    """Update checklist settings"""
    try:
        from models import ChecklistSettings
        from app import db
        
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        # Update settings
        settings.labs_cutoff_months = request.form.get('labs_cutoff_months', type=int) or 12
        settings.imaging_cutoff_months = request.form.get('imaging_cutoff_months', type=int) or 24
        settings.consults_cutoff_months = request.form.get('consults_cutoff_months', type=int) or 12
        settings.hospital_cutoff_months = request.form.get('hospital_cutoff_months', type=int) or 12
        settings.show_confidence_indicators = bool(request.form.get('show_confidence_indicators'))
        settings.phi_filtering_enabled = bool(request.form.get('phi_filtering_enabled'))
        
        db.session.commit()
        
        # Log the action
        admin_logger.log_action(
            user_id=current_user.id,
            action='update_checklist_settings',
            details='Updated checklist settings',
            ip_address=request.remote_addr
        )
        
        flash('Checklist settings updated successfully.', 'success')
        
    except Exception as e:
        logger.error(f"Error updating checklist settings: {str(e)}")
        flash('Error updating settings. Please try again.', 'error')
    
    return redirect(url_for('screening.checklist_settings'))
