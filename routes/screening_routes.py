"""
Screening management routes for CRUD operations on screening types and patient screenings.
Handles screening list display, type management, and automated screening processing.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import json
import logging
from datetime import datetime

from models import Patient, ScreeningType, Screening, MedicalDocument, db
from core.engine import ScreeningEngine
from presets.loader import PresetLoader
from admin.logs import AdminLogger

logger = logging.getLogger(__name__)
screening_bp = Blueprint('screening', __name__)
admin_logger = AdminLogger()

@screening_bp.route('/list')
@login_required
def screening_list():
    """Main screening list view with tabs for list, types, and settings."""
    try:
        # Get all patients for the dropdown
        patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        
        # Get all screening types for management
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        
        # Get recent screenings for display
        recent_screenings = Screening.query.join(Patient).join(ScreeningType).order_by(
            Screening.updated_at.desc()
        ).limit(50).all()
        
        return render_template('screening/screening_list.html',
                             patients=patients,
                             screening_types=screening_types,
                             recent_screenings=recent_screenings)
        
    except Exception as e:
        logger.error(f"Error loading screening list: {e}")
        flash('Error loading screening data', 'error')
        return render_template('screening/screening_list.html',
                             patients=[],
                             screening_types=[],
                             recent_screenings=[])

@screening_bp.route('/patient/<int:patient_id>')
@login_required
def patient_screenings(patient_id):
    """View screenings for a specific patient."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Get current screening evaluations
        screening_engine = ScreeningEngine()
        screening_results = screening_engine.evaluate_patient_screenings(patient_id)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='view_patient_screenings',
            details=f'Viewed screenings for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        return render_template('screening/patient_screenings.html',
                             patient=patient,
                             screening_results=screening_results)
        
    except Exception as e:
        logger.error(f"Error loading patient screenings: {e}")
        flash('Error loading patient screening data', 'error')
        return redirect(url_for('screening.screening_list'))

@screening_bp.route('/types')
@login_required
def screening_types():
    """Manage screening types."""
    try:
        screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
        
        # Get preset loader for importing presets
        preset_loader = PresetLoader()
        available_presets = preset_loader.list_available_presets()
        
        return render_template('screening/screening_types.html',
                             screening_types=screening_types,
                             presets=available_presets.get('presets', []))
        
    except Exception as e:
        logger.error(f"Error loading screening types: {e}")
        flash('Error loading screening types', 'error')
        return render_template('screening/screening_types.html',
                             screening_types=[],
                             presets=[])

@screening_bp.route('/types/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add a new screening type."""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description', '')
            keywords = request.form.getlist('keywords')
            gender_requirement = request.form.get('gender_requirement')
            min_age = request.form.get('min_age', type=int)
            max_age = request.form.get('max_age', type=int)
            frequency_years = request.form.get('frequency_years', type=int)
            frequency_months = request.form.get('frequency_months', type=int)
            trigger_conditions = request.form.getlist('trigger_conditions')
            is_active = request.form.get('is_active') == 'on'
            
            # Validate required fields
            if not name:
                flash('Screening name is required', 'error')
                return render_template('screening/add_screening_type.html')
            
            # Check for duplicate name
            existing = ScreeningType.query.filter_by(name=name).first()
            if existing:
                flash('A screening type with this name already exists', 'error')
                return render_template('screening/add_screening_type.html')
            
            # Create new screening type
            screening_type = ScreeningType(
                name=name,
                description=description,
                keywords=json.dumps([k.strip() for k in keywords if k.strip()]),
                gender_requirement=gender_requirement if gender_requirement else None,
                min_age=min_age,
                max_age=max_age,
                frequency_years=frequency_years,
                frequency_months=frequency_months,
                trigger_conditions=json.dumps([c.strip() for c in trigger_conditions if c.strip()]),
                is_active=is_active
            )
            
            db.session.add(screening_type)
            db.session.commit()
            
            admin_logger.log_action(
                user_id=current_user.id,
                action='add_screening_type',
                details=f'Added screening type: {name}',
                ip_address=request.remote_addr
            )
            
            flash(f'Screening type "{name}" added successfully', 'success')
            return redirect(url_for('screening.screening_types'))
            
        except Exception as e:
            logger.error(f"Error adding screening type: {e}")
            db.session.rollback()
            flash('Error adding screening type', 'error')
    
    return render_template('screening/add_screening_type.html')

