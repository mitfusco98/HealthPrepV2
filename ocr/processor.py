"""
Tesseract integration and text cleanup for medical documents
"""

import os
import logging
import tempfile
import subprocess
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import re
import pytesseract
from PIL import Image
import pdf2image
from models import MedicalDocument, db

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Handles OCR processing of medical documents"""
    
    def __init__(self):
        # Configure Tesseract path if needed
        tesseract_path = os.environ.get('TESSERACT_PATH')
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # OCR configuration optimized for medical documents
        self.ocr_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:()[]{}/<>@#$%^&*+-=|\\~`"\'?! '
        
        # Medical document preprocessing settings
        self.image_settings = {
            'dpi': 300,
            'format': 'RGB'
        }
    
    def process_document(self, document: MedicalDocument, file_content: bytes = None) -> Dict[str, Any]:
        """
        Process a medical document with OCR
        """
        logger.info(f"Starting OCR processing for document {document.id}: {document.filename}")
        
        try:
            # Load file content if not provided
            if file_content is None:
                if not document.file_path or not os.path.exists(document.file_path):
                    return {'success': False, 'error': 'File not found'}
                
                with open(document.file_path, 'rb') as f:
                    file_content = f.read()
            
            # Determine file type and extract text
            file_extension = os.path.splitext(document.filename)[1].lower()
            
            if file_extension == '.pdf':
                result = self._process_pdf(file_content)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']:
                result = self._process_image(file_content)
            else:
                return {'success': False, 'error': f'Unsupported file type: {file_extension}'}
            
            if result['success']:
                # Store original text before PHI filtering
                document.original_text = result['text']
                
                # Apply PHI filtering
                from ocr.phi_filter import PHIFilter
                phi_filter = PHIFilter()
                filtered_result = phi_filter.filter_text(result['text'])
                
                # Update document with OCR results
                document.ocr_text = filtered_result['filtered_text']
                document.ocr_confidence = result['confidence']
                document.ocr_processed = True
                document.ocr_processed_at = datetime.utcnow()
                document.phi_filtered = True
                document.phi_patterns_list = filtered_result['patterns_found']
                
                db.session.commit()
                
                logger.info(f"OCR processing completed for document {document.id} with confidence {result['confidence']:.2f}")
                
                return {
                    'success': True,
                    'text': document.ocr_text,
                    'confidence': result['confidence'],
                    'phi_patterns': filtered_result['patterns_found']
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error processing document {document.id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """Process PDF file with OCR"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(file_content)
                temp_pdf.flush()
                
                # Convert PDF to images
                images = pdf2image.convert_from_path(
                    temp_pdf.name,
                    dpi=self.image_settings['dpi'],
                    fmt=self.image_settings['format']
                )
                
                all_text = []
                confidences = []
                
                for i, image in enumerate(images):
                    # Preprocess image for better OCR
                    processed_image = self._preprocess_image(image)
                    
                    # Extract text with confidence
                    text, confidence = self._extract_text_with_confidence(processed_image)
                    
                    all_text.append(text)
                    confidences.append(confidence)
                    
                    logger.debug(f"Processed page {i+1}/{len(images)} with confidence {confidence:.2f}")
                
                # Clean up temp file
                os.unlink(temp_pdf.name)
                
                # Combine results
                combined_text = '\n\n'.join(all_text)
                average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return {
                    'success': True,
                    'text': combined_text,
                    'confidence': average_confidence,
                    'pages_processed': len(images)
                }
                
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_image(self, file_content: bytes) -> Dict[str, Any]:
        """Process image file with OCR"""
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_image:
                temp_image.write(file_content)
                temp_image.flush()
                
                # Load and preprocess image
                image = Image.open(temp_image.name)
                processed_image = self._preprocess_image(image)
                
                # Extract text with confidence
                text, confidence = self._extract_text_with_confidence(processed_image)
                
                # Clean up temp file
                os.unlink(temp_image.name)
                
                return {
                    'success': True,
                    'text': text,
                    'confidence': confidence
                }
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results"""
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if image is too small
        width, height = image.size
        if width < 1000 or height < 1000:
            scale_factor = max(1000 / width, 1000 / height)
            new_size = (int(width * scale_factor), int(height * scale_factor))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        return image
    
    def _extract_text_with_confidence(self, image: Image.Image) -> Tuple[str, float]:
        """Extract text and calculate confidence score"""
        try:
            # Get detailed OCR data
            data = pytesseract.image_to_data(image, config=self.ocr_config, output_type=pytesseract.Output.DICT)
            
            # Extract text
            text = pytesseract.image_to_string(image, config=self.ocr_config)
            
            # Calculate confidence score
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Clean up text
            cleaned_text = self._clean_text(text)
            
            return cleaned_text, average_confidence / 100.0  # Convert to 0-1 scale
            
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return "", 0.0
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common OCR artifacts
        text = re.sub(r'[^\w\s.,;:()[\]{}/<>@#$%^&*+-=|\\~`"\'?!]', '', text)
        
        # Fix common medical term OCR errors
        medical_corrections = {
            r'\b(\d+)\s*([a-zA-Z]+)\b': r'\1\2',  # Fix separated numbers and units
            r'\bO\b': '0',  # Fix O misread as 0
            r'\bl\b': '1',  # Fix l misread as 1
            r'\brnrn\b': 'mm',  # Common OCR error
            r'\brng\b': 'mg',  # Common OCR error
        }
        
        for pattern, replacement in medical_corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Strip and return
        return text.strip()
    
    def batch_process_documents(self, limit: int = 10) -> Dict[str, Any]:
        """
        Process multiple documents in batch
        """
        logger.info(f"Starting batch OCR processing (limit: {limit})")
        
        # Get unprocessed documents
        unprocessed_docs = MedicalDocument.query.filter_by(ocr_processed=False).limit(limit).all()
        
        results = {
            'processed': 0,
            'failed': 0,
            'total_found': len(unprocessed_docs),
            'details': []
        }
        
        for document in unprocessed_docs:
            try:
                result = self.process_document(document)
                if result['success']:
                    results['processed'] += 1
                    results['details'].append({
                        'document_id': document.id,
                        'filename': document.filename,
                        'status': 'success',
                        'confidence': result['confidence']
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'document_id': document.id,
                        'filename': document.filename,
                        'status': 'failed',
                        'error': result['error']
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'document_id': document.id,
                    'filename': document.filename,
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Batch processing error for document {document.id}: {str(e)}")
        
        logger.info(f"Batch processing complete: {results['processed']} processed, {results['failed']} failed")
        return results
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get OCR processing statistics"""
        total_docs = MedicalDocument.query.count()
        processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).count()
        pending_docs = total_docs - processed_docs
        
        # Average confidence for processed documents
        avg_confidence = db.session.query(db.func.avg(MedicalDocument.ocr_confidence)).\
            filter(MedicalDocument.ocr_processed == True).scalar()
        
        # Low confidence documents (< 70%)
        low_confidence_docs = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed == True,
            MedicalDocument.ocr_confidence < 0.7
        ).count()
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'pending_documents': pending_docs,
            'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'average_confidence': avg_confidence or 0.0,
            'low_confidence_count': low_confidence_docs
        }
