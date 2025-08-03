import logging
import os
import time
from datetime import datetime
from models import Document, OCRProcessingStats
from app import db

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Handles OCR processing using Tesseract"""

    def __init__(self):
        self.ocr_engine = 'tesseract'

    def process_document(self, document_id, file_path):
        """Process a single document with OCR"""
        try:
            start_time = time.time()

            # Get document record
            document = Document.query.get(document_id)
            if not document:
                return {'success': False, 'error': 'Document not found'}

            # Check if file exists
            if not os.path.exists(file_path):
                return {'success': False, 'error': 'File not found'}

            # Simulate OCR processing (replace with actual Tesseract integration)
            extracted_text = f"Sample OCR text for document {document.filename}"
            confidence = 0.85

            # Update document with OCR results
            document.ocr_text = extracted_text
            document.ocr_confidence = confidence
            document.ocr_processed = True

            # Create processing stats
            processing_time = time.time() - start_time
            stats = OCRProcessingStats(
                document_id=document_id,
                processing_time=processing_time,
                confidence_score=confidence,
                pages_processed=1,
                characters_extracted=len(extracted_text),
                ocr_engine=self.ocr_engine
            )

            db.session.add(stats)
            db.session.commit()

            logger.info(f"OCR processing completed for document {document_id}")

            return {
                'success': True,
                'confidence': confidence,
                'text_length': len(extracted_text),
                'processing_time': processing_time
            }

        except Exception as e:
            logger.error(f"OCR processing failed for document {document_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def batch_process_documents(self, document_ids):
        """Process multiple documents with OCR"""
        results = {
            'success': True,
            'processed': 0,
            'failed': 0,
            'errors': []
        }

        for doc_id in document_ids:
            try:
                document = Document.query.get(doc_id)
                if not document:
                    results['errors'].append(f"Document {doc_id} not found")
                    results['failed'] += 1
                    continue

                result = self.process_document(doc_id, document.file_path)

                if result['success']:
                    results['processed'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Document {doc_id}: {result.get('error')}")

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Document {doc_id}: {str(e)}")

        return results