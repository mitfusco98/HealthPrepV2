from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import Patient, MedicalDocument
from ocr.processor import OCRProcessor
from ocr.phi_filter import PHIFilter
from admin.logs import log_admin_action
from app import db
import os
from datetime import datetime

document_bp = Blueprint('documents', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@document_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Create upload directory if it doesn't exist
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Get patient information
            patient_id = request.form.get('patient_id', type=int)
            document_type = request.form.get('document_type', 'general')
            
            patient = Patient.query.get_or_404(patient_id)
            
            # Create document record
            document = MedicalDocument(
                patient_id=patient.id,
                filename=filename,
                document_type=document_type,
                file_path=file_path
            )
            db.session.add(document)
            db.session.commit()
            
            # Process with OCR
            ocr_processor = OCRProcessor()
            ocr_text, confidence = ocr_processor.process_document(file_path)
            
            # Apply PHI filtering
            phi_filter = PHIFilter()
            filtered_text = phi_filter.filter_text(ocr_text)
            
            # Update document with OCR results
            document.ocr_text = filtered_text
            document.ocr_confidence = confidence
            document.phi_filtered = True
            db.session.commit()
            
            log_admin_action(current_user.id, 'Document Uploaded',
                           f'Uploaded document: {filename} for patient: {patient.full_name}', 
                           request.remote_addr)
            
            flash(f'Document "{filename}" uploaded and processed successfully', 'success')
            return redirect(url_for('documents.document_list'))
        else:
            flash('Invalid file type. Please upload PDF, PNG, JPG, JPEG, TIFF, or BMP files.', 'error')
    
    # Get patients for dropdown
    patients = Patient.query.all()
    return render_template('document/document_upload.html', patients=patients)

@document_bp.route('/list')
@login_required
def document_list():
    """Display all uploaded documents"""
    documents = MedicalDocument.query.order_by(MedicalDocument.upload_date.desc()).all()
    return render_template('document/document_list.html', documents=documents)

@document_bp.route('/view/<int:document_id>')
@login_required
def view_document(document_id):
    """View document details and OCR text"""
    document = MedicalDocument.query.get_or_404(document_id)
    return render_template('document/document_detail.html', document=document)
