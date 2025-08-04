from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from models import PatientScreening, ScreeningType
import logging

class PrepSheetFilters:
    """Handles frequency-based filtering and cutoff logic for prep sheets"""
    
    def __init__(self):
        pass
    
    def filter_documents_by_cutoff(self, documents, cutoff_months):
        """Filter documents based on time cutoff"""
        if not cutoff_months:
            return documents
        
        cutoff_date = datetime.utcnow() - timedelta(days=30 * cutoff_months)
        
        return [
            doc for doc in documents
            if doc.created_at >= cutoff_date or (doc.document_date and doc.document_date >= cutoff_date.date())
        ]
    
    def filter_by_screening_frequency(self, documents, screening_type, last_completed_date=None):
        """Filter documents based on screening frequency"""
        if not last_completed_date:
            return documents
        
        # Calculate cutoff date based on frequency
        cutoff_date = self._calculate_frequency_cutoff(screening_type, last_completed_date)
        
        # Only show documents created after the cutoff
        return [
            doc for doc in documents
            if (doc.document_date and doc.document_date > cutoff_date) or
               (not doc.document_date and doc.created_at.date() > cutoff_date)
        ]
    
    def filter_documents_by_relevance(self, documents, patient):
        """Filter documents by relevance to patient's current screenings"""
        if not documents:
            return documents
        
        # Get patient's active screenings
        active_screenings = PatientScreening.query.filter(
            PatientScreening.patient_id == patient.id
        ).join(ScreeningType).filter(ScreeningType.is_active == True).all()
        
        relevant_docs = []
        
        for document in documents:
            relevance_score = self._calculate_document_relevance(document, active_screenings)
            
            # Add relevance score to document (temporary attribute)
            document.relevance_score = relevance_score
            
            # Include if relevance score is above threshold
            if relevance_score > 0.3:  # 30% relevance threshold
                relevant_docs.append(document)
        
        # Sort by relevance score (highest first)
        relevant_docs.sort(key=lambda doc: doc.relevance_score, reverse=True)
        
        return relevant_docs
    
    def apply_screening_filters(self, patient_screenings):
        """Apply filtering logic to patient screenings"""
        filtered_screenings = []
        
        for screening in patient_screenings:
            # Recalculate status
            screening.calculate_status()
            
            # Apply frequency-based document filtering
            if screening.matched_documents:
                documents = self._get_documents_by_ids(screening.matched_documents)
                filtered_documents = self.filter_by_screening_frequency(
                    documents, 
                    screening.screening_type, 
                    screening.last_completed_date
                )
                
                # Update matched documents with filtered list
                screening.filtered_matched_documents = [doc.id for doc in filtered_documents]
            
            filtered_screenings.append(screening)
        
        return filtered_screenings
    
    def _calculate_frequency_cutoff(self, screening_type, last_completed_date):
        """Calculate cutoff date based on screening frequency"""
        if screening_type.frequency_unit == 'years':
            cutoff_date = last_completed_date - relativedelta(years=screening_type.frequency_value)
        else:  # months
            cutoff_date = last_completed_date - relativedelta(months=screening_type.frequency_value)
        
        return cutoff_date
    
    def _calculate_document_relevance(self, document, active_screenings):
        """Calculate how relevant a document is to current screenings"""
        relevance_score = 0.0
        
        # Base relevance from document age (newer = more relevant)
        days_old = (datetime.utcnow().date() - (document.document_date or document.created_at.date())).days
        age_score = max(0, 1 - (days_old / 365))  # 1.0 for today, 0.0 for 1+ years old
        relevance_score += age_score * 0.3
        
        # Relevance from OCR confidence
        if document.ocr_confidence:
            relevance_score += document.ocr_confidence * 0.2
        
        # Relevance from screening keyword matches
        keyword_score = 0.0
        for screening in active_screenings:
            if screening.screening_type.keywords:
                keyword_score += self._calculate_keyword_relevance(document, screening.screening_type.keywords)
        
        relevance_score += min(keyword_score, 0.5)  # Cap at 0.5
        
        return min(relevance_score, 1.0)  # Cap at 1.0
    
    def _calculate_keyword_relevance(self, document, keywords):
        """Calculate relevance based on keyword matches"""
        if not keywords or not document.ocr_text:
            return 0.0
        
        text = (document.filename + ' ' + (document.ocr_text or '')).lower()
        matches = 0
        
        for keyword in keywords:
            if keyword.lower() in text:
                matches += 1
        
        return min(matches / len(keywords), 1.0)
    
    def _get_documents_by_ids(self, document_ids):
        """Get documents by list of IDs"""
        from models import MedicalDocument
        
        if not document_ids:
            return []
        
        return MedicalDocument.query.filter(MedicalDocument.id.in_(document_ids)).all()
    
    def get_cutoff_summary(self, settings):
        """Get summary of current cutoff settings"""
        return {
            'labs': {
                'months': settings.labs_cutoff_months,
                'cutoff_date': (datetime.utcnow() - timedelta(days=30 * settings.labs_cutoff_months)).date()
            },
            'imaging': {
                'months': settings.imaging_cutoff_months,
                'cutoff_date': (datetime.utcnow() - timedelta(days=30 * settings.imaging_cutoff_months)).date()
            },
            'consults': {
                'months': settings.consults_cutoff_months,
                'cutoff_date': (datetime.utcnow() - timedelta(days=30 * settings.consults_cutoff_months)).date()
            },
            'hospital': {
                'months': settings.hospital_cutoff_months,
                'cutoff_date': (datetime.utcnow() - timedelta(days=30 * settings.hospital_cutoff_months)).date()
            }
        }
