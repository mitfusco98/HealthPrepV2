from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import Patient, MedicalDocument, Screening
from forms import PatientForm, DocumentUploadForm
from app import db
from admin.logs import log_admin_action
from ocr.processor import OCRProcessor
from core.engine import ScreeningEngine
import os
from werkzeug.utils import secure_filename
from datetime import datetime

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/list')
@login_required
def patient_list():
    page = request.args.get('page', 1, type=int)
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
    
    patients = query.order_by(Patient.last_name, Patient.first_name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('patient/patient_list.html', patients=patients, search=search)

@patient_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    form = PatientForm()
    
    if form.validate_on_submit():
        # Check if MRN already exists
        existing_patient = Patient.query.filter_by(mrn=form.mrn.data).first()
        if existing_patient:
            flash('A patient with this MRN already exists.', 'error')
            return render_template('patient/add_patient.html', form=form)
        
        patient = Patient()
        form.populate_obj(patient)
        
        db.session.add(patient)
        db.session.commit()
        
        # Log the action
        log_admin_action(
            user_id=current_user.id,
            action='Patient Created',
            details=f'Created patient: {patient.full_name} (MRN: {patient.mrn})',
            ip_address=request.remote_addr
        )
        
        # Generate initial screenings for this patient
        engine = ScreeningEngine()
        engine.generate_screenings_for_patient(patient.id)
        
        flash(f'Patient "{patient.full_name}" created successfully.', 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient.id))
    
    return render_template('patient/add_patient.html', form=form)

@patient_bp.route('/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Get patient's documents
    documents = MedicalDocument.query.filter_by(patient_id=patient_id).order_by(
        MedicalDocument.document_date.desc().nullslast(),
        MedicalDocument.upload_date.desc()
    ).all()
    
    # Get patient's screenings
    screenings = Screening.query.filter_by(patient_id=patient_id).join(
        ScreeningType
    ).order_by(ScreeningType.name).all()
    
    # Get patient's conditions - removing this since Condition model doesn't exist
    conditions = []
    
    return render_template('patient/patient_detail.html',
                         patient=patient,
                         documents=documents,
                         screenings=screenings,
                         conditions=conditions)

@patient_bp.route('/<int:patient_id>/upload', methods=['GET', 'POST'])
@login_required
def upload_document(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        file = form.file.data
        if file:
            filename = secure_filename(file.filename)
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(current_app.instance_path, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Create document record
            document = MedicalDocument(
                patient_id=patient_id,
                filename=filename,
                file_path=file_path,
                document_type=form.document_type.data,
                document_date=form.document_date.data
            )
            
            db.session.add(document)
            db.session.commit()
            
            # Process document with OCR
            try:
                ocr_processor = OCRProcessor()
                ocr_processor.process_document(document.id)
                
                # Refresh screenings for this patient
                engine = ScreeningEngine()
                engine.refresh_screenings_for_patient(patient_id)
                
                flash(f'Document "{filename}" uploaded and processed successfully.', 'success')
            except Exception as e:
                flash(f'Document uploaded but OCR processing failed: {str(e)}', 'warning')
            
            # Log the action
            log_admin_action(
                user_id=current_user.id,
                action='Document Uploaded',
                details=f'Uploaded document "{filename}" for patient {patient.full_name}',
                ip_address=request.remote_addr
            )
            
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    
    return render_template('patient/upload_document.html', form=form, patient=patient)

@patient_bp.route('/document/<int:document_id>')
@login_required
def view_document(document_id):
    document = MedicalDocument.query.get_or_404(document_id)
    return render_template('patient/view_document.html', document=document)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Patient, db
from forms import PatientForm
from datetime import datetime

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    """Add a new patient"""
    form = PatientForm()
    
    if form.validate_on_submit():
        try:
            patient = Patient(
                mrn=form.mrn.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                date_of_birth=form.date_of_birth.data,
                gender=form.gender.data
            )
            
            db.session.add(patient)
            db.session.commit()
            
            flash('Patient added successfully!', 'success')
            return redirect(url_for('patient.patient_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding patient: {str(e)}', 'error')
    
    return render_template('patients/add_patient.html', form=form)

@patient_bp.route('/list')
@login_required
def patient_list():
    """List all patients"""
    patients = Patient.query.all()
    return render_template('patients/patient_list.html', patients=patients)

@patient_bp.route('/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    """Patient detail view"""
    patient = Patient.query.get_or_404(patient_id)
    return render_template('patients/patient_detail.html', patient=patient)
