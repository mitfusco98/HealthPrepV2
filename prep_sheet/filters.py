"""
Frequency and cutoff filtering logic for prep sheet data
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dateutil.relativedelta import relativedelta
from models import MedicalDocument, Screening, ScreeningType

logger = logging.getLogger(__name__)

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data based on frequency and cutoffs"""
    
    def filter_documents_by_date(self, documents: List[MedicalDocument], cutoff_date: date) -> List[MedicalDocument]:
        """
        Filter documents to only include those after the cutoff date
        """
        filtered_docs = []
        
        for doc in documents:
            if doc.document_date and doc.document_date >= cutoff_date:
                filtered_docs.append(doc)
            elif not doc.document_date:
                # Include documents without dates (they might be important)
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def filter_documents_by_screening_frequency(self, documents: List[MedicalDocument], 
                                               screening: Screening) -> List[MedicalDocument]:
        """
        Filter documents based on screening frequency cycle
        Only show documents from the current screening cycle
        """
        if not screening.last_completed_date:
            # If no last completed date, show all documents
            return documents
        
        # Calculate cutoff date based on screening frequency
        frequency_number = screening.screening_type.frequency_number
        frequency_unit = screening.screening_type.frequency_unit
        
        cutoff_date = self._calculate_frequency_cutoff(
            screening.last_completed_date, 
            frequency_number, 
            frequency_unit
        )
        
        return self.filter_documents_by_date(documents, cutoff_date)
    
    def _calculate_frequency_cutoff(self, last_completed: date, frequency_number: int, frequency_unit: str) -> date:
        """
        Calculate the cutoff date based on frequency settings
        """
        if frequency_unit.lower() in ['year', 'years']:
            return last_completed - relativedelta(years=frequency_number)
        elif frequency_unit.lower() in ['month', 'months']:
            return last_completed - relativedelta(months=frequency_number)
        elif frequency_unit.lower() in ['day', 'days']:
            return last_completed - timedelta(days=frequency_number)
        elif frequency_unit.lower() in ['week', 'weeks']:
            return last_completed - timedelta(weeks=frequency_number)
        else:
            # Default to years
            return last_completed - relativedelta(years=frequency_number)
    
    def get_relevant_documents_for_screening(self, documents: List[MedicalDocument], 
                                           screening_type: ScreeningType) -> List[MedicalDocument]:
        """
        Get documents that are relevant to a specific screening type
        Based on keyword matching and document content
        """
        if not screening_type.keywords_list:
            return []
        
        relevant_docs = []
        keywords = [kw.lower() for kw in screening_type.keywords_list]
        
        for doc in documents:
            if self._document_matches_screening(doc, keywords):
                relevant_docs.append(doc)
        
        return relevant_docs
    
    def _document_matches_screening(self, document: MedicalDocument, keywords: List[str]) -> bool:
        """
        Check if document matches screening keywords
        """
        # Check filename
        filename_lower = document.filename.lower()
        for keyword in keywords:
            if keyword in filename_lower:
                return True
        
        # Check OCR text if available
        if document.ocr_text:
            ocr_text_lower = document.ocr_text.lower()
            for keyword in keywords:
                if keyword in ocr_text_lower:
                    return True
        
        return False
    
    def filter_by_document_confidence(self, documents: List[MedicalDocument], 
                                    min_confidence: float = 0.7) -> List[MedicalDocument]:
        """
        Filter documents by OCR confidence threshold
        """
        filtered_docs = []
        
        for doc in documents:
            if doc.ocr_confidence is None or doc.ocr_confidence >= min_confidence:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def group_documents_by_type(self, documents: List[MedicalDocument]) -> Dict[str, List[MedicalDocument]]:
        """
        Group documents by their type
        """
        grouped_docs = {
            'lab': [],
            'imaging': [],
            'consult': [],
            'hospital': [],
            'other': []
        }
        
        for doc in documents:
            doc_type = doc.document_type or 'other'
            if doc_type in grouped_docs:
                grouped_docs[doc_type].append(doc)
            else:
                grouped_docs['other'].append(doc)
        
        return grouped_docs
    
    def sort_documents_by_date(self, documents: List[MedicalDocument], 
                              reverse: bool = True) -> List[MedicalDocument]:
        """
        Sort documents by date (most recent first by default)
        """
        def get_sort_date(doc):
            # Use document date if available, otherwise upload date
            return doc.document_date or doc.upload_date or date.min
        
        return sorted(documents, key=get_sort_date, reverse=reverse)
    
    def filter_duplicate_documents(self, documents: List[MedicalDocument]) -> List[MedicalDocument]:
        """
        Remove duplicate documents based on filename and date
        """
        seen_docs = set()
        filtered_docs = []
        
        for doc in documents:
            # Create identifier based on filename and date
            identifier = (doc.filename, doc.document_date)
            
            if identifier not in seen_docs:
                seen_docs.add(identifier)
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def get_documents_in_date_range(self, documents: List[MedicalDocument], 
                                   start_date: date, end_date: date) -> List[MedicalDocument]:
        """
        Get documents within a specific date range
        """
        filtered_docs = []
        
        for doc in documents:
            if doc.document_date:
                if start_date <= doc.document_date <= end_date:
                    filtered_docs.append(doc)
            else:
                # Include documents without dates if upload date is in range
                if doc.upload_date and start_date <= doc.upload_date.date() <= end_date:
                    filtered_docs.append(doc)
        
        return filtered_docs
    
    def apply_comprehensive_filters(self, documents: List[MedicalDocument],
                                  cutoff_date: date = None,
                                  min_confidence: float = 0.7,
                                  remove_duplicates: bool = True,
                                  sort_by_date: bool = True) -> List[MedicalDocument]:
        """
        Apply comprehensive filtering pipeline
        """
        filtered_docs = documents.copy()
        
        # Apply date filter
        if cutoff_date:
            filtered_docs = self.filter_documents_by_date(filtered_docs, cutoff_date)
        
        # Apply confidence filter
        filtered_docs = self.filter_by_document_confidence(filtered_docs, min_confidence)
        
        # Remove duplicates
        if remove_duplicates:
            filtered_docs = self.filter_duplicate_documents(filtered_docs)
        
        # Sort by date
        if sort_by_date:
            filtered_docs = self.sort_documents_by_date(filtered_docs)
        
        return filtered_docs
    
    def get_screening_document_summary(self, screening: Screening) -> Dict[str, Any]:
        """
        Get summary of documents for a screening
        """
        if not screening.matched_documents_list:
            return {
                'total_documents': 0,
                'most_recent_date': None,
                'oldest_date': None,
                'document_types': {},
                'confidence_levels': {'high': 0, 'medium': 0, 'low': 0}
            }
        
        # Get matched documents
        from models import MedicalDocument
        matched_docs = MedicalDocument.query.filter(
            MedicalDocument.id.in_(screening.matched_documents_list)
        ).all()
        
        if not matched_docs:
            return {
                'total_documents': 0,
                'most_recent_date': None,
                'oldest_date': None,
                'document_types': {},
                'confidence_levels': {'high': 0, 'medium': 0, 'low': 0}
            }
        
        # Analyze documents
        dates = [doc.document_date for doc in matched_docs if doc.document_date]
        doc_types = {}
        confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
        
        for doc in matched_docs:
            # Count document types
            doc_type = doc.document_type or 'unknown'
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
            
            # Count confidence levels
            if doc.ocr_confidence:
                if doc.ocr_confidence >= 0.85:
                    confidence_levels['high'] += 1
                elif doc.ocr_confidence >= 0.70:
                    confidence_levels['medium'] += 1
                else:
                    confidence_levels['low'] += 1
        
        return {
            'total_documents': len(matched_docs),
            'most_recent_date': max(dates).strftime('%m/%d/%Y') if dates else None,
            'oldest_date': min(dates).strftime('%m/%d/%Y') if dates else None,
            'document_types': doc_types,
            'confidence_levels': confidence_levels
        }
    
    def get_patient_document_statistics(self, patient_id: int, 
                                      months_back: int = 12) -> Dict[str, Any]:
        """
        Get comprehensive document statistics for a patient
        """
        from models import MedicalDocument
        
        cutoff_date = datetime.utcnow() - relativedelta(months=months_back)
        
        # Get all patient documents
        all_docs = MedicalDocument.query.filter_by(patient_id=patient_id).all()
        recent_docs = self.filter_documents_by_date(all_docs, cutoff_date.date())
        
        # Group by type
        grouped_docs = self.group_documents_by_type(recent_docs)
        
        # Calculate statistics
        stats = {
            'total_documents': len(all_docs),
            'recent_documents': len(recent_docs),
            'period_months': months_back,
            'by_type': {},
            'ocr_statistics': {
                'processed': 0,
                'pending': 0,
                'average_confidence': 0.0,
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0
            }
        }
        
        # Type breakdown
        for doc_type, docs in grouped_docs.items():
            stats['by_type'][doc_type] = len(docs)
        
        # OCR statistics
        processed_docs = [doc for doc in recent_docs if doc.ocr_processed]
        pending_docs = [doc for doc in recent_docs if not doc.ocr_processed]
        
        stats['ocr_statistics']['processed'] = len(processed_docs)
        stats['ocr_statistics']['pending'] = len(pending_docs)
        
        if processed_docs:
            confidences = [doc.ocr_confidence for doc in processed_docs if doc.ocr_confidence]
            if confidences:
                stats['ocr_statistics']['average_confidence'] = sum(confidences) / len(confidences)
                
                # Count confidence levels
                for confidence in confidences:
                    if confidence >= 0.85:
                        stats['ocr_statistics']['high_confidence'] += 1
                    elif confidence >= 0.70:
                        stats['ocr_statistics']['medium_confidence'] += 1
                    else:
                        stats['ocr_statistics']['low_confidence'] += 1
        
        return stats

