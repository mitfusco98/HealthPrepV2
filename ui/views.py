"""
User interface views for the main application.
Handles user-facing screens including screening lists, prep sheets, and patient management.
"""

import logging
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, date
from models import Patient, PatientScreening, ScreeningType, MedicalDocument, PatientCondition
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator
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
        """Main dashboard view"""
        try:
            # Get summary statistics
            total_patients = Patient.query.count()
            total_screenings = PatientScreening.query.count()
            due_screenings = PatientScreening.query.filter(PatientScreening.status.in_(['due', 'overdue'])).count()
            recent_documents = MedicalDocument.query.filter(
                MedicalDocument.created_at >= datetime.utcnow().replace(day=1)
            ).count()

            # Get recent activity
            recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(5).all()
            recent_screenings = PatientScreening.query.order_by(PatientScreening.updated_at.desc()).limit(10).all()

            return render_template('dashboard.html',
                                 total_patients=total_patients,
                                 total_screenings=total_screenings,
                                 due_screenings=due_screenings,
                                 recent_documents=recent_documents,
                                 recent_patients=recent_patients,
                                 recent_screenings=recent_screenings)

        except Exception as e:
            logger.error(f"Error in dashboard view: {str(e)}")
            flash('Error loading dashboard', 'error')
            return render_template('dashboard.html',
                                 total_patients=0,
                                 total_screenings=0,
                                 due_screenings=0,
                                 recent_documents=0,
                                 recent_patients=[],
                                 recent_screenings=[])

    def screening_list(self):
        """Screening list view with filtering"""
        try:
            screen_type = request.args.get('type', 'list')
            patient_filter = request.args.get('patient', '')
            status_filter = request.args.get('status', '')
            screening_type_filter = request.args.get('screening_type', '')

            # Build query based on filters
            query = PatientScreening.query.join(Patient).join(ScreeningType)

            if patient_filter:
                query = query.filter(
                    db.or_(
                        Patient.first_name.ilike(f'%{patient_filter}%'),
                        Patient.last_name.ilike(f'%{patient_filter}%'),
                        Patient.mrn.ilike(f'%{patient_filter}%')
                    )
                )

            if status_filter:
                query = query.filter(PatientScreening.status == status_filter)

            if screening_type_filter:
                query = query.filter(ScreeningType.name.ilike(f'%{screening_type_filter}%'))

            screenings = query.order_by(PatientScreening.updated_at.desc()).all()

            # Get additional data for the view
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            status_options = ['due', 'due_soon', 'complete', 'overdue']

            return render_template('screening/list.html',
                                 screenings=screenings,
                                 screening_types=screening_types,
                                 status_options=status_options,
                                 current_filters={
                                     'patient': patient_filter,
                                     'status': status_filter,
                                     'screening_type': screening_type_filter
                                 },
                                 screen_type=screen_type)

        except Exception as e:
            logger.error(f"Error in screening list view: {str(e)}")
            flash('Error loading screening list', 'error')
            return render_template('screening/list.html',
                                 screenings=[],
                                 screening_types=[],
                                 status_options=[],
                                 current_filters={},
                                 screen_type='list')

    def screening_types(self):
        """Screening types management view"""
        try:
            screening_types = ScreeningType.query.order_by(ScreeningType.name).all()

            return render_template('screening/types.html',
                                 screening_types=screening_types)

        except Exception as e:
            logger.error(f"Error in screening types view: {str(e)}")
            flash('Error loading screening types', 'error')
            return render_template('screening/types.html',
                                 screening_types=[])

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
            logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
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
            document = MedicalDocument.query.get_or_404(document_id)

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
                        Patient.first_name.ilike(f'%{search}%'),
                        Patient.last_name.ilike(f'%{search}%'),
                        Patient.mrn.ilike(f'%{search}%')
                    )
                )

            patients = query.order_by(Patient.last_name, Patient.first_name).all()

            return render_template('patient_list.html',
                                 patients=patients,
                                 search=search)

        except Exception as e:
            logger.error(f"Error in patient list view: {str(e)}")
            flash('Error loading patient list', 'error')
            return render_template('patient_list.html',
                                 patients=[],
                                 search='')