"""
Fixing the URL reference for 'dashboard' to 'ui.dashboard' in screening routes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from routes.auth_routes import non_admin_required

from datetime import datetime
import logging

from models import ScreeningType, Screening, Patient
from core.engine import ScreeningEngine
from models import log_admin_event
from forms import ScreeningTypeForm
from app import db
import json

logger = logging.getLogger(__name__)

def _extract_base_screening_name(name):
    """Extract base screening name from variant name with connecting descriptors"""
    if not name:
        return name
    
    # Handle connecting descriptors like "Pulmonary Function Test - COPD Monitoring"
    # Split on common delimiters and take the first part as the base name
    delimiters = [' - ', ' – ', ' — ', ' (', ':']
    
    base_name = name
    for delimiter in delimiters:
        if delimiter in name:
            base_name = name.split(delimiter)[0].strip()
            break
    
    return base_name

screening_bp = Blueprint('screening', __name__)

@screening_bp.route('/list')
@login_required
@non_admin_required
def screening_list():
    """Main screening list view"""
    try:
        patient_filter = request.args.get('patient', '', type=str)
        status_filter = request.args.get('status', '', type=str)
        screening_type_filter = request.args.get('screening_type', '', type=str)

        # Main screening list view - FILTER BY ORGANIZATION
        query = Screening.query.join(Patient).join(ScreeningType).filter(
            Patient.org_id == current_user.org_id
        )

        # Apply filters
        if patient_filter:
            query = query.filter(
                db.or_(
                    Patient.name.ilike(f'%{patient_filter}%'),
                    Patient.mrn.ilike(f'%{patient_filter}%')
                )
            )

        if status_filter:
            query = query.filter(Screening.status == status_filter)

        if screening_type_filter:
            query = query.filter(ScreeningType.name == screening_type_filter)

        screenings = query.order_by(Patient.name, ScreeningType.name).all()

        # Get filter options - FILTER BY ORGANIZATION
        patients = Patient.query.filter_by(org_id=current_user.org_id).order_by(Patient.name).all()
        
        # Get screening types grouped by base name with variant counts for current organization
        screening_type_groups = []
        try:
            base_names_with_counts = ScreeningType.get_base_names_with_counts(org_id=current_user.org_id)
            
            for base_name, variant_count, all_active in base_names_with_counts:
                if all_active:  # Only include if all variants are active
                    if variant_count > 1:
                        display_name = f"{base_name} [{variant_count} variants]"
                    else:
                        display_name = base_name
                    
                    screening_type_groups.append({
                        'name': base_name,
                        'display_name': display_name,
                        'variant_count': variant_count
                    })
        except Exception as e:
            logger.error(f"Error getting screening type groups: {str(e)}")
            # Fallback to simple list if grouping fails - FILTER BY ORGANIZATION
            screening_types = ScreeningType.query.filter_by(
                org_id=current_user.org_id,
                is_active=True
            ).order_by(ScreeningType.name).all()
            
            # Group fallback screening types by base name
            base_name_groups = {}
            for st in screening_types:
                base_name = ScreeningType._extract_base_name(st.name)
                if base_name not in base_name_groups:
                    base_name_groups[base_name] = 0
                base_name_groups[base_name] += 1
            
            for base_name, count in base_name_groups.items():
                if count > 1:
                    display_name = f"{base_name} [{count} variants]"
                else:
                    display_name = base_name
                    
                screening_type_groups.append({
                    'name': base_name,
                    'display_name': display_name,
                    'variant_count': count
                })

        return render_template('screening/list.html',
                             screenings=screenings,
                             patients=patients,
                             screening_type_groups=screening_type_groups,
                             filters={
                                 'patient': patient_filter,
                                 'status': status_filter,
                                 'screening_type': screening_type_filter
                             })

    except Exception as e:
        logger.error(f"Screening list error: {str(e)}")
        flash('Error loading screening data', 'error')
        return render_template('screening/list.html',
                             screenings=[],
                             patients=[],
                             screening_type_groups=[],
                             filters={
                                 'patient': '',
                                 'status': '',
                                 'screening_type': ''
                             })

@screening_bp.route('/types')
@login_required
@non_admin_required
def screening_types():
    """Screening types management"""
    try:
        # CRITICAL: Only show screening types from user's organization
        screening_types = ScreeningType.query.filter_by(
            org_id=current_user.org_id
        ).order_by(ScreeningType.name).all()

        return render_template('screening/types.html',
                             screening_types=screening_types)

    except Exception as e:
        logger.error(f"Error loading screening types: {str(e)}")
        flash('Error loading screening types', 'error')
        return render_template('error/500.html'), 500

@screening_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@non_admin_required
def screening_settings():
    """Screening settings management"""
    try:
        from forms import PrepSheetSettingsForm
        from models import PrepSheetSettings
        
        settings = PrepSheetSettings.query.first()
        if not settings:
            settings = PrepSheetSettings()
            db.session.add(settings)
            db.session.commit()
        
        form = PrepSheetSettingsForm(obj=settings)
        
        if form.validate_on_submit():
            form.populate_obj(settings)
            db.session.commit()
            
            # Log the action
            log_admin_event(
                event_type='update_screening_settings',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={'description': 'Updated screening settings'}
            )
            
            flash('Screening settings updated successfully', 'success')
            return redirect(url_for('screening.screening_settings'))
        
        return render_template('screening/settings.html', form=form, settings=settings)
        
    except Exception as e:
        logger.error(f"Error in screening settings: {str(e)}")
        flash('Error loading screening settings', 'error')
        return render_template('error/500.html'), 500

@screening_bp.route('/type/add', methods=['GET', 'POST'])
@login_required
@non_admin_required
def add_screening_type():
    """Add new screening type"""
    try:
        form = ScreeningTypeForm()

        if form.validate_on_submit():
            # Handle trigger conditions - could be JSON from inline management or comma-separated from textarea
            trigger_conditions_list = []
            if form.trigger_conditions.data:
                try:
                    # Try to parse as JSON first (from inline condition management)
                    trigger_conditions_list = json.loads(form.trigger_conditions.data)
                    if not isinstance(trigger_conditions_list, list):
                        trigger_conditions_list = []
                except (json.JSONDecodeError, ValueError):
                    # Fallback to comma-separated parsing (manual textarea input)
                    trigger_conditions_list = [tc.strip() for tc in form.trigger_conditions.data.split(',') if tc.strip()]
            
            # Convert frequency to years for storage
            frequency_years = form.frequency_value.data or 1.0
            if form.frequency_unit.data == 'months' and form.frequency_value.data:
                frequency_years = form.frequency_value.data / 12.0
            
            screening_type = ScreeningType()
            screening_type.name = form.name.data
            screening_type.org_id = current_user.org_id
            screening_type.keywords = json.dumps([])  # Start with empty keywords - will be set via modal
            screening_type.eligible_genders = form.eligible_genders.data
            screening_type.min_age = form.min_age.data
            screening_type.max_age = form.max_age.data
            screening_type.frequency_years = frequency_years
            screening_type.trigger_conditions = json.dumps(trigger_conditions_list) if trigger_conditions_list else None

            db.session.add(screening_type)
            db.session.commit()

            # Capture created values for logging
            created_values = {
                'name': screening_type.name,
                'eligible_genders': screening_type.eligible_genders,
                'min_age': screening_type.min_age,
                'max_age': screening_type.max_age,
                'frequency_years': screening_type.frequency_years,
                'trigger_conditions': trigger_conditions_list,
                'org_id': screening_type.org_id
            }

            # Log the action with created values
            log_admin_event(
                event_type='add_screening_type',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={
                    'screening_type_name': screening_type.name,
                    'after': created_values,
                    'description': f'Added screening type: {screening_type.name}'
                }
            )

            flash(f'Screening type "{screening_type.name}" added successfully', 'success')
            return redirect(url_for('screening.screening_types'))

        return render_template('screening/add_screening_type.html', form=form)

    except Exception as e:
        logger.error(f"Error adding screening type: {str(e)}")
        flash('Error adding screening type', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
@non_admin_required
def edit_screening_type(type_id):
    """Edit existing screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(type_id)
        form = ScreeningTypeForm(obj=screening_type)

        if form.validate_on_submit():
            # Capture before values for logging
            before_values = {
                'name': screening_type.name,
                'eligible_genders': screening_type.eligible_genders,
                'min_age': screening_type.min_age,
                'max_age': screening_type.max_age,
                'frequency_years': screening_type.frequency_years,
                'trigger_conditions': json.loads(screening_type.trigger_conditions) if screening_type.trigger_conditions else []
            }
            
            # Handle trigger conditions - could be JSON from inline management or comma-separated from textarea
            trigger_conditions_list = []
            if form.trigger_conditions.data:
                try:
                    # Try to parse as JSON first (from inline condition management)
                    trigger_conditions_list = json.loads(form.trigger_conditions.data)
                    if not isinstance(trigger_conditions_list, list):
                        trigger_conditions_list = []
                except (json.JSONDecodeError, ValueError):
                    # Fallback to comma-separated parsing (manual textarea input)
                    trigger_conditions_list = [tc.strip() for tc in form.trigger_conditions.data.split(',') if tc.strip()]
            
            # Convert frequency to years for storage
            frequency_years = form.frequency_value.data or 1.0
            if form.frequency_unit.data == 'months' and form.frequency_value.data:
                frequency_years = form.frequency_value.data / 12.0
            
            screening_type.name = form.name.data
            # Keywords are managed via modal - don't update from form
            screening_type.eligible_genders = form.eligible_genders.data
            screening_type.min_age = form.min_age.data
            screening_type.max_age = form.max_age.data
            screening_type.frequency_years = frequency_years
            screening_type.trigger_conditions = json.dumps(trigger_conditions_list) if trigger_conditions_list else None

            # Capture after values for logging
            after_values = {
                'name': screening_type.name,
                'eligible_genders': screening_type.eligible_genders,
                'min_age': screening_type.min_age,
                'max_age': screening_type.max_age,
                'frequency_years': screening_type.frequency_years,
                'trigger_conditions': trigger_conditions_list
            }

            db.session.commit()

            # Log the action with before/after values
            log_admin_event(
                event_type='edit_screening_type',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={
                    'screening_type_name': screening_type.name,
                    'before': before_values,
                    'after': after_values,
                    'description': f'Edited screening type: {screening_type.name}'
                }
            )

            flash(f'Screening type "{screening_type.name}" updated successfully', 'success')
            return redirect(url_for('screening.screening_types'))

        # Populate form fields for editing
        if not request.method == 'POST':  # Only populate on GET request
            form.eligible_genders.data = screening_type.eligible_genders
            
            # Convert frequency_years back to appropriate display units
            frequency_years = screening_type.frequency_years
            frequency_months = frequency_years * 12
            
            # If it's a clean number of months and less than 24 months, show in months
            if frequency_months < 24 and frequency_months == int(frequency_months):
                form.frequency_value.data = int(frequency_months)
                form.frequency_unit.data = 'months'
            # If it's 0.5 years (6 months), show as 6 months
            elif frequency_years == 0.5:
                form.frequency_value.data = 6
                form.frequency_unit.data = 'months'
            # Otherwise show in years
            else:
                form.frequency_value.data = frequency_years
                form.frequency_unit.data = 'years'
            
            # Set trigger conditions as JSON for inline management system
            if screening_type.trigger_conditions_list:
                form.trigger_conditions.data = json.dumps(screening_type.trigger_conditions_list)
            else:
                form.trigger_conditions.data = ""

        return render_template('screening/edit_screening_type.html',
                             form=form, screening_type=screening_type)

    except Exception as e:
        logger.error(f"Error editing screening type: {str(e)}")
        flash('Error editing screening type', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:type_id>/toggle-status', methods=['POST'])
@login_required
@non_admin_required
def toggle_screening_type_status(type_id):
    """Toggle screening type active status and sync to all variants"""
    try:
        screening_type = ScreeningType.query.get_or_404(type_id)

        screening_type.is_active = not screening_type.is_active
        
        # Sync status to all variants of the same base name
        screening_type.sync_status_to_variants()

        # Log the action
        log_admin_event(
            event_type='toggle_screening_type_status',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={'screening_type_name': screening_type.name, 'new_status': screening_type.is_active, 'synced_to_variants': True, 'description': f'Toggled screening type status: {screening_type.name} -> {screening_type.is_active} (synced to variants)'}
        )

        status = 'activated' if screening_type.is_active else 'deactivated'
        flash(f'Screening type "{screening_type.name}" {status} (all variants synced)', 'success')

        return redirect(url_for('screening.screening_types'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling screening type status: {str(e)}")
        flash('Error updating screening type status', 'error')
        return redirect(url_for('screening.screening_types'))

@screening_bp.route('/type/<int:type_id>/delete', methods=['POST'])
@login_required
@non_admin_required
def delete_screening_type(type_id):
    """Delete screening type"""
    try:
        # CRITICAL: Ensure multi-tenancy - only get screening types from user's organization
        screening_type = ScreeningType.query.filter_by(
            id=type_id, 
            org_id=current_user.org_id
        ).first_or_404()

        # Check if screening type is in use within this organization only
        active_screenings = Screening.query.join(Patient).filter(
            Screening.screening_type_id == type_id,
            Patient.org_id == current_user.org_id
        ).count()
        if active_screenings > 0:
            flash(f'Cannot delete screening type "{screening_type.name}" - it has {active_screenings} active screenings', 'error')
            return redirect(url_for('screening.screening_types'))

        screening_name = screening_type.name
        db.session.delete(screening_type)
        db.session.commit()

        # Log the action
        log_admin_event(
            event_type='delete_screening_type',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={'screening_type_name': screening_name, 'description': f'Deleted screening type: {screening_name}'}
        )

        flash(f'Screening type "{screening_name}" deleted successfully', 'success')
        return redirect(url_for('screening.screening_types'))

    except Exception as e:
        logger.error(f"Error deleting screening type: {str(e)}")
        flash('Error deleting screening type', 'error')
        return redirect(url_for('screening.screening_types'))



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
            log_admin_event(
                event_type='refresh_patient_screenings',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={'patient_id': patient_id, 'processed_screenings': result.get('processed_screenings', 0) if isinstance(result, dict) else 0, 'description': f'Refreshed screenings for patient {patient_id}'}
            )

        else:
            # Refresh all screenings
            result = engine.refresh_all_screenings()
            flash(f'Refreshed all screenings. Processed {result.get("total_screenings", 0) if isinstance(result, dict) else 0} screenings for {result.get("processed_patients", 0) if isinstance(result, dict) else 0} patients', 'success')

            # Log the action
            log_admin_event(
                event_type='refresh_all_screenings',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={'total_screenings': result.get('total_screenings', 0) if isinstance(result, dict) else 0, 'processed_patients': result.get('processed_patients', 0) if isinstance(result, dict) else 0, 'description': f'Refreshed all screenings'}
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

@screening_bp.route('/screening-settings', methods=['POST'])
@login_required
def update_screening_settings():
    """Update screening settings"""
    try:
        from forms import ScreeningSettingsForm
        from models import ScreeningSettings
        
        settings = ScreeningSettings.query.first()
        if not settings:
            settings = ScreeningSettings()
            db.session.add(settings)
        
        form = ScreeningSettingsForm()
        
        if form.validate_on_submit():
            form.populate_obj(settings)
            settings.updated_by = current_user.id
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Screening settings updated successfully', 'success')
        else:
            flash('Error updating screening settings', 'error')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update screening settings error: {str(e)}")
        flash('Error updating screening settings', 'error')
    
    return redirect(url_for('screening.screening_list', view='settings'))

@screening_bp.route('/api/keyword-analysis')
@login_required
def analyze_keyword_distribution():
    """Analyze keyword count distribution across screening types"""
    try:
        screening_types = ScreeningType.query.filter_by(
            org_id=current_user.org_id,
            is_active=True
        ).all()
        
        analysis = {
            'total_screening_types': len(screening_types),
            'keyword_distribution': {},
            'screening_details': [],
            'summary': {
                'avg_keywords': 0,
                'min_keywords': float('inf'),
                'max_keywords': 0,
                'total_keywords': 0
            }
        }
        
        keyword_counts = []
        
        for st in screening_types:
            keyword_count = len(st.keywords_list)
            keyword_counts.append(keyword_count)
            
            # Update distribution
            count_range = f"{(keyword_count // 5) * 5}-{(keyword_count // 5) * 5 + 4}"
            if keyword_count == 0:
                count_range = "0"
            elif keyword_count >= 20:
                count_range = "20+"
            
            analysis['keyword_distribution'][count_range] = analysis['keyword_distribution'].get(count_range, 0) + 1
            
            analysis['screening_details'].append({
                'name': st.name,
                'keyword_count': keyword_count,
                'keywords': st.keywords_list[:5],  # First 5 keywords for preview
                'created_by': st.created_by_user.username if st.created_by_user else 'System'
            })
        
        # Calculate summary stats
        if keyword_counts:
            analysis['summary'] = {
                'avg_keywords': round(sum(keyword_counts) / len(keyword_counts), 1),
                'min_keywords': min(keyword_counts),
                'max_keywords': max(keyword_counts),
                'total_keywords': sum(keyword_counts)
            }
        
        # Sort screening details by keyword count (descending)
        analysis['screening_details'].sort(key=lambda x: x['keyword_count'], reverse=True)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error analyzing keyword distribution: {str(e)}")
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

@screening_bp.route('/api/screening-keywords/<int:screening_type_id>', methods=['GET', 'POST'])
@login_required
def manage_screening_keywords(screening_type_id):
    """Get or update keywords for a screening type (tag-based system)"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    if request.method == 'GET':
        # Get keywords
        try:
            keywords = screening_type.get_content_keywords()
            return jsonify({
                'success': True,
                'keywords': keywords,
                'screening_type': screening_type.name
            })
        except Exception as e:
            logger.error(f"Error getting screening keywords: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e),
                'keywords': []
            }), 500
    
    elif request.method == 'POST':
        # Save keywords
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            keywords = data.get('keywords', [])
            
            # Validate keywords
            if not isinstance(keywords, list):
                return jsonify({
                    'success': False,
                    'error': 'Keywords must be an array'
                }), 400
            
            # Clean and validate keywords
            clean_keywords = []
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    clean_keywords.append(keyword.strip())
            
            # Save keywords
            screening_type.set_content_keywords(clean_keywords)
            db.session.commit()
            
            # Log the action
            log_admin_event(
                event_type='update_screening_type_keywords',
                user_id=current_user.id,
                org_id=current_user.org_id,
                ip=request.remote_addr,
                data={'screening_type_name': screening_type.name, 'keywords_count': len(clean_keywords), 'description': f'Updated keywords for screening type: {screening_type.name}'}
            )
            
            return jsonify({
                'success': True,
                'message': f'Updated {len(clean_keywords)} keywords for {screening_type.name}',
                'keywords': clean_keywords
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving screening keywords: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@screening_bp.route('/api/keyword-suggestions')
@login_required
def get_keyword_suggestions():
    """Get keyword suggestions for autocomplete"""
    try:
        partial = request.args.get('q', '').strip()
        if not partial:
            return jsonify({'success': True, 'suggestions': []})

        # Import medical terminology for suggestions
        from utils.medical_terminology import medical_terminology_db
        suggestions = medical_terminology_db.search_keywords(partial, limit=10)

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        logger.error(f"Error getting keyword suggestions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []
        }), 500

@screening_bp.route('/api/import-keywords/<int:screening_type_id>')
@login_required
def import_medical_keywords(screening_type_id):
    """Import standard medical keywords for a screening type with options"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        
        # Get import options from query parameters
        max_keywords = request.args.get('max_keywords', 8, type=int)
        include_variations = request.args.get('include_variations', 'false').lower() == 'true'
        priority_only = request.args.get('priority_only', 'true').lower() == 'true'
        
        from utils.medical_terminology import medical_terminology_db
        
        # Get current keywords
        current_keywords = set(screening_type.get_content_keywords())
        
        # Get medical keywords with limits
        medical_keywords = set(medical_terminology_db.import_standard_keywords(
            screening_type.name,
            max_keywords=max_keywords,
            include_variations=include_variations,
            priority_only=priority_only
        ))
        
        # Find new keywords
        new_keywords = medical_keywords - current_keywords
        
        # Combine and save
        all_keywords = list(current_keywords | medical_keywords)
        screening_type.set_content_keywords(all_keywords)
        db.session.commit()
        
        # Log the action
        log_admin_event(
            event_type='import_medical_keywords',
            user_id=current_user.id,
            org_id=current_user.org_id,
            ip=request.remote_addr,
            data={
                'screening_type_name': screening_type.name, 
                'imported_count': len(new_keywords),
                'max_keywords': max_keywords,
                'priority_only': priority_only,
                'description': f'Imported {len(new_keywords)} targeted medical keywords for screening type: {screening_type.name}'
            }
        )
        
        return jsonify({
            'success': True,
            'keywords': all_keywords,
            'new_keywords': list(new_keywords),
            'message': f'Imported {len(new_keywords)} targeted medical keywords (max: {max_keywords})',
            'options_used': {
                'max_keywords': max_keywords,
                'priority_only': priority_only,
                'include_variations': include_variations
            }
        })
        
    except Exception as e:
        logger.error(f"Error importing medical keywords: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500