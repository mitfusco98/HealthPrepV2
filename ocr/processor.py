"""
Tesseract integration and text cleanup for medical documents
Supports PDF, images, Word documents (.docx, .doc), and plain text
"""
import os
import subprocess
import tempfile
from PIL import Image
import pdf2image
from app import db
from models import Document
from .phi_filter import PHIFilter
import logging
from datetime import datetime

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

class OCRProcessor:
    """Handles OCR processing of medical documents using Tesseract"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.phi_filter = PHIFilter()

        # Tesseract configuration for medical documents
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,()[]{}:;/\\-+=%$@#!?"\' \n\t'

    def process_document(self, document_id):
        """Process a document with OCR and PHI filtering"""
        document = Document.query.get(document_id)
        if not document:
            self.logger.error(f"Document {document_id} not found")
            return False

        try:
            # Extract text using OCR
            ocr_text, confidence = self._extract_text(document.file_path)

            if ocr_text:
                # Apply PHI filtering if enabled
                filtered_text = self.phi_filter.filter_phi(ocr_text)

                # Update document record
                document.ocr_text = filtered_text
                document.content = filtered_text  # Also update content field for backward compatibility
                document.ocr_confidence = confidence
                document.phi_filtered = True
                document.processed_at = datetime.utcnow()

                db.session.commit()

                self.logger.info(f"Successfully processed document {document_id} with confidence {confidence:.2f}")

                # Trigger screening engine update
                from core.engine import ScreeningEngine
                engine = ScreeningEngine()
                engine.process_new_document(document_id)

                return True
            else:
                self.logger.warning(f"No text extracted from document {document_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {str(e)}")
            return False

    def _extract_text(self, file_path):
        """Extract text from document using appropriate method"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == '.pdf':
                return self._process_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                return self._process_image(file_path)
            elif file_ext == '.docx':
                return self._process_docx(file_path)
            elif file_ext == '.doc':
                return self._process_doc(file_path)
            elif file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(), 1.0
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")

        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None, 0.0

    def _process_pdf(self, pdf_path):
        """Process PDF document and extract text"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Convert PDF to images
                images = pdf2image.convert_from_path(pdf_path)

                all_text = []
                confidences = []

                for i, image in enumerate(images):
                    # Save image temporarily
                    image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(image_path, 'PNG')

                    # Extract text from image
                    text, confidence = self._process_image(image_path)

                    if text:
                        all_text.append(text)
                        confidences.append(confidence)

                # Combine all text and calculate average confidence
                combined_text = '\n'.join(all_text)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                return combined_text, avg_confidence

            except Exception as e:
                self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
                return None, 0.0

    def _process_image(self, image_path):
        """Process image and extract text using Tesseract"""
        try:
            # Preprocess image for better OCR results
            processed_image_path = self._preprocess_image(image_path)

            # Run Tesseract OCR
            cmd = [
                'tesseract',
                processed_image_path,
                'stdout',
                '--oem', '3',
                '--psm', '6'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                text = result.stdout.strip()

                # Get confidence score
                confidence = self._calculate_confidence(processed_image_path)

                return text, confidence
            else:
                self.logger.error(f"Tesseract failed with return code {result.returncode}: {result.stderr}")
                return None, 0.0

        except subprocess.TimeoutExpired:
            self.logger.error(f"Tesseract timeout processing {image_path}")
            return None, 0.0
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {str(e)}")
            return None, 0.0

    def _preprocess_image(self, image_path):
        """Preprocess image to improve OCR accuracy"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name

            # Open and preprocess image
            with Image.open(image_path) as image:
                # Convert to grayscale
                if image.mode != 'L':
                    image = image.convert('L')

                # Enhance contrast and resize if needed
                from PIL import ImageEnhance

                # Enhance contrast
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)

                # Resize if image is too small
                width, height = image.size
                if width < 800 or height < 600:
                    scale_factor = max(800 / width, 600 / height)
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save preprocessed image
                image.save(temp_path, 'PNG')

            return temp_path

        except Exception as e:
            self.logger.error(f"Error preprocessing image {image_path}: {str(e)}")
            return image_path  # Return original if preprocessing fails

    def _calculate_confidence(self, image_path):
        """Calculate OCR confidence score"""
        try:
            cmd = [
                'tesseract',
                image_path,
                'stdout',
                '--oem', '3',
                '--psm', '6',
                'tsv'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                confidences = []

                for line in lines[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 11 and parts[10].strip():  # Confidence is in column 10
                        try:
                            conf = float(parts[10])
                            if conf > 0:  # Only include positive confidences
                                confidences.append(conf)
                        except ValueError:
                            continue

                if confidences:
                    return sum(confidences) / len(confidences) / 100.0  # Convert to 0-1 scale
                else:
                    return 0.5  # Default confidence if no data
            else:
                return 0.5  # Default confidence on error

        except Exception as e:
            self.logger.error(f"Error calculating confidence for {image_path}: {str(e)}")
            return 0.5  # Default confidence on error

    def _process_docx(self, docx_path):
        """
        Extract text from modern Word documents (.docx)
        
        Uses python-docx library for direct text extraction.
        """
        if not DOCX_AVAILABLE:
            self.logger.error("python-docx library not available for .docx processing")
            return None, 0.0
        
        try:
            doc = DocxDocument(docx_path)  # type: ignore
            text_parts = []
            
            # Extract text from paragraphs
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    text_parts.append(text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        text_parts.append(' | '.join(row_text))
            
            if text_parts:
                combined_text = '\n'.join(text_parts)
                self.logger.info(f"Successfully extracted {len(combined_text)} characters from DOCX")
                return combined_text, 1.0
            else:
                self.logger.warning("No text found in DOCX document")
                return None, 0.0
                
        except Exception as e:
            self.logger.error(f"Error processing DOCX {docx_path}: {str(e)}")
            return None, 0.0

    def _process_doc(self, doc_path):
        """
        Extract text from legacy Word documents (.doc)
        
        Attempts antiword, catdoc, or LibreOffice conversion.
        """
        # Method 1: Try antiword
        try:
            result = subprocess.run(
                ['antiword', doc_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()
                self.logger.info(f"Successfully extracted {len(text)} characters from DOC using antiword")
                return text, 0.95
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            self.logger.warning(f"antiword extraction failed: {str(e)}")
        
        # Method 2: Try catdoc
        try:
            result = subprocess.run(
                ['catdoc', '-w', doc_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()
                self.logger.info(f"Successfully extracted {len(text)} characters from DOC using catdoc")
                return text, 0.9
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            self.logger.warning(f"catdoc extraction failed: {str(e)}")
        
        # Method 3: Try LibreOffice conversion to PDF then OCR
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                result = subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', temp_dir, doc_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    pdf_name = os.path.splitext(os.path.basename(doc_path))[0] + '.pdf'
                    pdf_path = os.path.join(temp_dir, pdf_name)
                    
                    if os.path.exists(pdf_path):
                        text, confidence = self._process_pdf(pdf_path)
                        if text:
                            self.logger.info(f"Successfully extracted text from DOC via PDF conversion")
                            return text, confidence * 0.9
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        except Exception as e:
            self.logger.warning(f"LibreOffice conversion failed: {str(e)}")
        
        self.logger.error(f"Unable to extract text from DOC file: {doc_path}")
        return None, 0.0

    def reprocess_document(self, document_id):
        """Reprocess an existing document"""
        return self.process_document(document_id)

    def get_processing_stats(self):
        """Get OCR processing statistics"""
        total_docs = Document.query.count()
        processed_docs = Document.query.filter(Document.ocr_text.isnot(None)).count()

        # Calculate average confidence
        avg_confidence = db.session.query(db.func.avg(Document.ocr_confidence)).scalar() or 0.0

        # Count low confidence documents
        low_confidence_docs = Document.query.filter(Document.ocr_confidence < 0.6).count()

        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'average_confidence': avg_confidence,
            'low_confidence_documents': low_confidence_docs
        }

    def cleanup_temp_files(self):
        """Clean up any temporary files created during processing"""
        temp_dir = tempfile.gettempdir()

        try:
            for filename in os.listdir(temp_dir):
                if filename.startswith('tesseract_') or filename.startswith('ocr_'):
                    file_path = os.path.join(temp_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

        except Exception as e:
            self.logger.warning(f"Error cleaning up temp files: {str(e)}")

    def process_documents_batch(self, document_ids, max_workers=4, progress_callback=None):
        """
        Process multiple documents in parallel using ThreadPoolExecutor.
        Each thread gets its own Flask app context and session for safe database access.
        
        Args:
            document_ids: List of document IDs to process
            max_workers: Maximum number of parallel workers (default 4)
            progress_callback: Optional callback function(processed, total, current_doc_id)
        
        Returns:
            Dict with results summary
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from app import app, db
        from sqlalchemy.orm import scoped_session, sessionmaker
        import time
        
        results = {
            'total': len(document_ids),
            'successful': [],
            'failed': [],
            'start_time': time.time()
        }
        
        if not document_ids:
            return results
        
        self.logger.info(f"Starting parallel OCR processing of {len(document_ids)} documents with {max_workers} workers")
        
        def process_single_with_isolated_session(doc_id):
            """Worker function with isolated session for thread-safe database access"""
            with app.app_context():
                try:
                    thread_session = scoped_session(sessionmaker(bind=db.engine))
                    try:
                        success = self._process_document_with_session(doc_id, thread_session)
                        return (doc_id, success, None)
                    finally:
                        thread_session.remove()
                except Exception as e:
                    return (doc_id, False, str(e))
        
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {executor.submit(process_single_with_isolated_session, doc_id): doc_id for doc_id in document_ids}
            
            for future in as_completed(future_to_doc):
                doc_id = future_to_doc[future]
                processed_count += 1
                
                try:
                    doc_id, success, error = future.result()
                    
                    if success:
                        results['successful'].append(doc_id)
                    else:
                        results['failed'].append({
                            'document_id': doc_id,
                            'error': error or 'Processing failed'
                        })
                        
                except Exception as e:
                    results['failed'].append({
                        'document_id': doc_id,
                        'error': str(e)
                    })
                
                if progress_callback:
                    try:
                        progress_callback(processed_count, len(document_ids), doc_id)
                    except Exception:
                        pass
        
        results['end_time'] = time.time()
        results['duration_seconds'] = results['end_time'] - results['start_time']
        results['docs_per_second'] = len(document_ids) / results['duration_seconds'] if results['duration_seconds'] > 0 else 0
        
        self.logger.info(
            f"Parallel OCR complete: {len(results['successful'])}/{len(document_ids)} successful, "
            f"{results['docs_per_second']:.2f} docs/sec"
        )
        
        return results
    
    def _process_document_with_session(self, document_id, session):
        """
        Internal document processing with explicit session for thread safety.
        Used by parallel batch processing.
        """
        document = session.query(Document).get(document_id)
        if not document:
            self.logger.error(f"Document {document_id} not found")
            return False

        try:
            ocr_text, confidence = self._extract_text(document.file_path)

            if ocr_text:
                filtered_text = self.phi_filter.filter_phi(ocr_text)
                document.ocr_text = filtered_text
                document.content = filtered_text
                document.ocr_confidence = confidence
                document.phi_filtered = True
                document.processed_at = datetime.utcnow()
                session.commit()
                self.logger.info(f"Successfully processed document {document_id} with confidence {confidence:.2f}")
                return True
            else:
                self.logger.warning(f"No text extracted from document {document_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error processing document {document_id}: {str(e)}")
            session.rollback()
            return False
    
    def process_documents_batch_with_screening_update(self, document_ids, max_workers=4, progress_callback=None):
        """
        Process documents in parallel and trigger screening updates after completion.
        This is the preferred method for bulk document intake.
        """
        from app import app
        
        results = self.process_documents_batch(document_ids, max_workers, progress_callback)
        
        if results['successful']:
            with app.app_context():
                try:
                    from core.engine import ScreeningEngine
                    engine = ScreeningEngine()
                    for doc_id in results['successful']:
                        try:
                            engine.process_new_document(doc_id)
                        except Exception as e:
                            self.logger.warning(f"Screening update failed for doc {doc_id}: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Error updating screenings after batch: {str(e)}")
        
        return results

    def process_pdf_pages_parallel(self, pdf_path, max_workers=4):
        """
        Process PDF pages in parallel for faster OCR.
        
        Args:
            pdf_path: Path to PDF file
            max_workers: Maximum number of parallel workers
        
        Returns:
            Tuple of (combined_text, average_confidence)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                images = pdf2image.convert_from_path(pdf_path)
                
                if len(images) <= 2:
                    return self._process_pdf(pdf_path)
                
                self.logger.info(f"Processing {len(images)} PDF pages in parallel")
                
                image_paths = []
                for i, image in enumerate(images):
                    image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(image_path, 'PNG')
                    image_paths.append((i, image_path))
                
                page_results = {}
                
                def process_page(args):
                    page_num, image_path = args
                    text, confidence = self._process_image(image_path)
                    return (page_num, text, confidence)
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(process_page, args): args[0] for args in image_paths}
                    
                    for future in as_completed(futures):
                        try:
                            page_num, text, confidence = future.result()
                            page_results[page_num] = (text, confidence)
                        except Exception as e:
                            page_num = futures[future]
                            self.logger.error(f"Error processing page {page_num}: {str(e)}")
                            page_results[page_num] = ('', 0.0)
                
                all_text = []
                confidences = []
                for i in range(len(images)):
                    text, confidence = page_results.get(i, ('', 0.0))
                    if text:
                        all_text.append(text)
                        confidences.append(confidence)
                
                combined_text = '\n'.join(all_text)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                return combined_text, avg_confidence
                
            except Exception as e:
                self.logger.error(f"Error in parallel PDF processing: {str(e)}")
                return self._process_pdf(pdf_path)