@screening_bp.route('/types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(type_id):
    """Edit an existing screening type."""
    screening_type = ScreeningType.query.get_or_404(type_id)
    
    if request.method == 'POST':
        try:
            # Update screening type fields
            screening_type.name = request.form.get('name')
            screening_type.description = request.form.get('description', '')
            keywords = request.form.getlist('keywords')
            screening_type.keywords = json.dumps([k.strip() for k in keywords if k.strip()])
            screening_type.gender_requirement = request.form.get('gender_requirement') or None
            screening_type.min_age = request.form.get('min_age', type=int)
            screening_type.max_age = request.form.get('max_age', type=int)
            screening_type.frequency_years = request.form.get('frequency_years', type=int)
            screening_type.frequency_months = request.form.get('frequency_months', type=int)
            trigger_conditions = request.form.getlist('trigger_conditions')
            screening_type.trigger_conditions = json.dumps([c.strip() for c in trigger_conditions if c.strip()])
            screening_type.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            
            admin_logger.log_action(
                user_id=current_user.id,
                action='edit_screening_type',
                details=f'Edited screening type: {screening_type.name}',
                ip_address=request.remote_addr
            )
            
            flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
            return redirect(url_for('screening.screening_types'))
            
        except Exception as e:
            logger.error(f"Error editing screening type: {e}")
            db.session.rollback()
            flash('Error updating screening type', 'error')
    
    # Parse existing data for form
    keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
    trigger_conditions = json.loads(screening_type.trigger_conditions) if screening_type.trigger_conditions else []
    
    return render_template('screening/edit_screening_type.html',
                         screening_type=screening_type,
                         keywords=keywords,
                         trigger_conditions=trigger_conditions)

@screening_bp.route('/types/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_screening_type(type_id):
    """Delete a screening type."""
    try:
        screening_type = ScreeningType.query.get_or_404(type_id)
        type_name = screening_type.name
        
        # Check if screening type is in use
        screenings_count = Screening.query.filter_by(screening_type_id=type_id).count()
        
        if screenings_count > 0:
            flash(f'Cannot delete screening type "{type_name}" - it is currently used by {screenings_count} screenings', 'error')
            return redirect(url_for('screening.screening_types'))
        
        db.session.delete(screening_type)
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='delete_screening_type',
            details=f'Deleted screening type: {type_name}',
            ip_address=request.remote_addr
        )
        
        flash(f'Screening type "{type_name}" deleted successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting screening type: {e}")
        db.session.rollback()
        flash('Error deleting screening type', 'error')
    
    return redirect(url_for('screening.screening_types'))

@screening_bp.route('/refresh/<int:patient_id>', methods=['POST'])
@login_required
def refresh_patient_screenings(patient_id):
    """Refresh screenings for a specific patient."""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        screening_engine = ScreeningEngine()
        result = screening_engine.refresh_patient_screenings(patient_id)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='refresh_patient_screenings',
            details=f'Refreshed screenings for patient {patient.full_name}',
            ip_address=request.remote_addr
        )
        
        if result['success']:
            flash(f'Successfully refreshed {result["screenings_evaluated"]} screenings for {patient.full_name}', 'success')
        else:
            flash(f'Error refreshing screenings: {result.get("error", "Unknown error")}', 'error')
        
    except Exception as e:
        logger.error(f"Error refreshing patient screenings: {e}")
        flash('Error refreshing screenings', 'error')
    
    return redirect(url_for('screening.patient_screenings', patient_id=patient_id))

@screening_bp.route('/bulk_refresh', methods=['POST'])
@login_required
def bulk_refresh_screenings():
    """Refresh screenings for all patients."""
    try:
        screening_engine = ScreeningEngine()
        result = screening_engine.bulk_refresh_screenings()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='bulk_refresh_screenings',
            details=f'Bulk refresh completed: {result.get("successful_refreshes", 0)} successful, {result.get("failed_refreshes", 0)} failed',
            ip_address=request.remote_addr
        )
        
        if result['success']:
            flash(f'Bulk refresh completed: {result["successful_refreshes"]} patients updated successfully', 'success')
            if result['failed_refreshes'] > 0:
                flash(f'{result["failed_refreshes"]} patients failed to refresh', 'warning')
        else:
            flash(f'Bulk refresh failed: {result.get("error", "Unknown error")}', 'error')
        
    except Exception as e:
        logger.error(f"Error in bulk refresh: {e}")
        flash('Error performing bulk refresh', 'error')
    
    return redirect(url_for('screening.screening_list'))

