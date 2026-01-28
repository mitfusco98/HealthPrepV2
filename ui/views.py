"""Fixes the screening_types method to include the form variable for rendering the template."""
"""
User interface views for the main application.
Handles user-facing screens including screening lists, prep sheets, and patient management.
"""

import logging
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import Patient, Screening, ScreeningType, Document, PatientCondition, Appointment
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator
from services.provider_scope import (
    get_provider_patients, get_provider_screenings, get_active_provider,
    get_provider_appointments, get_user_providers, validate_patient_access
)
from app import db

logger = logging.getLogger(__name__)

class UserViews:
    """Handles user-facing views and interactions"""

    def __init__(self, app=None):
        self.screening_engine = ScreeningEngine()
        self.prep_generator = PrepSheetGenerator()
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize views with Flask app"""
        self.app = app

    def dashboard(self):
        """Main user dashboard - provider scoped with 2-week appointment prioritization"""
        try:
            # Get active provider context
            active_provider = get_active_provider(current_user)
            user_providers = get_user_providers(current_user)
            
            # Get provider-scoped patient count
            patient_query = get_provider_patients(current_user, all_providers=False)
            total_patients = patient_query.count()
            
            # Calculate screening statistics from provider-scoped data
            screening_base = get_provider_screenings(current_user, all_providers=False)
            screening_base = screening_base.join(ScreeningType).filter(ScreeningType.is_active == True)
            
            due_screenings = screening_base.filter(Screening.status == 'due').count()
            due_soon_screenings = screening_base.filter(Screening.status == 'due_soon').count()
            complete_screenings = screening_base.filter(Screening.status == 'complete').count()
            
            # Count recent documents (from last 30 days) - provider scoped
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            patient_ids = [p.id for p in patient_query.limit(1000).all()]
            recent_documents = Document.query.filter(
                Document.patient_id.in_(patient_ids),
                Document.created_at >= thirty_days_ago
            ).count() if patient_ids and hasattr(Document, 'created_at') else 0

            stats = {
                'total_patients': total_patients,
                'due_screenings': due_screenings,
                'due_soon_screenings': due_soon_screenings,
                'recent_documents': recent_documents,
                'complete_screenings': complete_screenings,
                'completed_screenings': complete_screenings
            }

            # Get 2-week upcoming appointments for prioritization
            two_weeks_ahead = datetime.utcnow() + timedelta(days=14)
            appointment_query = get_provider_appointments(current_user, all_providers=False)
            upcoming_appointments = appointment_query.filter(
                Appointment.appointment_date >= datetime.utcnow(),
                Appointment.appointment_date <= two_weeks_ahead
            ).order_by(Appointment.appointment_date.asc()).limit(20).all()
            
            # Get patient IDs from upcoming appointments for prioritized display
            appointment_patient_ids = set(appt.patient_id for appt in upcoming_appointments if appt.patient_id)
            
            # Get screenings for patients with upcoming appointments (priority)
            priority_screenings = []
            if appointment_patient_ids:
                priority_screening_query = get_provider_screenings(current_user, all_providers=False)
                priority_screening_query = priority_screening_query.join(ScreeningType).filter(
                    ScreeningType.is_active == True,
                    Screening.patient_id.in_(appointment_patient_ids)
                )
                priority_screenings = priority_screening_query.order_by(Screening.updated_at.desc()).limit(20).all()
            
            # Get other recent screenings (non-priority)
            all_recent_query = get_provider_screenings(current_user, all_providers=False)
            all_recent_query = all_recent_query.join(ScreeningType).filter(ScreeningType.is_active == True)
            all_recent_screenings = all_recent_query.order_by(Screening.updated_at.desc()).limit(50).all()
            
            # Combine and deduplicate: priority patients first, then by status
            status_priority = {
                'complete': 0,
                'due_soon': 1,
                'due': 2,
                'overdue': 3
            }
            
            seen_ids = set()
            recent_screenings = []
            
            # Add priority screenings first (patients with appointments in 2 weeks)
            for s in sorted(priority_screenings, key=lambda x: (status_priority.get(x.status, 99), -(x.updated_at.timestamp() if x.updated_at else 0))):
                if s.id not in seen_ids:
                    s.is_priority = True  # Mark as priority for template display
                    recent_screenings.append(s)
                    seen_ids.add(s.id)
            
            # Then add remaining screenings
            for s in sorted(all_recent_screenings, key=lambda x: (status_priority.get(x.status, 99), -(x.updated_at.timestamp() if x.updated_at else 0))):
                if s.id not in seen_ids and len(recent_screenings) < 10:
                    s.is_priority = False
                    recent_screenings.append(s)
                    seen_ids.add(s.id)

            return render_template('dashboard.html',
                                 stats=stats,
                                 user_stats=stats,
                                 recent_activity=[],
                                 recent_screenings=recent_screenings,
                                 upcoming_appointments=upcoming_appointments,
                                 active_provider=active_provider,
                                 user_providers=user_providers,
                                 has_multiple_providers=len(user_providers) > 1)

        except Exception as e:
            logger.error(f"Error in dashboard view: {str(e)}")
            default_stats = {
                'total_patients': 0,
                'due_screenings': 0,
                'due_soon_screenings': 0,
                'recent_documents': 0,
                'complete_screenings': 0,
                'completed_screenings': 0
            }
            return render_template('dashboard.html',
                                 stats=default_stats,
                                 user_stats=default_stats,
                                 recent_activity=[],
                                 recent_screenings=[],
                                 upcoming_appointments=[],
                                 active_provider=None,
                                 user_providers=[],
                                 has_multiple_providers=False)

    def screening_list(self):
        """Screening list view with filtering - provider scoped"""
        try:
            screen_type = request.args.get('type', 'list')
            patient_filter = request.args.get('patient', '')
            status_filter = request.args.get('status', '')
            screening_type_filter = request.args.get('screening_type', '')
            
            # Get active provider context
            active_provider = get_active_provider(current_user)
            user_providers = get_user_providers(current_user)

            # Build provider-scoped query
            query = get_provider_screenings(current_user, all_providers=False)
            query = query.join(Patient).join(ScreeningType).filter(ScreeningType.is_active == True)

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
                query = query.filter(ScreeningType.name.ilike(f'%{screening_type_filter}%'))

            all_screenings = query.all()
            
            status_priority = {
                'complete': 0,
                'due_soon': 1,
                'due': 2,
                'overdue': 3
            }
            
            screenings = sorted(all_screenings, 
                              key=lambda s: (
                                  status_priority.get(s.status, 99),
                                  -(s.updated_at.timestamp() if s.updated_at else 0)
                              ))

            screening_types = ScreeningType.query.filter_by(
                org_id=current_user.org_id, 
                is_active=True
            ).all()
            
            screening_type_groups = []
            for st in screening_types:
                screening_type_groups.append({
                    'name': st.name,
                    'display_name': st.display_name
                })
            
            status_options = ['due', 'due_soon', 'complete', 'overdue']

            return render_template('screening/list.html',
                                 screenings=screenings,
                                 screening_types=screening_types,
                                 screening_type_groups=screening_type_groups,
                                 status_options=status_options,
                                 current_filters={
                                     'patient': patient_filter,
                                     'status': status_filter,
                                     'screening_type': screening_type_filter
                                 },
                                 screen_type=screen_type,
                                 active_provider=active_provider,
                                 user_providers=user_providers,
                                 has_multiple_providers=len(user_providers) > 1)

        except Exception as e:
            logger.error(f"Error in screening list view: {str(e)}")
            flash('Error loading screening list', 'error')
            return render_template('screening/list.html',
                                 screenings=[],
                                 screening_types=[],
                                 status_options=[],
                                 current_filters={},
                                 screen_type='list',
                                 active_provider=None,
                                 user_providers=[],
                                 has_multiple_providers=False)

    def screening_types(self):
        """Screening types management view"""
        try:
            from forms import ScreeningTypeForm

            # Get all screening types
            screening_types = ScreeningType.query.order_by(ScreeningType.name).all()

            # Create empty form for the template
            form = ScreeningTypeForm()

            return render_template('screening/types.html',
                                 screening_types=screening_types,
                                 form=form)

        except Exception as e:
            logger.error(f"Error in screening types view: {str(e)}")
            flash('Error loading screening types', 'error')
            return render_template('error/500.html'), 500

    def add_screening_type(self):
        """Add new screening type view"""
        if request.method == 'POST':
            try:
                # Extract form data
                name = request.form.get('name', '').strip()
                description = request.form.get('description', '').strip()
                keywords = [k.strip() for k in request.form.get('keywords', '').split(',') if k.strip()]
                frequency_value = int(request.form.get('frequency_value', 1))
                frequency_unit = request.form.get('frequency_unit', 'years')

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

                # Trigger conditions
                trigger_conditions = [c.strip() for c in request.form.get('trigger_conditions', '').split(',') if c.strip()]

                # Validation
                if not name:
                    flash('Screening type name is required', 'error')
                    return render_template('screening/add_type.html')

                # Check for duplicate name
                existing = ScreeningType.query.filter_by(name=name).first()
                if existing:
                    flash('A screening type with this name already exists', 'error')
                    return render_template('screening/add_type.html')

                # Create screening type
                screening_type = ScreeningType(
                    name=name,
                    description=description,
                    keywords=keywords,
                    eligibility_criteria=eligibility_criteria,
                    frequency_value=frequency_value,
                    frequency_unit=frequency_unit,
                    trigger_conditions=trigger_conditions,
                    is_active=True
                )

                db.session.add(screening_type)
                db.session.commit()

                flash(f'Screening type "{name}" created successfully', 'success')

                # Trigger selective refresh
                self.screening_engine.selective_refresh(screening_type_ids=[screening_type.id])

                return redirect(url_for('ui.screening_types'))

            except ValueError as e:
                logger.error(f"Validation error in add screening type: {str(e)}")
                flash('Invalid input values. Please check your entries.', 'error')
                return render_template('screening/add_type.html')
            except Exception as e:
                logger.error(f"Error adding screening type: {str(e)}")
                db.session.rollback()
                flash('Error creating screening type', 'error')
                return render_template('screening/add_type.html')

        # GET request - show form
        return render_template('screening/add_type.html')

    def edit_screening_type(self, screening_type_id):
        """Edit existing screening type"""
        try:
            screening_type = ScreeningType.query.get_or_404(screening_type_id)

            if request.method == 'POST':
                # Update screening type
                screening_type.name = request.form.get('name', '').strip()
                screening_type.description = request.form.get('description', '').strip()
                screening_type.keywords = [k.strip() for k in request.form.get('keywords', '').split(',') if k.strip()]
                screening_type.frequency_value = int(request.form.get('frequency_value', 1))
                screening_type.frequency_unit = request.form.get('frequency_unit', 'years')

                # Update eligibility criteria
                eligibility_criteria = {}
                min_age = request.form.get('min_age')
                max_age = request.form.get('max_age')
                gender = request.form.get('gender')

                if min_age:
                    eligibility_criteria['min_age'] = int(min_age)
                if max_age:
                    eligibility_criteria['max_age'] = int(max_age)
                if gender and gender != 'any':
                    eligibility_criteria['gender'] = gender

                screening_type.eligibility_criteria = eligibility_criteria

                # Update trigger conditions
                trigger_conditions = [c.strip() for c in request.form.get('trigger_conditions', '').split(',') if c.strip()]
                screening_type.trigger_conditions = trigger_conditions

                screening_type.updated_at = datetime.utcnow()

                db.session.commit()

                flash(f'Screening type "{screening_type.name}" updated successfully', 'success')

                # Trigger selective refresh
                self.screening_engine.selective_refresh(screening_type_ids=[screening_type_id])

                return redirect(url_for('ui.screening_types'))

            # GET request - show edit form
            return render_template('screening/edit_type.html', screening_type=screening_type)

        except Exception as e:
            logger.error(f"Error editing screening type {screening_type_id}: {str(e)}")
            flash('Error updating screening type', 'error')
            return redirect(url_for('ui.screening_types'))

    def delete_screening_type(self, screening_type_id):
        """Delete screening type"""
        try:
            screening_type = ScreeningType.query.get_or_404(screening_type_id)

            # Check if screening type is in use
            active_screenings = PatientScreening.query.filter_by(screening_type_id=screening_type_id).count()

            if active_screenings > 0:
                flash(f'Cannot delete "{screening_type.name}" - it is currently used by {active_screenings} screening(s)', 'error')
                return redirect(url_for('ui.screening_types'))

            name = screening_type.name
            db.session.delete(screening_type)
            db.session.commit()

            flash(f'Screening type "{name}" deleted successfully', 'success')

            return redirect(url_for('ui.screening_types'))

        except Exception as e:
            logger.error(f"Error deleting screening type {screening_type_id}: {str(e)}")
            flash('Error deleting screening type', 'error')
            return redirect(url_for('ui.screening_types'))

    def patient_detail(self, patient_id):
        """Patient detail view with prep sheet"""
        try:
            patient = Patient.query.get_or_404(patient_id)

            # Generate prep sheet
            prep_sheet = self.prep_generator.generate_prep_sheet(patient_id)

            return render_template('patient_detail.html',
                                 patient=patient,
                                 prep_sheet=prep_sheet)

        except Exception as e:
            logger.error(f"Error in patient detail view for {patient_id}: {str(e)}")
            flash('Error loading patient details', 'error')
            abort(404)

    def prep_sheet(self, patient_id):
        """Standalone prep sheet view"""
        try:
            patient = Patient.query.get_or_404(patient_id)
            prep_sheet = self.prep_generator.generate_prep_sheet(patient_id)

            return render_template('prep_sheet/template.html',
                                 patient=patient,
                                 prep_sheet=prep_sheet)

        except Exception as e:
            logger.error("Error generating prep sheet: %s", str(e))
            flash('Error generating preparation sheet', 'error')
            abort(404)

    def refresh_screenings(self):
        """Refresh screening engine for all patients"""
        try:
            if request.method == 'POST':
                # Get all patients and refresh their screenings
                patients = Patient.query.all()

                for patient in patients:
                    self.screening_engine.process_patient_screenings(patient.id, force_refresh=True)

                flash(f'Successfully refreshed screenings for {len(patients)} patients', 'success')

                return redirect(url_for('ui.screening_list'))

            # GET request - show confirmation
            patient_count = Patient.query.count()
            return render_template('confirm_refresh.html',
                                 patient_count=patient_count)

        except Exception as e:
            logger.error(f"Error refreshing screenings: {str(e)}")
            flash('Error refreshing screenings', 'error')
            return redirect(url_for('ui.screening_list'))

    def api_screening_keywords(self, screening_type_id):
        """API endpoint for screening keywords"""
        try:
            screening_type = ScreeningType.query.get_or_404(screening_type_id)

            return jsonify({
                'success': True,
                'keywords': screening_type.keywords or []
            })

        except Exception as e:
            logger.error(f"Error getting keywords for screening type {screening_type_id}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    def document_view(self, document_id):
        """View document content"""
        try:
            document = Document.query.get_or_404(document_id)

            # Check if user has access to this patient's documents
            # In a real implementation, you'd add proper authorization checks

            content = document.filtered_text or document.ocr_text or 'No text content available'

            return render_template('document_view.html',
                                 document=document,
                                 content=content)

        except Exception as e:
            logger.error(f"Error viewing document {document_id}: {str(e)}")
            flash('Error loading document', 'error')
            abort(404)

    def patient_list(self):
        """Patient list view"""
        try:
            search = request.args.get('search', '')

            query = Patient.query

            if search:
                query = query.filter(
                    db.or_(
                        Patient.name.ilike(f'%{search}%'),
                        Patient.mrn.ilike(f'%{search}%')
                    )
                )

            patients = query.order_by(Patient.name).all()

            return render_template('patients/patient_list.html',
                                 patients=patients,
                                 search=search)

        except Exception as e:
            logger.error(f"Error in patient list view: {str(e)}")
            flash('Error loading patient list', 'error')
            return render_template('patients/patient_list.html',
                                 patients=[],
                                 search='')