"""
Document upload and management routes.
"""

import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user

from models import Patient, Document, AdminLog
from ocr.processor import OCRProcessor
from ocr.phi_filter import PHIFilter
from forms import DocumentUploadForm
from app import db

logger = logging.getLogger(__name__)

document_bp = Blueprint('documents', __name__)

# Configure upload settings
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """Ensure upload folder exists"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

@document_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Document upload page"""
    form = DocumentUploadForm()

    # Populate patient choices
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    form.patient_id.choices = [(p.id, f"{p.last_name}, {p.first_name} ({p.mrn})") for p in patients]

    if form.validate_on_submit():
        try:
            ensure_upload_folder()

            file = form.file.data
            patient_id = form.patient_id.data
            document_type = form.document_type.data
            document_date = form.document_date.data

            if file and allowed_file(file.filename):
                # Secure the filename
                filename = secure_filename(file.filename)

                # Create unique filename to avoid conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                unique_filename = f"{patient_id}_{timestamp}_{name}{ext}"

                # Save file
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(file_path)

                # Get file size
                file_size = os.path.getsize(file_path)

                # Create document record
                document = Document(
                    patient_id=patient_id,
                    filename=filename,
                    document_type=document_type,
                    document_date=document_date,
                    file_path=file_path,
                    file_size=file_size,
                    upload_date=datetime.utcnow()
                )

                db.session.add(document)
                db.session.commit()

                # Process with OCR if enabled
                if form.process_ocr.data:
                    try:
                        ocr_processor = OCRProcessor()
                        ocr_result = ocr_processor.process_document(document.id, file_path)

                        if ocr_result['success']:
                            # Apply PHI filtering if enabled
                            if form.apply_phi_filter.data:
                                phi_filter = PHIFilter()
                                filter_result = phi_filter.filter_text(document.ocr_text, current_user.id)

                                if filter_result['success']:
                                    document.phi_filtered = True
                                    document.phi_filtered_text = filter_result['filtered_text']
                                    db.session.commit()

                    except Exception as ocr_error:
                        logger.warning(f"OCR processing failed for document {document.id}: {str(ocr_error)}")
                        flash('Document uploaded successfully, but OCR processing failed.', 'warning')

                # Log the action
                patient = Patient.query.get(patient_id)
                log_entry = AdminLog(
                    user_id=current_user.id,
                    action='UPLOAD_DOCUMENT',
                    description=f"Uploaded document: {filename} for patient {patient.first_name} {patient.last_name}",
                    ip_address=request.remote_addr
                )
                db.session.add(log_entry)
                db.session.commit()

                flash('Document uploaded successfully!', 'success')
                logger.info(f"Document uploaded: {filename} for patient {patient_id} by user {current_user.username}")

                return redirect(url_for('documents.document_list', patient_id=patient_id))
            else:
                flash('Invalid file type. Please upload PDF, PNG, JPG, JPEG, TIFF, or TIF files.', 'error')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error uploading document: {str(e)}")
            flash('Error uploading document. Please try again.', 'error')

    return render_template('documents/document_upload.html', form=form, patients=patients)

