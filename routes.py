from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import *
from forms import *
from core.engine import ScreeningEngine
from ocr.processor import OCRProcessor
from prep_sheet.generator import PrepSheetGenerator
from admin.logs import AdminLogger
import os
from datetime import datetime, date

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Main dashboard
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin_dashboard'))
    
    # Get recent patients and screenings
    recent_patients = Patient.query.order_by(Patient.updated_at.desc()).limit(10).all()
    due_screenings = Screening.query.filter_by(status='due').limit(10).all()
    
    return render_template('dashboard.html', 
                         recent_patients=recent_patients,
                         due_screenings=due_screenings)

# Screening management
@app.route('/screenings')
@login_required
def screening_list():
    # Get filter parameters
    patient_filter = request.args.get('patient', '')
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')
    
    # Build query
    query = Screening.query.join(Patient).join(ScreeningType)
    
    if patient_filter:
        query = query.filter(
            (Patient.first_name.contains(patient_filter)) |
            (Patient.last_name.contains(patient_filter)) |
            (Patient.mrn.contains(patient_filter))
        )
    
    if status_filter:
        query = query.filter(Screening.status == status_filter)
    
    if type_filter:
        query = query.filter(ScreeningType.name.contains(type_filter))
    
    screenings = query.order_by(Patient.last_name, Patient.first_name).all()
    screening_types = ScreeningType.query.filter_by(is_active=True).all()
    
    return render_template('screening/list.html', 
                         screenings=screenings,
                         screening_types=screening_types,
                         filters={'patient': patient_filter, 'status': status_filter, 'type': type_filter})

@app.route('/screening-types')
@login_required
def screening_types():
    screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
    return render_template('screening/types.html', screening_types=screening_types)

