from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json

from app import app, db, login_manager
from models import *
from forms import *
from core.engine import ScreeningEngine
from core.matcher import DocumentMatcher
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import log_admin_action
from ocr.processor import OCRProcessor
from ocr.phi_filter import PHIFilter

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

# Main Dashboard Routes
@app.route('/')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin_dashboard'))
    
    # User dashboard - show screening overview
    recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(5).all()
    overdue_screenings = PatientScreening.query.filter_by(status='due').limit(10).all()
    
    return render_template('screening/list.html', 
                         patients=recent_patients,
                         overdue_screenings=overdue_screenings,
                         active_tab='list')

# Screening Management Routes
@app.route('/screening')
@app.route('/screening/<tab>')
@login_required
def screening_list(tab='list'):
    if tab not in ['list', 'types', 'checklist']:
        tab = 'list'
    
    # Get all patients and their screenings
    patients = Patient.query.all()
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    # Generate screening matrix
    screening_engine = ScreeningEngine()
    screening_matrix = []
    
    for patient in patients:
        patient_screenings = screening_engine.generate_patient_screenings(patient)
        screening_matrix.append({
            'patient': patient,
            'screenings': patient_screenings
        })
    
    # Get checklist settings
    checklist_settings = ChecklistSettings.query.first()
    if not checklist_settings:
        checklist_settings = ChecklistSettings()
        db.session.add(checklist_settings)
        db.session.commit()
    
    return render_template('screening/list.html',
                         screening_matrix=screening_matrix,
                         screening_types=screening_types,
                         checklist_settings=checklist_settings,
                         active_tab=tab)

@app.route('/screening/refresh', methods=['POST'])
@login_required
def refresh_screenings():
    try:
        screening_engine = ScreeningEngine()
        matcher = DocumentMatcher()
        
        # Refresh all patient screenings
        patients = Patient.query.all()
        updated_count = 0
        
        for patient in patients:
            # Update document matches
            documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
            for document in documents:
                matcher.match_document_to_screenings(document)
            
            # Regenerate screenings
            screening_engine.update_patient_screenings(patient)
            updated_count += 1
        
        db.session.commit()
        flash(f'Successfully refreshed screenings for {updated_count} patients', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error refreshing screenings: {str(e)}', 'error')
    
    return redirect(url_for('screening_list'))

@app.route('/screening/type/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    form = ScreeningTypeForm()
    
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            keywords=form.keywords.data.split(',') if form.keywords.data else [],
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            gender_restriction=form.gender_restriction.data if form.gender_restriction.data != 'any' else None,
            frequency_value=form.frequency_value.data,
            frequency_unit=form.frequency_unit.data,
            trigger_conditions=form.trigger_conditions.data.split(',') if form.trigger_conditions.data else []
        )
        
        db.session.add(screening_type)
        db.session.commit()
        
        if current_user.is_admin():
            log_admin_action(f'Added screening type: {screening_type.name}')
        
        flash(f'Screening type "{screening_type.name}" added successfully', 'success')
        return redirect(url_for('screening_list', tab='types'))
    
    return render_template('screening/types.html', form=form, mode='add')

# Prep Sheet Routes
@app.route('/prep-sheet/<int:patient_id>')
@login_required
def generate_prep_sheet(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    generator = PrepSheetGenerator()
    prep_data = generator.generate_prep_sheet(patient)
    
    return render_template('prep_sheet/template.html', 
                         patient=patient, 
                         prep_data=prep_data)

# Document Upload Routes
@app.route('/patient/<int:patient_id>/upload', methods=['POST'])
@login_required
def upload_document(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(request.referrer)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(request.referrer)
    
    if file:
        filename = secure_filename(file.filename)
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(app.root_path, 'uploads', str(patient_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # Create document record
        document = MedicalDocument(
            patient_id=patient_id,
            filename=filename,
            file_path=file_path,
            document_type=request.form.get('document_type', 'other')
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process with OCR
        try:
            ocr_processor = OCRProcessor()
            ocr_result = ocr_processor.process_document(document)
            
            # Apply PHI filtering
            phi_filter = PHIFilter()
            filtered_text = phi_filter.filter_text(ocr_result['text'])
            
            # Update document with OCR results
            document.ocr_text = filtered_text
            document.ocr_confidence = ocr_result['confidence']
            document.phi_filtered = True
            
            db.session.commit()
            
            # Match to screenings
            matcher = DocumentMatcher()
            matcher.match_document_to_screenings(document)
            
            flash(f'Document uploaded and processed successfully', 'success')
            
        except Exception as e:
            flash(f'Document uploaded but OCR processing failed: {str(e)}', 'warning')
    
    return redirect(request.referrer)

# API Routes
@app.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    return jsonify({
        'success': True,
        'keywords': screening_type.keywords or []
    })

# Admin Routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Dashboard statistics
    stats = {
        'total_patients': Patient.query.count(),
        'total_documents': MedicalDocument.query.count(),
        'active_screening_types': ScreeningType.query.filter_by(is_active=True).count(),
        'recent_logs': AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/ocr')
@login_required
def admin_ocr_dashboard():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # OCR statistics
    total_docs = MedicalDocument.query.count()
    processed_docs = MedicalDocument.query.filter(MedicalDocument.ocr_text.isnot(None)).count()
    high_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence >= 0.8).count()
    medium_confidence = MedicalDocument.query.filter(
        MedicalDocument.ocr_confidence >= 0.6,
        MedicalDocument.ocr_confidence < 0.8
    ).count()
    low_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence < 0.6).count()
    
    recent_docs = MedicalDocument.query.order_by(MedicalDocument.created_at.desc()).limit(10).all()
    
    stats = {
        'total_documents': total_docs,
        'processed_documents': processed_docs,
        'pending_processing': total_docs - processed_docs,
        'high_confidence': high_confidence,
        'medium_confidence': medium_confidence,
        'low_confidence': low_confidence,
        'recent_documents': recent_docs
    }
    
    return render_template('admin/ocr_dashboard.html', stats=stats)

@app.route('/admin/phi')
@login_required
def admin_phi_settings():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
        db.session.commit()
    
    return render_template('admin/phi_settings.html', settings=settings)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/logs.html', logs=logs)
