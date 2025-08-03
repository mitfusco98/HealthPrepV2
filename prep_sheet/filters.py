"""
Frequency and cutoff filtering logic
Handles filtering of medical data based on time periods and relevancy
"""

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, or_
from app import db
from models import MedicalDocument, Screening, ChecklistSettings
import logging

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def filter_documents_by_cutoff(self, patient_id, document_type, cutoff_months):
        """Filter documents by cutoff period"""
        try:
            cutoff_date = date.today() - relativedelta(months=cutoff_months)
            
            documents = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.document_type == document_type,
                    MedicalDocument.document_date >= cutoff_date,
                    MedicalDocument.is_processed == True
                )
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by cutoff: {str(e)}")
            return []
    
    def filter_documents_by_screening_frequency(self, patient_id, screening_id):
        """Filter documents based on screening frequency"""
        try:
            screening = Screening.query.get(screening_id)
            if not screening:
                return []
            
            # Calculate frequency period
            frequency_years = screening.screening_type.frequency_years or 0
            frequency_months = screening.screening_type.frequency_months or 0
            
            if frequency_years == 0 and frequency_months == 0:
                # No frequency specified, return all documents
                cutoff_date = date.today() - relativedelta(years=10)  # Default 10 years
            else:
                # Calculate cutoff based on frequency
                cutoff_date = date.today()
                if frequency_years > 0:
                    cutoff_date = cutoff_date - relativedelta(years=frequency_years)
                if frequency_months > 0:
                    cutoff_date = cutoff_date - relativedelta(months=frequency_months)
            
            # Get documents that match the screening keywords
            if not screening.matched_documents:
                return []
            
            documents = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.id.in_(screening.matched_documents),
                    MedicalDocument.document_date >= cutoff_date
                )
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by screening frequency: {str(e)}")
            return []
    
    def get_relevant_documents_for_prep(self, patient_id, settings=None):
        """Get all relevant documents for prep sheet based on settings"""
        try:
            if not settings:
                settings = ChecklistSettings.query.filter_by(is_active=True).first()
                if not settings:
                    settings = self._get_default_settings()
            
            relevant_docs = {
                'labs': self.filter_documents_by_cutoff(patient_id, 'lab', settings.lab_cutoff_months),
                'imaging': self.filter_documents_by_cutoff(patient_id, 'imaging', settings.imaging_cutoff_months),
                'consults': self.filter_documents_by_cutoff(patient_id, 'consult', settings.consult_cutoff_months),
                'hospital': self.filter_documents_by_cutoff(patient_id, 'hospital', settings.hospital_cutoff_months)
            }
            
            return relevant_docs
            
        except Exception as e:
            self.logger.error(f"Error getting relevant documents for prep: {str(e)}")
            return {}
    
    def filter_documents_by_confidence(self, documents, min_confidence=60):
        """Filter documents by OCR confidence level"""
        try:
            high_confidence = []
            medium_confidence = []
            low_confidence = []
            no_confidence = []
            
            for doc in documents:
                if doc.ocr_confidence is None:
                    no_confidence.append(doc)
                elif doc.ocr_confidence >= 80:
                    high_confidence.append(doc)
                elif doc.ocr_confidence >= min_confidence:
                    medium_confidence.append(doc)
                else:
                    low_confidence.append(doc)
            
            return {
                'high_confidence': high_confidence,
                'medium_confidence': medium_confidence,
                'low_confidence': low_confidence,
                'no_confidence': no_confidence,
                'all_above_threshold': high_confidence + medium_confidence
            }
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by confidence: {str(e)}")
            return {}
    
    def get_documents_by_date_range(self, patient_id, start_date, end_date, document_types=None):
        """Get documents within a specific date range"""
        try:
            query = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.document_date >= start_date,
                    MedicalDocument.document_date <= end_date,
                    MedicalDocument.is_processed == True
                )
            )
            
            if document_types:
                query = query.filter(MedicalDocument.document_type.in_(document_types))
            
            documents = query.order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error getting documents by date range: {str(e)}")
            return []
    
    def filter_screenings_by_status(self, patient_id, status_filter=None):
        """Filter screenings by status"""
        try:
            query = Screening.query.filter_by(patient_id=patient_id)
            
            if status_filter:
                if isinstance(status_filter, list):
                    query = query.filter(Screening.status.in_(status_filter))
                else:
                    query = query.filter_by(status=status_filter)
            
            screenings = query.all()
            
            return screenings
            
        except Exception as e:
            self.logger.error(f"Error filtering screenings by status: {str(e)}")
            return []
    
    def get_priority_screenings(self, patient_id):
        """Get screenings that need immediate attention"""
        try:
            priority_statuses = ['Overdue', 'Due']
            
            priority_screenings = Screening.query.filter(
                and_(
                    Screening.patient_id == patient_id,
                    Screening.status.in_(priority_statuses)
                )
            ).order_by(
                # Order by priority: Overdue first, then Due
                Screening.status.desc(),
                Screening.next_due_date.asc()
            ).all()
            
            return priority_screenings
            
        except Exception as e:
            self.logger.error(f"Error getting priority screenings: {str(e)}")
            return []
    
    def calculate_document_relevancy_score(self, document, screening_keywords):
        """Calculate how relevant a document is to specific screening keywords"""
        try:
            if not screening_keywords or not document.ocr_text:
                return 0
            
            text_lower = document.ocr_text.lower()
            filename_lower = document.filename.lower()
            
            score = 0
            max_score = len(screening_keywords) * 10  # Max 10 points per keyword
            
            for keyword in screening_keywords:
                keyword_lower = keyword.lower()
                
                # Filename matches are worth more
                if keyword_lower in filename_lower:
                    score += 10
                # Content matches
                elif keyword_lower in text_lower:
                    score += 7
                # Partial matches (fuzzy)
                elif any(word in keyword_lower for word in text_lower.split() if len(word) > 3):
                    score += 3
            
            # Normalize score to 0-100
            relevancy_score = min(100, (score / max_score * 100)) if max_score > 0 else 0
            
            # Boost score based on OCR confidence
            if document.ocr_confidence:
                confidence_boost = document.ocr_confidence / 100
                relevancy_score = relevancy_score * (0.5 + 0.5 * confidence_boost)
            
            return round(relevancy_score, 2)
            
        except Exception as e:
            self.logger.error(f"Error calculating document relevancy: {str(e)}")
            return 0
    
    def get_most_recent_document_per_type(self, patient_id):
        """Get the most recent document for each document type"""
        try:
            from sqlalchemy import func
            
            # Subquery to get max date per document type
            subquery = db.session.query(
                MedicalDocument.document_type,
                func.max(MedicalDocument.document_date).label('max_date')
            ).filter(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.is_processed == True
                )
            ).group_by(MedicalDocument.document_type).subquery()
            
            # Join to get the actual documents
            recent_docs = db.session.query(MedicalDocument).join(
                subquery,
                and_(
                    MedicalDocument.document_type == subquery.c.document_type,
                    MedicalDocument.document_date == subquery.c.max_date,
                    MedicalDocument.patient_id == patient_id
                )
            ).all()
            
            return recent_docs
            
        except Exception as e:
            self.logger.error(f"Error getting most recent documents per type: {str(e)}")
            return []
    
    def filter_documents_older_than_frequency(self, patient_id, screening_type):
        """Filter out documents older than the screening frequency"""
        try:
            frequency_years = screening_type.frequency_years or 0
            frequency_months = screening_type.frequency_months or 0
            
            if frequency_years == 0 and frequency_months == 0:
                # No frequency specified, don't filter
                return MedicalDocument.query.filter_by(patient_id=patient_id).all()
            
            # Calculate cutoff date
            cutoff_date = date.today()
            if frequency_years > 0:
                cutoff_date = cutoff_date - relativedelta(years=frequency_years)
            if frequency_months > 0:
                cutoff_date = cutoff_date - relativedelta(months=frequency_months)
            
            # Get documents newer than cutoff
            recent_docs = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.document_date >= cutoff_date,
                    MedicalDocument.is_processed == True
                )
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return recent_docs
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by frequency: {str(e)}")
            return []
    
    def _get_default_settings(self):
        """Get default settings if none exist"""
        from models import ChecklistSettings
        
        return ChecklistSettings(
            name='Default',
            lab_cutoff_months=12,
            imaging_cutoff_months=24,
            consult_cutoff_months=12,
            hospital_cutoff_months=24
        )
    
    def apply_prep_sheet_filters(self, patient_id, filter_config=None):
        """Apply comprehensive filtering for prep sheet generation"""
        try:
            if not filter_config:
                filter_config = self._get_default_filter_config()
            
            filtered_data = {}
            
            # Apply document type filters
            for doc_type, config in filter_config.get('document_types', {}).items():
                cutoff_months = config.get('cutoff_months', 12)
                min_confidence = config.get('min_confidence', 60)
                
                docs = self.filter_documents_by_cutoff(patient_id, doc_type, cutoff_months)
                confidence_filtered = self.filter_documents_by_confidence(docs, min_confidence)
                
                filtered_data[doc_type] = {
                    'all_documents': docs,
                    'high_confidence': confidence_filtered['high_confidence'],
                    'above_threshold': confidence_filtered['all_above_threshold']
                }
            
            # Apply screening filters
            screening_config = filter_config.get('screenings', {})
            status_filter = screening_config.get('status_filter')
            
            screenings = self.filter_screenings_by_status(patient_id, status_filter)
            priority_screenings = self.get_priority_screenings(patient_id)
            
            filtered_data['screenings'] = {
                'all_screenings': screenings,
                'priority_screenings': priority_screenings
            }
            
            return filtered_data
            
        except Exception as e:
            self.logger.error(f"Error applying prep sheet filters: {str(e)}")
            return {}
    
    def _get_default_filter_config(self):
        """Get default filter configuration"""
        return {
            'document_types': {
                'lab': {'cutoff_months': 12, 'min_confidence': 60},
                'imaging': {'cutoff_months': 24, 'min_confidence': 70},
                'consult': {'cutoff_months': 12, 'min_confidence': 60},
                'hospital': {'cutoff_months': 24, 'min_confidence': 60}
            },
            'screenings': {
                'status_filter': None  # Include all statuses
            }
        }
