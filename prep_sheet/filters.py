"""
Frequency and cutoff filtering logic for prep sheet data
"""
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from models import MedicalDocument, ScreeningType

logger = logging.getLogger(__name__)

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data based on frequency and cutoffs"""
    
    def __init__(self):
        pass
    
    def calculate_cutoff_date(self, months_back: int) -> date:
        """
        Calculate cutoff date based on months back from today
        """
        try:
            today = date.today()
            cutoff_date = today - relativedelta(months=months_back)
            return cutoff_date
        except Exception as e:
            logger.error(f"Error calculating cutoff date: {str(e)}")
            # Fallback to simple calculation
            return date.today() - timedelta(days=months_back * 30)
    
    def filter_documents_by_frequency(self, documents: List[MedicalDocument], 
                                    screening_type: ScreeningType) -> List[MedicalDocument]:
        """
        Filter documents based on screening frequency
        Only show documents from the current screening cycle
        """
        if not documents or not screening_type:
            return documents
        
        try:
            # Calculate cutoff based on screening frequency
            frequency_months = screening_type.frequency_months
            cutoff_date = self.calculate_cutoff_date(frequency_months)
            
            # Filter documents after cutoff date
            filtered_docs = [
                doc for doc in documents 
                if doc.document_date and doc.document_date >= cutoff_date
            ]
            
            logger.debug(f"Filtered {len(documents)} documents to {len(filtered_docs)} based on {frequency_months} month frequency")
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error filtering documents by frequency: {str(e)}")
            return documents
    
    def filter_documents_by_cutoff(self, documents: List[MedicalDocument], 
                                 cutoff_months: int) -> List[MedicalDocument]:
        """
        Filter documents based on a specific cutoff period
        """
        if not documents:
            return documents
        
        try:
            cutoff_date = self.calculate_cutoff_date(cutoff_months)
            
            filtered_docs = [
                doc for doc in documents 
                if doc.document_date and doc.document_date >= cutoff_date
            ]
            
            logger.debug(f"Filtered {len(documents)} documents to {len(filtered_docs)} based on {cutoff_months} month cutoff")
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error filtering documents by cutoff: {str(e)}")
            return documents
    
    def get_relevant_documents_for_screening(self, patient_id: int, 
                                           screening_type: ScreeningType) -> List[MedicalDocument]:
        """
        Get documents relevant to a specific screening type with frequency filtering
        """
        try:
            # Get all patient documents
            all_documents = MedicalDocument.query.filter_by(patient_id=patient_id).all()
            
            # Apply frequency-based filtering
            filtered_documents = self.filter_documents_by_frequency(all_documents, screening_type)
            
            # Sort by date (most recent first)
            filtered_documents.sort(key=lambda d: d.document_date or date.min, reverse=True)
            
            return filtered_documents
            
        except Exception as e:
            logger.error(f"Error getting relevant documents for screening {screening_type.id}: {str(e)}")
            return []
    
    def categorize_documents_by_age(self, documents: List[MedicalDocument]) -> Dict[str, List[MedicalDocument]]:
        """
        Categorize documents by age (recent, older, very old)
        """
        categories = {
            'recent': [],      # Last 3 months
            'older': [],       # 3-12 months
            'very_old': []     # Over 12 months
        }
        
        try:
            today = date.today()
            three_months_ago = today - relativedelta(months=3)
            twelve_months_ago = today - relativedelta(months=12)
            
            for doc in documents:
                if not doc.document_date:
                    categories['very_old'].append(doc)
                elif doc.document_date >= three_months_ago:
                    categories['recent'].append(doc)
                elif doc.document_date >= twelve_months_ago:
                    categories['older'].append(doc)
                else:
                    categories['very_old'].append(doc)
            
            return categories
            
        except Exception as e:
            logger.error(f"Error categorizing documents by age: {str(e)}")
            return categories
    
    def filter_high_confidence_documents(self, documents: List[MedicalDocument], 
                                       min_confidence: float = 0.8) -> List[MedicalDocument]:
        """
        Filter documents to only include those with high OCR confidence
        """
        try:
            filtered_docs = [
                doc for doc in documents 
                if doc.ocr_confidence and doc.ocr_confidence >= min_confidence
            ]
            
            logger.debug(f"Filtered {len(documents)} documents to {len(filtered_docs)} high-confidence documents")
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error filtering high confidence documents: {str(e)}")
            return documents
    
    def get_documents_for_date_range(self, patient_id: int, start_date: date, 
                                   end_date: date, document_type: Optional[str] = None) -> List[MedicalDocument]:
        """
        Get documents within a specific date range
        """
        try:
            query = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.document_date >= start_date,
                MedicalDocument.document_date <= end_date
            )
            
            if document_type:
                query = query.filter(MedicalDocument.document_type == document_type)
            
            documents = query.order_by(MedicalDocument.document_date.desc()).all()
            
            logger.debug(f"Found {len(documents)} documents for date range {start_date} to {end_date}")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting documents for date range: {str(e)}")
            return []
    
    def apply_prep_sheet_filters(self, documents: List[MedicalDocument], 
                               filter_config: Dict[str, Any]) -> List[MedicalDocument]:
        """
        Apply comprehensive filters based on prep sheet configuration
        """
        filtered_docs = documents
        
        try:
            # Apply cutoff date filter
            if 'cutoff_months' in filter_config:
                filtered_docs = self.filter_documents_by_cutoff(
                    filtered_docs, filter_config['cutoff_months']
                )
            
            # Apply confidence filter
            if 'min_confidence' in filter_config:
                filtered_docs = self.filter_high_confidence_documents(
                    filtered_docs, filter_config['min_confidence']
                )
            
            # Apply document type filter
            if 'document_types' in filter_config:
                allowed_types = filter_config['document_types']
                filtered_docs = [
                    doc for doc in filtered_docs 
                    if doc.document_type in allowed_types
                ]
            
            # Apply limit
            if 'limit' in filter_config:
                filtered_docs = filtered_docs[:filter_config['limit']]
            
            logger.debug(f"Applied prep sheet filters: {len(documents)} -> {len(filtered_docs)} documents")
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error applying prep sheet filters: {str(e)}")
            return documents
    
    def get_screening_cycle_documents(self, patient_id: int, 
                                    screening_type: ScreeningType,
                                    last_completed_date: Optional[date] = None) -> List[MedicalDocument]:
        """
        Get documents from the current screening cycle
        """
        try:
            if last_completed_date:
                # Start from last completed date
                start_date = last_completed_date
            else:
                # Use frequency to determine cycle start
                start_date = self.calculate_cutoff_date(screening_type.frequency_months)
            
            end_date = date.today()
            
            documents = self.get_documents_for_date_range(
                patient_id, start_date, end_date
            )
            
            logger.debug(f"Found {len(documents)} documents in current screening cycle for {screening_type.name}")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting screening cycle documents: {str(e)}")
            return []
    
    def calculate_data_freshness_score(self, documents: List[MedicalDocument]) -> float:
        """
        Calculate a freshness score based on document dates
        """
        if not documents:
            return 0.0
        
        try:
            today = date.today()
            total_score = 0.0
            
            for doc in documents:
                if doc.document_date:
                    days_old = (today - doc.document_date).days
                    # Score decreases with age (max 1.0 for today, approaches 0 for very old)
                    freshness = max(0.0, 1.0 - (days_old / 365.0))
                    total_score += freshness
            
            # Average freshness score
            return total_score / len(documents)
            
        except Exception as e:
            logger.error(f"Error calculating data freshness score: {str(e)}")
            return 0.0
    
    def get_priority_documents(self, documents: List[MedicalDocument], 
                             max_count: int = 10) -> List[MedicalDocument]:
        """
        Get the most important documents based on recency and confidence
        """
        try:
            # Score documents based on recency and confidence
            scored_docs = []
            today = date.today()
            
            for doc in documents:
                score = 0.0
                
                # Recency score (0-1, higher for more recent)
                if doc.document_date:
                    days_old = (today - doc.document_date).days
                    recency_score = max(0.0, 1.0 - (days_old / 365.0))
                    score += recency_score * 0.6
                
                # Confidence score (0-1)
                if doc.ocr_confidence:
                    confidence_score = doc.ocr_confidence / 100.0
                    score += confidence_score * 0.4
                
                scored_docs.append((doc, score))
            
            # Sort by score and return top documents
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            priority_docs = [doc for doc, score in scored_docs[:max_count]]
            
            logger.debug(f"Selected {len(priority_docs)} priority documents from {len(documents)} total")
            return priority_docs
            
        except Exception as e:
            logger.error(f"Error getting priority documents: {str(e)}")
            return documents[:max_count]

# Global filters instance
prep_sheet_filters = PrepSheetFilters()
