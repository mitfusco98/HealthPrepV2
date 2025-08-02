"""
Tesseract integration and text cleanup for medical document OCR
"""
import pytesseract
from PIL import Image
import pdf2image
import logging
import os
import tempfile
from typing import Tuple, Optional

class OCRProcessor:
    
    def __init__(self):
        # Configure Tesseract for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:-/() '
        
        # Medical document specific settings
        self.medical_config = '--oem 3 --psm 4'  # Assume single column of text
        
    def process_document(self, file_path: str) -> Tuple[str, float]:
        """Process document with OCR and return text and confidence score"""
        try:
            if file_path.lower().endswith('.pdf'):
                return self._process_pdf(file_path)
            else:
                return self._process_image(file_path)
        except Exception as e:
            logging.error(f"Error processing document {file_path}: {e}")
            return "", 0.0
    
    def _process_pdf(self, pdf_path: str) -> Tuple[str, float]:
        """Process PDF document with OCR"""
        try:
            # Convert PDF pages to images
            pages = pdf2image.convert_from_path(pdf_path, dpi=300)
            
            all_text = []
            all_confidences = []
            
            for page_num, page in enumerate(pages):
                # Save page as temporary image
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    page.save(temp_file.name, 'PNG')
                    
                    # Process page with OCR
                    text, confidence = self._process_image(temp_file.name)
                    all_text.append(text)
                    all_confidences.append(confidence)
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
            
            # Combine results
            combined_text = '\n\n'.join(filter(None, all_text))
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            return combined_text, avg_confidence
            
        except Exception as e:
            logging.error(f"Error processing PDF {pdf_path}: {e}")
            return "", 0.0
    
    def _process_image(self, image_path: str) -> Tuple[str, float]:
        """Process image with OCR"""
        try:
            # Open and preprocess image
            image = Image.open(image_path)
            image = self._preprocess_image(image)
            
            # Perform OCR with confidence data
            ocr_data = pytesseract.image_to_data(image, config=self.medical_config, output_type=pytesseract.Output.DICT)
            
            # Extract text and calculate confidence
            text = self._extract_text_from_ocr_data(ocr_data)
            confidence = self._calculate_confidence(ocr_data)
            
            # Clean up text for medical documents
            cleaned_text = self._clean_medical_text(text)
            
            return cleaned_text, confidence
            
        except Exception as e:
            logging.error(f"Error processing image {image_path}: {e}")
            return "", 0.0
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results"""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast for medical documents
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Scale up small images
            width, height = image.size
            if width < 1000 or height < 1000:
                scale_factor = max(1000 / width, 1000 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logging.error(f"Error preprocessing image: {e}")
            return image
    
    def _extract_text_from_ocr_data(self, ocr_data: dict) -> str:
        """Extract text from Tesseract OCR data"""
        text_parts = []
        
        for i, word in enumerate(ocr_data['text']):
            confidence = int(ocr_data['conf'][i])
            
            # Only include words with reasonable confidence
            if confidence > 30 and word.strip():
                text_parts.append(word)
        
        return ' '.join(text_parts)
    
    def _calculate_confidence(self, ocr_data: dict) -> float:
        """Calculate overall confidence score from OCR data"""
        confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
        
        if not confidences:
            return 0.0
        
        # Calculate weighted average confidence
        return sum(confidences) / len(confidences) / 100.0
    
    def _clean_medical_text(self, text: str) -> str:
        """Clean and normalize text for medical documents"""
        if not text:
            return ""
        
        # Common OCR error corrections for medical terms
        corrections = {
            'B|ood': 'Blood',
            'G|ucose': 'Glucose',
            'Co|esterol': 'Cholesterol',
            'Hemog|obin': 'Hemoglobin',
            'Mammograrr': 'Mammogram',
            'Co|onoscopy': 'Colonoscopy',
            'Mammograpky': 'Mammography',
            'Radiograph': 'Radiography',
            'U|trasound': 'Ultrasound',
            'Computerized': 'Computed',
            'Tomograph': 'Tomography',
        }
        
        cleaned_text = text
        for error, correction in corrections.items():
            cleaned_text = cleaned_text.replace(error, correction)
        
        # Remove excessive whitespace
        import re
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Remove non-printable characters but keep medical symbols
        cleaned_text = ''.join(char for char in cleaned_text 
                              if char.isprintable() or char in ['\n', '\t'])
        
        return cleaned_text
    
    def get_text_blocks(self, file_path: str) -> list:
        """Get text organized by blocks/regions for better parsing"""
        try:
            if file_path.lower().endswith('.pdf'):
                pages = pdf2image.convert_from_path(file_path, dpi=300)
                image = pages[0] if pages else None
            else:
                image = Image.open(file_path)
            
            if not image:
                return []
            
            image = self._preprocess_image(image)
            
            # Get block-level OCR data
            ocr_data = pytesseract.image_to_data(image, config=self.medical_config, output_type=pytesseract.Output.DICT)
            
            # Group text by blocks
            blocks = {}
            for i, text in enumerate(ocr_data['text']):
                if not text.strip():
                    continue
                
                block_num = ocr_data['block_num'][i]
                if block_num not in blocks:
                    blocks[block_num] = []
                
                blocks[block_num].append(text)
            
            # Convert to list of text blocks
            text_blocks = []
            for block_num in sorted(blocks.keys()):
                block_text = ' '.join(blocks[block_num])
                if block_text.strip():
                    text_blocks.append(self._clean_medical_text(block_text))
            
            return text_blocks
            
        except Exception as e:
            logging.error(f"Error extracting text blocks from {file_path}: {e}")
            return []
