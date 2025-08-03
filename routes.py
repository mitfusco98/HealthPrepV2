from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
import logging

from app import app, db
from models import User, Patient, ScreeningType, MedicalDocument, Screening, AdminLog, ChecklistSettings, PHISettings
from forms import LoginForm, ScreeningTypeForm, PatientForm, DocumentUploadForm
from core.engine import ScreeningEngine
from ocr.processor import OCRProcessor
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import log_admin_action

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            if user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('Account is deactivated. Please contact administrator.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Main dashboard
@app.route('/')
@login_required
def dashboard():
    # Get recent patients and statistics
    recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(10).all()
    total_patients = Patient.query.count()
    total_documents = MedicalDocument.query.count()
    pending_ocr = MedicalDocument.query.filter_by(ocr_processed=False).count()
    
    # Get recent screenings needing attention
    overdue_screenings = Screening.query.filter_by(status='Due').limit(10).all()
    
    return render_template('dashboard.html',
                         recent_patients=recent_patients,
                         total_patients=total_patients,
                         total_documents=total_documents,
                         pending_ocr=pending_ocr,
                         overdue_screenings=overdue_screenings)

# Patient management
@app.route('/patients')
@login_required
def patients():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Patient.query
    if search:
        query = query.filter(
            (Patient.first_name.contains(search)) |
            (Patient.last_name.contains(search)) |
            (Patient.mrn.contains(search))
        )
    
    patients = query.order_by(Patient.last_name, Patient.first_name)\
                   .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('patients.html', patients=patients, search=search)

@app.route('/patient/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Get patient documents
    documents = MedicalDocument.query.filter_by(patient_id=patient_id)\
                                   .order_by(MedicalDocument.document_date.desc()).all()
    
    # Get patient screenings
    screenings = Screening.query.filter_by(patient_id=patient_id)\
                               .join(ScreeningType)\
                               .order_by(ScreeningType.name).all()
    
    # Get upcoming appointments
    appointments = patient.appointments
    
    return render_template('patient_detail.html',
                         patient=patient,
                         documents=documents,
                         screenings=screenings,
                         appointments=appointments)

@app.route('/add_patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    form = PatientForm()
    if form.validate_on_submit():
        patient = Patient(
            mrn=form.mrn.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            date_of_birth=form.date_of_birth.data,
            gender=form.gender.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data
        )
        db.session.add(patient)
        db.session.commit()
        
        # Initialize screenings for this patient
        engine = ScreeningEngine()
        engine.initialize_patient_screenings(patient.id)
        
        flash(f'Patient {patient.first_name} {patient.last_name} added successfully.', 'success')
        return redirect(url_for('patient_detail', patient_id=patient.id))
    
    return render_template('patient_form.html', form=form, title='Add Patient')

# Screening management
@app.route('/screenings')
@login_required
def screening_list():
    # Get all active screening types
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    # Get filter parameters
    patient_filter = request.args.get('patient')
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')
    
    # Build query
    query = Screening.query.join(Patient).join(ScreeningType)
    
    if patient_filter:
        query = query.filter(
            (Patient.first_name.contains(patient_filter)) |
            (Patient.last_name.contains(patient_filter))
        )
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if type_filter:
        query = query.filter(ScreeningType.id == type_filter)
    
    screenings = query.order_by(Patient.last_name, Patient.first_name).all()
    
    return render_template('screening/screening_list.html',
                         screenings=screenings,
                         screening_types=screening_types,
                         filters={
                             'patient': patient_filter,
                             'status': status_filter,
                             'type': type_filter
                         })

@app.route('/screening_types')
@login_required
def screening_types():
    types = ScreeningType.query.order_by(ScreeningType.name).all()
    return render_template('screening/screening_types.html', screening_types=types)

@app.route('/add_screening_type', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    form = ScreeningTypeForm()
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            keywords=json.dumps(form.keywords.data.split(',') if form.keywords.data else []),
            eligible_genders=form.eligible_genders.data,
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            frequency_number=form.frequency_number.data,
            frequency_unit=form.frequency_unit.data,
            trigger_conditions=form.trigger_conditions.data
        )
        db.session.add(screening_type)
        db.session.commit()
        
        # Refresh all patient screenings
        engine = ScreeningEngine()
        engine.refresh_all_screenings()
        
        flash(f'Screening type "{screening_type.name}" added successfully.', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/add_screening_type.html', form=form)

# Document management
@app.route('/upload_document/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def upload_document(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        file = form.file.data
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure upload directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            # Create document record
            document = MedicalDocument(
                patient_id=patient_id,
                filename=filename,
                file_path=file_path,
                document_type=form.document_type.data,
                document_date=form.document_date.data,
                file_size=os.path.getsize(file_path),
                mime_type=file.content_type
            )
            db.session.add(document)
            db.session.commit()
            
            # Process OCR asynchronously
            ocr_processor = OCRProcessor()
            ocr_processor.process_document(document.id)
            
            flash(f'Document "{filename}" uploaded successfully.', 'success')
            return redirect(url_for('patient_detail', patient_id=patient_id))
    
    return render_template('document_upload.html', form=form, patient=patient)

# Prep sheet generation
@app.route('/prep_sheet/<int:patient_id>')
@login_required
def prep_sheet(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate prep sheet
    generator = PrepSheetGenerator()
    prep_data = generator.generate_prep_sheet(patient_id)
    
    return render_template('prep_sheet.html', patient=patient, prep_data=prep_data)

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get system statistics
    stats = {
        'total_users': User.query.count(),
        'total_patients': Patient.query.count(),
        'total_documents': MedicalDocument.query.count(),
        'processed_documents': MedicalDocument.query.filter_by(ocr_processed=True).count(),
        'pending_ocr': MedicalDocument.query.filter_by(ocr_processed=False).count(),
        'active_screening_types': ScreeningType.query.filter_by(is_active=True).count()
    }
    
    # Get recent logs
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    return render_template('admin/admin_dashboard.html', stats=stats, recent_logs=recent_logs)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action')
    user_filter = request.args.get('user')
    
    query = AdminLog.query
    
    if action_filter:
        query = query.filter(AdminLog.action.contains(action_filter))
    
    if user_filter:
        query = query.join(User).filter(User.username.contains(user_filter))
    
    logs = query.order_by(AdminLog.timestamp.desc())\
              .paginate(page=page, per_page=50, error_out=False)
    
    return render_template('admin/admin_logs.html', logs=logs)

@app.route('/admin/ocr')
@login_required
def admin_ocr_dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # OCR statistics
    total_docs = MedicalDocument.query.count()
    processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).count()
    pending_docs = total_docs - processed_docs
    
    # Confidence statistics
    high_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence >= 0.8).count()
    medium_confidence = MedicalDocument.query.filter(
        MedicalDocument.ocr_confidence >= 0.6,
        MedicalDocument.ocr_confidence < 0.8
    ).count()
    low_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence < 0.6).count()
    
    stats = {
        'total_documents': total_docs,
        'processed_documents': processed_docs,
        'pending_documents': pending_docs,
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'low_confidence': low_confidence
    }
    
    # Recent processing activity
    recent_activity = MedicalDocument.query.filter_by(ocr_processed=True)\
                                          .order_by(MedicalDocument.ocr_processed_at.desc())\
                                          .limit(20).all()
    
    return render_template('admin/admin_ocr_dashboard.html', 
                         stats=stats, 
                         recent_activity=recent_activity)

@app.route('/admin/phi_settings', methods=['GET', 'POST'])
@login_required
def phi_settings():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    settings = PHISettings.query.first()
    if not settings:
        settings = PHISettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        settings.phi_filtering_enabled = request.form.get('phi_filtering_enabled') == 'on'
        settings.filter_ssn = request.form.get('filter_ssn') == 'on'
        settings.filter_phone = request.form.get('filter_phone') == 'on'
        settings.filter_mrn = request.form.get('filter_mrn') == 'on'
        settings.filter_insurance = request.form.get('filter_insurance') == 'on'
        settings.filter_addresses = request.form.get('filter_addresses') == 'on'
        settings.filter_names = request.form.get('filter_names') == 'on'
        settings.filter_dates = request.form.get('filter_dates') == 'on'
        
        db.session.commit()
        
        log_admin_action(current_user.id, 'PHI Settings Updated', 'PHI filtering settings modified')
        flash('PHI settings updated successfully.', 'success')
        return redirect(url_for('phi_settings'))
    
    return render_template('admin/phi_settings.html', settings=settings)

# API routes
@app.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    keywords = screening_type.get_keywords_list()
    
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@app.route('/api/refresh_screenings', methods=['POST'])
@login_required
def api_refresh_screenings():
    try:
        engine = ScreeningEngine()
        updated_count = engine.refresh_all_screenings()
        
        log_admin_action(current_user.id, 'Screening Refresh', f'Refreshed {updated_count} screenings')
        
        return jsonify({
            'success': True,
            'message': f'Successfully refreshed {updated_count} screenings',
            'updated_count': updated_count
        })
    except Exception as e:
        logging.error(f"Error refreshing screenings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error refreshing screenings: {str(e)}'
        }), 500

# Error handlers
@app.errorhandler(400)
def bad_request(error):
    return render_template('error/400.html'), 400

@app.errorhandler(401)
def unauthorized(error):
    return render_template('error/401.html'), 401

@app.errorhandler(403)
def forbidden(error):
    return render_template('error/403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error/500.html'), 500

# Template context processors
@app.context_processor
def utility_processor():
    def cache_timestamp():
        return str(int(datetime.utcnow().timestamp()))
    
    return dict(cache_timestamp=cache_timestamp)
