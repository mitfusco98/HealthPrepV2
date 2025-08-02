"""
Demo/main application routes
Handles patient management, prep sheet viewing, and general functionality
"""
import logging
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import Patient, MedicalDocument, Screening, ChecklistSettings
from prep_sheet.generator import PrepSheetGenerator
from core.engine import ScreeningEngine
from admin.analytics import Analytics
from app import db

logger = logging.getLogger(__name__)

demo_bp = Blueprint('demo', __name__)

@demo_bp.route('/')
@login_required
def index():
    """Main dashboard"""
    try:
        # Get recent statistics
        analytics = Analytics()
        stats = analytics.get_dashboard_statistics()
        
        # Get recent patients
        recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(10).all()
        
        # Get pending screenings
        pending_screenings = Screening.query.filter_by(status='Due').limit(5).all()
        
        return render_template('index.html',
                             stats=stats,
                             recent_patients=recent_patients,
                             pending_screenings=pending_screenings)
    
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('Error loading dashboard data.', 'error')
        return render_template('index.html', stats={}, recent_patients=[], pending_screenings=[])

@demo_bp.route('/patients')
@login_required
def patients():
    """Patient list page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        query = Patient.query
        
        if search:
            query = query.filter(
                db.or_(
                    Patient.name.contains(search),
                    Patient.mrn.contains(search)
                )
            )
        
        patients = query.paginate(
            page=page, per_page=20, error_out=False
        )
        
        return render_template('patients.html', patients=patients, search=search)
    
    except Exception as e:
        logger.error(f"Error loading patients: {str(e)}")
        flash('Error loading patient list.', 'error')
        return render_template('patients.html', patients=None, search='')

@demo_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail page"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Get patient documents
        documents = MedicalDocument.query.filter_by(patient_id=patient_id).order_by(
            MedicalDocument.created_at.desc()
        ).limit(20).all()
        
        # Get patient screenings
        screenings = Screening.query.filter_by(patient_id=patient_id).all()
        
        # Get patient conditions
        conditions = patient.conditions.filter_by(status='active').all()
        
        return render_template('patient_detail.html',
                             patient=patient,
                             documents=documents,
                             screenings=screenings,
                             conditions=conditions)
    
    except Exception as e:
        logger.error(f"Error loading patient {patient_id}: {str(e)}")
        flash('Error loading patient details.', 'error')
        return redirect(url_for('demo.patients'))

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
        flash('Error generating prep sheet.', 'error')
        return redirect(url_for('demo.patient_detail', patient_id=patient_id))

@demo_bp.route('/patient/<int:patient_id>/refresh-screenings', methods=['POST'])
@login_required
def refresh_patient_screenings(patient_id):
    """Refresh screenings for a specific patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # Refresh screenings using the engine
        engine = ScreeningEngine()
        result = engine.process_patient_screenings(patient_id, force_refresh=True)
        
        flash(f'Successfully refreshed {len(result["processed_screenings"])} screenings for {patient.name}.', 'success')
        
        if result['errors']:
            flash(f'Encountered {len(result["errors"])} errors during refresh.', 'warning')
        
    except Exception as e:
        logger.error(f"Error refreshing screenings for patient {patient_id}: {str(e)}")
        flash('Error refreshing patient screenings.', 'error')
    
    return redirect(url_for('demo.patient_detail', patient_id=patient_id))

@demo_bp.route('/documents')
@login_required
def documents():
    """Document management page"""
    try:
        page = request.args.get('page', 1, type=int)
        doc_type = request.args.get('type', '')
        patient_id = request.args.get('patient_id', type=int)
        
        query = MedicalDocument.query
        
        if doc_type:
            query = query.filter_by(document_type=doc_type)
        
        if patient_id:
            query = query.filter_by(patient_id=patient_id)
        
        documents = query.order_by(MedicalDocument.created_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Get filter options
        doc_types = db.session.query(MedicalDocument.document_type).distinct().all()
        doc_types = [dt[0] for dt in doc_types if dt[0]]
        
        return render_template('documents.html',
                             documents=documents,
                             doc_types=doc_types,
                             selected_type=doc_type,
                             selected_patient=patient_id)
    
    except Exception as e:
        logger.error(f"Error loading documents: {str(e)}")
        flash('Error loading document list.', 'error')
        return render_template('documents.html', documents=None, doc_types=[])

@demo_bp.route('/document/<int:document_id>')
@login_required
def view_document(document_id):
    """View document content"""
    try:
        document = MedicalDocument.query.get_or_404(document_id)
        
        return render_template('document_view.html', document=document)
    
    except Exception as e:
        logger.error(f"Error loading document {document_id}: {str(e)}")
        flash('Error loading document.', 'error')
        return redirect(url_for('demo.documents'))

@demo_bp.route('/upload-document', methods=['POST'])
@login_required
def upload_document():
    """Upload new document (placeholder for file upload)"""
    try:
        patient_id = request.form.get('patient_id', type=int)
        if not patient_id:
            flash('Patient ID is required.', 'error')
            return redirect(request.referrer or url_for('demo.patients'))
        
        patient = Patient.query.get_or_404(patient_id)
        
        # This would handle file upload in a real implementation
        # For now, just show a message
        flash('Document upload functionality would be implemented here.', 'info')
        
        return redirect(url_for('demo.patient_detail', patient_id=patient_id))
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        flash('Error uploading document.', 'error')
        return redirect(request.referrer or url_for('demo.patients'))

@demo_bp.route('/settings')
@login_required
def settings():
    """User settings page"""
    try:
        # Get current checklist settings
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
            db.session.commit()
        
        return render_template('settings.html', settings=settings)
    
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        flash('Error loading settings.', 'error')
        return render_template('settings.html', settings=None)

@demo_bp.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard"""
    try:
        analytics = Analytics()
        
        # Get comprehensive analytics
        data = {
            'overview': analytics.get_dashboard_statistics(),
            'screening_analytics': analytics.get_screening_analytics(),
            'document_analytics': analytics.get_document_analytics(),
            'patient_analytics': analytics.get_patient_analytics()
        }
        
        return render_template('analytics.html', analytics_data=data)
    
    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}")
        flash('Error loading analytics data.', 'error')
        return render_template('analytics.html', analytics_data={})

@demo_bp.route('/help')
@login_required
def help():
    """Help and documentation page"""
    return render_template('help.html')

@demo_bp.route('/search')
@login_required
def search():
    """Global search functionality"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return render_template('search_results.html', results={}, query='')
        
        # Search patients
        patients = Patient.query.filter(
            db.or_(
                Patient.name.contains(query),
                Patient.mrn.contains(query)
            )
        ).limit(10).all()
        
        # Search documents
        documents = MedicalDocument.query.filter(
            db.or_(
                MedicalDocument.filename.contains(query),
                MedicalDocument.content.contains(query)
            )
        ).limit(10).all()
        
        results = {
            'patients': patients,
            'documents': documents,
            'total': len(patients) + len(documents)
        }
        
        return render_template('search_results.html', results=results, query=query)
    
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        flash('Error performing search.', 'error')
        return render_template('search_results.html', results={}, query='')

@demo_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors in demo blueprint"""
    return render_template('error/404.html'), 404

@demo_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors in demo blueprint"""
    db.session.rollback()
    return render_template('error/500.html'), 500
