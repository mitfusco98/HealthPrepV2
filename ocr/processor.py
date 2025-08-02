"""
OCR processing with Tesseract integration and quality assessment
"""
import os
import logging
import tempfile
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Handles OCR processing with medical document optimization"""
    
    def __init__(self):
        # Configure Tesseract for medical documents
        self.tesseract_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,/:-()[]{}!@#$%^&*+=<>?;"\' '
        self.confidence_threshold = 60.0
    
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document with OCR and return text with confidence metrics
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return {
                    'success': False,
                    'error': 'File not found',
                    'text': '',
                    'confidence': 0.0,
                    'word_count': 0,
                    'processing_time': 0.0
                }
            
            logger.info(f"Processing OCR for file: {file_path}")
            import time
            start_time = time.time()
            
            # Load and preprocess image
            image = self._load_and_preprocess_image(file_path)
            if image is None:
                return {
                    'success': False,
                    'error': 'Could not load image',
                    'text': '',
                    'confidence': 0.0,
                    'word_count': 0,
                    'processing_time': 0.0
                }
            
            # Perform OCR with detailed data
            ocr_data = pytesseract.image_to_data(image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)
            
            # Extract text and calculate confidence
            text, confidence = self._extract_text_and_confidence(ocr_data)
            
            processing_time = time.time() - start_time
            word_count = len(text.split()) if text else 0
            
            # Quality assessment
            quality_score = self._assess_quality(text, confidence, word_count)
            
            result = {
                'success': True,
                'text': text,
                'confidence': confidence,
                'word_count': word_count,
                'processing_time': processing_time,
                'quality_score': quality_score,
                'needs_review': confidence < self.confidence_threshold
            }
            
            logger.info(f"OCR completed - Confidence: {confidence:.1f}%, Words: {word_count}, Time: {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error processing OCR for {file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0,
                'word_count': 0,
                'processing_time': 0.0
            }
    
    def _load_and_preprocess_image(self, file_path: str) -> Optional[np.ndarray]:
        """Load and preprocess image for better OCR results"""
        try:
            # Handle different file types
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                # Convert PDF to image (first page)
                image = self._pdf_to_image(file_path)
            else:
                # Load image directly
                image = cv2.imread(file_path)
                
            if image is None:
                return None
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Apply preprocessing techniques for medical documents
            processed = self._preprocess_medical_document(gray)
            
            return processed
            
        except Exception as e:
            logger.error(f"Error preprocessing image {file_path}: {str(e)}")
            return None
    
    def _pdf_to_image(self, pdf_path: str) -> Optional[np.ndarray]:
        """Convert PDF to image for OCR processing"""
        try:
            import fitz  # PyMuPDF
            
            # Open PDF
            doc = fitz.open(pdf_path)
            
            # Get first page
            page = doc[0]
            
            # Render page to image
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array
            img_data = pix.tobytes("ppm")
            
            # Save to temporary file and load with OpenCV
            with tempfile.NamedTemporaryFile(suffix='.ppm', delete=False) as temp_file:
                temp_file.write(img_data)
                temp_path = temp_file.name
            
            image = cv2.imread(temp_path)
            os.unlink(temp_path)  # Clean up temp file
            
            doc.close()
            return image
            
        except ImportError:
            logger.warning("PyMuPDF not available - PDF processing disabled")
            return None
        except Exception as e:
            logger.error(f"Error converting PDF to image: {str(e)}")
            return None
    
    def _preprocess_medical_document(self, image: np.ndarray) -> np.ndarray:
        """Apply preprocessing specific to medical documents"""
        try:
            # Noise reduction
            denoised = cv2.medianBlur(image, 3)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Binarization with adaptive threshold
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Morphological operations to clean up
            kernel = np.ones((1, 1), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error in medical document preprocessing: {str(e)}")
            return image
    
    def _extract_text_and_confidence(self, ocr_data: Dict) -> Tuple[str, float]:
        """Extract text and calculate average confidence from OCR data"""
        try:
            words = []
            confidences = []
            
            for i in range(len(ocr_data['text'])):
                word = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                
                # Only include words with reasonable confidence
                if word and conf > 0:
                    words.append(word)
                    confidences.append(conf)
            
            # Combine words into text
            text = ' '.join(words)
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return text, avg_confidence
            
        except Exception as e:
            logger.error(f"Error extracting text and confidence: {str(e)}")
            return '', 0.0
    
    def _assess_quality(self, text: str, confidence: float, word_count: int) -> float:
        """Assess overall quality of OCR result"""
        try:
            quality_factors = []
            
            # Confidence factor (0-1)
            confidence_factor = min(confidence / 100.0, 1.0)
            quality_factors.append(confidence_factor * 0.4)
            
            # Word count factor (more words generally better)
            word_factor = min(word_count / 100.0, 1.0)  # Normalize to 100 words
            quality_factors.append(word_factor * 0.2)
            
            # Text coherence factor (basic check)
            coherence_factor = self._assess_text_coherence(text)
            quality_factors.append(coherence_factor * 0.4)
            
            return sum(quality_factors)
            
        except Exception as e:
            logger.error(f"Error assessing quality: {str(e)}")
            return 0.0
    
    def _assess_text_coherence(self, text: str) -> float:
        """Basic assessment of text coherence"""
        if not text:
            return 0.0
        
        try:
            # Check for reasonable character distribution
            alpha_count = sum(c.isalpha() for c in text)
            digit_count = sum(c.isdigit() for c in text)
            space_count = sum(c.isspace() for c in text)
            total_chars = len(text)
            
            if total_chars == 0:
                return 0.0
            
            # Medical documents should have mostly alphabetic characters
            alpha_ratio = alpha_count / total_chars
            space_ratio = space_count / total_chars
            
            # Reasonable ratios for medical documents
            if alpha_ratio > 0.6 and space_ratio > 0.1 and space_ratio < 0.3:
                return 0.8
            elif alpha_ratio > 0.4:
                return 0.6
            else:
                return 0.3
                
        except Exception as e:
            logger.error(f"Error assessing text coherence: {str(e)}")
            return 0.0
    
    def process_batch(self, file_paths: list) -> Dict[str, Dict[str, Any]]:
        """Process multiple documents in batch"""
        results = {}
        
        for file_path in file_paths:
            try:
                result = self.process_document(file_path)
                results[file_path] = result
            except Exception as e:
                logger.error(f"Error processing {file_path} in batch: {str(e)}")
                results[file_path] = {
                    'success': False,
                    'error': str(e),
                    'text': '',
                    'confidence': 0.0
                }
        
        return results
    
    def get_processing_stats(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate processing statistics from batch results"""
        if not results:
            return {
                'total_documents': 0,
                'successful': 0,
                'failed': 0,
                'avg_confidence': 0.0,
                'avg_word_count': 0.0,
                'total_processing_time': 0.0
            }
        
        successful = [r for r in results.values() if r.get('success', False)]
        failed = [r for r in results.values() if not r.get('success', False)]
        
        avg_confidence = sum(r.get('confidence', 0) for r in successful) / len(successful) if successful else 0.0
        avg_word_count = sum(r.get('word_count', 0) for r in successful) / len(successful) if successful else 0.0
        total_processing_time = sum(r.get('processing_time', 0) for r in results.values())
        
        return {
            'total_documents': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(results) * 100 if results else 0.0,
            'avg_confidence': avg_confidence,
            'avg_word_count': avg_word_count,
            'total_processing_time': total_processing_time
        }

# Global OCR processor instance
ocr_processor = OCRProcessor()
