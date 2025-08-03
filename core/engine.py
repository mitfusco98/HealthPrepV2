"""
Core screening engine orchestration module.
Handles the main logic for screening eligibility, frequency calculation, and status determination.
"""

import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
import json

from app import db
from models import Patient, ScreeningType, Screening, MedicalDocument
from core.matcher import FuzzyMatcher  
from core.criteria import EligibilityCriteria
from core.variants import ScreeningVariants

class ScreeningEngine:
    """Main screening engine that orchestrates all screening logic"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
        self.criteria = EligibilityCriteria()
        self.variants = ScreeningVariants()
        self.logger = logging.getLogger(__name__)
    
    def initialize_patient_screenings(self, patient_id: int) -> int:
        """Initialize all applicable screenings for a new patient"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get all active screening types
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            initialized_count = 0
            
            for screening_type in screening_types:
                if self.criteria.is_patient_eligible(patient, screening_type):
                    # Check if screening already exists
                    existing = Screening.query.filter_by(
                        patient_id=patient_id,
                        screening_type_id=screening_type.id
                    ).first()
                    
                    if not existing:
                        screening = Screening(
                            patient_id=patient_id,
                            screening_type_id=screening_type.id,
                            status='Due'
                        )
                        db.session.add(screening)
                        initialized_count += 1
            
            db.session.commit()
            self.logger.info(f"Initialized {initialized_count} screenings for patient {patient_id}")
            return initialized_count
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error initializing screenings for patient {patient_id}: {str(e)}")
            raise
    
    def refresh_patient_screenings(self, patient_id: int) -> int:
        """Refresh all screenings for a specific patient"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get patient's documents for matching
            documents = MedicalDocument.query.filter_by(
                patient_id=patient_id,
                ocr_processed=True
            ).all()
            
            # Get patient's screenings
            screenings = Screening.query.filter_by(patient_id=patient_id).all()
            updated_count = 0
            
            for screening in screenings:
                if self._update_screening_status(screening, documents):
                    updated_count += 1
            
            db.session.commit()
            self.logger.info(f"Refreshed {updated_count} screenings for patient {patient_id}")
            return updated_count
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error refreshing screenings for patient {patient_id}: {str(e)}")
            raise
    
    def refresh_all_screenings(self) -> int:
        """Refresh all screenings in the system"""
        try:
            screenings = Screening.query.all()
            total_updated = 0
            
            for screening in screenings:
                # Get documents for this patient
                documents = MedicalDocument.query.filter_by(
                    patient_id=screening.patient_id,
                    ocr_processed=True
                ).all()
                
                if self._update_screening_status(screening, documents):
                    total_updated += 1
            
            db.session.commit()
            self.logger.info(f"Refreshed {total_updated} total screenings")
            return total_updated
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error refreshing all screenings: {str(e)}")
            raise
    
    def _update_screening_status(self, screening: Screening, documents: List[MedicalDocument]) -> bool:
        """Update a single screening's status based on document matches"""
        try:
            screening_type = screening.screening_type
            if not screening_type or not screening_type.is_active:
                return False
            
            # Find matching documents
            matched_docs = self.matcher.find_matching_documents(screening_type, documents)
            
            # Update matched documents
            screening.matched_documents = json.dumps([doc.id for doc in matched_docs])
            
            # Determine most recent completion date
            most_recent_date = None
            if matched_docs:
                most_recent_date = max(doc.document_date for doc in matched_docs if doc.document_date)
            
            # Calculate status
            old_status = screening.status
            old_last_completed = screening.last_completed_date
            
            screening.last_completed_date = most_recent_date
            screening.status = self._calculate_screening_status(screening_type, most_recent_date)
            screening.next_due_date = self._calculate_next_due_date(screening_type, most_recent_date)
            screening.updated_at = datetime.utcnow()
            
            # Return True if status changed
            return (old_status != screening.status or 
                   old_last_completed != screening.last_completed_date)
            
        except Exception as e:
            self.logger.error(f"Error updating screening {screening.id}: {str(e)}")
            return False
    
    def _calculate_screening_status(self, screening_type: ScreeningType, last_completed: Optional[datetime]) -> str:
        """Calculate screening status based on frequency and last completion date"""
        if not last_completed:
            return 'Due'
        
        # Calculate when next screening is due
        if screening_type.frequency_unit == 'years':
            next_due = last_completed + relativedelta(years=screening_type.frequency_number)
        else:  # months
            next_due = last_completed + relativedelta(months=screening_type.frequency_number)
        
        today = datetime.now().date()
        days_until_due = (next_due - today).days
        
        if days_until_due <= 0:
            return 'Due'
        elif days_until_due <= 30:  # Due within 30 days
            return 'Due Soon'
        else:
            return 'Complete'
    
    def _calculate_next_due_date(self, screening_type: ScreeningType, last_completed: Optional[datetime]) -> Optional[datetime]:
        """Calculate when the next screening is due"""
        if not last_completed:
            return None
        
        if screening_type.frequency_unit == 'years':
            return last_completed + relativedelta(years=screening_type.frequency_number)
        else:  # months
            return last_completed + relativedelta(months=screening_type.frequency_number)
    
    def get_screening_statistics(self) -> Dict[str, Any]:
        """Get overall screening statistics"""
        try:
            stats = {
                'total_screenings': Screening.query.count(),
                'due_screenings': Screening.query.filter_by(status='Due').count(),
                'due_soon_screenings': Screening.query.filter_by(status='Due Soon').count(),
                'complete_screenings': Screening.query.filter_by(status='Complete').count(),
                'active_screening_types': ScreeningType.query.filter_by(is_active=True).count(),
                'total_patients': Patient.query.count()
            }
            
            # Calculate completion rate
            total_applicable = stats['due_screenings'] + stats['due_soon_screenings'] + stats['complete_screenings']
            if total_applicable > 0:
                stats['completion_rate'] = round((stats['complete_screenings'] / total_applicable) * 100, 1)
            else:
                stats['completion_rate'] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating screening statistics: {str(e)}")
            return {}
    
    def selective_refresh(self, patient_ids: List[int] = None, screening_type_ids: List[int] = None) -> int:
        """Selectively refresh only specific patients or screening types"""
        try:
            query = Screening.query
            
            if patient_ids:
                query = query.filter(Screening.patient_id.in_(patient_ids))
            
            if screening_type_ids:
                query = query.filter(Screening.screening_type_id.in_(screening_type_ids))
            
            screenings = query.all()
            updated_count = 0
            
            for screening in screenings:
                documents = MedicalDocument.query.filter_by(
                    patient_id=screening.patient_id,
                    ocr_processed=True
                ).all()
                
                if self._update_screening_status(screening, documents):
                    updated_count += 1
            
            db.session.commit()
            self.logger.info(f"Selectively refreshed {updated_count} screenings")
            return updated_count
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error in selective refresh: {str(e)}")
            raise
