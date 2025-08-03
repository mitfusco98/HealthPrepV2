"""
Frequency and cutoff filtering logic for prep sheets
Handles document filtering based on time periods and screening cycles
"""

import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, List
from sqlalchemy import and_

from models import MedicalDocument, ScreeningType

logger = logging.getLogger(__name__)

class PrepSheetFilters:
    """Handles filtering logic for prep sheet generation"""
    
    def get_cutoff_date(self, period: int, unit: str) -> date:
        """
        Calculate cutoff date based on period and unit
        """
        today = date.today()
        
        if unit == 'years':
            return today - relativedelta(years=period)
        elif unit == 'months':
            return today - relativedelta(months=period)
        elif unit == 'days':
            return today - timedelta(days=period)
        else:
            # Default to months if unit is unknown
            return today - relativedelta(months=period)
    
    def filter_documents_by_cutoff(self, documents: List[MedicalDocument], 
                                 cutoff_months: int) -> List[MedicalDocument]:
        """
        Filter documents to only include those within the cutoff period
        """
        cutoff_date = self.get_cutoff_date(cutoff_months, 'months')
        
        filtered_docs = []
        for doc in documents:
            if doc.date_created and doc.date_created >= cutoff_date:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def filter_documents_by_screening_frequency(self, documents: List[MedicalDocument],
                                              screening_type: ScreeningType,
                                              last_completed_date: Optional[date] = None) -> List[MedicalDocument]:
        """
        Filter documents based on screening frequency
        Only show documents from the current screening cycle
        """
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return documents
        
        # Calculate the start of current screening cycle
        if last_completed_date:
            cycle_start = last_completed_date
        else:
            # If no previous completion, look back one frequency period from today
            cycle_start = self.get_cutoff_date(
                screening_type.frequency_number,
                screening_type.frequency_unit
            )
        
        filtered_docs = []
        for doc in documents:
            if doc.date_created and doc.date_created >= cycle_start:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def is_document_current(self, screening_type: ScreeningType) -> callable:
        """
        Return a SQLAlchemy filter condition for current documents
        """
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            # If no frequency defined, consider all documents current
            return MedicalDocument.date_created.isnot(None)
        
        cutoff_date = self.get_cutoff_date(
            screening_type.frequency_number,
            screening_type.frequency_unit
        )
        
        return MedicalDocument.date_created >= cutoff_date
    
    def is_document_recent(self, document: MedicalDocument, months: int = 6) -> bool:
        """
        Check if a document is from within the specified number of months
        """
        if not document.date_created:
            return False
        
        cutoff_date = self.get_cutoff_date(months, 'months')
        return document.date_created >= cutoff_date
    
    def get_documents_in_period(self, patient_id: int, document_type: str, 
                               period_months: int) -> List[MedicalDocument]:
        """
        Get documents of a specific type within a time period
        """
        from app import db
        
        cutoff_date = self.get_cutoff_date(period_months, 'months')
        
        documents = db.session.query(MedicalDocument).filter(
            and_(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.document_type == document_type,
                MedicalDocument.date_created >= cutoff_date
            )
        ).order_by(MedicalDocument.date_created.desc()).all()
        
        return documents
    
    def get_latest_document_by_type(self, patient_id: int, 
                                   document_type: str) -> Optional[MedicalDocument]:
        """
        Get the most recent document of a specific type for a patient
        """
        from app import db
        
        document = db.session.query(MedicalDocument).filter(
            and_(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.document_type == document_type
            )
        ).order_by(MedicalDocument.date_created.desc()).first()
        
        return document
    
    def calculate_document_age(self, document: MedicalDocument) -> Optional[dict]:
        """
        Calculate the age of a document in various units
        """
        if not document.date_created:
            return None
        
        today = date.today()
        delta = today - document.date_created
        
        return {
            'days': delta.days,
            'weeks': delta.days // 7,
            'months': self._calculate_months_between(document.date_created, today),
            'years': today.year - document.date_created.year
        }
    
    def _calculate_months_between(self, start_date: date, end_date: date) -> int:
        """
        Calculate number of months between two dates
        """
        months = (end_date.year - start_date.year) * 12
        months += end_date.month - start_date.month
        
        # Adjust if day hasn't been reached yet
        if end_date.day < start_date.day:
            months -= 1
        
        return max(0, months)
    
    def filter_by_confidence_threshold(self, documents: List[MedicalDocument],
                                     min_confidence: float = 60.0) -> List[MedicalDocument]:
        """
        Filter documents by OCR confidence threshold
        """
        filtered_docs = []
        for doc in documents:
            if doc.ocr_confidence is None or doc.ocr_confidence >= min_confidence:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def group_documents_by_month(self, documents: List[MedicalDocument]) -> dict:
        """
        Group documents by month for timeline display
        """
        grouped = {}
        
        for doc in documents:
            if not doc.date_created:
                continue
            
            month_key = doc.date_created.strftime('%Y-%m')
            month_name = doc.date_created.strftime('%B %Y')
            
            if month_key not in grouped:
                grouped[month_key] = {
                    'month_name': month_name,
                    'documents': []
                }
            
            grouped[month_key]['documents'].append(doc)
        
        # Sort by month (newest first)
        sorted_groups = dict(sorted(grouped.items(), reverse=True))
        
        return sorted_groups
    
    def get_screening_cycle_info(self, screening_type: ScreeningType,
                                last_completed_date: Optional[date] = None) -> dict:
        """
        Get information about the current screening cycle
        """
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return {
                'has_frequency': False,
                'cycle_start': None,
                'cycle_end': None,
                'next_due': None
            }
        
        if last_completed_date:
            cycle_start = last_completed_date
            
            if screening_type.frequency_unit == 'years':
                next_due = cycle_start + relativedelta(years=screening_type.frequency_number)
            elif screening_type.frequency_unit == 'months':
                next_due = cycle_start + relativedelta(months=screening_type.frequency_number)
            else:  # days
                next_due = cycle_start + timedelta(days=screening_type.frequency_number)
        else:
            # No previous completion - due now
            cycle_start = None
            next_due = date.today()
        
        return {
            'has_frequency': True,
            'frequency_text': self._format_frequency(screening_type),
            'cycle_start': cycle_start,
            'next_due': next_due,
            'is_overdue': next_due < date.today() if next_due else False,
            'days_until_due': (next_due - date.today()).days if next_due else None
        }
    
    def _format_frequency(self, screening_type: ScreeningType) -> str:
        """
        Format screening frequency for display
        """
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return 'As needed'
        
        unit = screening_type.frequency_unit
        number = screening_type.frequency_number
        
        if number == 1:
            return f"Every {unit[:-1]}"  # Remove 's' from plural
        else:
            return f"Every {number} {unit}"
    
    def get_document_relevance_score(self, document: MedicalDocument,
                                   screening_type: ScreeningType) -> float:
        """
        Calculate a relevance score for a document to a screening type
        """
        score = 0.0
        
        # Base score for document type match
        if document.document_type in ['lab', 'imaging', 'consult']:
            score += 0.3
        
        # OCR confidence boost
        if document.ocr_confidence:
            score += (document.ocr_confidence / 100) * 0.3
        
        # Recency boost (more recent = higher score)
        if document.date_created:
            age_months = self._calculate_months_between(document.date_created, date.today())
            recency_score = max(0, 1.0 - (age_months / 24))  # Decay over 24 months
            score += recency_score * 0.4
        
        return min(1.0, score)  # Cap at 1.0
