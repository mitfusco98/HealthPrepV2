"""
Screening management routes
Handles screening list, types management, and checklist settings
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging
import json

from app import db
from models import (Patient, Screening, ScreeningType, ScreeningVariant, Document, 
                   ScreeningDocumentMatch, ChecklistSettings)
from forms import ScreeningTypeForm, ScreeningVariantForm, ChecklistSettingsForm
from core.engine import ScreeningEngine
from core.matcher import FuzzyMatcher
from core.variants import VariantHandler

screening_bp = Blueprint('screening', __name__)
logger = logging.getLogger(__name__)

@screening_bp.route('/list')
@login_required
def screening_list():
    """Main screening list with multiple views"""
    try:
        view_mode = request.args.get('view', 'list')  # list, types, checklist
        patient_filter = request.args.get('patient', '', type=str)
        status_filter = request.args.get('status', '', type=str)
        screening_type_filter = request.args.get('screening_type', '', type=str)
        
        if view_mode == 'types':
            # Screening types management view
            screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
            return render_template('screening/screening_list.html',
                                 view_mode='types',
                                 screening_types=screening_types)
        
        elif view_mode == 'checklist':
            # Checklist settings view
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
            
            form = ChecklistSettingsForm(obj=settings)
            return render_template('screening/screening_list.html',
                                 view_mode='checklist',
                                 form=form,
                                 settings=settings)
        
        else:
            # Main screening list view
            query = Screening.query.join(Patient).join(ScreeningType)
            
            # Apply filters
            if patient_filter:
                query = query.filter(
                    db.or_(
                        Patient.first_name.contains(patient_filter),
                        Patient.last_name.contains(patient_filter),
                        Patient.mrn.contains(patient_filter)
                    )
                )
            
            if status_filter:
                query = query.filter(Screening.status == status_filter)
            
            if screening_type_filter:
                query = query.filter(ScreeningType.name.contains(screening_type_filter))
            
            screenings = query.order_by(Patient.last_name, Patient.first_name, ScreeningType.name).all()
            
            # Get filter options
            patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
            screening_types = ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
            
            return render_template('screening/screening_list.html',
                                 view_mode='list',
                                 screenings=screenings,
                                 patients=patients,
                                 screening_types=screening_types,
                                 filters={
                                     'patient': patient_filter,
                                     'status': status_filter,
                                     'screening_type': screening_type_filter
                                 })
        
    except Exception as e:
        logger.error(f"Screening list error: {str(e)}")
        flash('Error loading screening data', 'error')
        return render_template('screening/screening_list.html', view_mode='list')

@screening_bp.route('/type/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    """Add new screening type"""
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        try:
            # Parse keywords and trigger conditions
            keywords = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            trigger_conditions = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            
            screening_type = ScreeningType(
                name=form.name.data,
                description=form.description.data,
                gender_criteria=form.gender_criteria.data,
                age_min=form.age_min.data,
                age_max=form.age_max.data,
                frequency_number=form.frequency_number.data,
                frequency_unit=form.frequency_unit.data,
                is_active=form.is_active.data,
                created_by=current_user.id
            )
            
            screening_type.set_keywords(keywords)
            screening_type.set_trigger_conditions(trigger_conditions)
            
            db.session.add(screening_type)
            db.session.commit()
            
            flash(f'Screening type "{screening_type.name}" created successfully', 'success')
            return redirect(url_for('screening.screening_list', view='types'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add screening type error: {str(e)}")
            flash('Error creating screening type', 'error')
    
    return render_template('screening/screening_type_form.html', form=form, title='Add Screening Type')

@screening_bp.route('/type/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(type_id):
    """Edit existing screening type"""
    screening_type = ScreeningType.query.get_or_404(type_id)
    
    # Populate form with existing data
    form = ScreeningTypeForm(obj=screening_type)
    
    # Convert keywords and trigger conditions to text
    if screening_type.get_keywords():
        form.keywords.data = '\n'.join(screening_type.get_keywords())
    if screening_type.get_trigger_conditions():
        form.trigger_conditions.data = '\n'.join(screening_type.get_trigger_conditions())
    
    if form.validate_on_submit():
        try:
            # Parse updated keywords and trigger conditions
            keywords = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            trigger_conditions = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            
            # Update screening type
            form.populate_obj(screening_type)
            screening_type.set_keywords(keywords)
            screening_type.set_trigger_conditions(trigger_conditions)
            
            db.session.commit()
            
            flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
            return redirect(url_for('screening.screening_list', view='types'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Edit screening type error: {str(e)}")
            flash('Error updating screening type', 'error')
    
    return render_template('screening/screening_type_form.html', 
                         form=form, 
                         screening_type=screening_type,
                         title='Edit Screening Type')

@screening_bp.route('/type/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_screening_type(type_id):
    """Delete screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(type_id)
        
        # Check if screening type is in use
        screenings_count = Screening.query.filter_by(screening_type_id=type_id).count()
        
        if screenings_count > 0:
            flash(f'Cannot delete screening type "{screening_type.name}" - it is used by {screenings_count} screenings', 'error')
        else:
            db.session.delete(screening_type)
            db.session.commit()
            flash(f'Screening type "{screening_type.name}" deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete screening type error: {str(e)}")
        flash('Error deleting screening type', 'error')
    
    return redirect(url_for('screening.screening_list', view='types'))

@screening_bp.route('/type/<int:type_id>/toggle-status', methods=['POST'])
@login_required
def toggle_screening_type_status(type_id):
    """Toggle screening type active status"""
    try:
        screening_type = ScreeningType.query.get_or_404(type_id)
        screening_type.is_active = not screening_type.is_active
        
        db.session.commit()
        
        status_text = 'activated' if screening_type.is_active else 'deactivated'
        flash(f'Screening type "{screening_type.name}" {status_text} successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Toggle screening type status error: {str(e)}")
        flash('Error updating screening type status', 'error')
    
    return redirect(url_for('screening.screening_list', view='types'))

@screening_bp.route('/refresh', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh screening matches using current criteria"""
    try:
        view_mode = request.form.get('view', 'list')
        
        engine = ScreeningEngine()
        
        if view_mode == 'types':
            # Refresh all screening matches
            results = engine.refresh_screening_matches()
            flash(f'Screening refresh complete: {results["screenings_updated"]} screenings updated, '
                 f'{results["new_matches"]} new document matches found', 'success')
        else:
            # Generate screenings for all patients
            patients = Patient.query.all()
            total_updated = 0
            
            for patient in patients:
                try:
                    results = engine.generate_patient_screenings(patient.id, force_refresh=True)
                    total_updated += results['screenings_created'] + results['screenings_updated']
                except Exception as e:
                    logger.error(f"Error refreshing screenings for patient {patient.id}: {str(e)}")
            
            flash(f'Screening refresh complete: {total_updated} screenings updated', 'success')
        
    except Exception as e:
        logger.error(f"Screening refresh error: {str(e)}")
        flash('Error refreshing screenings', 'error')
    
    return redirect(url_for('screening.screening_list', view=view_mode))

@screening_bp.route('/settings/update', methods=['POST'])
@login_required
def update_checklist_settings():
    """Update checklist settings"""
    try:
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        form = ChecklistSettingsForm()
        
        if form.validate_on_submit():
            form.populate_obj(settings)
            settings.updated_by = current_user.id
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Checklist settings updated successfully', 'success')
        else:
            flash('Error updating checklist settings', 'error')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update checklist settings error: {str(e)}")
        flash('Error updating checklist settings', 'error')
    
    return redirect(url_for('screening.screening_list', view='checklist'))

@screening_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """API endpoint to get keywords for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        keywords = screening_type.get_keywords()
        
        return jsonify({
            'success': True,
            'keywords': keywords,
            'screening_name': screening_type.name
        })
        
    except Exception as e:
        logger.error(f"Get screening keywords error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to load keywords'
        }), 500

@screening_bp.route('/api/suggest-keywords', methods=['POST'])
@login_required
def suggest_keywords():
    """API endpoint to suggest keywords based on document text"""
    try:
        text = request.json.get('text', '')
        existing_keywords = request.json.get('existing_keywords', [])
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'})
        
        matcher = FuzzyMatcher()
        suggestions = matcher.suggest_keywords(text, existing_keywords)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Suggest keywords error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate suggestions'
        }), 500

@screening_bp.route('/variant/add/<int:screening_type_id>', methods=['GET', 'POST'])
@login_required
def add_screening_variant(screening_type_id):
    """Add screening type variant"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    form = ScreeningVariantForm()
    
    if form.validate_on_submit():
        try:
            condition_keywords = [k.strip() for k in form.condition_keywords.data.split('\n') if k.strip()]
            additional_keywords = [k.strip() for k in form.additional_keywords.data.split('\n') if k.strip()]
            
            variant_handler = VariantHandler()
            variant = variant_handler.create_variant(
                screening_type_id=screening_type_id,
                variant_name=form.variant_name.data,
                condition_keywords=condition_keywords,
                frequency_number=form.frequency_number.data,
                frequency_unit=form.frequency_unit.data,
                additional_keywords=additional_keywords
            )
            
            flash(f'Screening variant "{variant.variant_name}" created successfully', 'success')
            return redirect(url_for('screening.screening_list', view='types'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add screening variant error: {str(e)}")
            flash('Error creating screening variant', 'error')
    
    return render_template('screening/screening_variant_form.html', 
                         form=form, 
                         screening_type=screening_type,
                         title='Add Screening Variant')

