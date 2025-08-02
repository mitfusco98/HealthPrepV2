"""
Screening engine orchestration - Core logic for processing patient screenings
"""
import json
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument, PatientCondition
from core.matcher import FuzzyMatcher
from core.criteria import EligibilityCriteria
from core.variants import VariantProcessor

logger = logging.getLogger(__name__)

class ScreeningEngine:
    """Main screening engine that orchestrates the screening process"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
        self.criteria = EligibilityCriteria()
        self.variant_processor = VariantProcessor()
    
    def process_patient_screenings(self, patient_id: int) -> List[Dict[str, Any]]:
        """
        Process all applicable screenings for a patient
        Returns list of screening results with status and matched documents
        """
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                logger.error(f"Patient {patient_id} not found")
                return []
            
            logger.info(f"Processing screenings for patient {patient.full_name} (ID: {patient_id})")
            
            # Get all active screening types
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            results = []
            
            for screening_type in screening_types:
                try:
                    result = self._process_single_screening(patient, screening_type)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing screening {screening_type.name} for patient {patient_id}: {str(e)}")
                    continue
            
            logger.info(f"Processed {len(results)} screenings for patient {patient_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error processing patient screenings for {patient_id}: {str(e)}")
            return []
    
    def _process_single_screening(self, patient: Patient, screening_type: ScreeningType) -> Optional[Dict[str, Any]]:
        """Process a single screening type for a patient"""
        
        # Check eligibility
        if not self.criteria.is_eligible(patient, screening_type):
            logger.debug(f"Patient {patient.id} not eligible for {screening_type.name}")
            return None
        
        # Get or create screening record
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                status='Due'
            )
            db.session.add(screening)
        
        # Find matching documents
        matched_documents = self._find_matching_documents(patient, screening_type)
        
        # Determine status and dates
        status_info = self._determine_screening_status(screening_type, matched_documents)
        
        # Update screening record
        screening.status = status_info['status']
        screening.last_completed_date = status_info.get('last_completed_date')
        screening.next_due_date = status_info.get('next_due_date')
        screening.matched_documents = json.dumps([doc.id for doc in matched_documents])
        screening.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Error saving screening record: {str(e)}")
            db.session.rollback()
        
        return {
            'screening_id': screening.id,
            'patient_name': patient.full_name,
            'screening_type': screening_type.name,
            'status': screening.status,
            'last_completed_date': screening.last_completed_date,
            'next_due_date': screening.next_due_date,
            'frequency': f"{screening_type.frequency_months} {screening_type.frequency_unit}",
            'matched_documents': matched_documents,
            'eligibility_met': True
        }
    
    def _find_matching_documents(self, patient: Patient, screening_type: ScreeningType) -> List[MedicalDocument]:
        """Find documents that match the screening type keywords"""
        
        # Get patient documents
        documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
        matched_documents = []
        
        if not screening_type.keywords:
            return matched_documents
        
        try:
            keywords = json.loads(screening_type.keywords)
        except (json.JSONDecodeError, TypeError):
            keywords = []
        
        for document in documents:
            if self.matcher.document_matches_keywords(document, keywords):
                matched_documents.append(document)
        
        # Sort by document date (most recent first)
        matched_documents.sort(key=lambda d: d.document_date or date.min, reverse=True)
        
        return matched_documents
    
    def _determine_screening_status(self, screening_type: ScreeningType, matched_documents: List[MedicalDocument]) -> Dict[str, Any]:
        """Determine screening status based on matched documents and frequency"""
        
        if not matched_documents:
            return {
                'status': 'Due',
                'last_completed_date': None,
                'next_due_date': None
            }
        
        # Get most recent document
        most_recent_doc = matched_documents[0]
        last_completed_date = most_recent_doc.document_date
        
        if not last_completed_date:
            return {
                'status': 'Due',
                'last_completed_date': None,
                'next_due_date': None
            }
        
        # Calculate next due date based on frequency
        if screening_type.frequency_unit == 'months':
            next_due_date = last_completed_date + relativedelta(months=screening_type.frequency_months)
        else:  # years
            next_due_date = last_completed_date + relativedelta(years=screening_type.frequency_months)
        
        # Determine status
        today = date.today()
        days_until_due = (next_due_date - today).days
        
        if days_until_due > 30:
            status = 'Complete'
        elif days_until_due > 0:
            status = 'Due Soon'
        else:
            status = 'Due'
        
        return {
            'status': status,
            'last_completed_date': last_completed_date,
            'next_due_date': next_due_date
        }
    
    def refresh_patient_screenings(self, patient_id: int) -> bool:
        """Refresh all screenings for a specific patient"""
        try:
            results = self.process_patient_screenings(patient_id)
            logger.info(f"Refreshed {len(results)} screenings for patient {patient_id}")
            return True
        except Exception as e:
            logger.error(f"Error refreshing screenings for patient {patient_id}: {str(e)}")
            return False
    
    def refresh_all_screenings(self) -> Dict[str, int]:
        """Refresh screenings for all patients"""
        patients = Patient.query.all()
        success_count = 0
        error_count = 0
        
        for patient in patients:
            try:
                self.refresh_patient_screenings(patient.id)
                success_count += 1
            except Exception as e:
                logger.error(f"Error refreshing screenings for patient {patient.id}: {str(e)}")
                error_count += 1
        
        logger.info(f"Refreshed screenings: {success_count} successful, {error_count} errors")
        return {'success': success_count, 'errors': error_count}

# Global instance
screening_engine = ScreeningEngine()
