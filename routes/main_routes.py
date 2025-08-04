"""
Apply the changes described in the prompt, fixing the dashboard route and addressing error handling.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging

from models import Patient, Screening, Document, ScreeningType
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator
from forms import LoginForm

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main index route - redirect to dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    else:
        return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard view"""
    try:
        logger.info(f"Dashboard accessed by user: {current_user.username}")

        # Get basic statistics
        total_patients = Patient.query.count()
        total_documents = Document.query.count()

        # Get screening statistics
        total_screenings = Screening.query.count()
        due_screenings = Screening.query.filter_by(status='Due').count()
        complete_screenings = Screening.query.filter_by(status='Complete').count()

        # Create stats object for template
        stats = {
            'total_patients': total_patients,
            'total_documents': total_documents,
            'total_screenings': total_screenings,
            'due_screenings': due_screenings,
            'complete_screenings': complete_screenings
        }

        # Recent activity
        recent_documents = Document.query.order_by(Document.created_at.desc()).limit(5).all()
        recent_screenings = Screening.query.order_by(Screening.created_at.desc()).limit(5).all()

        return render_template('dashboard.html',
                             stats=stats,
                             total_patients=total_patients,
                             total_documents=total_documents,
                             total_screenings=total_screenings,
                             due_screenings=due_screenings,
                             complete_screenings=complete_screenings,
                             recent_documents=recent_documents,
                             recent_screenings=recent_screenings)

    except Exception as e:
        logger.error(f"Error in dashboard route: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('error/500.html'), 500

@main_bp.route('/screening-list')
@login_required
def screening_list():
    """Screening list page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')

        query = Screening.query.join(Patient).join(ScreeningType)

        if search:
            query = query.filter(
                Patient.first_name.contains(search) |
                Patient.last_name.contains(search) |
                ScreeningType.name.contains(search)
            )

        screenings = query.order_by(
            Screening.next_due_date.asc()
        ).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('screening/screening_list.html', 
                             screenings=screenings, search=search)

    except Exception as e:
        logger.error(f"Error in screening list route: {str(e)}")
        flash('Error loading screenings', 'error')
        return render_template('error/500.html'), 500

@main_bp.route('/patients')
@login_required
def patients():
    """Patient list page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')

        query = Patient.query

        if search:
            query = query.filter(
                Patient.first_name.contains(search) |
                Patient.last_name.contains(search) |
                Patient.mrn.contains(search)
            )

        patients = query.order_by(
            Patient.last_name, Patient.first_name
        ).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('patients/list.html', 
                             patients=patients, search=search)

    except Exception as e:
        logger.error(f"Error in patients route: {str(e)}")
        flash('Error loading patients', 'error')
        return render_template('error/500.html'), 500

@main_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail page"""
    try:
        patient = Patient.query.get_or_404(patient_id)

        # Get patient screenings
        screenings = Screening.query.filter_by(
            patient_id=patient_id
        ).join(ScreeningType).filter_by(is_active=True).all()

        # Get recent documents
        recent_docs = Document.query.filter_by(
            patient_id=patient_id
        ).order_by(Document.created_at.desc()).limit(10).all()

        return render_template('patients/detail.html',
                             patient=patient,
                             screenings=screenings,
                             recent_documents=recent_docs)

    except Exception as e:
        logger.error(f"Error in patient detail route: {str(e)}")
        flash('Error loading patient details', 'error')
        return render_template('error/404.html'), 404

@main_bp.route('/patient/<int:patient_id>/prep-sheet')
@login_required
def generate_prep_sheet(patient_id):
    """Generate prep sheet for a patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)

        generator = PrepSheetGenerator()
        result = generator.generate_prep_sheet(patient_id)

        if result['success']:
            return render_template('prep_sheet/prep_sheet.html', **result['data'])
        else:
            flash(f'Error generating prep sheet: {result["error"]}', 'error')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))

    except Exception as e:
        logger.error(f"Error generating prep sheet: {str(e)}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

@main_bp.route('/refresh-screenings', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh all screenings"""
    try:
        engine = ScreeningEngine()

        # Get patient ID if specified, otherwise refresh all
        patient_id = request.form.get('patient_id', type=int)

        if patient_id:
            result = engine.process_patient_screenings(patient_id, refresh_all=True)
            flash(f'Refreshed screenings for patient. Processed: {result["processed_screenings"]}', 'success')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        else:
            result = engine.refresh_all_screenings()
            flash(f'Refreshed all screenings. Processed {result["total_screenings"]} screenings for {result["processed_patients"]} patients', 'success')
            return redirect(url_for('main.dashboard'))

    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        flash('Error refreshing screenings', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    """API endpoint to get keywords for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)

        return jsonify({
            'success': True,
            'keywords': screening_type.keywords or [],
            'screening_name': screening_type.name
        })

    except Exception as e:
        logger.error(f"Error getting screening keywords: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/search')
@login_required
def search():
    """Global search functionality"""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')

        if not query:
            return render_template('search_results.html', 
                                 query='', results={})

        results = {}

        # Search patients
        if search_type in ['all', 'patients']:
            results['patients'] = Patient.query.filter(
                Patient.first_name.contains(query) |
                Patient.last_name.contains(query) |
                Patient.mrn.contains(query)
            ).limit(10).all()

        # Search documents
        if search_type in ['all', 'documents']:
            results['documents'] = Document.query.filter(
                Document.filename.contains(query) |
                Document.ocr_text.contains(query)
            ).limit(10).all()

        # Search screening types
        if search_type in ['all', 'screenings']:
            results['screening_types'] = ScreeningType.query.filter(
                ScreeningType.name.contains(query) |
                ScreeningType.description.contains(query)
            ).limit(10).all()

        return render_template('search_results.html',
                             query=query, results=results,
                             search_type=search_type)

    except Exception as e:
        logger.error(f"Error in search route: {str(e)}")
        flash('Error performing search', 'error')
        return render_template('search_results.html', 
                             query='', results={})

@main_bp.route('/upload-document', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Upload document for a patient"""
    try:
        if request.method == 'GET':
            patient_id = request.args.get('patient_id', type=int)
            patient = Patient.query.get(patient_id) if patient_id else None
            return render_template('upload_document.html', patient=patient)

        # Handle POST request
        patient_id = request.form.get('patient_id', type=int)
        document_type = request.form.get('document_type')
        document_date = request.form.get('document_date')

        if not patient_id:
            flash('Patient ID is required', 'error')
            return redirect(url_for('main.upload_document'))

        patient = Patient.query.get_or_404(patient_id)

        # Handle file upload
        if 'document_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('main.upload_document', patient_id=patient_id))

        file = request.files['document_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('main.upload_document', patient_id=patient_id))

        # Process document upload (this would typically involve OCR processing)
        # For now, just create the database record
        from datetime import datetime, date
        from app import db

        document = Document(
            patient_id=patient_id,
            filename=file.filename,
            document_type=document_type,
            document_date=datetime.strptime(document_date, '%Y-%m-%d').date() if document_date else date.today()
        )

        db.session.add(document)
        db.session.commit()

        flash('Document uploaded successfully', 'success')
        return redirect(url_for('main.patient_detail', patient_id=patient_id))

    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        flash('Error uploading document', 'error')
        return redirect(url_for('main.upload_document'))

@main_bp.route('/help')
def help():
    """Help and documentation page"""
    return render_template('help.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard route"""
    return redirect(url_for('demo.index'))

@main_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')