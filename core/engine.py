from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app import db
from models import Patient, ScreeningType, PatientScreening, MedicalDocument
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria

class ScreeningEngine:
    """Core screening engine that orchestrates patient screening generation and updates"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
    
    def generate_patient_screenings(self, patient):
        """Generate all applicable screenings for a patient"""
        screenings = []
        
        # Get all active screening types
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for screening_type in screening_types:
            # Check eligibility
            if self.criteria.is_eligible(patient, screening_type):
                screening = self._get_or_create_screening(patient, screening_type)
                self._update_screening_status(screening)
                self._match_documents(screening)
                screenings.append(screening)
        
        return screenings
    
    def update_patient_screenings(self, patient):
        """Update existing screenings for a patient"""
        existing_screenings = PatientScreening.query.filter_by(patient_id=patient.id).all()
        
        for screening in existing_screenings:
            self._update_screening_status(screening)
            self._match_documents(screening)
        
        db.session.commit()
    
    def refresh_all_screenings(self):
        """Refresh all patient screenings - selective refresh"""
        patients = Patient.query.all()
        updated_count = 0
        
        for patient in patients:
            self.update_patient_screenings(patient)
            updated_count += 1
        
        return updated_count
    
    def _get_or_create_screening(self, patient, screening_type):
        """Get existing screening or create new one"""
        screening = PatientScreening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = PatientScreening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                status='due'
            )
            db.session.add(screening)
        
        return screening
    
    def _update_screening_status(self, screening):
        """Update screening status based on frequency and completion date"""
        screening.calculate_status()
    
    def _match_documents(self, screening):
        """Match relevant documents to screening"""
        patient_documents = MedicalDocument.query.filter_by(
            patient_id=screening.patient_id
        ).all()
        
        matched_doc_ids = []
        for document in patient_documents:
            if self.matcher.matches_screening(document, screening.screening_type):
                matched_doc_ids.append(document.id)
                # Update last completed date if document is recent
                if document.document_date and (
                    not screening.last_completed_date or 
                    document.document_date > screening.last_completed_date
                ):
                    screening.last_completed_date = document.document_date
        
        screening.matched_documents = matched_doc_ids
