"""
OCR processing with Tesseract integration for medical document text extraction.
Includes quality scoring, confidence assessment, and automated processing.
"""

import os
import logging
import tempfile
import subprocess
from typing import Dict, Optional, Tuple, List
from datetime import datetime
import pytesseract
from PIL import Image
import pdf2image
import io

from app import db
from models import MedicalDocument

class OCRProcessor:
    """Handles OCR processing for medical documents with quality assessment."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configure Tesseract path from environment or default
        tesseract_path = os.getenv('TESSERACT_PATH', '/usr/bin/tesseract')
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # OCR configuration optimized for medical documents
        self.tesseract_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()-/:%'
        
        # Quality thresholds
        self.high_confidence_threshold = 80.0
        self.medium_confidence_threshold = 60.0
        self.low_confidence_threshold = 40.0
        
        # Processing statistics
        self.processing_stats = {
            'total_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'high_confidence_count': 0,
            'medium_confidence_count': 0,
            'low_confidence_count': 0,
            'average_confidence': 0.0,
            'last_processed': None
        }
    
    def process_document(self, document: MedicalDocument, file_content: bytes) -> Dict[str, any]:
        """Process a document and extract text with OCR."""
        
        try:
            self.logger.info(f"Starting OCR processing for document {document.id}")
            
            # Determine file type and convert to image if needed
            images = self._prepare_images_from_content(file_content, document.filename)
            
            if not images:
                return self._create_error_result("Unable to convert document to processable format")
            
            # Process each page/image
            extracted_text = ""
            total_confidence = 0.0
            confidence_scores = []
            
            for i, image in enumerate(images):
                try:
                    # Extract text with confidence data
                    text, confidence = self._extract_text_with_confidence(image)
                    
                    if text.strip():
                        extracted_text += f"\n--- Page {i+1} ---\n{text}\n"
                        confidence_scores.append(confidence)
                        total_confidence += confidence
                    
                except Exception as e:
                    self.logger.warning(f"Error processing page {i+1} of document {document.id}: {e}")
                    continue
            
            # Calculate overall confidence
            overall_confidence = total_confidence / len(confidence_scores) if confidence_scores else 0.0
            
            # Apply PHI filtering if enabled
            from .phi_filter import PHIFilter
            phi_filter = PHIFilter()
            
            if phi_filter.is_filtering_enabled():
                filtered_text = phi_filter.filter_text(extracted_text)
                document.has_phi_filtered = True
            else:
                filtered_text = extracted_text
                document.has_phi_filtered = False
            
            # Update document with extracted content
            document.content = filtered_text
            document.confidence_score = overall_confidence / 100.0  # Store as 0-1 range
            
            # Update processing statistics
            self._update_processing_stats(overall_confidence, True)
            
            db.session.commit()
            
            result = {
                'success': True,
                'extracted_text': filtered_text,
                'confidence_score': overall_confidence,
                'page_count': len(images),
                'character_count': len(filtered_text),
                'quality_assessment': self._assess_quality(overall_confidence),
                'phi_filtered': document.has_phi_filtered,
                'processing_time': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Successfully processed document {document.id} with {overall_confidence:.1f}% confidence")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing document {document.id}: {e}")
            self._update_processing_stats(0.0, False)
            return self._create_error_result(f"OCR processing failed: {str(e)}")
    
    def _prepare_images_from_content(self, file_content: bytes, filename: str) -> List[Image.Image]:
        """Convert file content to processable images."""
        
        images = []
        file_extension = os.path.splitext(filename.lower())[1]
        
        try:
            if file_extension == '.pdf':
                # Convert PDF to images
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_file.write(file_content)
                    temp_file.flush()
                    
                    # Convert PDF pages to images
                    pdf_images = pdf2image.convert_from_path(
                        temp_file.name,
                        dpi=300,  # High DPI for better OCR accuracy
                        fmt='jpeg'
                    )
                    images.extend(pdf_images)
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
            
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                # Direct image processing
                image = Image.open(io.BytesIO(file_content))
                images.append(image)
            
            else:
                self.logger.warning(f"Unsupported file format: {file_extension}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error preparing images from {filename}: {e}")
            return []
        
        return images
    
    def _extract_text_with_confidence(self, image: Image.Image) -> Tuple[str, float]:
        """Extract text from image with confidence scoring."""
        
        try:
            # Preprocess image for better OCR results
            processed_image = self._preprocess_image(image)
            
            # Extract text
            text = pytesseract.image_to_string(processed_image, config=self.tesseract_config)
            
            # Get confidence data
            confidence_data = pytesseract.image_to_data(
                processed_image, 
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate weighted confidence score
            confidence_score = self._calculate_confidence_score(confidence_data)
            
            return text, confidence_score
            
        except Exception as e:
            self.logger.error(f"Error extracting text from image: {e}")
            return "", 0.0
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for optimal OCR results."""
        
        try:
            # Convert to grayscale if not already
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast and sharpness for medical documents
            from PIL import ImageEnhance, ImageFilter
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Sharpen image
            image = image.filter(ImageFilter.SHARPEN)
            
            # Resize if too small (improves OCR accuracy)
            width, height = image.size
            if width < 1000 or height < 1000:
                scale_factor = max(1000 / width, 1000 / height)
                new_size = (int(width * scale_factor), int(height * scale_factor))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            self.logger.warning(f"Error preprocessing image: {e}")
            return image  # Return original if preprocessing fails
    
    def _calculate_confidence_score(self, confidence_data: Dict) -> float:
        """Calculate weighted confidence score from Tesseract output."""
        
        try:
            confidences = confidence_data['conf']
            texts = confidence_data['text']
            
            # Filter out empty/invalid confidence scores
            valid_confidences = []
            total_chars = 0
            
            for i, (conf, text) in enumerate(zip(confidences, texts)):
                if conf > 0 and text.strip():  # Valid confidence and non-empty text
                    char_count = len(text.strip())
                    valid_confidences.extend([conf] * char_count)  # Weight by character count
                    total_chars += char_count
            
            if not valid_confidences:
                return 0.0
            
            # Calculate weighted average
            weighted_confidence = sum(valid_confidences) / len(valid_confidences)
            
            return min(weighted_confidence, 100.0)  # Cap at 100%
            
        except Exception as e:
            self.logger.warning(f"Error calculating confidence score: {e}")
            return 50.0  # Default moderate confidence
    
    def _assess_quality(self, confidence_score: float) -> str:
        """Assess OCR quality based on confidence score."""
        
        if confidence_score >= self.high_confidence_threshold:
            return "High"
        elif confidence_score >= self.medium_confidence_threshold:
            return "Medium"
        elif confidence_score >= self.low_confidence_threshold:
            return "Low"
        else:
            return "Very Low"
    
    def _update_processing_stats(self, confidence_score: float, success: bool):
        """Update processing statistics."""
        
        self.processing_stats['total_processed'] += 1
        self.processing_stats['last_processed'] = datetime.utcnow()
        
        if success:
            self.processing_stats['successful_extractions'] += 1
            
            # Update confidence counters
            if confidence_score >= self.high_confidence_threshold:
                self.processing_stats['high_confidence_count'] += 1
            elif confidence_score >= self.medium_confidence_threshold:
                self.processing_stats['medium_confidence_count'] += 1
            else:
                self.processing_stats['low_confidence_count'] += 1
            
            # Update average confidence
            total_successful = self.processing_stats['successful_extractions']
            current_avg = self.processing_stats['average_confidence']
            self.processing_stats['average_confidence'] = (
                (current_avg * (total_successful - 1) + confidence_score) / total_successful
            )
        else:
            self.processing_stats['failed_extractions'] += 1
    
    def _create_error_result(self, error_message: str) -> Dict[str, any]:
        """Create standardized error result."""
        
        return {
            'success': False,
            'error': error_message,
            'extracted_text': "",
            'confidence_score': 0.0,
            'page_count': 0,
            'character_count': 0,
            'quality_assessment': "Failed",
            'phi_filtered': False,
            'processing_time': datetime.utcnow().isoformat()
        }
    
    def get_processing_stats(self) -> Dict[str, any]:
        """Get current processing statistics."""
        
        return {
            **self.processing_stats,
            'success_rate': (
                self.processing_stats['successful_extractions'] / 
                max(self.processing_stats['total_processed'], 1) * 100
            ),
            'confidence_distribution': {
                'high': self.processing_stats['high_confidence_count'],
                'medium': self.processing_stats['medium_confidence_count'],
                'low': self.processing_stats['low_confidence_count']
            }
        }
    
    def test_ocr_capability(self) -> Dict[str, any]:
        """Test OCR system capabilities and configuration."""
        
        try:
            # Test Tesseract installation
            version = pytesseract.get_tesseract_version()
            
            # Test with a simple image
            test_image = Image.new('L', (200, 50), color=255)
            from PIL import ImageDraw, ImageFont
            
            draw = ImageDraw.Draw(test_image)
            draw.text((10, 10), "Test OCR 123", fill=0)
            
            test_text = pytesseract.image_to_string(test_image, config=self.tesseract_config)
            
            return {
                'success': True,
                'tesseract_version': str(version),
                'test_extraction': test_text.strip(),
                'configuration': self.tesseract_config,
                'supported_formats': ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']
            }
            
        except Exception as e:
            self.logger.error(f"OCR capability test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'tesseract_version': None,
                'test_extraction': None
            }
