"""
Tesseract integration and text cleanup for medical documents
"""
import os
import subprocess
import tempfile
from PIL import Image
import pdf2image
from app import db
from models import Document
from .phi_filter import PHIFilter
import logging

class OCRProcessor:
    """Handles OCR processing of medical documents using Tesseract"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.phi_filter = PHIFilter()
        
        # Tesseract configuration for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,()[]{}:;/\\-+=%$@#!?"\' \n\t'
    
    def process_document(self, document_id):
        """Process a document with OCR and PHI filtering"""
        document = Document.query.get(document_id)
        if not document:
            self.logger.error(f"Document {document_id} not found")
            return False
        
        try:
            # Extract text using OCR
            ocr_text, confidence = self._extract_text(document.file_path)
            
            if ocr_text:
                # Apply PHI filtering if enabled
                filtered_text = self.phi_filter.filter_phi(ocr_text)
                
                # Update document record
                document.ocr_text = filtered_text
                document.ocr_confidence = confidence
                document.phi_filtered = True
                document.processed_at = datetime.utcnow()
                
                db.session.commit()
                
                self.logger.info(f"Successfully processed document {document_id} with confidence {confidence:.2f}")
                
                # Trigger screening engine update
                from core.engine import ScreeningEngine
                engine = ScreeningEngine()
                engine.process_new_document(document_id)
                
                return True
            else:
                self.logger.warning(f"No text extracted from document {document_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {str(e)}")
            return False
    
    def _extract_text(self, file_path):
        """Extract text from document using Tesseract OCR"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.pdf':
                return self._process_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                return self._process_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
                
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None, 0.0
    
    def _process_pdf(self, pdf_path):
        """Process PDF document and extract text"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Convert PDF to images
                images = pdf2image.convert_from_path(pdf_path)
                
                all_text = []
                confidences = []
                
                for i, image in enumerate(images):
                    # Save image temporarily
                    image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(image_path, 'PNG')
                    
                    # Extract text from image
                    text, confidence = self._process_image(image_path)
                    
                    if text:
                        all_text.append(text)
                        confidences.append(confidence)
                
                # Combine all text and calculate average confidence
                combined_text = '\n'.join(all_text)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return combined_text, avg_confidence
                
            except Exception as e:
                self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
                return None, 0.0
    
    def _process_image(self, image_path):
        """Process image and extract text using Tesseract"""
        try:
            # Preprocess image for better OCR results
            processed_image_path = self._preprocess_image(image_path)
            
            # Run Tesseract OCR
            cmd = [
                'tesseract',
                processed_image_path,
                'stdout',
                '--oem', '3',
                '--psm', '6'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                text = result.stdout.strip()
                
                # Get confidence score
                confidence = self._calculate_confidence(processed_image_path)
                
                return text, confidence
            else:
                self.logger.error(f"Tesseract failed with return code {result.returncode}: {result.stderr}")
                return None, 0.0
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Tesseract timeout processing {image_path}")
            return None, 0.0
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {str(e)}")
            return None, 0.0
    
    def _preprocess_image(self, image_path):
        """Preprocess image to improve OCR accuracy"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Open and preprocess image
            with Image.open(image_path) as image:
                # Convert to grayscale
                if image.mode != 'L':
                    image = image.convert('L')
                
                # Enhance contrast and resize if needed
                from PIL import ImageEnhance
                
                # Enhance contrast
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)
                
                # Resize if image is too small
                width, height = image.size
                if width < 800 or height < 600:
                    scale_factor = max(800 / width, 600 / height)
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save preprocessed image
                image.save(temp_path, 'PNG')
            
            return temp_path
            
        except Exception as e:
            self.logger.error(f"Error preprocessing image {image_path}: {str(e)}")
            return image_path  # Return original if preprocessing fails
    
    def _calculate_confidence(self, image_path):
        """Calculate OCR confidence score"""
        try:
            cmd = [
                'tesseract',
                image_path,
                'stdout',
                '--oem', '3',
                '--psm', '6',
                'tsv'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                confidences = []
                
                for line in lines[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 11 and parts[10].strip():  # Confidence is in column 10
                        try:
                            conf = float(parts[10])
                            if conf > 0:  # Only include positive confidences
                                confidences.append(conf)
                        except ValueError:
                            continue
                
                if confidences:
                    return sum(confidences) / len(confidences) / 100.0  # Convert to 0-1 scale
                else:
                    return 0.5  # Default confidence if no data
            else:
                return 0.5  # Default confidence on error
                
        except Exception as e:
            self.logger.error(f"Error calculating confidence for {image_path}: {str(e)}")
            return 0.5  # Default confidence on error
    
    def reprocess_document(self, document_id):
        """Reprocess an existing document"""
        return self.process_document(document_id)
    
    def get_processing_stats(self):
        """Get OCR processing statistics"""
        total_docs = Document.query.count()
        processed_docs = Document.query.filter(Document.ocr_text.isnot(None)).count()
        
        # Calculate average confidence
        avg_confidence = db.session.query(db.func.avg(Document.ocr_confidence)).scalar() or 0.0
        
        # Count low confidence documents
        low_confidence_docs = Document.query.filter(Document.ocr_confidence < 0.6).count()
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'average_confidence': avg_confidence,
            'low_confidence_documents': low_confidence_docs
        }
    
    def cleanup_temp_files(self):
        """Clean up any temporary files created during processing"""
        temp_dir = tempfile.gettempdir()
        
        try:
            for filename in os.listdir(temp_dir):
                if filename.startswith('tesseract_') or filename.startswith('ocr_'):
                    file_path = os.path.join(temp_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        
        except Exception as e:
            self.logger.warning(f"Error cleaning up temp files: {str(e)}")

from datetime import datetime
