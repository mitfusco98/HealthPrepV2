"""
Core screening engine orchestration
Implements the main screening logic and coordination between components
"""

import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import and_, or_

from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument, PatientCondition
from core.matcher import FuzzyMatcher
from core.criteria import EligibilityCriteria
from core.variants import ScreeningVariants

logger = logging.getLogger(__name__)

class ScreeningEngine:
    """Main screening engine that orchestrates all screening logic"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
        self.criteria = EligibilityCriteria()
        self.variants = ScreeningVariants()
    
    def run_screening_analysis(self, patient_id: int = None) -> Dict[str, Any]:
        """
        Run complete screening analysis for a patient or all patients
        """
        try:
            if patient_id:
                patients = [Patient.query.get(patient_id)]
            else:
                patients = Patient.query.all()
            
            results = {
                'processed_patients': 0,
                'total_screenings': 0,
                'updated_screenings': 0,
                'errors': []
            }
            
            for patient in patients:
                if not patient:
                    continue
                
                try:
                    patient_results = self._process_patient_screenings(patient)
                    results['processed_patients'] += 1
                    results['total_screenings'] += patient_results['total_screenings']
                    results['updated_screenings'] += patient_results['updated_screenings']
                    
                except Exception as e:
                    error_msg = f"Error processing patient {patient.id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            return results
            
        except Exception as e:
            logger.error(f"Screening engine error: {str(e)}")
            return {'error': str(e)}
    
    def _process_patient_screenings(self, patient: Patient) -> Dict[str, int]:
        """Process all screenings for a single patient"""
        results = {'total_screenings': 0, 'updated_screenings': 0}
        
        # Get all active screening types
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for screening_type in screening_types:
            results['total_screenings'] += 1
            
            # Check eligibility
            if not self.criteria.is_eligible(patient, screening_type):
                continue
            
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
            matched_docs = self._find_matching_documents(patient, screening_type)
            
            # Update screening status
            old_status = screening.status
            screening.matched_documents = [doc.id for doc in matched_docs]
            screening.status = self._determine_status(screening_type, matched_docs)
            screening.last_completed_date = self._get_latest_document_date(matched_docs)
            screening.next_due_date = self._calculate_next_due_date(
                screening_type, screening.last_completed_date
            )
            screening.updated_at = datetime.utcnow()
            
            if old_status != screening.status:
                results['updated_screenings'] += 1
        
        db.session.commit()
        return results
    
    def _find_matching_documents(self, patient: Patient, screening_type: ScreeningType) -> List[MedicalDocument]:
        """Find documents that match screening type keywords"""
        matched_docs = []
        
        # Get patient documents
        documents = MedicalDocument.query.filter_by(patient_id=patient.id).all()
        
        for document in documents:
            if self.matcher.matches_screening(document, screening_type):
                matched_docs.append(document)
        
        return matched_docs
    
    def _determine_status(self, screening_type: ScreeningType, matched_docs: List[MedicalDocument]) -> str:
        """Determine screening status based on matched documents and frequency"""
        if not matched_docs:
            return 'Due'
        
        latest_date = self._get_latest_document_date(matched_docs)
        if not latest_date:
            return 'Due'
        
        # Calculate if screening is current based on frequency
        if screening_type.frequency_unit == 'years':
            due_date = latest_date + relativedelta(years=screening_type.frequency_number)
        elif screening_type.frequency_unit == 'months':
            due_date = latest_date + relativedelta(months=screening_type.frequency_number)
        else:  # days
            due_date = latest_date + timedelta(days=screening_type.frequency_number)
        
        today = date.today()
        days_until_due = (due_date - today).days
        
        if days_until_due > 30:
            return 'Complete'
        elif days_until_due > 0:
            return 'Due Soon'
        else:
            return 'Due'
    
    def _get_latest_document_date(self, documents: List[MedicalDocument]) -> Optional[date]:
        """Get the latest date from a list of documents"""
        if not documents:
            return None
        
        dates = [doc.date_created for doc in documents if doc.date_created]
        return max(dates) if dates else None
    
    def _calculate_next_due_date(self, screening_type: ScreeningType, last_completed: Optional[date]) -> Optional[date]:
        """Calculate when the next screening is due"""
        if not last_completed:
            return date.today()  # Due now if never completed
        
        if screening_type.frequency_unit == 'years':
            return last_completed + relativedelta(years=screening_type.frequency_number)
        elif screening_type.frequency_unit == 'months':
            return last_completed + relativedelta(months=screening_type.frequency_number)
        else:  # days
            return last_completed + timedelta(days=screening_type.frequency_number)
    
    def refresh_selective(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Selectively refresh only affected screenings based on changes
        """
        affected_patients = set()
        affected_screening_types = set()
        
        # Determine what needs to be refreshed based on changes
        if 'screening_types' in changes:
            affected_screening_types.update(changes['screening_types'])
        
        if 'documents' in changes:
            # Get patients affected by document changes
            doc_ids = changes['documents']
            docs = MedicalDocument.query.filter(MedicalDocument.id.in_(doc_ids)).all()
            affected_patients.update([doc.patient_id for doc in docs])
        
        if 'patients' in changes:
            affected_patients.update(changes['patients'])
        
        # Run analysis only on affected items
        results = {'updated_screenings': 0, 'errors': []}
        
        if affected_screening_types:
            # Refresh all screenings for affected screening types
            for st_id in affected_screening_types:
                screenings = Screening.query.filter_by(screening_type_id=st_id).all()
                for screening in screenings:
                    affected_patients.add(screening.patient_id)
        
        # Process affected patients
        for patient_id in affected_patients:
            try:
                patient_results = self._process_patient_screenings(Patient.query.get(patient_id))
                results['updated_screenings'] += patient_results['updated_screenings']
            except Exception as e:
                error_msg = f"Error refreshing patient {patient_id}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        return results
