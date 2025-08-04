"""
Filtering logic for prep sheet generation including frequency-based filtering,
relevancy scoring, and document cutoff management.
"""

import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional, Tuple
import json

from app import db
from models import (Patient, MedicalDocument, Screening, ScreeningType, 
                   ChecklistSettings, ScreeningDocumentMatch)

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data generation."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def filter_documents_by_cutoff(self, documents: List[MedicalDocument], 
                                  cutoff_months: int) -> List[MedicalDocument]:
        """Filter documents based on cutoff period."""
        
        if cutoff_months <= 0:
            return documents
        
        cutoff_date = date.today() - relativedelta(months=cutoff_months)
        
        return [doc for doc in documents if doc.document_date >= cutoff_date]
    
    def filter_documents_by_type_and_cutoff(self, patient: Patient, 
                                          document_type: str,
                                          cutoff_months: int) -> List[MedicalDocument]:
        """Get documents of specific type within cutoff period."""
        
        cutoff_date = date.today() - relativedelta(months=cutoff_months)
        
        return MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == document_type,
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).all()
    
    def filter_documents_by_screening_frequency(self, documents: List[MedicalDocument],
                                               screening_type: ScreeningType) -> List[MedicalDocument]:
        """Filter documents based on screening frequency requirements."""
        
        if not documents:
            return []
        
        # Calculate frequency cutoff date
        if screening_type.frequency_unit == 'years':
            cutoff_date = date.today() - relativedelta(years=screening_type.frequency_value)
        else:  # months
            cutoff_date = date.today() - relativedelta(months=screening_type.frequency_value)
        
        # Filter documents within one frequency cycle
        return [doc for doc in documents if doc.document_date >= cutoff_date]
    
    def calculate_document_relevancy(self, document: MedicalDocument, patient: Patient) -> float:
        """Calculate relevancy score for a document in the context of current patient care."""
        
        try:
            relevancy_score = 0.0
            
            # Base score for recent documents
            days_old = (date.today() - document.document_date).days
            if days_old <= 30:
                relevancy_score += 0.4  # Very recent
            elif days_old <= 90:
                relevancy_score += 0.3  # Recent
            elif days_old <= 180:
                relevancy_score += 0.2  # Moderately recent
            else:
                relevancy_score += 0.1  # Older
            
            # OCR confidence score contribution
            if document.confidence_score:
                relevancy_score += min(document.confidence_score * 0.3, 0.3)
            
            # Document type importance
            type_weights = {
                'lab': 0.8,     # Lab results are highly relevant
                'imaging': 0.7, # Imaging studies are important
                'consult': 0.9, # Specialist reports are very relevant
                'hospital': 0.6 # Hospital notes are moderately relevant
            }
            relevancy_score += type_weights.get(document.document_type, 0.5) * 0.2
            
            # Screening match relevancy
            screening_match_bonus = self._calculate_screening_match_bonus(document, patient)
            relevancy_score += screening_match_bonus
            
            # Content quality bonus
            content_quality_bonus = self._calculate_content_quality_bonus(document)
            relevancy_score += content_quality_bonus
            
            return min(relevancy_score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            self.logger.warning(f"Error calculating document relevancy: {e}")
            return 0.5  # Default moderate relevancy
    
    def _calculate_screening_match_bonus(self, document: MedicalDocument, patient: Patient) -> float:
        """Calculate bonus points for documents that match active screenings."""
        
        try:
            # Check if document matches any active screenings
            matches = ScreeningDocumentMatch.query.join(Screening).filter(
                ScreeningDocumentMatch.document_id == document.id,
                Screening.patient_id == patient.id
            ).all()
            
            if not matches:
                return 0.0
            
            # Calculate bonus based on match confidence
            total_bonus = 0.0
            for match in matches:
                if match.match_confidence:
                    total_bonus += match.match_confidence * 0.2
            
            return min(total_bonus, 0.3)  # Cap bonus at 0.3
            
        except Exception as e:
            self.logger.warning(f"Error calculating screening match bonus: {e}")
            return 0.0
    
    def _calculate_content_quality_bonus(self, document: MedicalDocument) -> float:
        """Calculate bonus points based on document content quality."""
        
        if not document.content:
            return 0.0
        
        bonus = 0.0
        content_lower = document.content.lower()
        
        # Bonus for medical keywords that indicate important content
        important_keywords = [
            'abnormal', 'elevated', 'decreased', 'critical', 'urgent',
            'follow-up', 'recommend', 'treatment', 'diagnosis', 'findings'
        ]
        
        keyword_count = sum(1 for keyword in important_keywords if keyword in content_lower)
        bonus += min(keyword_count * 0.02, 0.1)  # Up to 0.1 bonus for keywords
        
        # Bonus for good content length (not too short, not too long)
        content_length = len(document.content)
        if 100 <= content_length <= 2000:
            bonus += 0.05
        elif content_length > 50:
            bonus += 0.02
        
        return bonus
    
    def is_document_relevant_for_current_cycle(self, document: MedicalDocument, 
                                             patient: Patient) -> bool:
        """Determine if a document is relevant for the current screening cycle."""
        
        try:
            # Get patient's active screenings
            active_screenings = Screening.query.filter_by(patient_id=patient.id).all()
            
            for screening in active_screenings:
                # Check if document falls within this screening's frequency cycle
                if self._is_document_in_screening_cycle(document, screening):
                    return True
            
            # Also include very recent documents regardless of screening cycles
            days_old = (date.today() - document.document_date).days
            if days_old <= 90:  # Documents from last 3 months
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking document cycle relevancy: {e}")
            return True  # Default to including document
    
    def _is_document_in_screening_cycle(self, document: MedicalDocument, 
                                       screening: Screening) -> bool:
        """Check if document falls within a screening's current cycle."""
        
        screening_type = screening.screening_type
        
        # Calculate current cycle start date
        if screening.last_completed_date:
            cycle_start = screening.last_completed_date
        else:
            # If no previous completion, use a default lookback period
            if screening_type.frequency_unit == 'years':
                cycle_start = date.today() - relativedelta(years=screening_type.frequency_value)
            else:
                cycle_start = date.today() - relativedelta(months=screening_type.frequency_value)
        
        return document.document_date >= cycle_start
    
    def get_filtered_medical_data(self, patient: Patient, 
                                cutoff_settings: ChecklistSettings) -> Dict[str, List]:
        """Get all medical data filtered by cutoff settings."""
        
        filtered_data = {}
        
        # Define categories and their cutoffs
        categories = {
            'labs': cutoff_settings.labs_cutoff_months,
            'imaging': cutoff_settings.imaging_cutoff_months,
            'consults': cutoff_settings.consults_cutoff_months,
            'hospital': cutoff_settings.hospital_cutoff_months
        }
        
        for category, cutoff_months in categories.items():
            documents = self.filter_documents_by_type_and_cutoff(
                patient, category.rstrip('s'), cutoff_months
            )
            
            # Apply relevancy filtering
            relevant_docs = [doc for doc in documents 
                           if self.calculate_document_relevancy(doc, patient) > 0.3]
            
            filtered_data[category] = relevant_docs
        
        return filtered_data
    
    def filter_screening_documents_by_frequency(self, patient: Patient) -> Dict[int, List]:
        """Filter documents for each screening based on their frequency requirements."""
        
        screening_documents = {}
        
        # Get all patient screenings
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        for screening in screenings:
            # Get all patient documents
            all_documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
            
            # Filter by frequency
            frequency_filtered = self.filter_documents_by_screening_frequency(
                all_documents, screening.screening_type
            )
            
            # Further filter by relevancy to this screening
            screening_relevant = self._filter_documents_by_screening_relevancy(
                frequency_filtered, screening
            )
            
            screening_documents[screening.id] = screening_relevant
        
        return screening_documents
    
    def _filter_documents_by_screening_relevancy(self, documents: List[MedicalDocument],
                                                screening: Screening) -> List[MedicalDocument]:
        """Filter documents by their relevancy to a specific screening."""
        
        screening_type = screening.screening_type
        keywords = screening_type.get_keywords_list()
        
        if not keywords:
            return documents
        
        relevant_docs = []
        
        for doc in documents:
            # Check if document content matches screening keywords
            if self._document_matches_keywords(doc, keywords):
                relevant_docs.append(doc)
        
        return relevant_docs
    
    def _document_matches_keywords(self, document: MedicalDocument, 
                                  keywords: List[str]) -> bool:
        """Check if document content matches any of the provided keywords."""
        
        if not document.content or not keywords:
            return False
        
        content_lower = document.content.lower()
        filename_lower = document.filename.lower()
        
        # Check content and filename
        search_text = f"{content_lower} {filename_lower}"
        
        for keyword in keywords:
            if keyword.lower().strip() in search_text:
                return True
        
        return False
    
    def apply_confidence_threshold_filter(self, documents: List[MedicalDocument],
                                        min_confidence: float = 0.6) -> List[MedicalDocument]:
        """Filter documents based on OCR confidence threshold."""
        
        return [doc for doc in documents 
                if doc.confidence_score is None or doc.confidence_score >= min_confidence]
    
    def get_document_age_categories(self, documents: List[MedicalDocument]) -> Dict[str, List]:
        """Categorize documents by age for better organization."""
        
        today = date.today()
        categories = {
            'recent': [],      # Last 30 days
            'current': [],     # Last 90 days
            'relevant': [],    # Last 6 months
            'historical': []   # Older than 6 months
        }
        
        for doc in documents:
            days_old = (today - doc.document_date).days
            
            if days_old <= 30:
                categories['recent'].append(doc)
            elif days_old <= 90:
                categories['current'].append(doc)
            elif days_old <= 180:
                categories['relevant'].append(doc)
            else:
                categories['historical'].append(doc)
        
        return categories
    
    def prioritize_documents(self, documents: List[MedicalDocument], 
                           patient: Patient) -> List[MedicalDocument]:
        """Sort documents by priority/relevancy for prep sheet display."""
        
        if not documents:
            return []
        
        # Calculate priority scores for each document
        doc_scores = []
        for doc in documents:
            relevancy = self.calculate_document_relevancy(doc, patient)
            
            # Additional priority factors
            priority_score = relevancy
            
            # Boost score for certain document types
            if doc.document_type == 'consult':
                priority_score *= 1.2
            elif doc.document_type == 'lab':
                priority_score *= 1.1
            
            # Boost score for recent documents
            days_old = (date.today() - doc.document_date).days
            if days_old <= 7:
                priority_score *= 1.3
            elif days_old <= 30:
                priority_score *= 1.1
            
            doc_scores.append((doc, priority_score))
        
        # Sort by priority score (highest first)
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in doc_scores]
    
    def get_cutoff_date_for_type(self, document_type: str, 
                               cutoff_settings: ChecklistSettings) -> date:
        """Get the cutoff date for a specific document type."""
        
        cutoff_months_map = {
            'lab': cutoff_settings.labs_cutoff_months,
            'imaging': cutoff_settings.imaging_cutoff_months,
            'consult': cutoff_settings.consults_cutoff_months,
            'hospital': cutoff_settings.hospital_cutoff_months
        }
        
        cutoff_months = cutoff_months_map.get(document_type, 12)  # Default to 12 months
        return date.today() - relativedelta(months=cutoff_months)
    
    def generate_filter_summary(self, patient: Patient, 
                              cutoff_settings: ChecklistSettings) -> Dict[str, any]:
        """Generate a summary of applied filters for transparency."""
        
        total_docs = MedicalDocument.query.filter_by(patient_id=patient.id).count()
        
        # Count documents by type and cutoff
        type_counts = {}
        for doc_type in ['lab', 'imaging', 'consult', 'hospital']:
            cutoff_date = self.get_cutoff_date_for_type(doc_type, cutoff_settings)
            
            total_type = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type == doc_type
            ).count()
            
            filtered_type = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type == doc_type,
                MedicalDocument.document_date >= cutoff_date
            ).count()
            
            type_counts[doc_type] = {
                'total': total_type,
                'filtered': filtered_type,
                'cutoff_months': getattr(cutoff_settings, f'{doc_type}s_cutoff_months' if doc_type != 'consult' else 'consults_cutoff_months')
            }
        
        return {
            'total_documents': total_docs,
            'type_breakdown': type_counts,
            'filter_applied_at': datetime.now().isoformat(),
            'cutoff_settings': {
                'labs': cutoff_settings.labs_cutoff_months,
                'imaging': cutoff_settings.imaging_cutoff_months,
                'consults': cutoff_settings.consults_cutoff_months,
                'hospital': cutoff_settings.hospital_cutoff_months
            }
        }
