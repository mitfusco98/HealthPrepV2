"""
Enhanced Document Processor for EMR Integration
Processes Epic FHIR documents with OCR, keyword matching, and screening detection
"""

import os
import logging
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from PIL import Image
import pdf2image
import pytesseract

from models import db, FHIRDocument
from ocr.processor import OCRProcessor
from ocr.phi_filter import PHIFilter
from core.fuzzy_detection import FuzzyDetectionEngine

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Enhanced document processor for EMR integration
    Handles Epic FHIR documents with screening-specific processing
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.ocr_processor = OCRProcessor()
        self.phi_filter = PHIFilter()
        self.fuzzy_engine = FuzzyDetectionEngine()
        
        # Screening-specific document types
        self.screening_document_types = {
            'mammography': ['mammogram', 'mammography', 'breast imaging', 'tomosynthesis'],
            'colonoscopy': ['colonoscopy', 'sigmoidoscopy', 'colon', 'colorectal'],
            'cervical': ['pap smear', 'pap test', 'cervical', 'cytology'],
            'bone_density': ['dexa', 'dxa', 'bone density', 'osteoporosis'],
            'dermatology': ['skin', 'dermatology', 'mole', 'lesion', 'biopsy'],
            'prostate': ['prostate', 'psa', 'digital rectal'],
            'lung': ['chest ct', 'ldct', 'lung', 'thoracic'],
            'eye': ['eye exam', 'ophthalmology', 'vision', 'retinal'],
            'hearing': ['hearing', 'audiometry', 'audiology']
        }
        
        # Keywords that indicate screening completion
        self.completion_indicators = [
            'normal', 'negative', 'no evidence', 'unremarkable', 'within normal limits',
            'satisfactory', 'adequate', 'complete', 'findings', 'impression',
            'recommendation', 'follow-up', 'next screening'
        ]
    
    def process_document(self, document_content: bytes, document_title: str) -> Optional[str]:
        """
        Process document content and extract text with screening analysis
        
        Args:
            document_content: Binary document content
            document_title: Document title or filename
            
        Returns:
            Extracted and processed text or None if processing failed
        """
        try:
            self.logger.info(f"Processing document: {document_title}")
            
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_file_extension(document_title)) as temp_file:
                temp_file.write(document_content)
                temp_file_path = temp_file.name
            
            try:
                # Extract text using OCR
                extracted_text, confidence = self._extract_text_from_file(temp_file_path)
                
                if extracted_text:
                    # Apply PHI filtering
                    filtered_text = self.phi_filter.filter_phi(extracted_text)
                    
                    # Enhance text for screening detection
                    enhanced_text = self._enhance_text_for_screening(filtered_text, document_title)
                    
                    self.logger.info(f"Successfully processed document with {confidence:.2f} confidence")
                    return enhanced_text
                else:
                    self.logger.warning(f"No text extracted from document: {document_title}")
                    return None
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            self.logger.error(f"Error processing document {document_title}: {str(e)}")
            return None
    
    def analyze_document_for_screenings(self, document_text: str, document_title: str) -> Dict[str, Any]:
        """
        Analyze document text for screening-related content
        
        Args:
            document_text: Extracted document text
            document_title: Document title
            
        Returns:
            Dict with screening analysis results
        """
        try:
            analysis = {
                'screening_types': [],
                'completion_evidence': False,
                'confidence_scores': {},
                'keywords_found': [],
                'document_classification': 'unknown'
            }
            
            text_lower = f"{document_title} {document_text}".lower()
            
            # Check for screening types
            for screening_type, keywords in self.screening_document_types.items():
                max_confidence = 0.0
                found_keywords = []
                
                for keyword in keywords:
                    # Use fuzzy matching for keyword detection
                    confidence = self._calculate_keyword_confidence(keyword, text_lower)
                    
                    if confidence > 0.7:  # High confidence threshold
                        found_keywords.append(keyword)
                        max_confidence = max(max_confidence, confidence)
                
                if max_confidence > 0.7:
                    analysis['screening_types'].append(screening_type)
                    analysis['confidence_scores'][screening_type] = max_confidence
                    analysis['keywords_found'].extend(found_keywords)
            
            # Check for completion indicators
            analysis['completion_evidence'] = self._has_completion_evidence(text_lower)
            
            # Classify document type
            if analysis['screening_types']:
                analysis['document_classification'] = 'screening_report'
            elif any(term in text_lower for term in ['report', 'result', 'findings']):
                analysis['document_classification'] = 'medical_report'
            elif any(term in text_lower for term in ['note', 'visit', 'consultation']):
                analysis['document_classification'] = 'clinical_note'
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing document for screenings: {str(e)}")
            return {'screening_types': [], 'completion_evidence': False, 'confidence_scores': {}, 'keywords_found': [], 'document_classification': 'unknown'}
    
    def extract_screening_dates(self, document_text: str) -> List[Dict[str, Any]]:
        """
        Extract screening dates from document text
        
        Args:
            document_text: Document text to analyze
            
        Returns:
            List of extracted dates with context
        """
        import re
        from datetime import datetime
        
        dates_found = []
        
        # Common date patterns in medical documents
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # MM/DD/YYYY or MM-DD-YYYY
            r'\b(\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',  # DD Mon YYYY
            r'\b((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b',  # Mon DD, YYYY
        ]
        
        try:
            for pattern in date_patterns:
                matches = re.finditer(pattern, document_text, re.IGNORECASE)
                
                for match in matches:
                    date_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Get context around the date
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(document_text), end_pos + 50)
                    context = document_text[context_start:context_end]
                    
                    dates_found.append({
                        'date_string': date_str,
                        'context': context.strip(),
                        'position': start_pos
                    })
            
            return dates_found
            
        except Exception as e:
            self.logger.error(f"Error extracting screening dates: {str(e)}")
            return []
    
    def _extract_text_from_file(self, file_path: str) -> Tuple[Optional[str], float]:
        """
        Extract text from file using appropriate method
        
        Args:
            file_path: Path to document file
            
        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                return self._extract_from_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                return self._extract_from_image(file_path)
            elif file_ext in ['.txt']:
                # Plain text file
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read(), 1.0
            else:
                self.logger.warning(f"Unsupported file type: {file_ext}")
                return None, 0.0
                
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None, 0.0
    
    def _extract_from_pdf(self, pdf_path: str) -> Tuple[Optional[str], float]:
        """Extract text from PDF using OCR"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert PDF to images
                images = pdf2image.convert_from_path(pdf_path)
                
                all_text = []
                confidences = []
                
                for i, image in enumerate(images):
                    # Save image temporarily
                    image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(image_path, 'PNG')
                    
                    # Extract text from image
                    text, confidence = self._extract_from_image(image_path)
                    
                    if text:
                        all_text.append(text)
                        confidences.append(confidence)
                
                # Combine all text and calculate average confidence
                combined_text = '\n'.join(all_text) if all_text else None
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return combined_text, avg_confidence
                
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            return None, 0.0
    
    def _extract_from_image(self, image_path: str) -> Tuple[Optional[str], float]:
        """Extract text from image using Tesseract OCR"""
        try:
            # Load and preprocess image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Tesseract configuration optimized for medical documents
            config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,()[]{}:;/\\-+=%$@#!?"\' \n\t'
            
            # Extract text with confidence data
            ocr_data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            # Filter out low-confidence words and combine text
            extracted_text = []
            confidences = []
            
            for i in range(len(ocr_data['text'])):
                confidence = int(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()
                
                if confidence > 30 and text:  # Filter low-confidence text
                    extracted_text.append(text)
                    confidences.append(confidence)
            
            if extracted_text:
                combined_text = ' '.join(extracted_text)
                avg_confidence = sum(confidences) / len(confidences) / 100.0  # Convert to 0-1 scale
                return combined_text, avg_confidence
            else:
                return None, 0.0
                
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {str(e)}")
            return None, 0.0
    
    def _enhance_text_for_screening(self, text: str, document_title: str) -> str:
        """
        Enhance extracted text for better screening detection
        
        Args:
            text: Original extracted text
            document_title: Document title for context
            
        Returns:
            Enhanced text with normalized formatting
        """
        try:
            # Start with title for additional context
            enhanced = f"DOCUMENT: {document_title}\n\n{text}"
            
            # Normalize spacing and line breaks
            enhanced = ' '.join(enhanced.split())
            
            # Add section markers for common medical document sections
            section_markers = {
                'FINDINGS:': '\n\nFINDINGS:\n',
                'IMPRESSION:': '\n\nIMPRESSION:\n',
                'RECOMMENDATION:': '\n\nRECOMMENDATION:\n',
                'DIAGNOSIS:': '\n\nDIAGNOSIS:\n',
                'PROCEDURE:': '\n\nPROCEDURE:\n'
            }
            
            for marker, replacement in section_markers.items():
                enhanced = enhanced.replace(marker, replacement)
            
            return enhanced
            
        except Exception as e:
            self.logger.error(f"Error enhancing text: {str(e)}")
            return text
    
    def _calculate_keyword_confidence(self, keyword: str, text: str) -> float:
        """
        Calculate confidence score for keyword match in text
        
        Args:
            keyword: Keyword to search for
            text: Text to search in
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            # Direct exact match
            if keyword.lower() in text.lower():
                return 1.0
            
            # Use fuzzy matching for partial matches
            return self.fuzzy_engine.calculate_similarity(keyword.lower(), text.lower())
            
        except Exception as e:
            self.logger.error(f"Error calculating keyword confidence: {str(e)}")
            return 0.0
    
    def _has_completion_evidence(self, text: str) -> bool:
        """
        Check if text contains evidence of screening completion
        
        Args:
            text: Text to analyze
            
        Returns:
            True if completion evidence found
        """
        try:
            for indicator in self.completion_indicators:
                if indicator.lower() in text.lower():
                    return True
            
            # Check for specific completion phrases
            completion_phrases = [
                'screening complete',
                'examination complete',
                'study complete',
                'procedure completed',
                'results available',
                'no further action needed'
            ]
            
            for phrase in completion_phrases:
                if phrase.lower() in text.lower():
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking completion evidence: {str(e)}")
            return False
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        if not filename:
            return '.tmp'
        
        _, ext = os.path.splitext(filename)
        return ext if ext else '.tmp'
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get document processing statistics"""
        try:
            # This would return processing statistics
            # For now, return a placeholder
            return {
                'documents_processed': 0,
                'screening_documents_identified': 0,
                'average_confidence': 0.0,
                'processing_errors': 0
            }
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {str(e)}")
            return {}