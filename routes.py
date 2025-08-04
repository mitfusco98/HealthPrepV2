from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
import os
from datetime import datetime, date, timedelta
import json
import logging

from app import app, db
from models import (User, Patient, ScreeningType, MedicalDocument, Screening, 
                   ScreeningDocumentMatch, PatientCondition, AdminLog, 
                   ChecklistSettings, PHISettings)
from forms import (LoginForm, ScreeningTypeForm, PatientForm, DocumentUploadForm,
                  ChecklistSettingsForm, PHISettingsForm)
from core.engine import ScreeningEngine
from ocr.processor import OCRProcessor
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import log_admin_action

# Initialize components
screening_engine = ScreeningEngine()
ocr_processor = OCRProcessor()
prep_sheet_generator = PrepSheetGenerator()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('dashboard')
            return redirect(next_page)
        flash('Invalid username or password', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get basic statistics
    total_patients = Patient.query.count()
    total_screenings = Screening.query.count()
    due_screenings = Screening.query.filter_by(status='Due').count()
    overdue_screenings = Screening.query.filter_by(status='Overdue').count()
    
    # Recent activity
    recent_documents = MedicalDocument.query.order_by(MedicalDocument.created_at.desc()).limit(5).all()
    recent_screenings = Screening.query.order_by(Screening.updated_at.desc()).limit(5).all()
    
    return render_template('dashboard.html',
                         total_patients=total_patients,
                         total_screenings=total_screenings,
                         due_screenings=due_screenings,
                         overdue_screenings=overdue_screenings,
                         recent_documents=recent_documents,
                         recent_screenings=recent_screenings)

@app.route('/patients')
@login_required
def patients():
    page = request.args.get('page', 1, type=int)
    patients = Patient.query.paginate(
        page=page, per_page=20, error_out=False)
    return render_template('patients.html', patients=patients)

@app.route('/patients/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    screenings = Screening.query.filter_by(patient_id=patient_id).all()
    documents = MedicalDocument.query.filter_by(patient_id=patient_id).order_by(MedicalDocument.document_date.desc()).all()
    conditions = PatientCondition.query.filter_by(patient_id=patient_id, is_active=True).all()
    
    return render_template('patient_detail.html',
                         patient=patient,
                         screenings=screenings,
                         documents=documents,
                         conditions=conditions)

@app.route('/patients/<int:patient_id>/prep_sheet')
@login_required
def prep_sheet(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    try:
        prep_data = prep_sheet_generator.generate_prep_sheet(patient)
        return render_template('prep_sheet/prep_sheet.html', 
                             patient=patient, 
                             prep_data=prep_data)
    except Exception as e:
        logging.error(f"Error generating prep sheet for patient {patient_id}: {e}")
        flash('Error generating prep sheet', 'error')
        return redirect(url_for('patient_detail', patient_id=patient_id))

@app.route('/screenings')
@login_required
def screening_list():
    # Get filter parameters
    patient_filter = request.args.get('patient', '')
    status_filter = request.args.get('status', '')
    screening_type_filter = request.args.get('type', '')
    
    # Base query
    query = db.session.query(Screening).join(Patient).join(ScreeningType)
    
    # Apply filters
    if patient_filter:
        query = query.filter(
            (Patient.first_name.ilike(f'%{patient_filter}%')) |
            (Patient.last_name.ilike(f'%{patient_filter}%')) |
            (Patient.mrn.ilike(f'%{patient_filter}%'))
        )
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if screening_type_filter:
        query = query.filter(ScreeningType.name.ilike(f'%{screening_type_filter}%'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    screenings = query.order_by(Screening.updated_at.desc()).paginate(
        page=page, per_page=50, error_out=False)
    
    # Get screening types for filter dropdown
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    return render_template('screening/screening_list.html',
                         screenings=screenings,
                         screening_types=screening_types,
                         current_filters={
                             'patient': patient_filter,
                             'status': status_filter,
                             'type': screening_type_filter
                         })

@app.route('/screening_types')
@login_required
def screening_types():
    screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
    return render_template('screening/screening_types.html', screening_types=screening_types)

@app.route('/screening_types/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            gender_restriction=form.gender_restriction.data or None,
            frequency_value=form.frequency_value.data,
            frequency_unit=form.frequency_unit.data,
            is_active=form.is_active.data
        )
        
        # Process keywords
        if form.keywords.data:
            keywords_list = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            screening_type.set_keywords_list(keywords_list)
        
        # Process trigger conditions
        if form.trigger_conditions.data:
            conditions_list = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            screening_type.set_trigger_conditions_list(conditions_list)
        
        db.session.add(screening_type)
        db.session.commit()
        
        if current_user.is_admin:
            log_admin_action(current_user.id, 'CREATE_SCREENING_TYPE', f'Added screening type: {screening_type.name}')
        
        flash('Screening type added successfully', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/add_screening_type.html', form=form)

@app.route('/screening_types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(type_id):
    screening_type = ScreeningType.query.get_or_404(type_id)
    form = ScreeningTypeForm(obj=screening_type)
    
    # Pre-populate form fields
    if request.method == 'GET':
        keywords_list = screening_type.get_keywords_list()
        form.keywords.data = '\n'.join(keywords_list)
        
        conditions_list = screening_type.get_trigger_conditions_list()
        form.trigger_conditions.data = '\n'.join(conditions_list)
    
    if form.validate_on_submit():
        screening_type.name = form.name.data
        screening_type.description = form.description.data
        screening_type.min_age = form.min_age.data
        screening_type.max_age = form.max_age.data
        screening_type.gender_restriction = form.gender_restriction.data or None
        screening_type.frequency_value = form.frequency_value.data
        screening_type.frequency_unit = form.frequency_unit.data
        screening_type.is_active = form.is_active.data
        
        # Process keywords
        if form.keywords.data:
            keywords_list = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            screening_type.set_keywords_list(keywords_list)
        else:
            screening_type.keywords = None
        
        # Process trigger conditions
        if form.trigger_conditions.data:
            conditions_list = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            screening_type.set_trigger_conditions_list(conditions_list)
        else:
            screening_type.trigger_conditions = None
        
        db.session.commit()
        
        if current_user.is_admin:
            log_admin_action(current_user.id, 'UPDATE_SCREENING_TYPE', f'Updated screening type: {screening_type.name}')
        
        flash('Screening type updated successfully', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/edit_screening_type.html', form=form, screening_type=screening_type)

@app.route('/refresh_screenings', methods=['POST'])
@login_required
def refresh_screenings():
    try:
        screening_engine.refresh_all_screenings()
        flash('Screenings refreshed successfully', 'success')
    except Exception as e:
        logging.error(f"Error refreshing screenings: {e}")
        flash('Error refreshing screenings', 'error')
    
    return redirect(request.referrer or url_for('screening_list'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get system statistics
    stats = {
        'total_users': User.query.count(),
        'total_patients': Patient.query.count(),
        'total_documents': MedicalDocument.query.count(),
        'total_screenings': Screening.query.count(),
        'active_screening_types': ScreeningType.query.filter_by(is_active=True).count(),
        'recent_activity': AdminLog.query.order_by(AdminLog.created_at.desc()).limit(10).all()
    }
    
    return render_template('admin/admin_dashboard.html', stats=stats)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get filter parameters
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base query
    query = AdminLog.query
    
    # Apply filters
    if action_filter:
        query = query.filter(AdminLog.action.ilike(f'%{action_filter}%'))
    
    if user_filter:
        query = query.join(User).filter(User.username.ilike(f'%{user_filter}%'))
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AdminLog.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AdminLog.created_at < date_to_obj)
        except ValueError:
            pass
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    logs = query.order_by(AdminLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False)
    
    return render_template('admin/admin_logs.html', logs=logs)

@app.route('/admin/ocr')
@login_required
def admin_ocr_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get OCR statistics
    ocr_stats = ocr_processor.get_processing_stats()
    
    return render_template('admin/admin_ocr_dashboard.html', stats=ocr_stats)

@app.route('/admin/phi_settings', methods=['GET', 'POST'])
@login_required
def phi_settings():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    # Get or create PHI settings
    phi_settings = PHISettings.query.first()
    if not phi_settings:
        phi_settings = PHISettings()
        db.session.add(phi_settings)
        db.session.commit()
    
    form = PHISettingsForm(obj=phi_settings)
    
    if form.validate_on_submit():
        form.populate_obj(phi_settings)
        phi_settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_admin_action(current_user.id, 'UPDATE_PHI_SETTINGS', 'Updated PHI filtering settings')
        flash('PHI settings updated successfully', 'success')
        return redirect(url_for('phi_settings'))
    
    return render_template('admin/phi_settings.html', form=form, settings=phi_settings)

# API endpoints
@app.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    keywords = screening_type.get_keywords_list()
    
    return jsonify({
        'success': True,
        'keywords': keywords
    })

@app.route('/api/refresh-screening/<int:screening_id>', methods=['POST'])
@login_required
def api_refresh_screening(screening_id):
    try:
        screening = Screening.query.get_or_404(screening_id)
        screening_engine.refresh_single_screening(screening)
        
        return jsonify({
            'success': True,
            'message': 'Screening refreshed successfully'
        })
    except Exception as e:
        logging.error(f"Error refreshing screening {screening_id}: {e}")
        return jsonify({
            'success': False,
            'message': 'Error refreshing screening'
        }), 500
