"""
Core screening engine orchestration
Implements the main logic for processing patient screenings based on eligibility criteria
"""

from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, or_
from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument, Condition
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria
from core.variants import VariantProcessor
import logging

class ScreeningEngine:
    """Main screening engine for processing patient eligibility and document matching"""
    
    def __init__(self):
        self.matcher = DocumentMatcher()
        self.criteria = EligibilityCriteria()
        self.variant_processor = VariantProcessor()
        self.logger = logging.getLogger(__name__)
    
    def process_patient_screenings(self, patient):
        """Process all screenings for a specific patient"""
        try:
            self.logger.info(f"Processing screenings for patient {patient.mrn}")
            
            # Get active screening types
            active_screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            for screening_type in active_screening_types:
                self._process_patient_screening_type(patient, screening_type)
            
            db.session.commit()
            self.logger.info(f"Completed processing screenings for patient {patient.mrn}")
            
        except Exception as e:
            self.logger.error(f"Error processing screenings for patient {patient.mrn}: {str(e)}")
            db.session.rollback()
            raise
    
    def _process_patient_screening_type(self, patient, screening_type):
        """Process a specific screening type for a patient"""
        # Check eligibility
        if not self.criteria.is_patient_eligible(patient, screening_type):
            # Remove screening if it exists and patient is no longer eligible
            existing_screening = Screening.query.filter_by(
                patient_id=patient.id,
                screening_type_id=screening_type.id
            ).first()
            
            if existing_screening:
                db.session.delete(existing_screening)
                self.logger.info(f"Removed screening {screening_type.name} for patient {patient.mrn} - no longer eligible")
            
            return
        
        # Check for variants based on patient conditions
        applicable_variant = self.variant_processor.get_applicable_variant(patient, screening_type)
        
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
        matched_documents = self.matcher.find_matching_documents(
            patient, screening_type, applicable_variant
        )
        
        # Update screening with matched documents
        screening.matched_documents = [doc.id for doc in matched_documents]
        
        # Determine screening status and dates
        self._update_screening_status(screening, screening_type, applicable_variant, matched_documents)
        
        self.logger.debug(f"Updated screening {screening_type.name} for patient {patient.mrn} - status: {screening.status}")
    
    def _update_screening_status(self, screening, screening_type, variant, matched_documents):
        """Update screening status based on matched documents and frequency"""
        # Get frequency from variant or screening type
        if variant:
            frequency_years = variant.frequency_years or 0
            frequency_months = variant.frequency_months or 0
        else:
            frequency_years = screening_type.frequency_years or 0
            frequency_months = screening_type.frequency_months or 0
        
        # Find most recent relevant document
        most_recent_doc = None
        most_recent_date = None
        
        for doc in matched_documents:
            if doc.document_date and (not most_recent_date or doc.document_date > most_recent_date):
                most_recent_doc = doc
                most_recent_date = doc.document_date
        
        if most_recent_doc:
            screening.last_completed_date = most_recent_date
            
            # Calculate next due date
            next_due = most_recent_date
            if frequency_years > 0:
                next_due = next_due + relativedelta(years=frequency_years)
            if frequency_months > 0:
                next_due = next_due + relativedelta(months=frequency_months)
            
            screening.next_due_date = next_due
            
            # Determine status based on current date
            today = date.today()
            if today < next_due:
                # Check if due soon (within 30 days)
                if (next_due - today).days <= 30:
                    screening.status = 'Due Soon'
                else:
                    screening.status = 'Complete'
            else:
                # Overdue
                screening.status = 'Overdue'
        else:
            # No matching documents found
            screening.last_completed_date = None
            screening.status = 'Due'
            
            # Set next due date based on patient age or default
            if frequency_years > 0 or frequency_months > 0:
                today = date.today()
                screening.next_due_date = today  # Due now
    
    def refresh_all_screenings(self):
        """Refresh screenings for all patients"""
        try:
            self.logger.info("Starting full screening refresh")
            
            patients = Patient.query.all()
            total_patients = len(patients)
            
            for i, patient in enumerate(patients):
                self.logger.info(f"Processing patient {i+1}/{total_patients}: {patient.mrn}")
                self.process_patient_screenings(patient)
            
            self.logger.info(f"Completed full screening refresh for {total_patients} patients")
            
        except Exception as e:
            self.logger.error(f"Error during full screening refresh: {str(e)}")
            raise
    
    def refresh_screening_type(self, screening_type_id):
        """Refresh screenings for a specific screening type across all patients"""
        try:
            screening_type = ScreeningType.query.get(screening_type_id)
            if not screening_type:
                raise ValueError(f"Screening type {screening_type_id} not found")
            
            self.logger.info(f"Refreshing screening type: {screening_type.name}")
            
            patients = Patient.query.all()
            
            for patient in patients:
                self._process_patient_screening_type(patient, screening_type)
            
            db.session.commit()
            self.logger.info(f"Completed refresh for screening type: {screening_type.name}")
            
        except Exception as e:
            self.logger.error(f"Error refreshing screening type {screening_type_id}: {str(e)}")
            db.session.rollback()
            raise
    
    def refresh_patient_documents(self, patient_id):
        """Refresh screenings after new documents are added for a patient"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            self.logger.info(f"Refreshing screenings after document update for patient {patient.mrn}")
            
            self.process_patient_screenings(patient)
            
        except Exception as e:
            self.logger.error(f"Error refreshing patient documents for {patient_id}: {str(e)}")
            raise
    
    def get_screening_statistics(self):
        """Get overall screening statistics"""
        try:
            stats = {
                'total_screenings': Screening.query.count(),
                'due_screenings': Screening.query.filter_by(status='Due').count(),
                'due_soon_screenings': Screening.query.filter_by(status='Due Soon').count(),
                'complete_screenings': Screening.query.filter_by(status='Complete').count(),
                'overdue_screenings': Screening.query.filter_by(status='Overdue').count(),
                'total_patients': Patient.query.count(),
                'total_screening_types': ScreeningType.query.filter_by(is_active=True).count()
            }
            
            # Calculate compliance rate
            total_applicable = stats['total_screenings']
            if total_applicable > 0:
                compliant = stats['complete_screenings'] + stats['due_soon_screenings']
                stats['compliance_rate'] = round((compliant / total_applicable) * 100, 1)
            else:
                stats['compliance_rate'] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting screening statistics: {str(e)}")
            return {}