@screening_bp.route('/import_preset', methods=['POST'])
@login_required
def import_preset():
    """Import a screening type preset."""
    try:
        preset_name = request.form.get('preset_name')
        overwrite_existing = request.form.get('overwrite_existing') == 'on'
        
        if not preset_name:
            flash('Please select a preset to import', 'error')
            return redirect(url_for('screening.screening_types'))
        
        preset_loader = PresetLoader()
        result = preset_loader.import_preset_to_database(preset_name, overwrite_existing)
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='import_screening_preset',
            details=f'Imported preset: {preset_name}, imported: {result.get("imported_count", 0)}, skipped: {result.get("skipped_count", 0)}',
            ip_address=request.remote_addr
        )
        
        if result['success']:
            flash(f'Successfully imported {result["imported_count"]} screening types from "{preset_name}"', 'success')
            if result['skipped_count'] > 0:
                flash(f'{result["skipped_count"]} screening types were skipped (already exist)', 'info')
        else:
            flash(f'Error importing preset: {result.get("error", "Unknown error")}', 'error')
        
    except Exception as e:
        logger.error(f"Error importing preset: {e}")
        flash('Error importing screening preset', 'error')
    
    return redirect(url_for('screening.screening_types'))

@screening_bp.route('/export_screenings')
@login_required
def export_screenings():
    """Export current screening types as a preset."""
    try:
        preset_loader = PresetLoader()
        result = preset_loader.export_current_screenings()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='export_screening_types',
            details=f'Exported {result.get("screening_count", 0)} screening types',
            ip_address=request.remote_addr
        )
        
        if result['success']:
            flash(f'Successfully exported {result["screening_count"]} screening types to {result["filename"]}', 'success')
        else:
            flash(f'Error exporting screening types: {result.get("error", "Unknown error")}', 'error')
        
    except Exception as e:
        logger.error(f"Error exporting screening types: {e}")
        flash('Error exporting screening types', 'error')
    
    return redirect(url_for('screening.screening_types'))

@screening_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """API endpoint to get keywords for a screening type."""
    try:
        screening_type = ScreeningType.query.get(screening_type_id)
        
        if not screening_type:
            return jsonify({'success': False, 'error': 'Screening type not found'}), 404
        
        keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
        
        return jsonify({
            'success': True,
            'keywords': keywords,
            'screening_name': screening_type.name
        })
        
    except Exception as e:
        logger.error(f"Error getting screening keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@screening_bp.route('/settings')
@login_required
def checklist_settings():
    """Manage checklist and prep sheet settings."""
    try:
        from models import ChecklistSettings, PHIFilterSettings
        
        # Get current settings
        checklist_settings = ChecklistSettings.query.first()
        phi_settings = PHIFilterSettings.query.first()
        
        if not checklist_settings:
            checklist_settings = ChecklistSettings()
            db.session.add(checklist_settings)
            db.session.commit()
        
        if not phi_settings:
            phi_settings = PHIFilterSettings()
            db.session.add(phi_settings)
            db.session.commit()
        
        return render_template('screening/checklist_settings.html',
                             checklist_settings=checklist_settings,
                             phi_settings=phi_settings)
        
    except Exception as e:
        logger.error(f"Error loading checklist settings: {e}")
        flash('Error loading settings', 'error')
        return redirect(url_for('screening.screening_list'))

@screening_bp.route('/settings/update', methods=['POST'])
@login_required
def update_checklist_settings():
    """Update checklist and prep sheet settings."""
    try:
        from models import ChecklistSettings
        
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        # Update cutoff settings
        settings.lab_cutoff_months = request.form.get('lab_cutoff_months', type=int) or 12
        settings.imaging_cutoff_months = request.form.get('imaging_cutoff_months', type=int) or 24
        settings.consult_cutoff_months = request.form.get('consult_cutoff_months', type=int) or 12
        settings.hospital_cutoff_months = request.form.get('hospital_cutoff_months', type=int) or 12
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        admin_logger.log_action(
            user_id=current_user.id,
            action='update_checklist_settings',
            details='Updated prep sheet cutoff settings',
            ip_address=request.remote_addr
        )
        
        flash('Checklist settings updated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error updating checklist settings: {e}")
        db.session.rollback()
        flash('Error updating settings', 'error')
    
    return redirect(url_for('screening.checklist_settings'))
