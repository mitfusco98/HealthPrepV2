"""
Demo/main application routes
Handles core screening functionality and prep sheet viewing
"""
import logging
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import Patient, Document, Screening, ScreeningType
from prep_sheet.generator import PrepSheetGenerator
from core.engine import ScreeningEngine
from admin.analytics import HealthPrepAnalytics
from app import db

logger = logging.getLogger(__name__)

demo_bp = Blueprint('demo', __name__)

@demo_bp.route('/')
@login_required
def index():
    """Main dashboard - screening overview"""
    try:
        # Get screening statistics
        total_patients = Patient.query.count()
        total_screenings = Screening.query.count()
        due_screenings = Screening.query.filter_by(status='Due').count()
        due_soon_screenings = Screening.query.filter_by(status='Due Soon').count()
        complete_screenings = Screening.query.filter_by(status='Complete').count()

        # Get recent screening activity
        recent_screenings = Screening.query.order_by(
            Screening.updated_at.desc()
        ).limit(10).all()

        # Create stats structure for template
        stats = {
            'total_patients': total_patients,
            'due_screenings': due_screenings,
            'due_soon_screenings': due_soon_screenings,
            'complete_screenings': complete_screenings
        }

        return render_template('dashboard.html',
                             stats=stats,
                             recent_screenings=recent_screenings)

    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('Error loading dashboard', 'error')
        empty_stats = {
            'total_patients': 0,
            'due_screenings': 0,
            'due_soon_screenings': 0,
            'complete_screenings': 0
        }
        return render_template('dashboard.html',
                             stats=empty_stats,
                             recent_screenings=[])

@demo_bp.route('/screening-list')
@login_required
def screening_list():
    """Main screening list view"""
    try:
        page = request.args.get('page', 1, type=int)
        patient_filter = request.args.get('patient', '')
        status_filter = request.args.get('status', '')
        screening_type_filter = request.args.get('screening_type', '')

        query = Screening.query.join(Patient)

        if patient_filter:
            query = query.filter(Patient.name.contains(patient_filter))

        if status_filter:
            query = query.filter(Screening.status == status_filter)

        if screening_type_filter:
            query = query.join(ScreeningType).filter(ScreeningType.name.contains(screening_type_filter))

        screenings = query.order_by(Screening.updated_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )

        # Get filter options
        all_patients = Patient.query.all()
        screening_types = ScreeningType.query.filter_by(status='active').all()

        return render_template('screening/screening_list.html',
                             screenings=screenings,
                             all_patients=all_patients,
                             screening_types=screening_types,
                             filters={
                                 'patient': patient_filter,
                                 'status': status_filter,
                                 'screening_type': screening_type_filter
                             })

    except Exception as e:
        logger.error(f"Error loading screening list: {str(e)}")
        flash('Error loading screening list', 'error')
        return render_template('screening/screening_list.html',
                             screenings=None,
                             all_patients=[],
                             screening_types=[],
                             filters={})

@demo_bp.route('/patient/<int:patient_id>/prep-sheet')
@login_required
def view_prep_sheet(patient_id):
    """View patient prep sheet"""
    try:
        patient = Patient.query.get_or_404(patient_id)

        # Generate prep sheet
        generator = PrepSheetGenerator()
        prep_sheet = generator.generate_prep_sheet(patient_id)

        return render_template('prep_sheet/prep_sheet.html',
                             patient=patient,
                             prep_sheet=prep_sheet)

    except Exception as e:
        logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('demo.screening_list'))

@demo_bp.route('/refresh-screenings', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh all screenings using the screening engine"""
    try:
        engine = ScreeningEngine()
        result = engine.process_all_screenings(force_refresh=True)

        flash(f'Successfully refreshed {len(result["processed_screenings"])} screenings.', 'success')

        if result['errors']:
            flash(f'Encountered {len(result["errors"])} errors during refresh.', 'warning')

    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        flash('Error refreshing screenings', 'error')

    return redirect(url_for('demo.screening_list'))

@demo_bp.route('/patients')
@login_required
def patients():
    """Patient list view"""
    try:
        page = request.args.get('page', 1, type=int)
        search_term = request.args.get('search', '')
        
        query = Patient.query
        
        if search_term:
            query = query.filter(
                db.or_(
                    Patient.name.contains(search_term),
                    Patient.mrn.contains(search_term)
                )
            )
        
        patients = query.order_by(Patient.created_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        return render_template('patients/patient_list.html',
                             patients=patients.items,
                             search_term=search_term)
                             
    except Exception as e:
        logger.error(f"Error loading patients: {str(e)}")
        flash('Error loading patient list', 'error')
        return render_template('patients/patient_list.html',
                             patients=[],
                             search_term='')

@demo_bp.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard for screening performance"""
    try:
        analytics = HealthPrepAnalytics()

        # Get comprehensive analytics
        data = {
            'overview': analytics.get_system_performance_metrics(),
            'time_saved': analytics.calculate_time_saved(),
            'compliance_gaps': analytics.analyze_compliance_gaps_closed(),
            'roi_report': analytics.generate_roi_report()
        }

        return render_template('analytics.html', analytics_data=data)

    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}")
        flash('Error loading analytics data', 'error')
        return render_template('analytics.html', analytics_data={})

@demo_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors in demo blueprint"""
    return render_template('error/404.html'), 404

@demo_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors in demo blueprint"""
    db.session.rollback()
    return render_template('error/500.html'), 500