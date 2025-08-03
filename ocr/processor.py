"""
Tesseract integration and text cleanup for medical documents
Handles OCR processing with confidence scoring
"""
import os
import logging
import tempfile
import pytesseract
from PIL import Image
import pdf2image
from datetime import datetime
from app import db
from models import Document
from .phi_filter import PHIFilter

logger = logging.getLogger(__name__)

# Configure Tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

class OCRProcessor:
    """Handles OCR processing of medical documents"""
    
    def __init__(self):
        self.phi_filter = PHIFilter()
        
        # Medical-optimized Tesseract configuration
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:()/-+[]{}@#$%^&*=_|\\<>?!" "'
        
    def process_document(self, document_id):
        """Process a document for OCR text extraction"""
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return False
        
        if document.ocr_processed:
            logger.info(f"Document {document_id} already processed")
            return True
        
        try:
            # Extract text from document
            ocr_text, confidence = self.extract_text_from_file(document.file_path)
            
            if ocr_text:
                # Apply PHI filtering if enabled
                filtered_text = self.phi_filter.filter_text(ocr_text)
                
                # Update document with OCR results
                document.ocr_text = filtered_text
                document.ocr_confidence = confidence
                document.ocr_processed = True
                document.phi_filtered = self.phi_filter.is_enabled()
                
                db.session.commit()
                
                logger.info(f"Successfully processed document {document_id} with confidence {confidence:.2f}")
                return True
            else:
                logger.warning(f"No text extracted from document {document_id}")
                document.ocr_processed = True
                document.ocr_confidence = 0.0
                db.session.commit()
                return False
                
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            return False
    
    def extract_text_from_file(self, file_path):
        """Extract text from various file types"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            return self.extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using OCR"""
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path, dpi=300)
            
            all_text = []
            total_confidence = 0
            page_count = 0
            
            for page_num, image in enumerate(images):
                page_text, page_confidence = self.extract_text_from_image_object(image)
                
                if page_text.strip():
                    all_text.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    total_confidence += page_confidence
                    page_count += 1
            
            combined_text = '\n\n'.join(all_text)
            average_confidence = total_confidence / page_count if page_count > 0 else 0
            
            return combined_text, average_confidence
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return None, 0
    
    def extract_text_from_image(self, image_path):
        """Extract text from image file"""
        try:
            image = Image.open(image_path)
            return self.extract_text_from_image_object(image)
            
        except Exception as e:
            logger.error(f"Error extracting text from image {image_path}: {e}")
            return None, 0
    
    def extract_text_from_image_object(self, image):
        """Extract text from PIL Image object"""
        try:
            # Get OCR data with confidence scores
            ocr_data = pytesseract.image_to_data(
                image, 
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate confidence
            words = []
            confidences = []
            
            for i, conf in enumerate(ocr_data['conf']):
                if int(conf) > 0:  # Only include words with confidence > 0
                    word = ocr_data['text'][i].strip()
                    if word:
                        words.append(word)
                        confidences.append(int(conf))
            
            text = ' '.join(words)
            average_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Normalize confidence to 0-1 scale
            normalized_confidence = average_confidence / 100.0
            
            return text, normalized_confidence
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {e}")
            return None, 0
    
    def process_batch(self, document_ids):
        """Process multiple documents in batch"""
        results = {
            'processed': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for doc_id in document_ids:
            try:
                success = self.process_document(doc_id)
                if success:
                    results['processed'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                logger.error(f"Error in batch processing document {doc_id}: {e}")
                results['failed'] += 1
        
        return results
    
    def get_processing_stats(self):
        """Get OCR processing statistics"""
        total_docs = Document.query.count()
        processed_docs = Document.query.filter_by(ocr_processed=True).count()
        pending_docs = Document.query.filter_by(ocr_processed=False).count()
        
        # Confidence distribution
        high_confidence = Document.query.filter(Document.ocr_confidence >= 0.8).count()
        medium_confidence = Document.query.filter(
            Document.ocr_confidence >= 0.6,
            Document.ocr_confidence < 0.8
        ).count()
        low_confidence = Document.query.filter(
            Document.ocr_confidence > 0,
            Document.ocr_confidence < 0.6
        ).count()
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'pending_documents': pending_docs,
            'success_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'confidence_distribution': {
                'high': high_confidence,
                'medium': medium_confidence,
                'low': low_confidence
            }
        }
    
    def reprocess_low_confidence_documents(self, confidence_threshold=0.6):
        """Reprocess documents with low confidence scores"""
        low_confidence_docs = Document.query.filter(
            Document.ocr_confidence < confidence_threshold,
            Document.ocr_processed == True
        ).all()
        
        reprocessed_count = 0
        
        for doc in low_confidence_docs:
            try:
                # Mark as unprocessed to force reprocessing
                doc.ocr_processed = False
                db.session.commit()
                
                # Reprocess
                if self.process_document(doc.id):
                    reprocessed_count += 1
                    
            except Exception as e:
                logger.error(f"Error reprocessing document {doc.id}: {e}")
        
        return reprocessed_count