@document_bp.route('/patient/<int:patient_id>')
@login_required
def document_list(patient_id):
    """List documents for a specific patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)

        # Get documents for this patient
        documents = Document.query.filter_by(patient_id=patient_id).order_by(
            Document.document_date.desc(),
            Document.upload_date.desc()
        ).all()

        return render_template('documents/document_list.html',
                             patient=patient,
                             documents=documents)

    except Exception as e:
        logger.error(f"Error loading document list for patient {patient_id}: {str(e)}")
        flash('Error loading documents.', 'error')
        return redirect(url_for('index'))

@document_bp.route('/view/<int:document_id>')
@login_required
def view_document(document_id):
    """View document details and OCR text"""
    try:
        document = Document.query.get_or_404(document_id)
        patient = Patient.query.get(document.patient_id)

        # Check if file exists
        file_exists = document.file_path and os.path.exists(document.file_path)

        return render_template('documents/document_view.html',
                             document=document,
                             patient=patient,
                             file_exists=file_exists)

    except Exception as e:
        logger.error(f"Error viewing document {document_id}: {str(e)}")
        flash('Error loading document.', 'error')
        return redirect(url_for('index'))

@document_bp.route('/download/<int:document_id>')
@login_required
def download_document(document_id):
    """Download original document file"""
    try:
        document = Document.query.get_or_404(document_id)

        if not document.file_path or not os.path.exists(document.file_path):
            flash('Document file not found.', 'error')
            return redirect(url_for('documents.view_document', document_id=document_id))

        # Log the action
        log_entry = AdminLog(
            user_id=current_user.id,
            action='DOWNLOAD_DOCUMENT',
            description=f"Downloaded document: {document.filename}",
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()

        return send_file(document.file_path,
                        as_attachment=True,
                        download_name=document.filename)

    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        flash('Error downloading document.', 'error')
        return redirect(url_for('documents.view_document', document_id=document_id))

@document_bp.route('/delete/<int:document_id>', methods=['POST'])
@login_required
def delete_document(document_id):
    """Delete document"""
    try:
        document = Document.query.get_or_404(document_id)
        patient_id = document.patient_id
        filename = document.filename
        file_path = document.file_path

        # Delete database record
        db.session.delete(document)
        db.session.commit()

        # Delete file from filesystem
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError as e:
                logger.warning(f"Could not delete file {file_path}: {str(e)}")

        # Log the action
        log_entry = AdminLog(
            user_id=current_user.id,
            action='DELETE_DOCUMENT',
            description=f"Deleted document: {filename}",
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()

        flash('Document deleted successfully.', 'success')
        logger.info(f"Document deleted: {filename} by user {current_user.username}")

        return redirect(url_for('documents.document_list', patient_id=patient_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        flash('Error deleting document. Please try again.', 'error')
        return redirect(url_for('documents.view_document', document_id=document_id))

@document_bp.route('/batch-ocr', methods=['POST'])
@login_required
def batch_ocr_processing():
    """Process multiple documents with OCR"""
    try:
        document_ids_str = request.form.get('document_ids', '')

        if not document_ids_str:
            flash('No documents selected for OCR processing.', 'error')
            return redirect(url_for('index'))

        # Parse document IDs
        try:
            document_ids = [int(did.strip()) for did in document_ids_str.split(',') if did.strip()]
        except ValueError:
            flash('Invalid document IDs format.', 'error')
            return redirect(url_for('index'))

        # Process documents with OCR
        ocr_processor = OCRProcessor()
        batch_result = ocr_processor.batch_process_documents(document_ids)

        if batch_result['success']:
            # Log the action
            log_entry = AdminLog(
                user_id=current_user.id,
                action='BATCH_OCR_PROCESSING',
                description=f"Processed {batch_result['processed']} documents with OCR",
                ip_address=request.remote_addr
            )
            db.session.add(log_entry)
            db.session.commit()

            flash(f'OCR processing completed: {batch_result["processed"]} processed, '
                  f'{batch_result["failed"]} failed.', 'success')

            if batch_result['errors']:
                for error in batch_result['errors'][:5]:  # Show first 5 errors
                    flash(f'Error: {error}', 'warning')

            logger.info(f"Batch OCR processing completed by user {current_user.username}: {batch_result}")
        else:
            flash(f'Error in batch OCR processing: {batch_result.get("error")}', 'error')

        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Error in batch OCR processing: {str(e)}")
        flash('Error processing documents. Please try again.', 'error')
        return redirect(url_for('index'))

@document_bp.route('/api/upload-progress/<upload_id>')
@login_required
def upload_progress(upload_id):
    """API endpoint for upload progress (placeholder for future implementation)"""
    try:
        # This would track upload progress for large files
        # For now, return a simple response
        return jsonify({
            'upload_id': upload_id,
            'progress': 100,
            'status': 'complete'
        })

    except Exception as e:
        logger.error(f"Error getting upload progress: {str(e)}")
        return jsonify({'error': str(e)}), 500