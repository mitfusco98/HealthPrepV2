"""
Fixing the URL reference for 'dashboard' to 'ui.dashboard' in screening routes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging

from models import ScreeningType, Screening, Patient
from core.engine import ScreeningEngine
from admin.logs import AdminLogManager
from forms import ScreeningTypeForm, ChecklistSettingsForm

logger = logging.getLogger(__name__)

screening_bp = Blueprint('screening', __name__)

@screening_bp.route('/list')
@login_required
def screening_list():
    """Main screening list with multiple modes"""
    try:
        # Get all patients with their screenings
        patients = Patient.query.all()

        # Get all screening types
        screening_types = ScreeningType.query.filter_by(is_active=True).all()

        # Get all screenings with status summary
        screenings = Screening.query.join(ScreeningType).filter_by(is_active=True).all()

        # Organize data for display
        screening_data = []
        for screening in screenings:
            screening_data.append({
                'id': screening.id,
                'patient_name': f"{screening.patient.first_name} {screening.patient.last_name}",
                'patient_mrn': screening.patient.mrn,
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed_date,
                'frequency': screening.screening_type.frequency_years,
                'matched_documents': len(screening.matched_documents),
                'patient_id': screening.patient_id
            })

        return render_template('screening/screening_list.html',
                             screenings=screening_data,
                             screening_types=screening_types,
                             patients=patients)

    except Exception as e:
        logger.error(f"Error in screening list: {str(e)}")
        flash('Error loading screening list', 'error')
        return render_template('error/500.html'), 500

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
        flash('Error loading screening types', 'error')
        return render_template('error/500.html'), 500

@screening_bp.route('/type/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add new screening type"""
    try:
        form = ScreeningTypeForm()

        if form.validate_on_submit():
            # Create new screening type
            screening_type = ScreeningType(
                name=form.name.data,
                description=form.description.data,
                keywords=form.keywords.data.split(',') if form.keywords.data else [],
                eligible_genders=form.eligible_genders.data,
                min_age=form.min_age.data,
                max_age=form.max_age.data,
                frequency_years=form.frequency_years.data,
                trigger_conditions=form.trigger_conditions.data.split(',') if form.trigger_conditions.data else []
            )

            db.session.add(screening_type)
            db.session.commit()

            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='add_screening_type',
                target_type='screening_type',
                target_id=screening_type.id,
                details={'name': screening_type.name}
            )

            flash(f'Screening type "{screening_type.name}" added successfully', 'success')
            return redirect(url_for('screening.screening_types'))

        return render_template('screening/add_screening_type.html', form=form)

    except Exception as e:
        logger.error(f"Error adding screening type: {str(e)}")
        flash('Error adding screening type', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:screening_type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(screening_type_id):
    """Edit existing screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        form = ScreeningTypeForm(obj=screening_type)

        if form.validate_on_submit():
            # Update screening type
            screening_type.name = form.name.data
            screening_type.description = form.description.data
            screening_type.keywords = form.keywords.data.split(',') if form.keywords.data else []
            screening_type.eligible_genders = form.eligible_genders.data
            screening_type.min_age = form.min_age.data
            screening_type.max_age = form.max_age.data
            screening_type.frequency_years = form.frequency_years.data
            screening_type.trigger_conditions = form.trigger_conditions.data.split(',') if form.trigger_conditions.data else []

            db.session.commit()

            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='edit_screening_type',
                target_type='screening_type',
                target_id=screening_type.id,
                details={'name': screening_type.name}
            )

            flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
            return redirect(url_for('screening.screening_types'))

        # Populate form with existing data
        if screening_type.keywords:
            form.keywords.data = ','.join(screening_type.keywords)
        if screening_type.trigger_conditions:
            form.trigger_conditions.data = ','.join(screening_type.trigger_conditions)

        return render_template('screening/edit_screening_type.html', 
                             form=form, screening_type=screening_type)

    except Exception as e:
        logger.error(f"Error editing screening type: {str(e)}")
        flash('Error editing screening type', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:screening_type_id>/toggle-status', methods=['POST'])
@login_required
def toggle_screening_type_status(screening_type_id):
    """Toggle screening type active status"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)

        screening_type.is_active = not screening_type.is_active
        db.session.commit()

        # Log the action
        log_manager = AdminLogManager()
        log_manager.log_action(
            user_id=current_user.id,
            action='toggle_screening_type_status',
            target_type='screening_type',
            target_id=screening_type.id,
            details={'new_status': screening_type.is_active}
        )

        status = 'activated' if screening_type.is_active else 'deactivated'
        flash(f'Screening type "{screening_type.name}" {status}', 'success')

        return redirect(url_for('screening.screening_types'))

    except Exception as e:
        logger.error(f"Error toggling screening type status: {str(e)}")
        flash('Error updating screening type status', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:screening_type_id>/delete', methods=['POST'])
@login_required
def delete_screening_type(screening_type_id):
    """Delete screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)

        # Check if screening type is in use
        active_screenings = Screening.query.filter_by(screening_type_id=screening_type_id).count()
        if active_screenings > 0:
            flash(f'Cannot delete screening type "{screening_type.name}" - it has {active_screenings} active screenings', 'error')
            return redirect(url_for('screening.screening_types'))

        screening_name = screening_type.name
        db.session.delete(screening_type)
        db.session.commit()

        # Log the action
        log_manager = AdminLogManager()
        log_manager.log_action(
            user_id=current_user.id,
            action='delete_screening_type',
            target_type='screening_type',
            target_id=screening_type_id,
            details={'name': screening_name}
        )

        flash(f'Screening type "{screening_name}" deleted successfully', 'success')
        return redirect(url_for('screening.screening_types'))

    except Exception as e:
        logger.error(f"Error deleting screening type: {str(e)}")
        flash('Error deleting screening type', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def checklist_settings():
    """Checklist settings management"""
    try:
        from models import ChecklistSettings

        settings = ChecklistSettings.query.first()
        form = ChecklistSettingsForm(obj=settings)

        if form.validate_on_submit():
            if not settings:
                settings = ChecklistSettings()
                db.session.add(settings)

            settings.lab_cutoff_months = form.lab_cutoff_months.data
            settings.imaging_cutoff_months = form.imaging_cutoff_months.data
            settings.consult_cutoff_months = form.consult_cutoff_months.data
            settings.hospital_cutoff_months = form.hospital_cutoff_months.data

            db.session.commit()

            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='update_checklist_settings',
                details={
                    'lab_cutoff': settings.lab_cutoff_months,
                    'imaging_cutoff': settings.imaging_cutoff_months,
                    'consult_cutoff': settings.consult_cutoff_months,
                    'hospital_cutoff': settings.hospital_cutoff_months
                }
            )

            flash('Checklist settings updated successfully', 'success')
            return redirect(url_for('screening.checklist_settings'))

        return render_template('screening/checklist_settings.html', 
                             form=form, settings=settings)

    except Exception as e:
        logger.error(f"Error in checklist settings: {str(e)}")
        flash('Error loading checklist settings', 'error')
        return render_template('error/500.html'), 500

@screening_bp.route('/refresh', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh screenings using the screening engine"""
    try:
        engine = ScreeningEngine()

        # Get refresh type
        refresh_type = request.form.get('refresh_type', 'all')
        patient_id = request.form.get('patient_id', type=int)

        if refresh_type == 'patient' and patient_id:
            # Refresh specific patient
            result = engine.process_patient_screenings(patient_id, refresh_all=True)
            flash(f'Refreshed screenings for patient. Processed: {result["processed_screenings"]}', 'success')

            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='refresh_patient_screenings',
                target_type='patient',
                target_id=patient_id,
                details=result
            )

        else:
            # Refresh all screenings
            result = engine.refresh_all_screenings()
            flash(f'Refreshed all screenings. Processed {result["total_screenings"]} screenings for {result["processed_patients"]} patients', 'success')

            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='refresh_all_screenings',
                details=result
            )

        return redirect(url_for('screening.screening_list'))

    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        flash('Error refreshing screenings', 'error')
        return redirect(url_for('screening.screening_list'))