@app.route('/screening-types/add', methods=['GET', 'POST'])
@login_required
def add_screening_type():
    form = ScreeningTypeForm()
    if form.validate_on_submit():
        screening_type = ScreeningType(
            name=form.name.data,
            description=form.description.data,
            min_age=form.min_age.data,
            max_age=form.max_age.data,
            gender=form.gender.data if form.gender.data else None,
            frequency_value=form.frequency_value.data,
            frequency_unit=form.frequency_unit.data,
            is_active=form.is_active.data
        )
        
        # Process keywords
        if form.keywords.data:
            keywords = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            screening_type.keywords_list = keywords
        
        # Process trigger conditions
        if form.trigger_conditions.data:
            conditions = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            screening_type.trigger_conditions = '\n'.join(conditions)
        
        db.session.add(screening_type)
        db.session.commit()
        
        AdminLogger.log(current_user.id, 'screening_type_created', 
                       f'Created screening type: {screening_type.name}')
        
        flash('Screening type created successfully', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/add_type.html', form=form)

@app.route('/screening-types/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_screening_type(id):
    screening_type = ScreeningType.query.get_or_404(id)
    form = ScreeningTypeForm(obj=screening_type)
    
    if request.method == 'GET':
        # Populate form fields
        form.keywords.data = '\n'.join(screening_type.keywords_list)
        if screening_type.trigger_conditions:
            form.trigger_conditions.data = screening_type.trigger_conditions.replace(',', '\n')
    
    if form.validate_on_submit():
        screening_type.name = form.name.data
        screening_type.description = form.description.data
        screening_type.min_age = form.min_age.data
        screening_type.max_age = form.max_age.data
        screening_type.gender = form.gender.data if form.gender.data else None
        screening_type.frequency_value = form.frequency_value.data
        screening_type.frequency_unit = form.frequency_unit.data
        screening_type.is_active = form.is_active.data
        
        # Process keywords
        if form.keywords.data:
            keywords = [k.strip() for k in form.keywords.data.split('\n') if k.strip()]
            screening_type.keywords_list = keywords
        
        # Process trigger conditions
        if form.trigger_conditions.data:
            conditions = [c.strip() for c in form.trigger_conditions.data.split('\n') if c.strip()]
            screening_type.trigger_conditions = '\n'.join(conditions)
        
        db.session.commit()
        
        AdminLogger.log(current_user.id, 'screening_type_updated', 
                       f'Updated screening type: {screening_type.name}')
        
        flash('Screening type updated successfully', 'success')
        return redirect(url_for('screening_types'))
    
    return render_template('screening/edit_type.html', form=form, screening_type=screening_type)

# Patient management
@app.route('/patients')
@login_required
def patients():
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    return render_template('patients/list.html', patients=patients)

@app.route('/patients/add', methods=['GET', 'POST'])
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
        
        AdminLogger.log(current_user.id, 'patient_created', 
                       f'Created patient: {patient.full_name} (MRN: {patient.mrn})')
        
        flash('Patient created successfully', 'success')
        return redirect(url_for('patients'))
    
    return render_template('patients/add.html', form=form)

@app.route('/patients/<int:id>')
@login_required
def patient_detail(id):
    patient = Patient.query.get_or_404(id)
    screenings = Screening.query.filter_by(patient_id=id).join(ScreeningType).all()
    documents = Document.query.filter_by(patient_id=id).order_by(Document.document_date.desc()).all()
    appointments = Appointment.query.filter_by(patient_id=id).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template('patients/detail.html', 
                         patient=patient, 
                         screenings=screenings,
                         documents=documents,
                         appointments=appointments)

# Document management
@app.route('/patients/<int:patient_id>/upload', methods=['GET', 'POST'])
@login_required
def upload_document(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(current_app.instance_path, 'uploads', str(patient_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # Create document record
        document = Document(
            patient_id=patient_id,
            filename=filename,
            original_filename=file.filename,
            file_path=file_path,
            document_type=form.document_type.data,
            document_date=form.document_date.data or date.today()
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process with OCR
        ocr_processor = OCRProcessor()
        ocr_processor.process_document(document.id)
        
        AdminLogger.log(current_user.id, 'document_uploaded', 
                       f'Uploaded document for patient {patient.full_name}: {filename}')
        
        flash('Document uploaded and processed successfully', 'success')
        return redirect(url_for('patient_detail', id=patient_id))
    
    return render_template('patients/upload.html', form=form, patient=patient)

# Prep sheet generation
@app.route('/patients/<int:patient_id>/prep-sheet')
@login_required
def generate_prep_sheet(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    generator = PrepSheetGenerator()
    prep_data = generator.generate_prep_sheet(patient_id)
    
    AdminLogger.log(current_user.id, 'prep_sheet_generated', 
                   f'Generated prep sheet for patient {patient.full_name}')
    
    return render_template('prep_sheet/template.html', 
                         patient=patient, 
                         prep_data=prep_data)

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get statistics
    total_patients = Patient.query.count()
    total_documents = Document.query.count()
    total_screenings = Screening.query.count()
    due_screenings = Screening.query.filter_by(status='due').count()
    
    # Recent activity
    recent_logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         stats={
                             'total_patients': total_patients,
                             'total_documents': total_documents,
                             'total_screenings': total_screenings,
                             'due_screenings': due_screenings
                         },
                         recent_logs=recent_logs)

@app.route('/admin/ocr')
@login_required
def admin_ocr_dashboard():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get OCR statistics
    total_docs = Document.query.count()
    processed_docs = Document.query.filter(Document.ocr_text.isnot(None)).count()
    avg_confidence = db.session.query(db.func.avg(Document.ocr_confidence)).scalar() or 0
    low_confidence_docs = Document.query.filter(Document.ocr_confidence < 0.6).count()
    
    recent_documents = Document.query.order_by(Document.created_at.desc()).limit(10).all()
    
    return render_template('admin/ocr_dashboard.html',
                         ocr_stats={
                             'total_documents': total_docs,
                             'processed_documents': processed_docs,
                             'average_confidence': round(avg_confidence * 100, 1) if avg_confidence else 0,
                             'low_confidence_documents': low_confidence_docs
                         },
                         recent_documents=recent_documents)

@app.route('/admin/phi', methods=['GET', 'POST'])
@login_required
def admin_phi_settings():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    settings = PHIFilterSettings.query.first()
    if not settings:
        settings = PHIFilterSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = PHIFilterForm(obj=settings)
    
    if form.validate_on_submit():
        form.populate_obj(settings)
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        AdminLogger.log(current_user.id, 'phi_settings_updated', 'Updated PHI filter settings')
        
        flash('PHI filter settings updated successfully', 'success')
        return redirect(url_for('admin_phi_settings'))
    
    return render_template('admin/phi_settings.html', form=form, settings=settings)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    
    query = AdminLog.query
    
    if action_filter:
        query = query.filter(AdminLog.action.contains(action_filter))
    
    if user_filter:
        query = query.join(User).filter(User.username.contains(user_filter))
    
    logs = query.order_by(AdminLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False)
    
    return render_template('admin/logs.html', logs=logs, 
                         filters={'action': action_filter, 'user': user_filter})

# API endpoints
@app.route('/api/refresh-screenings', methods=['POST'])
@login_required
def api_refresh_screenings():
    try:
        engine = ScreeningEngine()
        updated_count = engine.refresh_all_screenings()
        
        AdminLogger.log(current_user.id, 'screenings_refreshed', 
                       f'Refreshed {updated_count} screenings')
        
        return jsonify({'success': True, 'updated_count': updated_count})
    except Exception as e:
        current_app.logger.error(f"Error refreshing screenings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/screening-keywords/<int:screening_type_id>')
@login_required
def api_screening_keywords(screening_type_id):
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    return jsonify({
        'success': True,
        'keywords': screening_type.keywords_list
    })

# Import secure_filename
from werkzeug.utils import secure_filename
