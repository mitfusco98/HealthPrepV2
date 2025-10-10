"""
Selective refresh system for EMR synchronization
Implements intelligent change detection and targeted screening regeneration
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional
from sqlalchemy import and_, or_
from models import (
    Patient, Screening, ScreeningType, Document, 
    PrepSheetSettings, PatientCondition, db
)
from core.criteria import EligibilityCriteria
# from core.screening_engine import ScreeningEngine  # Will implement when needed

class SelectiveRefreshManager:
    """
    Manages selective refreshing of screening data based on detected changes
    Prevents universal refreshes by targeting only affected screening types
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # self.screening_engine = ScreeningEngine()  # Will implement when needed
        self.change_tracker = ChangeTracker()
        self.criteria = EligibilityCriteria()
        
    def sync_emr_changes(self, emr_changes: Dict) -> Dict:
        """
        Main entry point for EMR synchronization with selective refresh
        
        Args:
            emr_changes: Dictionary containing EMR change data
            
        Returns:
            Dictionary with sync results and affected screenings
        """
        try:
            self.logger.info("Starting EMR sync with selective refresh")
            
            # Track all changes
            detected_changes = self.change_tracker.detect_changes(emr_changes)
            
            if not detected_changes['has_changes']:
                self.logger.info("No changes detected, skipping refresh")
                return {'success': True, 'message': 'No changes detected', 'affected_screenings': 0}
            
            # Identify affected screening types
            affected_screening_types = self._identify_affected_screening_types(detected_changes)
            
            # Get affected patients based on changes
            affected_patients = self._identify_affected_patients(detected_changes)
            
            # Perform selective regeneration
            regeneration_results = self._perform_selective_regeneration(
                affected_screening_types, 
                affected_patients,
                detected_changes
            )
            
            # Log results
            self.logger.info(f"Selective refresh completed: {regeneration_results['total_regenerated']} screenings updated")
            
            return {
                'success': True,
                'affected_screening_types': len(affected_screening_types),
                'affected_patients': len(affected_patients),
                'total_regenerated': regeneration_results['total_regenerated'],
                'preserved_screenings': regeneration_results['preserved_screenings'],
                'changes_detected': detected_changes
            }
            
        except Exception as e:
            self.logger.error(f"Error during selective EMR sync: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _identify_affected_screening_types(self, changes: Dict) -> Set[int]:
        """Identify which screening types are affected by the changes"""
        affected_types = set()
        
        # Direct screening type changes
        if changes['screening_types']['modified']:
            affected_types.update(changes['screening_types']['modified'])
        
        if changes['screening_types']['added']:
            affected_types.update(changes['screening_types']['added'])
        
        # Document changes affect screening types with matching keywords
        if changes['documents']['added'] or changes['documents']['removed']:
            # Get all screening types to check keyword matches
            all_screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            for screening_type in all_screening_types:
                if self._screening_type_affected_by_documents(screening_type, changes['documents']):
                    affected_types.add(screening_type.id)
        
        # Patient condition changes affect screening types with trigger conditions
        if changes['patient_conditions']['modified']:
            condition_codes = [c['condition_code'] for c in changes['patient_conditions']['modified']]
            screening_types_with_triggers = ScreeningType.query.filter(
                ScreeningType.trigger_conditions != None
            ).all()
            
            for screening_type in screening_types_with_triggers:
                if self._screening_type_affected_by_conditions(screening_type, condition_codes):
                    affected_types.add(screening_type.id)
        
        return affected_types
    
    def _identify_affected_patients(self, changes: Dict) -> Set[int]:
        """Identify which patients are affected by the changes"""
        affected_patients = set()
        
        # Patients with new/modified documents
        if changes['documents']['added']:
            patient_ids = [doc['patient_id'] for doc in changes['documents']['added']]
            affected_patients.update(patient_ids)
        
        if changes['documents']['removed']:
            patient_ids = [doc['patient_id'] for doc in changes['documents']['removed']]
            affected_patients.update(patient_ids)
        
        # Patients with modified conditions
        if changes['patient_conditions']['modified']:
            patient_ids = [c['patient_id'] for c in changes['patient_conditions']['modified']]
            affected_patients.update(patient_ids)
        
        # Patients with demographic changes that affect eligibility
        if changes['patients']['modified']:
            patient_ids = [p['patient_id'] for p in changes['patients']['modified']]
            affected_patients.update(patient_ids)
        
        return affected_patients
    
    def _perform_selective_regeneration(self, affected_screening_types: Set[int], 
                                      affected_patients: Set[int], 
                                      changes: Dict) -> Dict:
        """Perform targeted regeneration of affected screenings"""
        regenerated_count = 0
        preserved_count = 0
        
        try:
            # Get all current screenings
            all_screenings = Screening.query.all()
            
            for screening in all_screenings:
                should_regenerate = self._should_regenerate_screening(
                    screening, affected_screening_types, affected_patients, changes
                )
                
                if should_regenerate:
                    # Regenerate this screening
                    self._regenerate_screening(screening)
                    regenerated_count += 1
                    self.logger.debug(f"Regenerated screening {screening.id} for patient {screening.patient_id}")
                else:
                    # Preserve existing screening
                    preserved_count += 1
            
            # Handle new screening types - generate screenings for all eligible patients
            if changes['screening_types']['added']:
                new_screenings = self._generate_screenings_for_new_types(
                    changes['screening_types']['added']
                )
                regenerated_count += len(new_screenings)
            
            # Clean up screenings for deleted screening types
            if changes['screening_types']['deleted']:
                deleted_screenings = self._clean_up_deleted_screening_types(
                    changes['screening_types']['deleted']
                )
                self.logger.info(f"Cleaned up {deleted_screenings} screenings for deleted types")
            
            db.session.commit()
            
            return {
                'total_regenerated': regenerated_count,
                'preserved_screenings': preserved_count,
                'success': True
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during selective regeneration: {str(e)}")
            raise
    
    def _should_regenerate_screening(self, screening: Screening, 
                                   affected_types: Set[int], 
                                   affected_patients: Set[int],
                                   changes: Dict) -> bool:
        """Determine if a screening should be regenerated based on changes"""
        
        # Check if screening type was modified
        if hasattr(screening, 'screening_type_id') and screening.screening_type_id in affected_types:
            return True
        
        # Check if patient was affected by changes
        if screening.patient_id in affected_patients:
            return True
        
        # Check if screening is potentially affected by document changes
        if changes['documents']['added'] or changes['documents']['removed']:
            # Check if this screening's keywords would match new/removed documents
            if hasattr(screening, 'screening_type') and self._screening_affected_by_document_changes(screening, changes['documents']):
                return True
        
        return False
    
    def _regenerate_screening(self, screening: Screening):
        """Regenerate a single screening using basic logic"""
        try:
            # Basic screening regeneration logic
            # In production, this would use a full screening engine
            
            # Update timestamp to mark as refreshed
            screening.updated_at = datetime.utcnow()
            
            # Basic status determination based on dates
            if hasattr(screening, 'last_completed_date') and screening.last_completed_date:
                from datetime import date
                from dateutil.relativedelta import relativedelta
                
                # Check if due based on frequency
                if hasattr(screening.screening_type, 'frequency_value') and screening.screening_type.frequency_value:
                    frequency_months = getattr(screening.screening_type, 'frequency_value', 12)
                    frequency_unit = getattr(screening.screening_type, 'frequency_unit', 'months')
                    
                    if frequency_unit == 'years':
                        next_due = screening.last_completed_date + relativedelta(years=frequency_months)
                    else:
                        next_due = screening.last_completed_date + relativedelta(months=frequency_months)
                    
                    if hasattr(screening, 'next_due_date'):
                        screening.next_due_date = next_due
                    
                    # Update status based on due date
                    today = date.today()
                    if next_due <= today:
                        screening.status = 'due'
                    elif next_due <= today + relativedelta(months=1):
                        screening.status = 'due_soon'
                    else:
                        screening.status = 'complete'
                
        except Exception as e:
            self.logger.error(f"Error regenerating screening {screening.id}: {str(e)}")
            raise
    
    def _screening_type_affected_by_documents(self, screening_type: ScreeningType, 
                                            document_changes: Dict) -> bool:
        """Check if a screening type is affected by document changes"""
        keywords = screening_type.keywords_list
        if not keywords:
            return False
        
        # Check if any new/removed documents match this screening type's keywords
        all_docs = document_changes.get('added', []) + document_changes.get('removed', [])
        
        for doc in all_docs:
            doc_text = doc.get('content', '').lower()
            for keyword in keywords:
                if keyword.lower() in doc_text:
                    return True
        
        return False
    
    def _screening_type_affected_by_conditions(self, screening_type: ScreeningType, 
                                             condition_codes: List[str]) -> bool:
        """Check if a screening type is affected by condition changes"""
        trigger_conditions = screening_type.trigger_conditions_list
        if not trigger_conditions:
            return False
        
        # Check if any modified conditions match trigger conditions
        for condition_code in condition_codes:
            if condition_code in trigger_conditions:
                return True
        
        return False
    
    def _screening_affected_by_document_changes(self, screening: Screening, 
                                              document_changes: Dict) -> bool:
        """Check if a specific screening is affected by document changes"""
        # Get documents associated with this patient
        patient_docs = document_changes.get('added', []) + document_changes.get('removed', [])
        patient_docs = [d for d in patient_docs if d.get('patient_id') == screening.patient_id]
        
        if not patient_docs:
            return False
        
        # Check if screening type keywords match any of the patient's changed documents
        return self._screening_type_affected_by_documents(screening.screening_type, {'added': patient_docs})
    
    def _generate_screenings_for_new_types(self, new_screening_type_ids: List[int]) -> List[Screening]:
        """Generate screenings for all eligible patients for new screening types"""
        new_screenings = []
        
        for type_id in new_screening_type_ids:
            screening_type = ScreeningType.query.get(type_id)
            if not screening_type:
                continue
            
            # Get all patients from the same organization
            patients = Patient.query.filter_by(org_id=screening_type.org_id).all()
            
            for patient in patients:
                # Use full eligibility criteria system (age, gender, trigger conditions, keywords)
                if self.criteria.is_patient_eligible(patient, screening_type):
                    # Create new screening
                    screening = Screening()
                    screening.patient_id = patient.id
                    screening.screening_type_id = screening_type.id
                    screening.org_id = patient.org_id
                    screening.status = 'due'
                    screening.created_at = datetime.utcnow()
                    screening.updated_at = datetime.utcnow()
                    
                    db.session.add(screening)
                    new_screenings.append(screening)
                    
                    self.logger.debug(
                        f"Created screening for patient {patient.id} - "
                        f"screening type '{screening_type.name}' (includes trigger conditions)"
                    )
        
        return new_screenings
    
    def _clean_up_deleted_screening_types(self, deleted_type_ids: List[int]) -> int:
        """Clean up screenings for deleted screening types"""
        deleted_count = 0
        
        for type_id in deleted_type_ids:
            # Remove or deactivate screenings for deleted types
            screenings = Screening.query.filter_by(screening_type_id=type_id).all()
            
            for screening in screenings:
                db.session.delete(screening)
                deleted_count += 1
        
        return deleted_count


class ChangeTracker:
    """
    Tracks and analyzes changes from EMR synchronization
    Identifies what has been modified, added, or removed
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_changes(self, emr_data: Dict) -> Dict:
        """
        Detect changes from EMR synchronization data
        
        Returns comprehensive change analysis
        """
        changes = {
            'has_changes': False,
            'screening_types': {'added': [], 'modified': [], 'deleted': []},
            'documents': {'added': [], 'removed': [], 'modified': []},
            'patients': {'added': [], 'modified': []},
            'patient_conditions': {'added': [], 'modified': [], 'removed': []}
        }
        
        # Detect screening type changes
        if 'screening_types' in emr_data:
            screening_changes = self._detect_screening_type_changes(emr_data['screening_types'])
            changes['screening_types'].update(screening_changes)
            if any(screening_changes.values()):
                changes['has_changes'] = True
        
        # Detect document changes
        if 'documents' in emr_data:
            document_changes = self._detect_document_changes(emr_data['documents'])
            changes['documents'].update(document_changes)
            if any(document_changes.values()):
                changes['has_changes'] = True
        
        # Detect patient changes
        if 'patients' in emr_data:
            patient_changes = self._detect_patient_changes(emr_data['patients'])
            changes['patients'].update(patient_changes)
            if any(patient_changes.values()):
                changes['has_changes'] = True
        
        # Detect patient condition changes
        if 'patient_conditions' in emr_data:
            condition_changes = self._detect_condition_changes(emr_data['patient_conditions'])
            changes['patient_conditions'].update(condition_changes)
            if any(condition_changes.values()):
                changes['has_changes'] = True
        
        self.logger.info(f"Change detection completed: {changes['has_changes']}")
        return changes
    
    def _detect_screening_type_changes(self, screening_type_data: List[Dict]) -> Dict:
        """Detect changes to screening types"""
        changes = {'added': [], 'modified': [], 'deleted': []}
        
        # Compare with existing screening types
        existing_types = {st.id: st for st in ScreeningType.query.all()}
        
        for type_data in screening_type_data:
            type_id = type_data.get('id')
            
            if type_id and type_id in existing_types:
                # Check if modified
                if self._screening_type_modified(existing_types[type_id], type_data):
                    changes['modified'].append(type_id)
            else:
                # New screening type
                changes['added'].append(type_id)
        
        # Check for deleted types (types that exist locally but not in EMR data)
        emr_type_ids = {t.get('id') for t in screening_type_data if t.get('id')}
        for existing_id in existing_types:
            if existing_id not in emr_type_ids:
                changes['deleted'].append(existing_id)
        
        return changes
    
    def _detect_document_changes(self, document_data: List[Dict]) -> Dict:
        """Detect changes to patient documents"""
        changes = {'added': [], 'removed': [], 'modified': []}
        
        # Compare with existing documents
        existing_docs = {doc.id: doc for doc in Document.query.all()}
        
        for doc_data in document_data:
            doc_id = doc_data.get('id')
            
            if doc_id and doc_id in existing_docs:
                # Check if modified
                if self._document_modified(existing_docs[doc_id], doc_data):
                    changes['modified'].append(doc_data)
            else:
                # New document
                changes['added'].append(doc_data)
        
        # Check for removed documents
        emr_doc_ids = {d.get('id') for d in document_data if d.get('id')}
        for existing_id, existing_doc in existing_docs.items():
            if existing_id not in emr_doc_ids:
                changes['removed'].append({
                    'id': existing_id,
                    'patient_id': existing_doc.patient_id,
                    'document_type': existing_doc.document_type
                })
        
        return changes
    
    def _detect_patient_changes(self, patient_data: List[Dict]) -> Dict:
        """Detect changes to patient information"""
        changes = {'added': [], 'modified': []}
        
        existing_patients = {p.id: p for p in Patient.query.all()}
        
        for patient_data_item in patient_data:
            patient_id = patient_data_item.get('id')
            
            if patient_id and patient_id in existing_patients:
                # Check if modified (demographics that affect eligibility)
                if self._patient_modified(existing_patients[patient_id], patient_data_item):
                    changes['modified'].append(patient_data_item)
            else:
                # New patient
                changes['added'].append(patient_data_item)
        
        return changes
    
    def _detect_condition_changes(self, condition_data: List[Dict]) -> Dict:
        """Detect changes to patient conditions"""
        changes = {'added': [], 'modified': [], 'removed': []}
        
        # Implementation for condition change detection
        # This would compare incoming condition data with existing PatientCondition records
        
        return changes
    
    def _screening_type_modified(self, existing_type: ScreeningType, new_data: Dict) -> bool:
        """Check if screening type has been modified"""
        # Check key fields that affect screening eligibility
        fields_to_check = ['keywords', 'eligible_genders', 'min_age', 'max_age', 
                          'frequency_years', 'trigger_conditions']
        
        for field in fields_to_check:
            if field in new_data:
                existing_value = getattr(existing_type, field, None)
                new_value = new_data[field]
                
                if existing_value != new_value:
                    return True
        
        return False
    
    def _document_modified(self, existing_doc: Document, new_data: Dict) -> bool:
        """Check if document has been modified"""
        # Check if document content or metadata has changed
        fields_to_check = ['content', 'document_date', 'document_type']
        
        for field in fields_to_check:
            if field in new_data:
                existing_value = getattr(existing_doc, field, None)
                new_value = new_data[field]
                
                if existing_value != new_value:
                    return True
        
        return False
    
    def _patient_modified(self, existing_patient: Patient, new_data: Dict) -> bool:
        """Check if patient demographics affecting eligibility have changed"""
        # Check fields that affect screening eligibility
        fields_to_check = ['date_of_birth', 'gender']
        
        for field in fields_to_check:
            if field in new_data:
                existing_value = getattr(existing_patient, field, None)
                new_value = new_data[field]
                
                if existing_value != new_value:
                    return True
        
        return False