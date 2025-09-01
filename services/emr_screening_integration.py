"""
EMR Screening Integration Service
Bridges the comprehensive EMR sync with the existing screening engine
to process synchronized data and update screening statuses
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple

from models import db, Patient, ScreeningType, Screening, FHIRDocument, PatientCondition
from core.engine import ScreeningEngine
from core.criteria import EligibilityCriteria
from core.fuzzy_detection import FuzzyDetectionEngine
from core.matcher import DocumentMatcher
from services.comprehensive_emr_sync import ComprehensiveEMRSync

logger = logging.getLogger(__name__)


class EMRScreeningIntegration:
    """
    Enhanced screening integration that processes EMR data from comprehensive sync
    and updates screening eligibility and completion status
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        
        # Initialize core screening components
        self.screening_engine = ScreeningEngine()
        self.eligibility_criteria = EligibilityCriteria()
        self.fuzzy_engine = FuzzyDetectionEngine()
        self.document_matcher = DocumentMatcher()
        
        # Initialize EMR sync service
        self.emr_sync = ComprehensiveEMRSync(organization_id)
        
        # Integration statistics
        self.integration_stats = {
            'patients_processed': 0,
            'screenings_updated': 0,
            'documents_analyzed': 0,
            'conditions_processed': 0,
            'observations_processed': 0,
            'eligibility_changes': 0
        }
        
        logger.info(f"Initialized EMR Screening Integration for organization {organization_id}")
    
    def process_patient_emr_data(self, patient_id: int, emr_sync_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process EMR synchronization results to update screening eligibility and status
        
        Args:
            patient_id: Patient database ID
            emr_sync_results: Results from comprehensive EMR sync
            
        Returns:
            Dict with processing results and updated screening statuses
        """
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise Exception(f"Patient {patient_id} not found")
            
            logger.info(f"Processing EMR data for patient {patient.name} (ID: {patient_id})")
            
            # Step 1: Process demographic changes that might affect eligibility
            demographic_updates = self._process_demographic_updates(patient)
            
            # Step 2: Process new conditions that might trigger screenings
            condition_updates = self._process_patient_conditions(patient)
            
            # Step 3: Process observations for screening evidence
            observation_updates = self._process_patient_observations(patient, emr_sync_results)
            
            # Step 4: Process documents for screening completion evidence
            document_updates = self._process_patient_documents(patient, emr_sync_results)
            
            # Step 5: Re-evaluate all screenings based on new data
            screening_updates = self._reevaluate_patient_screenings(patient)
            
            # Step 6: Generate screening recommendations based on updated data
            recommendations = self._generate_screening_recommendations(patient)
            
            # Update integration statistics
            self.integration_stats.update({
                'patients_processed': self.integration_stats['patients_processed'] + 1,
                'conditions_processed': self.integration_stats['conditions_processed'] + condition_updates,
                'documents_analyzed': self.integration_stats['documents_analyzed'] + document_updates,
                'screenings_updated': self.integration_stats['screenings_updated'] + screening_updates,
                'eligibility_changes': self.integration_stats['eligibility_changes'] + demographic_updates
            })
            
            db.session.commit()
            
            result = {
                'success': True,
                'patient_id': patient_id,
                'patient_name': patient.name,
                'demographic_updates': demographic_updates,
                'condition_updates': condition_updates,
                'observation_updates': observation_updates,
                'document_updates': document_updates,
                'screening_updates': screening_updates,
                'recommendations': recommendations,
                'total_screenings': len(recommendations)
            }
            
            logger.info(f"Successfully processed EMR data for patient {patient.name}: "
                       f"{screening_updates} screenings updated")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing EMR data for patient {patient_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            
            return {
                'success': False,
                'patient_id': patient_id,
                'error': str(e)
            }
    
    def _process_demographic_updates(self, patient: Patient) -> int:
        """Process demographic changes that might affect screening eligibility"""
        try:
            changes = 0
            
            # Check if age changes affect any screening eligibility
            current_screenings = Screening.query.filter_by(patient_id=patient.id).all()
            
            for screening in current_screenings:
                screening_type = screening.screening_type
                
                # Re-check eligibility based on current demographics
                was_eligible = screening.status != 'not_eligible'
                is_eligible = self.eligibility_criteria.is_patient_eligible(patient, screening_type)
                
                if was_eligible != is_eligible:
                    if is_eligible:
                        screening.status = 'due'
                        screening.notes = f"Became eligible based on updated demographics on {datetime.now().strftime('%Y-%m-%d')}"
                    else:
                        screening.status = 'not_eligible'
                        screening.notes = f"No longer eligible based on updated demographics on {datetime.now().strftime('%Y-%m-%d')}"
                    
                    changes += 1
                    logger.info(f"Eligibility changed for {patient.name}: {screening_type.name} -> {'eligible' if is_eligible else 'not eligible'}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error processing demographic updates: {str(e)}")
            return 0
    
    def _process_patient_conditions(self, patient: Patient) -> int:
        """Process patient conditions to identify new screening triggers"""
        try:
            # Get patient conditions from EMR sync
            patient_conditions = PatientCondition.query.filter_by(
                patient_id=patient.id,
                is_active=True
            ).all()
            
            conditions_processed = 0
            
            # Get all screening types that use trigger conditions
            screening_types = ScreeningType.query.filter_by(org_id=self.organization_id).all()
            
            for screening_type in screening_types:
                if not screening_type.trigger_conditions:
                    continue
                
                trigger_conditions = json.loads(screening_type.trigger_conditions) if screening_type.trigger_conditions else []
                
                # Check if patient has any trigger conditions
                patient_has_trigger = self._patient_has_trigger_condition(patient_conditions, trigger_conditions)
                
                if patient_has_trigger:
                    # Ensure screening exists for this patient
                    screening = self._get_or_create_screening(patient, screening_type)
                    
                    # Update screening based on trigger condition
                    if screening.status == 'not_eligible':
                        screening.status = 'due'
                        screening.notes = f"Triggered by condition: {self._get_matching_condition_names(patient_conditions, trigger_conditions)}"
                        conditions_processed += 1
                        
                        logger.info(f"Screening triggered by condition for {patient.name}: {screening_type.name}")
            
            return conditions_processed
            
        except Exception as e:
            logger.error(f"Error processing patient conditions: {str(e)}")
            return 0
    
    def _process_patient_observations(self, patient: Patient, emr_sync_results: Dict[str, Any]) -> int:
        """Process patient observations for screening-relevant data"""
        try:
            observations_processed = 0
            
            # This would process specific observation values that indicate screening completion
            # For example, PSA values, cholesterol levels, etc.
            
            # Get observation data from sync results or query patient's observations
            # For now, we'll focus on document-based evidence which is more common
            
            logger.debug(f"Processed {observations_processed} observations for {patient.name}")
            return observations_processed
            
        except Exception as e:
            logger.error(f"Error processing patient observations: {str(e)}")
            return 0
    
    def _process_patient_documents(self, patient: Patient, emr_sync_results: Dict[str, Any]) -> int:
        """Process patient documents for screening completion evidence"""
        try:
            # Get recently synchronized documents
            recent_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id
            ).filter(
                FHIRDocument.created_at >= datetime.now() - timedelta(hours=24)
            ).all()
            
            documents_processed = 0
            
            for document in recent_documents:
                # Use document matcher to find relevant screenings
                matches = self.document_matcher.find_document_matches_by_text(
                    document.extracted_text or document.title,
                    patient.id
                )
                
                for screening_id, confidence in matches:
                    screening = Screening.query.get(screening_id)
                    
                    if screening and confidence >= 0.7:  # High confidence match
                        # Update screening completion based on document evidence
                        self._update_screening_from_document_evidence(
                            screening, document, confidence
                        )
                        documents_processed += 1
                        
                        logger.info(f"Document evidence found for {patient.name}: "
                                   f"{screening.screening_type.name} (confidence: {confidence:.2f})")
            
            return documents_processed
            
        except Exception as e:
            logger.error(f"Error processing patient documents: {str(e)}")
            return 0
    
    def _reevaluate_patient_screenings(self, patient: Patient) -> int:
        """Re-evaluate all patient screenings based on updated EMR data"""
        try:
            screening_types = ScreeningType.query.filter_by(
                org_id=self.organization_id,
                is_active=True
            ).all()
            
            screenings_updated = 0
            
            for screening_type in screening_types:
                # Check eligibility with updated patient data
                is_eligible = self.eligibility_criteria.is_patient_eligible(patient, screening_type)
                
                if is_eligible:
                    screening = self._get_or_create_screening(patient, screening_type)
                    
                    # Recalculate status based on latest document evidence
                    old_status = screening.status
                    new_status = self._calculate_screening_status_from_documents(
                        patient, screening_type
                    )
                    
                    if old_status != new_status:
                        screening.status = new_status
                        screening.last_updated = datetime.now()
                        screening.notes = f"Status updated from EMR sync on {datetime.now().strftime('%Y-%m-%d')}"
                        screenings_updated += 1
                        
                        logger.info(f"Screening status updated for {patient.name}: "
                                   f"{screening_type.name} {old_status} -> {new_status}")
            
            return screenings_updated
            
        except Exception as e:
            logger.error(f"Error re-evaluating patient screenings: {str(e)}")
            return 0
    
    def _generate_screening_recommendations(self, patient: Patient) -> List[Dict[str, Any]]:
        """Generate screening recommendations based on current status"""
        try:
            recommendations = []
            
            # Get all active screenings for patient
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            
            for screening in screenings:
                screening_type = screening.screening_type
                
                recommendation = {
                    'screening_id': screening.id,
                    'screening_name': screening_type.name,
                    'status': screening.status,
                    'priority': self._calculate_screening_priority(screening),
                    'next_due_date': self._calculate_next_due_date(screening),
                    'frequency': f"Every {screening_type.frequency_value} {screening_type.frequency_unit}" if screening_type.frequency_value else None,
                    'notes': screening.notes,
                    'last_completed': screening.last_completed_date.isoformat() if screening.last_completed_date else None
                }
                
                # Add specific recommendations based on status
                if screening.status == 'due':
                    recommendation['action'] = 'Schedule screening'
                    recommendation['urgency'] = 'high'
                elif screening.status == 'due_soon':
                    recommendation['action'] = 'Schedule screening soon'
                    recommendation['urgency'] = 'medium'
                elif screening.status == 'complete':
                    recommendation['action'] = 'Up to date'
                    recommendation['urgency'] = 'low'
                else:
                    recommendation['action'] = 'Review eligibility'
                    recommendation['urgency'] = 'low'
                
                recommendations.append(recommendation)
            
            # Sort by priority and urgency
            recommendations.sort(key=lambda x: (
                {'high': 0, 'medium': 1, 'low': 2}[x['urgency']],
                -x['priority']
            ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating screening recommendations: {str(e)}")
            return []
    
    def sync_and_process_patient(self, epic_patient_id: str) -> Dict[str, Any]:
        """
        Complete workflow: sync patient from Epic and process for screenings
        
        Args:
            epic_patient_id: Patient ID in Epic system
            
        Returns:
            Dict with complete sync and processing results
        """
        try:
            logger.info(f"Starting complete EMR sync and screening processing for Epic patient {epic_patient_id}")
            
            # Step 1: Perform comprehensive EMR sync
            sync_results = self.emr_sync.sync_patient_comprehensive(epic_patient_id)
            
            if not sync_results.get('success'):
                return {
                    'success': False,
                    'error': f"EMR sync failed: {sync_results.get('error')}"
                }
            
            # Step 2: Process synced data for screening integration
            processing_results = self.process_patient_emr_data(
                sync_results['patient_id'], sync_results
            )
            
            if not processing_results.get('success'):
                return {
                    'success': False,
                    'error': f"Screening processing failed: {processing_results.get('error')}"
                }
            
            # Step 3: Combine results
            combined_results = {
                'success': True,
                'epic_patient_id': epic_patient_id,
                'patient_id': sync_results['patient_id'],
                'patient_name': processing_results.get('patient_name'),
                'sync_summary': {
                    'conditions_synced': sync_results.get('conditions_synced', 0),
                    'observations_synced': sync_results.get('observations_synced', 0),
                    'documents_processed': sync_results.get('documents_processed', 0),
                    'encounters_synced': sync_results.get('encounters_synced', 0)
                },
                'screening_summary': {
                    'screenings_updated': processing_results.get('screening_updates', 0),
                    'total_screenings': processing_results.get('total_screenings', 0),
                    'eligibility_changes': processing_results.get('demographic_updates', 0)
                },
                'recommendations': processing_results.get('recommendations', [])
            }
            
            logger.info(f"Successfully completed EMR sync and screening processing for {epic_patient_id}")
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Error in complete EMR sync and processing: {str(e)}", exc_info=True)
            
            return {
                'success': False,
                'epic_patient_id': epic_patient_id,
                'error': str(e)
            }
    
    # Helper Methods
    def _get_or_create_screening(self, patient: Patient, screening_type: ScreeningType) -> Screening:
        """Get existing screening or create new one"""
        screening = Screening.query.filter_by(
            patient_id=patient.id,
            screening_type_id=screening_type.id
        ).first()
        
        if not screening:
            screening = Screening(
                patient_id=patient.id,
                screening_type_id=screening_type.id,
                status='due',
                created_at=datetime.now()
            )
            db.session.add(screening)
        
        return screening
    
    def _patient_has_trigger_condition(self, patient_conditions: List[PatientCondition], 
                                     trigger_conditions: List[str]) -> bool:
        """Check if patient has any of the trigger conditions"""
        if not trigger_conditions:
            return False
        
        condition_names = [condition.condition_name.lower() for condition in patient_conditions]
        
        for trigger in trigger_conditions:
            trigger_lower = trigger.lower()
            
            # Use fuzzy matching for condition names
            for condition_name in condition_names:
                if self.fuzzy_engine.calculate_similarity(trigger_lower, condition_name) > 0.8:
                    return True
        
        return False
    
    def _get_matching_condition_names(self, patient_conditions: List[PatientCondition],
                                    trigger_conditions: List[str]) -> str:
        """Get names of matching trigger conditions"""
        matching = []
        condition_names = [condition.condition_name for condition in patient_conditions]
        
        for trigger in trigger_conditions:
            for condition_name in condition_names:
                if self.fuzzy_engine.calculate_similarity(trigger.lower(), condition_name.lower()) > 0.8:
                    matching.append(condition_name)
        
        return ", ".join(matching)
    
    def _update_screening_from_document_evidence(self, screening: Screening, 
                                               document: FHIRDocument, confidence: float):
        """Update screening status based on document evidence"""
        try:
            # Document provides evidence of screening completion
            screening.status = 'complete'
            screening.last_completed_date = document.document_date or datetime.now().date()
            screening.last_updated = datetime.now()
            screening.confidence_score = confidence
            screening.notes = f"Completed based on document: {document.title} (confidence: {confidence:.2f})"
            
            # Calculate next due date based on frequency
            if screening.screening_type.frequency_value:
                screening.next_due_date = self._calculate_next_due_date_from_completion(
                    screening.last_completed_date,
                    screening.screening_type.frequency_value,
                    screening.screening_type.frequency_unit
                )
                
        except Exception as e:
            logger.error(f"Error updating screening from document evidence: {str(e)}")
    
    def _calculate_screening_status_from_documents(self, patient: Patient, screening_type: ScreeningType) -> str:
        """Calculate screening status based on document evidence"""
        try:
            # Look for recent documents that indicate screening completion
            keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
            
            if not keywords:
                return 'due'  # No keywords to match against
            
            # Search patient's documents for screening keywords within frequency period
            cutoff_date = datetime.now() - timedelta(days=screening_type.frequency_months * 30) if screening_type.frequency_months else datetime.now() - timedelta(days=365)
            
            recent_documents = FHIRDocument.query.filter_by(
                patient_id=patient.id
            ).filter(
                FHIRDocument.document_date >= cutoff_date
            ).all()
            
            for document in recent_documents:
                if self._document_contains_screening_keywords(document, keywords):
                    # Found evidence of completion
                    return 'complete'
            
            # No recent evidence found
            return 'due'
            
        except Exception as e:
            logger.error(f"Error calculating screening status from documents: {str(e)}")
            return 'due'
    
    def _document_contains_screening_keywords(self, document: FHIRDocument, keywords: List[str]) -> bool:
        """Check if document contains screening keywords"""
        text_to_search = f"{document.title or ''} {document.extracted_text or ''}".lower()
        
        for keyword in keywords:
            if self.fuzzy_engine.calculate_similarity(keyword.lower(), text_to_search) > 0.6:
                return True
        
        return False
    
    def _calculate_screening_priority(self, screening: Screening) -> int:
        """Calculate screening priority score (higher = more important)"""
        priority = 5  # Base priority
        
        # Higher priority for overdue screenings
        if screening.status == 'due':
            priority += 10
        elif screening.status == 'due_soon':
            priority += 5
        
        # Adjust based on screening type importance (could be configured)
        screening_name = screening.screening_type.name.lower()
        if any(term in screening_name for term in ['cancer', 'mammogram', 'colonoscopy']):
            priority += 5
        
        return priority
    
    def _calculate_next_due_date(self, screening: Screening) -> Optional[str]:
        """Calculate when screening is next due"""
        try:
            if not screening.last_completed_date or not screening.screening_type.frequency_value:
                return None
            
            next_due = self._calculate_next_due_date_from_completion(
                screening.last_completed_date,
                screening.screening_type.frequency_value,
                screening.screening_type.frequency_unit
            )
            
            return next_due.isoformat()
            
        except Exception as e:
            logger.error(f"Error calculating next due date: {str(e)}")
            return None
    
    def _calculate_next_due_date_from_completion(self, completion_date: date, 
                                               frequency_value: int, frequency_unit: str) -> date:
        """Calculate next due date from completion date and frequency"""
        if frequency_unit == 'years':
            return completion_date.replace(year=completion_date.year + frequency_value)
        elif frequency_unit == 'months':
            from dateutil.relativedelta import relativedelta
            return completion_date + relativedelta(months=frequency_value)
        elif frequency_unit == 'days':
            return completion_date + timedelta(days=frequency_value)
        else:
            # Default to annual
            return completion_date.replace(year=completion_date.year + 1)
    
    def get_integration_statistics(self) -> Dict[str, Any]:
        """Get integration processing statistics"""
        return {
            **self.integration_stats,
            'organization_id': self.organization_id,
            'timestamp': datetime.now().isoformat()
        }