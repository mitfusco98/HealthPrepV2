"""
OCR processing with Tesseract integration
Handles document text extraction with quality controls
"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Dict, Optional, Tuple
import pytesseract
from PIL import Image
import pdf2image
import io

from models import MedicalDocument, OCRProcessingStats
from app import db

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Handles OCR processing of medical documents"""
    
    def __init__(self):
        # Configure Tesseract for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?()[]{}/-+= \n'
        self.confidence_threshold = 60  # Minimum confidence for good quality
        
        # Medical terminology boost
        self.medical_terms = [
            'patient', 'diagnosis', 'treatment', 'medication', 'dosage', 'mg', 'ml',
            'blood pressure', 'heart rate', 'temperature', 'weight', 'height',
            'laboratory', 'results', 'normal', 'abnormal', 'positive', 'negative',
            'radiology', 'imaging', 'xray', 'ct scan', 'mri', 'ultrasound',
            'consultation', 'specialist', 'recommendation', 'follow up',
            'hospital', 'admission', 'discharge', 'emergency', 'surgery'
        ]
    
    def process_document(self, document: MedicalDocument, file_content: bytes = None) -> Dict[str, any]:
        """
        Process a document for OCR text extraction
        """
        try:
            start_time = datetime.now()
            
            # If no file content provided, skip OCR (for existing documents)
            if not file_content:
                logger.warning(f"No file content provided for document {document.id}")
                return {
                    'success': False,
                    'error': 'No file content provided',
                    'confidence': 0.0,
                    'processing_time': 0.0
                }
            
            # Extract text based on file type
            if document.filename and document.filename.lower().endswith('.pdf'):
                ocr_result = self._process_pdf(file_content)
            elif document.filename and any(document.filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']):
                ocr_result = self._process_image(file_content)
            else:
                logger.warning(f"Unsupported file type for document {document.id}: {document.filename}")
                return {
                    'success': False,
                    'error': 'Unsupported file type',
                    'confidence': 0.0,
                    'processing_time': 0.0
                }
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if ocr_result['success']:
                # Update document with OCR results
                document.ocr_text = ocr_result['text']
                document.ocr_confidence = ocr_result['confidence']
                document.processed_at = datetime.now()
                
                # Update processing statistics
                self._update_processing_stats(ocr_result['confidence'], processing_time, True)
                
                db.session.commit()
                
                logger.info(f"Successfully processed document {document.id} with {ocr_result['confidence']:.1f}% confidence")
                
                return {
                    'success': True,
                    'text': ocr_result['text'],
                    'confidence': ocr_result['confidence'],
                    'processing_time': processing_time
                }
            else:
                self._update_processing_stats(0.0, processing_time, False)
                return {
                    'success': False,
                    'error': ocr_result['error'],
                    'confidence': 0.0,
                    'processing_time': processing_time
                }
                
        except Exception as e:
            logger.error(f"Error processing document {document.id}: {str(e)}")
            self._update_processing_stats(0.0, 0.0, False)
            return {
                'success': False,
                'error': str(e),
                'confidence': 0.0,
                'processing_time': 0.0
            }
    
    def _process_pdf(self, pdf_content: bytes) -> Dict[str, any]:
        """Process PDF document for OCR"""
        try:
            # Convert PDF to images
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_content)
                temp_pdf.flush()
                
                # Convert PDF pages to images
                images = pdf2image.convert_from_path(
                    temp_pdf.name,
                    dpi=300,  # High DPI for better OCR
                    first_page=1,
                    last_page=10  # Limit to first 10 pages for performance
                )
                
                os.unlink(temp_pdf.name)  # Clean up temp file
            
            all_text = []
            total_confidence = 0
            page_count = 0
            
            # Process each page
            for i, image in enumerate(images):
                try:
                    # Run OCR on the image
                    ocr_data = pytesseract.image_to_data(
                        image, 
                        config=self.tesseract_config,
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Extract text and calculate confidence
                    page_text = []
                    confidences = []
                    
                    for j in range(len(ocr_data['text'])):
                        text = ocr_data['text'][j].strip()
                        conf = int(ocr_data['conf'][j])
                        
                        if text and conf > 0:
                            page_text.append(text)
                            confidences.append(conf)
                    
                    if page_text:
                        page_text_str = ' '.join(page_text)
                        all_text.append(page_text_str)
                        
                        # Calculate page confidence
                        if confidences:
                            page_confidence = sum(confidences) / len(confidences)
                            total_confidence += page_confidence
                            page_count += 1
                
                except Exception as e:
                    logger.warning(f"Error processing PDF page {i+1}: {str(e)}")
                    continue
            
            if not all_text:
                return {
                    'success': False,
                    'error': 'No text extracted from PDF',
                    'confidence': 0.0
                }
            
            # Combine all text and calculate overall confidence
            combined_text = '\n\n'.join(all_text)
            overall_confidence = total_confidence / page_count if page_count > 0 else 0
            
            # Boost confidence for medical terminology
            boosted_confidence = self._apply_medical_term_boost(combined_text, overall_confidence)
            
            return {
                'success': True,
                'text': combined_text,
                'confidence': boosted_confidence
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'confidence': 0.0
            }
    
    def _process_image(self, image_content: bytes) -> Dict[str, any]:
        """Process image document for OCR"""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Run OCR
            ocr_data = pytesseract.image_to_data(
                image,
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate confidence
            text_parts = []
            confidences = []
            
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                
                if text and conf > 0:
                    text_parts.append(text)
                    confidences.append(conf)
            
            if not text_parts:
                return {
                    'success': False,
                    'error': 'No text extracted from image',
                    'confidence': 0.0
                }
            
            # Combine text and calculate confidence
            combined_text = ' '.join(text_parts)
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Boost confidence for medical terminology
            boosted_confidence = self._apply_medical_term_boost(combined_text, overall_confidence)
            
            return {
                'success': True,
                'text': combined_text,
                'confidence': boosted_confidence
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'confidence': 0.0
            }
    
    def _apply_medical_term_boost(self, text: str, base_confidence: float) -> float:
        """Apply confidence boost for medical terminology"""
        text_lower = text.lower()
        medical_term_count = 0
        
        for term in self.medical_terms:
            if term in text_lower:
                medical_term_count += 1
        
        # Boost confidence based on medical term density
        if len(text.split()) > 0:
            term_density = medical_term_count / len(text.split())
            boost_factor = min(1.2, 1.0 + (term_density * 0.5))  # Max 20% boost
            return min(100.0, base_confidence * boost_factor)
        
        return base_confidence
    
    def _update_processing_stats(self, confidence: float, processing_time: float, success: bool):
        """Update OCR processing statistics"""
        try:
            stats = OCRProcessingStats.query.first()
            if not stats:
                stats = OCRProcessingStats()
                db.session.add(stats)
            
            if success:
                # Update document count and confidence
                old_count = stats.documents_processed
                old_avg_conf = stats.avg_confidence or 0
                
                stats.documents_processed = old_count + 1
                stats.avg_confidence = ((old_avg_conf * old_count) + confidence) / stats.documents_processed
                
                # Track low confidence documents
                if confidence < self.confidence_threshold:
                    stats.low_confidence_count += 1
                
                # Update processing time
                old_avg_time = stats.processing_time_avg or 0
                stats.processing_time_avg = ((old_avg_time * old_count) + processing_time) / stats.documents_processed
            
            stats.last_updated = datetime.now()
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating processing stats: {str(e)}")
    
    def get_processing_stats(self) -> Dict[str, any]:
        """Get current OCR processing statistics"""
        stats = OCRProcessingStats.query.first()
        if not stats:
            return {
                'documents_processed': 0,
                'avg_confidence': 0.0,
                'low_confidence_count': 0,
                'processing_time_avg': 0.0,
                'last_updated': None
            }
        
        return {
            'documents_processed': stats.documents_processed,
            'avg_confidence': round(stats.avg_confidence or 0, 1),
            'low_confidence_count': stats.low_confidence_count,
            'processing_time_avg': round(stats.processing_time_avg or 0, 2),
            'last_updated': stats.last_updated
        }
    
    def is_high_quality(self, confidence: float) -> bool:
        """Check if OCR result is high quality"""
        return confidence >= 80
    
    def is_low_quality(self, confidence: float) -> bool:
        """Check if OCR result is low quality"""
        return confidence < self.confidence_threshold
    
    def get_confidence_color_class(self, confidence: float) -> str:
        """Get CSS class for confidence-based coloring"""
        if confidence >= 80:
            return 'confidence-high'
        elif confidence >= 60:
            return 'confidence-medium'
        else:
            return 'confidence-low'