@screening_bp.route('/api/screening-status/<int:patient_id>')
@login_required
def api_screening_status(patient_id):
    """API endpoint to get screening status for a patient"""
    try:
        screenings = Screening.query.filter_by(
            patient_id=patient_id
        ).join(ScreeningType).filter_by(is_active=True).all()

        screening_data = []
        for screening in screenings:
            screening_data.append({
                'id': screening.id,
                'name': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed_date.isoformat() if screening.last_completed_date else None,
                'next_due': screening.next_due_date.isoformat() if screening.next_due_date else None,
                'matched_documents': len(screening.matched_documents)
            })

        return jsonify({
            'success': True,
            'screenings': screening_data,
            'patient_id': patient_id
        })

    except Exception as e:
        logger.error(f"Error getting screening status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@screening_bp.route('/presets')
@login_required
def screening_presets():
    """Screening type presets management"""
    try:
        # This would typically load preset configurations
        # For now, return a basic page

        presets = [
            {
                'name': 'Primary Care Bundle',
                'description': 'Common screenings for primary care',
                'screening_count': 8
            },
            {
                'name': 'Cardiology Bundle',
                'description': 'Cardiac screening protocols',
                'screening_count': 5
            },
            {
                'name': 'Women\'s Health Bundle',
                'description': 'Screening for women\'s health',
                'screening_count': 6
            }
        ]

        return render_template('screening/presets.html', presets=presets)

    except Exception as e:
        logger.error(f"Error loading screening presets: {str(e)}")
        flash('Error loading screening presets', 'error')
        return render_template('error/500.html'), 500

@screening_bp.route('/import-preset', methods=['POST'])
@login_required
def import_preset():
    """Import screening type preset"""
    try:
        preset_name = request.form.get('preset_name')

        # This would implement preset import logic
        # For now, show a placeholder message

        flash(f'Preset import for "{preset_name}" not yet implemented', 'info')
        return redirect(url_for('ui.dashboard'))

    except Exception as e:
        logger.error(f"Error importing preset: {str(e)}")
        flash('Error importing preset', 'error')
        return redirect(url_for('screening.screening_presets'))