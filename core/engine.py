"""
Core screening engine for processing patient screenings based on defined criteria.
Handles eligibility determination, document matching, and status updates.
"""

import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional

from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument, ScreeningDocumentMatch
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria

class ScreeningEngine:
    """Main screening engine orchestration class."""
    
    def __init__(self):
        self.document_matcher = DocumentMatcher()
        self.eligibility_criteria = EligibilityCriteria()
        self.logger = logging.getLogger(__name__)
    
    def refresh_all_screenings(self):
        """Refresh all screenings for all patients."""
        self.logger.info("Starting full screening refresh")
        
        patients = Patient.query.all()
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for patient in patients:
            self._process_patient_screenings(patient, screening_types)
        
        db.session.commit()
        self.logger.info(f"Completed screening refresh for {len(patients)} patients")
    
    def refresh_patient_screenings(self, patient: Patient):
        """Refresh screenings for a specific patient."""
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        self._process_patient_screenings(patient, screening_types)
        db.session.commit()
    
    def refresh_single_screening(self, screening: Screening):
        """Refresh a single screening record."""
        patient = screening.patient
        screening_type = screening.screening_type
        
        # Check if patient is still eligible
        if not self.eligibility_criteria.is_eligible(patient, screening_type):
            # Patient no longer eligible - mark as inactive or remove
            db.session.delete(screening)
        else:
            # Update screening status and matches
            self._update_screening_status(screening, patient)
            self._update_document_matches(screening, patient)
        
        db.session.commit()
    
    def _process_patient_screenings(self, patient: Patient, screening_types: List[ScreeningType]):
        """Process all screening types for a patient."""
        existing_screenings = {s.screening_type_id: s for s in patient.screenings}
        
        for screening_type in screening_types:
            if self.eligibility_criteria.is_eligible(patient, screening_type):
                if screening_type.id in existing_screenings:
                    # Update existing screening
                    screening = existing_screenings[screening_type.id]
                    self._update_screening_status(screening, patient)
                    self._update_document_matches(screening, patient)
                else:
                    # Create new screening
                    screening = self._create_new_screening(patient, screening_type)
                    self._update_screening_status(screening, patient)
                    self._update_document_matches(screening, patient)
            else:
                # Patient not eligible - remove screening if exists
                if screening_type.id in existing_screenings:
                    screening = existing_screenings[screening_type.id]
                    db.session.delete(screening)
    
    def _create_new_screening(self, patient: Patient, screening_type: ScreeningType) -> Screening:
        """Create a new screening record."""
        screening = Screening(
            patient_id=patient.id,
            screening_type_id=screening_type.id,
            status='Due'
        )
        db.session.add(screening)
        return screening
    
    def _update_screening_status(self, screening: Screening, patient: Patient):
        """Update screening status based on document matches and frequency."""
        screening_type = screening.screening_type
        
        # Find most recent matching document
        latest_match = self._find_latest_document_match(screening, patient)
        
        if latest_match:
            screening.last_completed_date = latest_match.document_date
            
            # Calculate next due date
            if screening_type.frequency_unit == 'years':
                screening.next_due_date = latest_match.document_date + relativedelta(years=screening_type.frequency_value)
            else:  # months
                screening.next_due_date = latest_match.document_date + relativedelta(months=screening_type.frequency_value)
            
            # Determine status based on next due date
            today = date.today()
            if screening.next_due_date > today:
                screening.status = 'Complete'
            elif screening.next_due_date <= today - timedelta(days=30):
                screening.status = 'Overdue'
            elif screening.next_due_date <= today + timedelta(days=30):
                screening.status = 'Due Soon'
            else:
                screening.status = 'Due'
        else:
            # No matching documents found
            screening.last_completed_date = None
            screening.next_due_date = None
            screening.status = 'Due'
        
        screening.updated_at = datetime.utcnow()
    
    def _update_document_matches(self, screening: Screening, patient: Patient):
        """Update document matches for a screening."""
        # Clear existing matches
        ScreeningDocumentMatch.query.filter_by(screening_id=screening.id).delete()
        
        # Find new matches
        documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
        screening_type = screening.screening_type
        keywords = screening_type.get_keywords_list()
        
        for document in documents:
            match_score = self.document_matcher.calculate_match_score(document, keywords)
            
            if match_score > 0.5:  # Minimum threshold for match
                match = ScreeningDocumentMatch(
                    screening_id=screening.id,
                    document_id=document.id,
                    match_confidence=match_score,
                    matched_keywords=str(self.document_matcher.get_matched_keywords(document, keywords))
                )
                db.session.add(match)
    
    def _find_latest_document_match(self, screening: Screening, patient: Patient) -> Optional[MedicalDocument]:
        """Find the most recent document that matches the screening criteria."""
        screening_type = screening.screening_type
        keywords = screening_type.get_keywords_list()
        
        documents = MedicalDocument.query.filter_by(patient_id=patient.id)\
                                        .order_by(MedicalDocument.document_date.desc()).all()
        
        for document in documents:
            if self.document_matcher.calculate_match_score(document, keywords) > 0.5:
                return document
        
        return None
    
    def get_screening_summary(self, patient: Patient) -> Dict:
        """Generate screening summary for a patient."""
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        summary = {
            'total_screenings': len(screenings),
            'complete': len([s for s in screenings if s.status == 'Complete']),
            'due': len([s for s in screenings if s.status == 'Due']),
            'due_soon': len([s for s in screenings if s.status == 'Due Soon']),
            'overdue': len([s for s in screenings if s.status == 'Overdue']),
            'screenings': screenings
        }
        
        return summary
