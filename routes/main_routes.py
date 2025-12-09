"""
Apply the changes described in the prompt, fixing the dashboard route and addressing error handling.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from flask_login import login_required, current_user
from datetime import datetime
import logging

from models import Patient, Screening, Document, ScreeningType
from core.engine import ScreeningEngine
from prep_sheet.generator import PrepSheetGenerator
from forms import LoginForm
from services.provider_scope import (
    get_provider_patients, get_provider_screenings, get_active_provider,
    validate_patient_access, inject_provider_context, apply_provider_scope,
    set_active_provider, get_user_providers
)

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.before_request
def before_request():
    """Inject provider context before each request"""
    if current_user.is_authenticated:
        inject_provider_context()

@main_bp.route('/')
def index():
    """Main landing page"""
    if current_user.is_authenticated:
        if current_user.is_root_admin_user():
            return redirect(url_for('root_admin.dashboard'))
        elif current_user.is_admin_user():
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('ui.dashboard'))

    return render_template('auth/login.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard view - redirect to ui dashboard"""
    # Check if user is admin and redirect to admin dashboard
    if current_user.is_admin_user():
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('ui.dashboard'))

@main_bp.route('/screening-list')
@login_required
def screening_list():
    """Screening list page - provider scoped"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        query = get_provider_screenings(current_user, all_providers=False)
        query = query.join(Patient).join(ScreeningType)

        if search:
            query = query.filter(
                Patient.name.ilike(f'%{search}%') |
                ScreeningType.name.ilike(f'%{search}%')
            )

        screenings = query.order_by(
            Screening.next_due_date.asc()
        ).paginate(
            page=page, per_page=20, error_out=False
        )
        
        active_provider = get_active_provider(current_user)

        return render_template('screening/screening_list.html', 
                             screenings=screenings, 
                             search=search,
                             active_provider=active_provider)

    except Exception as e:
        logger.error(f"Error in screening list route: {str(e)}")
        flash('Error loading screenings', 'error')
        return render_template('error/500.html'), 500

@main_bp.route('/patients')
@login_required
def patients():
    """Patient list page - provider scoped"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')

        query = get_provider_patients(current_user, all_providers=False)

        if search:
            query = query.filter(
                Patient.name.ilike(f'%{search}%') |
                Patient.mrn.ilike(f'%{search}%')
            )

        patients_paginated = query.order_by(
            Patient.name
        ).paginate(
            page=page, per_page=20, error_out=False
        )
        
        active_provider = get_active_provider(current_user)

        return render_template('patients/list.html', 
                             patients=patients_paginated, 
                             search=search,
                             active_provider=active_provider)

    except Exception as e:
        logger.error(f"Error in patients route: {str(e)}")
        flash('Error loading patients', 'error')
        return render_template('error/500.html'), 500

@main_bp.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail page - with provider access validation"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        if not validate_patient_access(current_user, patient):
            flash('You do not have access to this patient.', 'error')
            return redirect(url_for('main.patients'))

        screenings = Screening.query.filter_by(
            patient_id=patient_id
        ).join(ScreeningType).filter_by(is_active=True).all()

        recent_docs = Document.query.filter_by(
            patient_id=patient_id
        ).order_by(Document.created_at.desc()).limit(10).all()
        
        active_provider = get_active_provider(current_user)

        return render_template('patients/detail.html',
                             patient=patient,
                             screenings=screenings,
                             recent_documents=recent_docs,
                             active_provider=active_provider)

    except Exception as e:
        logger.error(f"Error in patient detail route: {str(e)}")
        flash('Error loading patient details', 'error')
        return render_template('error/404.html'), 404

@main_bp.route('/patient/<int:patient_id>/prep-sheet')
@login_required
def generate_prep_sheet(patient_id):
    """Generate prep sheet for a patient - with provider access validation"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        if not validate_patient_access(current_user, patient):
            flash('You do not have access to this patient.', 'error')
            return redirect(url_for('main.patients'))

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


@main_bp.route('/switch-provider/<int:provider_id>')
@login_required
def switch_provider(provider_id):
    """Switch the active provider context for the current session"""
    from services.provider_scope import set_active_provider
    from models import Provider
    
    if set_active_provider(current_user, provider_id):
        provider = Provider.query.get(provider_id)
        if provider:
            flash(f'Switched to {provider.name}', 'success')
    else:
        flash('Unable to switch to that provider.', 'error')
    
    return redirect(request.referrer or url_for('main.dashboard'))

@main_bp.route('/refresh-screenings', methods=['POST'])
@login_required
def refresh_screenings():
    """Comprehensive EMR sync for all patients"""
    try:
        from services.comprehensive_emr_sync import ComprehensiveEMRSync
        
        # Get patient ID if specified, otherwise sync all
        patient_id = request.form.get('patient_id', type=int)
        
        # Initialize comprehensive EMR sync for the user's organization
        emr_sync = ComprehensiveEMRSync(current_user.org_id)

        if patient_id:
            # Sync specific patient from Epic EMR
            patient = Patient.query.get_or_404(patient_id)
            if patient.epic_patient_id:
                sync_result = emr_sync.sync_patient_comprehensive(patient.epic_patient_id)
                if sync_result.get('success'):
                    flash(f'Successfully synced data from Epic for {patient.name}', 'success')
                else:
                    flash(f'EMR sync failed: {sync_result.get("error", "Unknown error")}', 'error')
            else:
                flash('Patient has no Epic ID - cannot sync from EMR', 'warning')
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        else:
            # Use patient discovery to automatically find and sync Epic sandbox patients
            sync_results = emr_sync.discover_and_sync_patients()
            
            if sync_results.get('success'):
                discovered = sync_results.get('discovered_patients', 0)
                imported = sync_results.get('imported_patients', 0)
                synced = sync_results.get('synced_patients', 0)
                updated_screenings = sync_results.get('updated_screenings', 0)
                errors = sync_results.get('errors', [])
                
                message = f'EMR sync completed! Discovered {discovered} patients, imported {imported}, synced {synced} patients, updated {updated_screenings} screenings'
                if errors:
                    message += f'. {len(errors)} errors occurred.'
                flash(message, 'success')
            else:
                error_msg = sync_results.get('error', 'Unknown error occurred')
                flash(f'EMR sync failed: {error_msg}', 'error')
            return redirect(url_for('ui.dashboard'))

    except Exception as e:
        logger.error(f"Error syncing from EMR: {str(e)}")
        flash('Error syncing data from EMR', 'error')
        return redirect(url_for('ui.dashboard'))

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

@main_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')