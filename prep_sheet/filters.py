"""
Frequency and cutoff filtering logic for prep sheet data.
Handles date-based filtering and document relevancy for prep sheets.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from app import db
from models import MedicalDocument, Screening, ScreeningType, Patient

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def filter_documents_by_type_and_date(self, patient_id: int, document_type: str, 
                                        cutoff_date: date) -> List[MedicalDocument]:
        """Filter documents by type and date cutoff"""
        try:
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.document_type == document_type,
                MedicalDocument.document_date >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error filtering documents for patient {patient_id}: {str(e)}")
            return []
    
    def filter_documents_by_frequency(self, patient_id: int, screening_type: ScreeningType) -> List[MedicalDocument]:
        """Filter documents based on screening frequency"""
        try:
            # Calculate cutoff date based on frequency
            cutoff_date = self._calculate_frequency_cutoff(screening_type)
            
            # Get all documents for patient
            all_documents = MedicalDocument.query.filter_by(patient_id=patient_id).all()
            
            # Find matching documents within frequency period
            from core.matcher import FuzzyMatcher
            matcher = FuzzyMatcher()
            
            matching_docs = matcher.find_matching_documents(screening_type, all_documents)
            
            # Filter by date
            filtered_docs = [doc for doc in matching_docs 
                           if doc.document_date and doc.document_date >= cutoff_date]
            
            return sorted(filtered_docs, key=lambda x: x.document_date or date.min, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by frequency: {str(e)}")
            return []
    
    def _calculate_frequency_cutoff(self, screening_type: ScreeningType) -> date:
        """Calculate cutoff date based on screening frequency"""
        today = date.today()
        
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            # Default to 12 months if no frequency specified
            return today - relativedelta(months=12)
        
        if screening_type.frequency_unit == 'years':
            return today - relativedelta(years=screening_type.frequency_number)
        else:  # months
            return today - relativedelta(months=screening_type.frequency_number)
    
    def get_recent_documents(self, patient_id: int, months: int = 12) -> List[MedicalDocument]:
        """Get all recent documents within specified months"""
        try:
            cutoff_date = date.today() - relativedelta(months=months)
            
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.document_date >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error getting recent documents: {str(e)}")
            return []
    
    def filter_screening_relevant_documents(self, patient_id: int, 
                                          screening_ids: List[int] = None) -> Dict[int, List[MedicalDocument]]:
        """Get documents relevant to specific screenings"""
        try:
            # Get screenings to filter for
            if screening_ids:
                screenings = Screening.query.filter(
                    Screening.patient_id == patient_id,
                    Screening.id.in_(screening_ids)
                ).all()
            else:
                screenings = Screening.query.filter_by(patient_id=patient_id).all()
            
            screening_documents = {}
            
            for screening in screenings:
                docs = self.filter_documents_by_frequency(patient_id, screening.screening_type)
                screening_documents[screening.id] = docs
            
            return screening_documents
            
        except Exception as e:
            self.logger.error(f"Error filtering screening relevant documents: {str(e)}")
            return {}
    
    def apply_prep_sheet_cutoffs(self, documents: List[MedicalDocument], 
                                cutoff_settings: Dict[str, int]) -> Dict[str, List[MedicalDocument]]:
        """Apply prep sheet cutoff settings to documents"""
        try:
            filtered_docs = {
                'lab': [],
                'imaging': [],
                'consult': [],
                'hospital': []
            }
            
            # Calculate cutoff dates for each type
            today = date.today()
            cutoff_dates = {}
            
            for doc_type, months in cutoff_settings.items():
                cutoff_key = doc_type.replace('cutoff_', '')
                cutoff_dates[cutoff_key] = today - relativedelta(months=months)
            
            # Filter documents by type and cutoff
            for doc in documents:
                doc_type = doc.document_type
                
                if doc_type in cutoff_dates and doc.document_date:
                    if doc.document_date >= cutoff_dates[doc_type]:
                        filtered_docs[doc_type].append(doc)
            
            # Sort by date (most recent first)
            for doc_type in filtered_docs:
                filtered_docs[doc_type].sort(
                    key=lambda x: x.document_date or date.min, 
                    reverse=True
                )
            
            return filtered_docs
            
        except Exception as e:
            self.logger.error(f"Error applying prep sheet cutoffs: {str(e)}")
            return {'lab': [], 'imaging': [], 'consult': [], 'hospital': []}
    
    def get_documents_with_confidence_filter(self, patient_id: int, 
                                           min_confidence: float = 0.0) -> List[MedicalDocument]:
        """Get documents filtered by OCR confidence threshold"""
        try:
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.ocr_processed == True,
                MedicalDocument.ocr_confidence >= min_confidence
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error filtering by confidence: {str(e)}")
            return []
    
    def filter_documents_by_keywords(self, patient_id: int, keywords: List[str]) -> List[MedicalDocument]:
        """Filter documents by keyword matching"""
        try:
            if not keywords:
                return []
            
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.ocr_processed == True
            ).all()
            
            matching_docs = []
            
            for doc in documents:
                if doc.ocr_text:
                    text_lower = doc.ocr_text.lower()
                    filename_lower = doc.filename.lower() if doc.filename else ''
                    
                    for keyword in keywords:
                        keyword_lower = keyword.lower().strip()
                        if keyword_lower in text_lower or keyword_lower in filename_lower:
                            matching_docs.append(doc)
                            break  # Found a match, no need to check other keywords
            
            return sorted(matching_docs, key=lambda x: x.document_date or date.min, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error filtering documents by keywords: {str(e)}")
            return []
    
    def get_document_relevancy_score(self, document: MedicalDocument, 
                                   screening_type: ScreeningType) -> float:
        """Calculate relevancy score for document to screening type"""
        try:
            if not document.ocr_text:
                return 0.0
            
            keywords = screening_type.get_keywords_list()
            if not keywords:
                return 0.0
            
            text_lower = document.ocr_text.lower()
            filename_lower = document.filename.lower() if document.filename else ''
            search_text = f"{filename_lower} {text_lower}"
            
            matched_keywords = 0
            total_keywords = len(keywords)
            
            for keyword in keywords:
                if keyword.lower() in search_text:
                    matched_keywords += 1
            
            # Base score on keyword match ratio
            keyword_score = matched_keywords / total_keywords
            
            # Boost score based on document type alignment
            type_boost = self._get_document_type_relevancy_boost(document, screening_type)
            
            # Consider OCR confidence
            confidence_factor = document.ocr_confidence if document.ocr_confidence else 0.8
            
            final_score = keyword_score * type_boost * confidence_factor
            return min(1.0, final_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating relevancy score: {str(e)}")
            return 0.0
    
    def _get_document_type_relevancy_boost(self, document: MedicalDocument, 
                                         screening_type: ScreeningType) -> float:
        """Get relevancy boost based on document type alignment with screening"""
        if not document.document_type:
            return 1.0
        
        screening_name = screening_type.name.lower()
        doc_type = document.document_type.lower()
        
        # Define type alignments
        type_alignments = {
            'lab': ['blood', 'laboratory', 'test', 'panel', 'a1c', 'lipid', 'glucose'],
            'imaging': ['mammogram', 'dexa', 'dxa', 'ct', 'mri', 'xray', 'ultrasound', 'scan'],
            'consult': ['consultation', 'specialist', 'cardiology', 'endocrine'],
            'hospital': ['hospital', 'admission', 'discharge', 'inpatient']
        }
        
        if doc_type in type_alignments:
            alignment_terms = type_alignments[doc_type]
            for term in alignment_terms:
                if term in screening_name:
                    return 1.3  # 30% boost for aligned document type
        
        return 1.0
    
    def get_frequency_filtered_documents(self, patient_id: int) -> Dict[str, List[MedicalDocument]]:
        """Get documents filtered by their respective screening frequencies"""
        try:
            # Get all active screenings for patient
            screenings = Screening.query.filter_by(patient_id=patient_id)\
                                      .join(ScreeningType)\
                                      .filter(ScreeningType.is_active == True).all()
            
            frequency_filtered = {}
            
            for screening in screenings:
                screening_name = screening.screening_type.name
                filtered_docs = self.filter_documents_by_frequency(patient_id, screening.screening_type)
                frequency_filtered[screening_name] = filtered_docs
            
            return frequency_filtered
            
        except Exception as e:
            self.logger.error(f"Error getting frequency filtered documents: {str(e)}")
            return {}
    
    def calculate_document_age_score(self, document: MedicalDocument, 
                                   screening_type: ScreeningType) -> float:
        """Calculate age-based relevancy score for document"""
        try:
            if not document.document_date:
                return 0.5  # Neutral score for unknown dates
            
            # Calculate age in days
            today = date.today()
            age_days = (today - document.document_date).days
            
            # Get screening frequency in days
            if screening_type.frequency_unit == 'years':
                frequency_days = screening_type.frequency_number * 365
            else:  # months
                frequency_days = screening_type.frequency_number * 30
            
            # Score based on recency within frequency period
            if age_days <= 0:
                return 1.0  # Future date (shouldn't happen, but handle gracefully)
            elif age_days <= frequency_days:
                # Linear decay within frequency period
                return 1.0 - (age_days / frequency_days) * 0.5  # Score between 0.5 and 1.0
            else:
                # Older than frequency period
                return 0.2  # Low but not zero score
            
        except Exception as e:
            self.logger.error(f"Error calculating age score: {str(e)}")
            return 0.5
