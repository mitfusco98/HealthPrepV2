"""
OCR processing routes and document management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime
import logging
import os

from models import Document, Patient
from ocr.processor import OCRProcessor
from ocr.monitor import OCRMonitor
from ocr.phi_filter import PHIFilter
from admin.logs import AdminLogManager

logger = logging.getLogger(__name__)

ocr_bp = Blueprint('ocr', __name__)

@ocr_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Upload and process document through OCR"""
    try:
        if request.method == 'GET':
            # Show upload form
            patient_id = request.args.get('patient_id', type=int)
            patient = Patient.query.get(patient_id) if patient_id else None
            patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
            
            return render_template('ocr/upload.html', 
                                 patient=patient, patients=patients)
        
        # Handle POST request
        patient_id = request.form.get('patient_id', type=int)
        document_type = request.form.get('document_type')
        document_date = request.form.get('document_date')
        
        if not patient_id:
            flash('Patient selection is required', 'error')
            return redirect(url_for('ocr.upload_document'))
        
        patient = Patient.query.get_or_404(patient_id)
        
        # Handle file upload
        if 'document_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('ocr.upload_document', patient_id=patient_id))
        
        file = request.files['document_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('ocr.upload_document', patient_id=patient_id))
        
        # Process the document
        result = process_uploaded_document(file, patient_id, document_type, document_date)
        
        if result['success']:
            flash(f'Document uploaded and processed successfully. OCR confidence: {result["confidence"]:.1f}%', 'success')
            
            # Log the action
            log_manager = AdminLogManager()
            log_manager.log_action(
                user_id=current_user.id,
                action='upload_document',
                target_type='document',
                target_id=result['document_id'],
                details={
                    'filename': file.filename,
                    'patient_mrn': patient.mrn,
                    'ocr_confidence': result['confidence']
                }
            )
            
            return redirect(url_for('main.patient_detail', patient_id=patient_id))
        else:
            flash(f'Error processing document: {result["error"]}', 'error')
            return redirect(url_for('ocr.upload_document', patient_id=patient_id))
        
    except Exception as e:
        logger.error(f"Error in document upload: {str(e)}")
        flash('Error uploading document', 'error')
        return redirect(url_for('ocr.upload_document'))

@ocr_bp.route('/document/<int:document_id>')
@login_required
def view_document(document_id):
    """View document with OCR results"""
    try:
        document = Document.query.get_or_404(document_id)
        
        # Apply PHI filtering if enabled
        phi_filter = PHIFilter()
        if phi_filter.settings and phi_filter.settings.enabled:
            filtered_result = phi_filter.filter_text(document.ocr_text or '')
            display_text = filtered_result['filtered_text']
            phi_filtered = True
        else:
            display_text = document.ocr_text
            phi_filtered = False
        
        return render_template('ocr/document_view.html',
                             document=document,
                             display_text=display_text,
                             phi_filtered=phi_filtered)
        
    except Exception as e:
        logger.error(f"Error viewing document: {str(e)}")
        flash('Error loading document', 'error')
        return redirect(url_for('main.dashboard'))

@ocr_bp.route('/document/<int:document_id>/download')
@login_required
def download_document(document_id):
    """Download original document file"""
    try:
        document = Document.query.get_or_404(document_id)
        
        if document.file_path and os.path.exists(document.file_path):
            return send_file(document.file_path, 
                           as_attachment=True,
                           download_name=document.filename)
        else:
            flash('Document file not found', 'error')
            return redirect(url_for('ocr.view_document', document_id=document_id))
        
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        flash('Error downloading document', 'error')
        return redirect(url_for('ocr.view_document', document_id=document_id))

@ocr_bp.route('/processing-stats')
@login_required
def processing_stats():
    """OCR processing statistics dashboard"""
    try:
        monitor = OCRMonitor()
        
        # Get comprehensive processing statistics
        dashboard_data = monitor.get_processing_dashboard()
        
        # Get processor statistics
        processor = OCRProcessor()
        processor_stats = processor.get_processing_stats()
        
        return render_template('ocr/processing_stats.html',
                             dashboard=dashboard_data,
                             processor_stats=processor_stats)
        
    except Exception as e:
        logger.error(f"Error loading processing stats: {str(e)}")
        flash('Error loading processing statistics', 'error')
        return render_template('error/500.html'), 500

@ocr_bp.route('/low-confidence')
@login_required
def low_confidence_documents():
    """View documents with low OCR confidence"""
    try:
        monitor = OCRMonitor()
        threshold = request.args.get('threshold', 60.0, type=float)
        
        # Get low confidence documents
        low_confidence_docs = monitor.get_low_confidence_documents(threshold)
        
        return render_template('ocr/low_confidence.html',
                             documents=low_confidence_docs,
                             threshold=threshold)
        
    except Exception as e:
        logger.error(f"Error loading low confidence documents: {str(e)}")
        flash('Error loading low confidence documents', 'error')
        return render_template('error/500.html'), 500

@ocr_bp.route('/api/process-document', methods=['POST'])
@login_required
def api_process_document():
    """API endpoint to process a document through OCR"""
    try:
        document_id = request.json.get('document_id')
        if not document_id:
            return jsonify({'success': False, 'error': 'Document ID required'})
        
        document = Document.query.get_or_404(document_id)
        
        if not document.file_path or not os.path.exists(document.file_path):
            return jsonify({'success': False, 'error': 'Document file not found'})
        
        # Process document through OCR
        processor = OCRProcessor()
        result = processor.process_document(document.file_path)
        
        if result['success']:
            # Update document with OCR results
            document.ocr_text = result['text']
            document.ocr_confidence = result['confidence']
            db.session.commit()
            
            # Record processing result
            monitor = OCRMonitor()
            monitor.record_processing_result(document.id, result)
            
            return jsonify({
                'success': True,
                'confidence': result['confidence'],
                'text_length': len(result['text']),
                'processing_time': result['processing_time']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            })
        
    except Exception as e:
        logger.error(f"Error in API process document: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ocr_bp.route('/api/validate-document', methods=['POST'])
@login_required
def api_validate_document():
    """API endpoint to validate document before processing"""
    try:
        document_id = request.json.get('document_id')
        if not document_id:
            return jsonify({'success': False, 'error': 'Document ID required'})
        
        document = Document.query.get_or_404(document_id)
        
        if not document.file_path:
            return jsonify({'success': False, 'error': 'No file path associated with document'})
        
        # Validate document
        processor = OCRProcessor()
        validation_result = processor.validate_document(document.file_path)
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating document: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ocr_bp.route('/batch-process', methods=['GET', 'POST'])
@login_required
def batch_process():
    """Batch process multiple documents"""
    try:
        if request.method == 'GET':
            # Show batch processing interface
            pending_docs = Document.query.filter(
                Document.ocr_text.is_(None)
            ).order_by(Document.created_at.desc()).limit(50).all()
            
            return render_template('ocr/batch_process.html',
                                 pending_documents=pending_docs)
        
        # Handle POST request
        document_ids = request.form.getlist('document_ids')
        if not document_ids:
            flash('No documents selected for processing', 'error')
            return redirect(url_for('ocr.batch_process'))
        
        # Process documents in batch
        processor = OCRProcessor()
        monitor = OCRMonitor()
        processed_count = 0
        error_count = 0
        
        for doc_id in document_ids:
            try:
                document = Document.query.get(int(doc_id))
                if document and document.file_path and os.path.exists(document.file_path):
                    result = processor.process_document(document.file_path)
                    
                    if result['success']:
                        document.ocr_text = result['text']
                        document.ocr_confidence = result['confidence']
                        monitor.record_processing_result(document.id, result)
                        processed_count += 1
                    else:
                        error_count += 1
                        logger.error(f"OCR failed for document {doc_id}: {result['error']}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing document {doc_id}: {str(e)}")
        
        db.session.commit()
        
        # Log the batch processing action
        log_manager = AdminLogManager()
        log_manager.log_action(
            user_id=current_user.id,
            action='batch_process_documents',
            details={
                'processed_count': processed_count,
                'error_count': error_count,
                'total_requested': len(document_ids)
            }
        )
        
        if processed_count > 0:
            flash(f'Successfully processed {processed_count} documents', 'success')
        if error_count > 0:
            flash(f'{error_count} documents failed processing', 'warning')
        
        return redirect(url_for('ocr.batch_process'))
        
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        flash('Error in batch processing', 'error')
        return redirect(url_for('ocr.batch_process'))

def process_uploaded_document(file, patient_id, document_type, document_date):
    """Helper function to process uploaded document"""
    try:
        from datetime import datetime
        import tempfile
        import uuid
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        temp_path = os.path.join(temp_dir, unique_filename)
        
        # Save uploaded file
        file.save(temp_path)
        
        # Create document record
        document = Document(
            patient_id=patient_id,
            filename=file.filename,
            file_path=temp_path,
            document_type=document_type,
            document_date=datetime.strptime(document_date, '%Y-%m-%d').date() if document_date else datetime.now().date()
        )
        
        db.session.add(document)
        db.session.flush()  # Get document ID
        
        # Process through OCR
        processor = OCRProcessor()
        ocr_result = processor.process_document(temp_path)
        
        if ocr_result['success']:
            # Apply PHI filtering
            phi_filter = PHIFilter()
            if phi_filter.settings and phi_filter.settings.enabled:
                filtered_result = phi_filter.filter_text(ocr_result['text'])
                document.ocr_text = filtered_result['filtered_text']
                document.phi_filtered = True
            else:
                document.ocr_text = ocr_result['text']
                document.phi_filtered = False
            
            document.ocr_confidence = ocr_result['confidence']
            
            # Record processing statistics
            monitor = OCRMonitor()
            monitor.record_processing_result(document.id, ocr_result)
        
        db.session.commit()
        
        return {
            'success': True,
            'document_id': document.id,
            'confidence': ocr_result.get('confidence', 0)
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing uploaded document: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
