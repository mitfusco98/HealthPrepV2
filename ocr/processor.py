"""
Tesseract integration and text cleanup
Handles automated document processing with HIPAA compliance
"""

import os
import subprocess
import logging
import tempfile
from datetime import datetime
from PIL import Image
import pdf2image
from werkzeug.utils import secure_filename
from app import db
from models import MedicalDocument, OCRProcessingStats

class OCRProcessor:
    """Handles OCR processing of medical documents using Tesseract"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tesseract_cmd = os.environ.get('TESSERACT_CMD', '/usr/bin/tesseract')
        self.supported_formats = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']
        
        # OCR configuration for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?()[]{}"-/+= '
    
    def process_document(self, document_id):
        """Process a single document with OCR"""
        try:
            document = MedicalDocument.query.get(document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False
            
            # Update processing status
            document.processing_status = 'processing'
            db.session.commit()
            
            # Extract text from document
            extracted_text, confidence = self._extract_text_from_file(document.file_path)
            
            if extracted_text:
                document.ocr_text = extracted_text
                document.ocr_confidence = confidence
                document.is_processed = True
                document.processing_status = 'completed'
                
                # Apply PHI filtering
                from ocr.phi_filter import PHIFilter
                phi_filter = PHIFilter()
                filtered_text = phi_filter.filter_text(extracted_text)
                document.phi_filtered_text = filtered_text
                
                # Update document keywords
                from core.matcher import DocumentMatcher
                matcher = DocumentMatcher()
                matcher.update_document_keywords(document_id)
                
                self.logger.info(f"Successfully processed document {document.filename} with confidence {confidence}")
                
            else:
                document.processing_status = 'failed'
                self.logger.error(f"Failed to extract text from document {document.filename}")
            
            db.session.commit()
            
            # Update processing statistics
            self._update_processing_stats()
            
            return document.is_processed
            
        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {str(e)}")
            
            # Update document status on error
            try:
                document = MedicalDocument.query.get(document_id)
                if document:
                    document.processing_status = 'failed'
                    db.session.commit()
            except:
                pass
            
            return False
    
    def _extract_text_from_file(self, file_path):
        """Extract text from various file formats"""
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return None, 0
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext not in self.supported_formats:
            self.logger.error(f"Unsupported file format: {file_ext}")
            return None, 0
        
        try:
            if file_ext == '.pdf':
                return self._process_pdf(file_path)
            else:
                return self._process_image(file_path)
                
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None, 0
    
    def _process_pdf(self, file_path):
        """Process PDF file with OCR"""
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(file_path, dpi=300)
            
            all_text = []
            total_confidence = 0
            page_count = 0
            
            for i, image in enumerate(images):
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    image.save(temp_file.name, 'PNG')
                    
                    text, confidence = self._run_tesseract(temp_file.name)
                    
                    if text:
                        all_text.append(f"[Page {i+1}]\n{text}")
                        total_confidence += confidence
                        page_count += 1
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
            
            combined_text = '\n\n'.join(all_text)
            average_confidence = total_confidence / page_count if page_count > 0 else 0
            
            return combined_text, average_confidence
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {file_path}: {str(e)}")
            return None, 0
    
    def _process_image(self, file_path):
        """Process image file with OCR"""
        try:
            # Preprocess image for better OCR results
            processed_image_path = self._preprocess_image(file_path)
            
            text, confidence = self._run_tesseract(processed_image_path)
            
            # Clean up processed image if it's different from original
            if processed_image_path != file_path:
                os.unlink(processed_image_path)
            
            return text, confidence
            
        except Exception as e:
            self.logger.error(f"Error processing image {file_path}: {str(e)}")
            return None, 0
    
    def _preprocess_image(self, file_path):
        """Preprocess image for better OCR results"""
        try:
            with Image.open(file_path) as image:
                # Convert to grayscale
                if image.mode != 'L':
                    image = image.convert('L')
                
                # Enhance contrast and brightness for medical documents
                from PIL import ImageEnhance
                
                # Increase contrast
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)
                
                # Increase sharpness
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(2.0)
                
                # Save processed image to temp file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    image.save(temp_file.name, 'PNG')
                    return temp_file.name
                    
        except Exception as e:
            self.logger.warning(f"Could not preprocess image {file_path}: {str(e)}")
            return file_path  # Return original if preprocessing fails
    
    def _run_tesseract(self, image_path):
        """Run Tesseract OCR on an image"""
        try:
            # Run Tesseract with confidence scores
            cmd = [
                self.tesseract_cmd,
                image_path,
                'stdout',
                '--oem', '3',
                '--psm', '6',
                '-c', 'tessedit_create_tsv=1'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                self.logger.error(f"Tesseract error: {result.stderr}")
                return None, 0
            
            # Parse TSV output to extract text and confidence
            text_lines = []
            confidences = []
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 12:
                        confidence = parts[10]
                        word = parts[11]
                        
                        if word.strip() and confidence.isdigit():
                            text_lines.append(word)
                            confidences.append(int(confidence))
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Join text
            full_text = ' '.join(text_lines)
            
            # Clean up text
            cleaned_text = self._clean_extracted_text(full_text)
            
            return cleaned_text, avg_confidence
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Tesseract timeout processing {image_path}")
            return None, 0
        except Exception as e:
            self.logger.error(f"Error running Tesseract on {image_path}: {str(e)}")
            return None, 0
    
    def _clean_extracted_text(self, text):
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common OCR artifacts
        text = re.sub(r'[|¦]', 'I', text)  # Common misreads
        text = re.sub(r'[º°]', 'o', text)
        text = re.sub(r'[¹¡]', '1', text)
        
        # Fix common medical term OCR errors
        medical_corrections = {
            r'\bpatient\b': 'patient',
            r'\bdoctor\b': 'doctor',
            r'\bdiagnosis\b': 'diagnosis',
            r'\btreatment\b': 'treatment',
            r'\bmedicine\b': 'medicine',
            r'\bprescription\b': 'prescription'
        }
        
        for pattern, replacement in medical_corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _update_processing_stats(self):
        """Update OCR processing statistics"""
        try:
            stats = OCRProcessingStats.query.first()
            if not stats:
                stats = OCRProcessingStats()
                db.session.add(stats)
            
            # Calculate current statistics
            total_docs = MedicalDocument.query.count()
            processed_docs = MedicalDocument.query.filter_by(is_processed=True).count()
            failed_docs = MedicalDocument.query.filter_by(processing_status='failed').count()
            
            # Calculate average confidence
            confidence_results = db.session.query(MedicalDocument.ocr_confidence).filter(
                MedicalDocument.ocr_confidence.isnot(None)
            ).all()
            
            avg_confidence = 0
            if confidence_results:
                confidences = [r[0] for r in confidence_results if r[0] is not None]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Update statistics
            stats.total_documents = total_docs
            stats.processed_documents = processed_docs
            stats.failed_documents = failed_docs
            stats.average_confidence = avg_confidence
            stats.last_updated = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating processing stats: {str(e)}")
    
    def batch_process_pending(self):
        """Process all pending documents"""
        try:
            pending_docs = MedicalDocument.query.filter_by(
                processing_status='pending'
            ).limit(10).all()  # Process in batches
            
            success_count = 0
            
            for doc in pending_docs:
                if self.process_document(doc.id):
                    success_count += 1
            
            self.logger.info(f"Batch processed {success_count}/{len(pending_docs)} documents")
            return success_count
            
        except Exception as e:
            self.logger.error(f"Error in batch processing: {str(e)}")
            return 0
    
    def get_processing_queue_size(self):
        """Get number of documents pending processing"""
        return MedicalDocument.query.filter_by(processing_status='pending').count()
    
    def validate_file_upload(self, filename):
        """Validate uploaded file for OCR processing"""
        if not filename:
            return False, "No filename provided"
        
        # Secure filename
        filename = secure_filename(filename)
        
        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in self.supported_formats:
            return False, f"Unsupported file format. Supported formats: {', '.join(self.supported_formats)}"
        
        return True, "File valid for processing"
