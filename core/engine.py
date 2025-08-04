"""
Core screening engine that orchestrates the screening process
"""
from app import db
from models import Patient, ScreeningType, Screening, Document
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria
from datetime import datetime, date
import logging

class ScreeningEngine:
    """Main screening engine that coordinates all screening operations"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        self.logger = logging.getLogger(__name__)
    
    def refresh_all_screenings(self):
        """Refresh all patient screenings based on current criteria"""
        updated_count = 0
        
        try:
            patients = Patient.query.all()
            
            for patient in patients:
                updated_count += self.refresh_patient_screenings(patient.id)
            
            db.session.commit()
            self.logger.info(f"Successfully refreshed {updated_count} screenings")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error refreshing screenings: {str(e)}")
            raise
        
        return updated_count
    
    def refresh_patient_screenings(self, patient_id):
        """Refresh screenings for a specific patient"""
        patient = Patient.query.get(patient_id)
        if not patient:
            return 0
        
        updated_count = 0
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for screening_type in screening_types:
            if self.criteria.is_patient_eligible(patient, screening_type):
                screening = self._get_or_create_screening(patient, screening_type)
                if self._update_screening_status(screening):
                    updated_count += 1
        
        return updated_count
    
    def process_new_document(self, document_id):
        """Process a new document and update relevant screenings"""
        document = Document.query.get(document_id)
        if not document or not document.patient:
            return
        
        # Find matching screenings for this document
        matches = self.matcher.find_document_matches(document)
        
        # Update screening statuses based on matches
        for screening_id, confidence in matches:
            screening = Screening.query.get(screening_id)
            if screening:
                self._update_screening_from_document(screening, document, confidence)
        
        db.session.commit()
    
    def _get_or_create_screening(self, patient, screening_type):
        """Get existing screening or create new one"""
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                status='due'
            )
            db.session.add(screening)
        
        return screening
    
    def _update_screening_status(self, screening):
        """Update screening status based on documents and criteria"""
        # Find matching documents
        matches = self.matcher.find_screening_matches(screening)
        
        if matches:
            # Get the most recent matching document
            latest_match = max(matches, key=lambda x: x['document_date'] or date.min)
            
            # Calculate status based on frequency and last completion
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                latest_match['document_date']
            )
            
            if new_status != screening.status:
                screening.status = new_status
                screening.last_completed_date = latest_match['document_date']
                screening.updated_at = datetime.utcnow()
                return True
        
        return False
    
    def _update_screening_from_document(self, screening, document, confidence):
        """Update a specific screening based on a document match"""
        # Create or update document match record
        from models import ScreeningDocumentMatch
        
        match = ScreeningDocumentMatch.query.filter_by(
            screening_id=screening.id,
            document_id=document.id
        ).first()
        
        if not match:
            match = ScreeningDocumentMatch(
                screening_id=screening.id,
                document_id=document.id,
                match_confidence=confidence
            )
            db.session.add(match)
        else:
            match.match_confidence = confidence
        
        # Update screening status
        if document.document_date:
            new_status = self.criteria.calculate_screening_status(
                screening.screening_type,
                document.document_date
            )
            
            if new_status != screening.status:
                screening.status = new_status
                screening.last_completed_date = document.document_date
                screening.updated_at = datetime.utcnow()
    
    def get_screening_summary(self, patient_id):
        """Get comprehensive screening summary for a patient"""
        screenings = Screening.query.filter_by(patient_id=patient_id).join(ScreeningType).all()
        
        summary = {
            'total': len(screenings),
            'due': len([s for s in screenings if s.status == 'due']),
            'due_soon': len([s for s in screenings if s.status == 'due_soon']),
            'complete': len([s for s in screenings if s.status == 'complete']),
            'screenings': []
        }
        
        for screening in screenings:
            matches = self.matcher.find_screening_matches(screening)
            summary['screenings'].append({
                'screening': screening,
                'matches': matches
            })
        
        return summary
