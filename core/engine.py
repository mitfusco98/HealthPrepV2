"""
Core screening engine orchestration
Handles the main logic for processing screenings and determining eligibility
"""
from datetime import datetime, timedelta
from app import db
from models import Patient, ScreeningType, Screening, Document, ScreeningDocument
from .matcher import DocumentMatcher
from .criteria import EligibilityCriteria
from .variants import VariantHandler
import logging

logger = logging.getLogger(__name__)

class ScreeningEngine:
    """Main screening engine that orchestrates all screening operations"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        self.variant_handler = VariantHandler()
    
    def refresh_all_screenings(self):
        """Refresh all patient screenings based on current criteria"""
        updated_count = 0
        
        # Get all active screening types
        screening_types = ScreeningType.query.filter_by(status='active').all()
        patients = Patient.query.all()
        
        for patient in patients:
            for screening_type in screening_types:
                if self.criteria.is_eligible(patient, screening_type):
                    updated = self.process_patient_screening(patient, screening_type)
                    if updated:
                        updated_count += 1
        
        db.session.commit()
        logger.info(f"Refreshed {updated_count} screenings")
        return updated_count
    
    def process_patient_screening(self, patient, screening_type):
        """Process a single patient screening"""
        # Get or create screening record
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id
            )
            db.session.add(screening)
        
        # Find matching documents
        matching_docs = self.matcher.find_matching_documents(patient, screening_type)
        
        # Update screening status based on documents
        old_status = screening.status
        self.update_screening_status(screening, screening_type, matching_docs)
        
        # Update document associations
        self.update_screening_documents(screening, matching_docs)
        
        screening.updated_at = datetime.utcnow()
        
        return old_status != screening.status
    
    def update_screening_status(self, screening, screening_type, matching_docs):
        """Update screening status based on document matches and frequency"""
        if not matching_docs:
            screening.status = 'due'
            screening.last_completed = None
            return
        
        # Find the most recent relevant document
        latest_doc = max(matching_docs, key=lambda d: d.document_date or datetime.min)
        screening.last_completed = latest_doc.document_date
        
        # Calculate next due date
        if screening_type.frequency_unit == 'months':
            next_due = latest_doc.document_date + timedelta(days=screening_type.frequency_value * 30)
        else:  # years
            next_due = latest_doc.document_date + timedelta(days=screening_type.frequency_value * 365)
        
        screening.next_due = next_due
        
        # Determine status
        now = datetime.utcnow()
        days_until_due = (next_due - now).days
        
        if days_until_due > 30:
            screening.status = 'complete'
        elif days_until_due > 0:
            screening.status = 'due_soon'
        else:
            screening.status = 'due'
    
    def update_screening_documents(self, screening, matching_docs):
        """Update the document associations for a screening"""
        # Remove existing associations
        ScreeningDocument.query.filter_by(screening_id=screening.id).delete()
        
        # Add new associations
        for doc in matching_docs:
            match_data = self.matcher.get_match_details(doc, screening.screening_type)
            
            screening_doc = ScreeningDocument(
                screening_id=screening.id,
                document_id=doc.id,
                match_confidence=match_data['confidence'],
                matched_keywords=match_data['keywords']
            )
            db.session.add(screening_doc)
    
    def process_new_document(self, document):
        """Process a newly uploaded document for all relevant screenings"""
        patient = document.patient
        screening_types = ScreeningType.query.filter_by(status='active').all()
        
        updated_screenings = []
        
        for screening_type in screening_types:
            if self.criteria.is_eligible(patient, screening_type):
                if self.matcher.document_matches_screening(document, screening_type):
                    # Update the relevant screening
                    updated = self.process_patient_screening(patient, screening_type)
                    if updated:
                        updated_screenings.append(screening_type.name)
        
        db.session.commit()
        return updated_screenings
