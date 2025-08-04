import os
import subprocess
import tempfile
import logging
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

class OCRProcessor:
    """Handles OCR processing of medical documents using Tesseract"""
    
    def __init__(self):
        # Configure Tesseract for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:!?()[]{}"-/ '
        self.supported_formats = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
        
    def process_document(self, document):
        """Process document with OCR and return text and confidence"""
        try:
            file_path = document.file_path
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Document file not found: {file_path}")
            
            # Get file extension
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            if ext not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {ext}")
            
            # Process based on file type
            if ext == '.pdf':
                return self._process_pdf(file_path)
            else:
                return self._process_image(file_path)
                
        except Exception as e:
            logging.error(f"OCR processing failed for document {document.id}: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _process_pdf(self, file_path):
        """Process PDF document"""
        try:
            # Convert PDF to images
            images = convert_from_path(file_path, dpi=300)
            
            all_text = []
            confidences = []
            
            for i, image in enumerate(images):
                # Save image to temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    image.save(tmp_file.name, 'PNG')
                    
                    # Process with OCR
                    result = self._extract_text_with_confidence(tmp_file.name)
                    all_text.append(result['text'])
                    confidences.append(result['confidence'])
                    
                    # Clean up temp file
                    os.unlink(tmp_file.name)
            
            # Combine results
            combined_text = '\n\n'.join(all_text)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'text': combined_text,
                'confidence': avg_confidence
            }
            
        except Exception as e:
            logging.error(f"PDF processing failed: {str(e)}")
            raise
    
    def _process_image(self, file_path):
        """Process image document"""
        try:
            return self._extract_text_with_confidence(file_path)
        except Exception as e:
            logging.error(f"Image processing failed: {str(e)}")
            raise
    
    def _extract_text_with_confidence(self, image_path):
        """Extract text and calculate confidence from image"""
        try:
            # Open and preprocess image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance image for better OCR
            image = self._enhance_image(image)
            
            # Extract text
            text = pytesseract.image_to_string(image, config=self.tesseract_config)
            
            # Get confidence data
            confidence_data = pytesseract.image_to_data(image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence
            confidences = [int(conf) for conf in confidence_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            
            return {
                'text': text.strip(),
                'confidence': avg_confidence
            }
            
        except Exception as e:
            logging.error(f"Text extraction failed: {str(e)}")
            raise
    
    def _enhance_image(self, image):
        """Enhance image for better OCR results"""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Resize if too small (minimum 300 DPI equivalent)
            width, height = image.size
            if width < 1200 or height < 1600:
                scale_factor = max(1200/width, 1600/height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logging.error(f"Image enhancement failed: {str(e)}")
            return image
    
    def get_processing_stats(self):
        """Get OCR processing statistics"""
        from models import MedicalDocument
        
        total_docs = MedicalDocument.query.count()
        processed_docs = MedicalDocument.query.filter(MedicalDocument.ocr_text.isnot(None)).count()
        
        high_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence >= 0.8).count()
        medium_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_confidence >= 0.6,
            MedicalDocument.ocr_confidence < 0.8
        ).count()
        low_confidence = MedicalDocument.query.filter(MedicalDocument.ocr_confidence < 0.6).count()
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'pending_processing': total_docs - processed_docs,
            'high_confidence_docs': high_confidence,
            'medium_confidence_docs': medium_confidence,
            'low_confidence_docs': low_confidence,
            'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0
        }
    
    def is_tesseract_available(self):
        """Check if Tesseract is available"""
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
