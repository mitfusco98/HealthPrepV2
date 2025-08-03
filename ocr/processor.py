"""
OCR processor with Tesseract integration and PHI filtering.
Handles automated document text extraction with medical document optimization.
"""

import logging
import os
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import fitz  # PyMuPDF for PDF processing
import cv2
import numpy as np

from app import db
from models import MedicalDocument
from ocr.phi_filter import PHIFilter

class OCRProcessor:
    """Main OCR processor for medical documents"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.phi_filter = PHIFilter()
        
        # OCR configuration optimized for medical documents
        self.tesseract_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,/:()-+=%'
        
        # Tesseract path configuration
        tesseract_path = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    def process_document(self, document_id: int) -> bool:
        """Process a document for OCR extraction"""
        try:
            document = MedicalDocument.query.get(document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False
            
            if document.ocr_processed:
                self.logger.info(f"Document {document_id} already processed")
                return True
            
            # Extract text based on file type
            if document.file_path and os.path.exists(document.file_path):
                extracted_text, confidence = self._extract_text_from_file(document.file_path)
                
                if extracted_text:
                    # Store original text before filtering
                    document.original_text = extracted_text
                    
                    # Apply PHI filtering if enabled
                    filtered_text = self.phi_filter.filter_phi(extracted_text)
                    
                    # Update document
                    document.ocr_text = filtered_text
                    document.ocr_confidence = confidence
                    document.ocr_processed = True
                    document.ocr_processed_at = datetime.utcnow()
                    document.phi_filtered = True
                    
                    db.session.commit()
                    
                    self.logger.info(f"Successfully processed document {document_id} with confidence {confidence:.2f}")
                    return True
                else:
                    self.logger.warning(f"No text extracted from document {document_id}")
                    
                    # Mark as processed even if no text found
                    document.ocr_processed = True
                    document.ocr_processed_at = datetime.utcnow()
                    document.ocr_confidence = 0.0
                    db.session.commit()
                    
                    return False
            else:
                self.logger.error(f"File not found for document {document_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {str(e)}")
            return False
    
    def _extract_text_from_file(self, file_path: str) -> tuple[str, float]:
        """Extract text from file based on its type"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                return self._extract_from_pdf(file_path)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                return self._extract_from_image(file_path)
            else:
                self.logger.warning(f"Unsupported file type: {file_ext}")
                return "", 0.0
                
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return "", 0.0
    
    def _extract_from_pdf(self, pdf_path: str) -> tuple[str, float]:
        """Extract text from PDF file"""
        try:
            extracted_text = ""
            total_confidence = 0.0
            page_count = 0
            
            # Try text extraction first (for text-based PDFs)
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                if text.strip():
                    # Text-based PDF
                    extracted_text += text + "\n"
                    total_confidence += 0.95  # High confidence for text extraction
                    page_count += 1
                else:
                    # Image-based PDF, use OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x scaling
                    img_data = pix.tobytes("png")
                    
                    # Save to temporary file for processing
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                        temp_file.write(img_data)
                        temp_path = temp_file.name
                    
                    try:
                        page_text, page_confidence = self._extract_from_image(temp_path)
                        extracted_text += page_text + "\n"
                        total_confidence += page_confidence
                        page_count += 1
                    finally:
                        os.unlink(temp_path)
            
            doc.close()
            
            average_confidence = total_confidence / page_count if page_count > 0 else 0.0
            return extracted_text.strip(), min(average_confidence, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error extracting from PDF {pdf_path}: {str(e)}")
            return "", 0.0
    
    def _extract_from_image(self, image_path: str) -> tuple[str, float]:
        """Extract text from image file using OCR"""
        try:
            # Preprocess image for better OCR
            processed_image = self._preprocess_image(image_path)
            
            # Extract text with confidence data
            ocr_data = pytesseract.image_to_data(
                processed_image, 
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
            average_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract text
            text = pytesseract.image_to_string(processed_image, config=self.tesseract_config)
            
            return text.strip(), average_confidence / 100.0  # Convert to 0-1 scale
            
        except Exception as e:
            self.logger.error(f"Error extracting from image {image_path}: {str(e)}")
            return "", 0.0
    
    def _preprocess_image(self, image_path: str) -> Image.Image:
        """Preprocess image for better OCR results"""
        try:
            # Load image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to OpenCV format for preprocessing
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Apply image preprocessing techniques
            # 1. Convert to grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # 2. Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (1, 1), 0)
            
            # 3. Apply threshold to get binary image
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 4. Apply morphological operations to clean up
            kernel = np.ones((1, 1), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Convert back to PIL Image
            processed_image = Image.fromarray(cleaned)
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(processed_image)
            processed_image = enhancer.enhance(1.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(processed_image)
            processed_image = enhancer.enhance(2.0)
            
            # Resize if image is too small (OCR works better on larger images)
            width, height = processed_image.size
            if width < 1000 or height < 1000:
                scale_factor = max(1000 / width, 1000 / height)
                new_size = (int(width * scale_factor), int(height * scale_factor))
                processed_image = processed_image.resize(new_size, Image.LANCZOS)
            
            return processed_image
            
        except Exception as e:
            self.logger.error(f"Error preprocessing image {image_path}: {str(e)}")
            # Return original image if preprocessing fails
            return Image.open(image_path)
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get OCR processing statistics"""
        try:
            total_docs = MedicalDocument.query.count()
            processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).count()
            pending_docs = total_docs - processed_docs
            
            # Confidence statistics
            high_confidence = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence >= 0.8
            ).count()
            
            medium_confidence = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence >= 0.6,
                MedicalDocument.ocr_confidence < 0.8
            ).count()
            
            low_confidence = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence < 0.6,
                MedicalDocument.ocr_confidence > 0
            ).count()
            
            # Recent processing activity
            recent_processed = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            ).count()
            
            return {
                'total_documents': total_docs,
                'processed_documents': processed_docs,
                'pending_documents': pending_docs,
                'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
                'confidence_distribution': {
                    'high': high_confidence,
                    'medium': medium_confidence,
                    'low': low_confidence
                },
                'today_processed': recent_processed
            }
            
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {str(e)}")
            return {}
    
    def reprocess_low_confidence_documents(self, threshold: float = 0.5) -> int:
        """Reprocess documents with confidence below threshold"""
        try:
            low_confidence_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence < threshold,
                MedicalDocument.ocr_processed == True
            ).all()
            
            reprocessed_count = 0
            for doc in low_confidence_docs:
                # Reset processing status
                doc.ocr_processed = False
                doc.ocr_text = None
                doc.ocr_confidence = None
                doc.ocr_processed_at = None
                
                # Reprocess
                if self.process_document(doc.id):
                    reprocessed_count += 1
            
            db.session.commit()
            self.logger.info(f"Reprocessed {reprocessed_count} low confidence documents")
            return reprocessed_count
            
        except Exception as e:
            self.logger.error(f"Error reprocessing documents: {str(e)}")
            return 0
    
    def validate_ocr_installation(self) -> Dict[str, Any]:
        """Validate OCR dependencies and configuration"""
        validation_results = {
            'tesseract_available': False,
            'tesseract_version': None,
            'supported_languages': [],
            'opencv_available': False,
            'pil_available': False,
            'pymupdf_available': False
        }
        
        try:
            # Check Tesseract
            version = pytesseract.get_tesseract_version()
            validation_results['tesseract_available'] = True
            validation_results['tesseract_version'] = str(version)
            
            # Check languages
            languages = pytesseract.get_languages(config='')
            validation_results['supported_languages'] = languages
            
        except Exception as e:
            self.logger.warning(f"Tesseract validation failed: {str(e)}")
        
        try:
            # Check OpenCV
            import cv2
            validation_results['opencv_available'] = True
        except ImportError:
            self.logger.warning("OpenCV not available")
        
        try:
            # Check PIL
            from PIL import Image
            validation_results['pil_available'] = True
        except ImportError:
            self.logger.warning("PIL not available")
        
        try:
            # Check PyMuPDF
            import fitz
            validation_results['pymupdf_available'] = True
        except ImportError:
            self.logger.warning("PyMuPDF not available")
        
        return validation_results
