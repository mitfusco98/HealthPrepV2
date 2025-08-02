"""
Core screening engine that orchestrates the screening process
"""
from models import Patient, ScreeningType, Screening, MedicalDocument
from core.matcher import FuzzyMatcher
from core.criteria import EligibilityCriteria
from app import db
from datetime import datetime, date
import json
import logging

class ScreeningEngine:
    def __init__(self):
        self.matcher = FuzzyMatcher()
        self.criteria = EligibilityCriteria()
        
    def is_eligible(self, patient, screening_type):
        """Check if patient is eligible for a screening type"""
        return self.criteria.check_eligibility(patient, screening_type)
    
    def calculate_status(self, patient, screening_type):
        """Calculate screening status (Due, Due Soon, Complete)"""
        # Find matching documents
        matched_docs = self.find_matching_documents(patient, screening_type)
        
        if not matched_docs:
            return 'Due', None
        
        # Get most recent document date
        latest_date = max(doc.upload_date.date() for doc in matched_docs)
        
        # Calculate next due date based on frequency
        if screening_type.frequency_unit == 'years':
            from dateutil.relativedelta import relativedelta
            next_due = latest_date + relativedelta(years=screening_type.frequency_value)
        elif screening_type.frequency_unit == 'months':
            from dateutil.relativedelta import relativedelta
            next_due = latest_date + relativedelta(months=screening_type.frequency_value)
        else:  # days
            from datetime import timedelta
            next_due = latest_date + timedelta(days=screening_type.frequency_value)
        
        today = date.today()
        
        if today >= next_due:
            return 'Due', latest_date
        elif (next_due - today).days <= 30:  # Due within 30 days
            return 'Due Soon', latest_date
        else:
            return 'Complete', latest_date
    
    def find_matching_documents(self, patient, screening_type):
        """Find documents that match screening type keywords"""
        try:
            keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
        except (json.JSONDecodeError, TypeError):
            keywords = []
        
        if not keywords:
            return []
        
        # Get patient documents
        documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
        matched_docs = []
        
        for doc in documents:
            # Check filename matching
            if self.matcher.matches_keywords(doc.filename, keywords):
                matched_docs.append(doc)
            # Check OCR text matching
            elif doc.ocr_text and self.matcher.matches_keywords(doc.ocr_text, keywords):
                matched_docs.append(doc)
        
        return matched_docs
    
    def refresh_all_screenings(self):
        """Refresh all screening records with current status"""
        updated_count = 0
        patients = Patient.query.all()
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for patient in patients:
            for screening_type in screening_types:
                if self.is_eligible(patient, screening_type):
                    status, last_date = self.calculate_status(patient, screening_type)
                    
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
                    
                    # Update screening
                    screening.status = status
                    screening.last_completed_date = last_date
                    screening.updated_at = datetime.utcnow()
                    
                    # Store matched document IDs
                    matched_docs = self.find_matching_documents(patient, screening_type)
                    screening.matched_documents = json.dumps([doc.id for doc in matched_docs])
                    
                    updated_count += 1
        
        try:
            db.session.commit()
            logging.info(f"Successfully refreshed {updated_count} screening records")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error refreshing screenings: {e}")
            raise
        
        return updated_count
    
    def selective_refresh(self, changed_screening_types=None, changed_patients=None):
        """Refresh only affected screenings for efficiency"""
        updated_count = 0
        
        # If specific screening types changed, update all related screenings
        if changed_screening_types:
            for screening_type in changed_screening_types:
                if screening_type.is_active:
                    patients = Patient.query.all()
                    for patient in patients:
                        if self.is_eligible(patient, screening_type):
                            self._update_screening_record(patient, screening_type)
                            updated_count += 1
        
        # If specific patients changed, update all their screenings
        if changed_patients:
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            for patient in changed_patients:
                for screening_type in screening_types:
                    if self.is_eligible(patient, screening_type):
                        self._update_screening_record(patient, screening_type)
                        updated_count += 1
        
        try:
            db.session.commit()
            logging.info(f"Selective refresh updated {updated_count} screening records")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error in selective refresh: {e}")
            raise
        
        return updated_count
    
    def _update_screening_record(self, patient, screening_type):
        """Helper method to update a single screening record"""
        status, last_date = self.calculate_status(patient, screening_type)
        
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
        
        screening.status = status
        screening.last_completed_date = last_date
        screening.updated_at = datetime.utcnow()
        
        # Store matched document IDs
        matched_docs = self.find_matching_documents(patient, screening_type)
        screening.matched_documents = json.dumps([doc.id for doc in matched_docs])
