"""
Frequency and cutoff filtering logic for prep sheets
Handles time-based filtering of medical data
"""
import logging
from datetime import datetime, timedelta
from app import db
from models import Document, Screening, ScreeningType

logger = logging.getLogger(__name__)

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data"""
    
    def __init__(self):
        pass
    
    def filter_documents_by_relevancy(self, patient_id, section_type, cutoff_date):
        """Filter documents by relevancy to specific sections"""
        base_query = Document.query.filter_by(patient_id=patient_id)\
                                 .filter(Document.document_date >= cutoff_date)
        
        # Section-specific filtering
        if section_type == 'laboratories':
            relevant_docs = base_query.filter(
                db.or_(
                    Document.document_type == 'lab',
                    Document.original_filename.ilike('%lab%'),
                    Document.original_filename.ilike('%blood%'),
                    Document.original_filename.ilike('%urine%'),
                    Document.ocr_text.ilike('%laboratory%'),
                    Document.ocr_text.ilike('%lab results%')
                )
            ).order_by(Document.document_date.desc()).all()
            
        elif section_type == 'imaging':
            relevant_docs = base_query.filter(
                db.or_(
                    Document.document_type == 'imaging',
                    Document.original_filename.ilike('%xray%'),
                    Document.original_filename.ilike('%ct%'),
                    Document.original_filename.ilike('%mri%'),
                    Document.original_filename.ilike('%ultrasound%'),
                    Document.original_filename.ilike('%mammogram%'),
                    Document.ocr_text.ilike('%radiology%'),
                    Document.ocr_text.ilike('%imaging%')
                )
            ).order_by(Document.document_date.desc()).all()
            
        elif section_type == 'consults':
            relevant_docs = base_query.filter(
                db.or_(
                    Document.document_type == 'consult',
                    Document.original_filename.ilike('%consult%'),
                    Document.original_filename.ilike('%referral%'),
                    Document.original_filename.ilike('%specialist%'),
                    Document.ocr_text.ilike('%consultation%'),
                    Document.ocr_text.ilike('%specialist%')
                )
            ).order_by(Document.document_date.desc()).all()
            
        elif section_type == 'hospital_visits':
            relevant_docs = base_query.filter(
                db.or_(
                    Document.document_type == 'hospital',
                    Document.original_filename.ilike('%discharge%'),
                    Document.original_filename.ilike('%admission%'),
                    Document.original_filename.ilike('%hospital%'),
                    Document.original_filename.ilike('%emergency%'),
                    Document.ocr_text.ilike('%discharge summary%'),
                    Document.ocr_text.ilike('%hospital%')
                )
            ).order_by(Document.document_date.desc()).all()
            
        else:
            # Generic filtering for unknown section types
            relevant_docs = base_query.order_by(Document.document_date.desc()).all()
        
        return relevant_docs
    
    def filter_by_screening_frequency(self, documents, screening_type_id):
        """Filter documents based on screening frequency cycles"""
        screening_type = ScreeningType.query.get(screening_type_id)
        if not screening_type:
            return documents
        
        # Calculate frequency period in days
        if screening_type.frequency_unit == 'months':
            frequency_days = screening_type.frequency_value * 30
        else:  # years
            frequency_days = screening_type.frequency_value * 365
        
        cutoff_date = datetime.utcnow() - timedelta(days=frequency_days)
        
        # Filter documents within the current screening cycle
        filtered_docs = [
            doc for doc in documents 
            if doc.document_date and doc.document_date >= cutoff_date
        ]
        
        return filtered_docs
    
    def apply_confidence_threshold(self, documents, min_confidence=0.0):
        """Filter documents by OCR confidence threshold"""
        if min_confidence <= 0:
            return documents
        
        return [
            doc for doc in documents 
            if doc.ocr_confidence and doc.ocr_confidence >= min_confidence
        ]
    
    def filter_by_document_type(self, documents, allowed_types):
        """Filter documents by specific document types"""
        if not allowed_types:
            return documents
        
        return [
            doc for doc in documents 
            if doc.document_type in allowed_types
        ]
    
    def deduplicate_documents(self, documents):
        """Remove duplicate documents based on filename and date"""
        seen_combinations = set()
        unique_docs = []
        
        for doc in documents:
            # Create a unique identifier based on filename and date
            identifier = (
                doc.original_filename.lower(),
                doc.document_date.date() if doc.document_date else None
            )
            
            if identifier not in seen_combinations:
                seen_combinations.add(identifier)
                unique_docs.append(doc)
        
        return unique_docs
    
    def sort_by_priority(self, documents, priority_keywords=None):
        """Sort documents by priority based on keywords"""
        if not priority_keywords:
            # Default priority order
            priority_keywords = [
                'urgent', 'stat', 'critical', 'abnormal', 'positive',
                'negative', 'normal', 'routine'
            ]
        
        def get_priority_score(doc):
            if not doc.ocr_text:
                return 999  # Low priority for docs without text
            
            text_lower = doc.ocr_text.lower()
            for i, keyword in enumerate(priority_keywords):
                if keyword in text_lower:
                    return i
            
            return len(priority_keywords)  # No keywords found
        
        return sorted(documents, key=get_priority_score)
    
    def filter_by_date_range(self, documents, start_date=None, end_date=None):
        """Filter documents by date range"""
        filtered_docs = documents
        
        if start_date:
            filtered_docs = [
                doc for doc in filtered_docs 
                if doc.document_date and doc.document_date >= start_date
            ]
        
        if end_date:
            filtered_docs = [
                doc for doc in filtered_docs 
                if doc.document_date and doc.document_date <= end_date
            ]
        
        return filtered_docs
    
    def group_documents_by_type(self, documents):
        """Group documents by their type for organized display"""
        grouped = {}
        
        for doc in documents:
            doc_type = doc.document_type or 'other'
            if doc_type not in grouped:
                grouped[doc_type] = []
            grouped[doc_type].append(doc)
        
        # Sort each group by date (newest first)
        for doc_type in grouped:
            grouped[doc_type].sort(
                key=lambda x: x.document_date or datetime.min, 
                reverse=True
            )
        
        return grouped
    
    def apply_prep_sheet_filters(self, patient_id, section_config):
        """Apply comprehensive filtering for prep sheet sections"""
        section_type = section_config.get('type')
        cutoff_months = section_config.get('cutoff_months', 12)
        min_confidence = section_config.get('min_confidence', 0.0)
        max_documents = section_config.get('max_documents', 50)
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        # Get relevant documents
        documents = self.filter_documents_by_relevancy(
            patient_id, section_type, cutoff_date
        )
        
        # Apply confidence filtering
        documents = self.apply_confidence_threshold(documents, min_confidence)
        
        # Remove duplicates
        documents = self.deduplicate_documents(documents)
        
        # Sort by priority
        documents = self.sort_by_priority(documents)
        
        # Limit number of documents
        documents = documents[:max_documents]
        
        return documents
    
    def calculate_data_freshness(self, documents):
        """Calculate how fresh/recent the document data is"""
        if not documents:
            return {
                'avg_age_days': None,
                'newest_doc_age': None,
                'oldest_doc_age': None,
                'freshness_score': 0
            }
        
        now = datetime.utcnow()
        doc_ages = []
        
        for doc in documents:
            if doc.document_date:
                age_days = (now - doc.document_date).days
                doc_ages.append(age_days)
        
        if not doc_ages:
            return {
                'avg_age_days': None,
                'newest_doc_age': None,
                'oldest_doc_age': None,
                'freshness_score': 0
            }
        
        avg_age = sum(doc_ages) / len(doc_ages)
        newest_age = min(doc_ages)
        oldest_age = max(doc_ages)
        
        # Calculate freshness score (0-100, higher = fresher)
        # Documents less than 30 days old get high scores
        freshness_score = max(0, 100 - (avg_age / 365 * 100))
        
        return {
            'avg_age_days': round(avg_age, 1),
            'newest_doc_age': newest_age,
            'oldest_doc_age': oldest_age,
            'freshness_score': round(freshness_score, 1)
        }
