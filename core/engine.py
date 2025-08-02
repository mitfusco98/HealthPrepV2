"""
Core screening engine orchestration
Coordinates fuzzy matching, eligibility checking, and status determination
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import Patient, ScreeningType, Screening, MedicalDocument, Condition, db
from .matcher import FuzzyMatcher
from .criteria import EligibilityCriteria, StatusCalculator
from .variants import VariantHandler

logger = logging.getLogger(__name__)

class ScreeningEngine:
    """Main screening engine that orchestrates all screening logic"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
        self.criteria = EligibilityCriteria()
        self.status_calculator = StatusCalculator()
        self.variant_handler = VariantHandler()
    
    def process_patient(self, patient: Patient) -> List[Dict[str, Any]]:
        """
        Process a single patient through the screening engine
        Returns list of screening results
        """
        logger.info(f"Processing patient {patient.mrn}")
        
        # Get all active screening types
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        # Get patient's conditions
        conditions = [c.condition_name for c in patient.conditions.filter_by(status='active')]
        
        # Get patient's documents
        documents = patient.documents.all()
        
        results = []
        
        for screening_type in screening_types:
            # Check eligibility including variants
            eligible_variants = self.criteria.check_eligibility(
                patient, screening_type, conditions
            )
            
            if eligible_variants:
                # For each eligible variant, create or update screening
                for variant in eligible_variants:
                    screening = self._get_or_create_screening(patient, screening_type, variant)
                    
                    # Find matching documents
                    matched_docs = self.matcher.find_matching_documents(
                        documents, screening_type, variant
                    )
                    
                    # Update document matches
                    screening.matched_documents_list = [doc.id for doc in matched_docs]
                    
                    # Calculate status
                    status_info = self.status_calculator.calculate_status(
                        screening, matched_docs, variant
                    )
                    
                    # Update screening
                    screening.status = status_info['status']
                    screening.last_completed_date = status_info.get('last_completed')
                    screening.next_due_date = status_info.get('next_due')
                    screening.updated_at = datetime.utcnow()
                    
                    results.append({
                        'screening': screening,
                        'matched_documents': matched_docs,
                        'status_info': status_info,
                        'variant': variant
                    })
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"Processed {len(results)} screenings for patient {patient.mrn}")
        return results
    
    def process_all_patients(self) -> Dict[str, Any]:
        """
        Process all patients through the screening engine
        Returns summary statistics
        """
        logger.info("Starting batch processing of all patients")
        
        patients = Patient.query.all()
        total_processed = 0
        total_screenings = 0
        
        for patient in patients:
            try:
                results = self.process_patient(patient)
                total_processed += 1
                total_screenings += len(results)
            except Exception as e:
                logger.error(f"Error processing patient {patient.mrn}: {str(e)}")
                continue
        
        summary = {
            'patients_processed': total_processed,
            'total_patients': len(patients),
            'total_screenings': total_screenings,
            'processed_at': datetime.utcnow()
        }
        
        logger.info(f"Batch processing complete: {summary}")
        return summary
    
    def refresh_screening_type(self, screening_type_id: int) -> Dict[str, Any]:
        """
        Refresh all screenings for a specific screening type
        Used when screening criteria change
        """
        logger.info(f"Refreshing screening type {screening_type_id}")
        
        screening_type = ScreeningType.query.get(screening_type_id)
        if not screening_type:
            raise ValueError(f"Screening type {screening_type_id} not found")
        
        # Get all patients potentially eligible for this screening
        patients = Patient.query.all()
        updated_screenings = 0
        
        for patient in patients:
            conditions = [c.condition_name for c in patient.conditions.filter_by(status='active')]
            documents = patient.documents.all()
            
            # Check eligibility
            eligible_variants = self.criteria.check_eligibility(
                patient, screening_type, conditions
            )
            
            if eligible_variants:
                for variant in eligible_variants:
                    screening = self._get_or_create_screening(patient, screening_type, variant)
                    
                    # Update document matches
                    matched_docs = self.matcher.find_matching_documents(
                        documents, screening_type, variant
                    )
                    screening.matched_documents_list = [doc.id for doc in matched_docs]
                    
                    # Calculate status
                    status_info = self.status_calculator.calculate_status(
                        screening, matched_docs, variant
                    )
                    
                    screening.status = status_info['status']
                    screening.last_completed_date = status_info.get('last_completed')
                    screening.next_due_date = status_info.get('next_due')
                    screening.updated_at = datetime.utcnow()
                    
                    updated_screenings += 1
        
        db.session.commit()
        
        result = {
            'screening_type': screening_type.name,
            'updated_screenings': updated_screenings,
            'updated_at': datetime.utcnow()
        }
        
        logger.info(f"Refreshed {updated_screenings} screenings for type {screening_type.name}")
        return result
    
    def _get_or_create_screening(self, patient: Patient, screening_type: ScreeningType, variant: Dict) -> Screening:
        """Get existing screening or create new one"""
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                status='Due',
                created_at=datetime.utcnow()
            )
            db.session.add(screening)
        
        return screening
