"""
Screening eligibility and frequency logic
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from dateutil.relativedelta import relativedelta
from models import Patient, ScreeningType, Screening, MedicalDocument

logger = logging.getLogger(__name__)

class EligibilityCriteria:
    """Handles screening eligibility determination"""
    
    def check_eligibility(self, patient: Patient, screening_type: ScreeningType, 
                         conditions: List[str]) -> List[Dict[str, Any]]:
        """
        Check if patient is eligible for screening type
        Returns list of eligible variants (including base screening)
        """
        eligible_variants = []
        
        # Check basic eligibility criteria
        if self._meets_basic_criteria(patient, screening_type):
            # Add base screening
            base_variant = {
                'type': 'base',
                'frequency_number': screening_type.frequency_number,
                'frequency_unit': screening_type.frequency_unit,
                'trigger_condition': None
            }
            eligible_variants.append(base_variant)
            
            # Check for trigger condition variants
            if screening_type.trigger_conditions_list:
                for trigger_condition in screening_type.trigger_conditions_list:
                    if self._has_trigger_condition(conditions, trigger_condition):
                        variant = self._get_trigger_variant(screening_type, trigger_condition)
                        if variant:
                            eligible_variants.append(variant)
        
        return eligible_variants
    
    def _meets_basic_criteria(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient meets basic eligibility criteria"""
        
        # Gender criteria
        if screening_type.gender_criteria and screening_type.gender_criteria != 'Both':
            if patient.gender.upper() != screening_type.gender_criteria.upper():
                return False
        
        # Age criteria
        patient_age = patient.age
        
        if screening_type.min_age and patient_age < screening_type.min_age:
            return False
        
        if screening_type.max_age and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _has_trigger_condition(self, patient_conditions: List[str], trigger_condition: str) -> bool:
        """Check if patient has the trigger condition"""
        trigger_lower = trigger_condition.lower()
        
        for condition in patient_conditions:
            condition_lower = condition.lower()
            
            # Direct match or partial match for common variations
            if trigger_lower in condition_lower or condition_lower in trigger_lower:
                return True
            
            # Check for common medical condition variations
            if self._condition_matches(condition_lower, trigger_lower):
                return True
        
        return False
    
    def _condition_matches(self, patient_condition: str, trigger_condition: str) -> bool:
        """Check if conditions match considering medical terminology"""
        
        # Diabetes variations
        if 'diabetes' in trigger_condition:
            diabetes_terms = ['diabetes', 'diabetic', 'dm', 'diabetes mellitus']
            return any(term in patient_condition for term in diabetes_terms)
        
        # Hypertension variations
        if 'hypertension' in trigger_condition:
            htn_terms = ['hypertension', 'high blood pressure', 'htn', 'elevated bp']
            return any(term in patient_condition for term in htn_terms)
        
        # Hyperlipidemia variations
        if 'hyperlipidemia' in trigger_condition or 'cholesterol' in trigger_condition:
            cholesterol_terms = ['hyperlipidemia', 'high cholesterol', 'dyslipidemia', 'elevated cholesterol']
            return any(term in patient_condition for term in cholesterol_terms)
        
        return False
    
    def _get_trigger_variant(self, screening_type: ScreeningType, trigger_condition: str) -> Optional[Dict[str, Any]]:
        """Get variant configuration for trigger condition"""
        
        # Define condition-specific frequency modifications
        condition_variants = {
            'diabetes': {
                'a1c': {'frequency_number': 3, 'frequency_unit': 'months'},
                'cholesterol': {'frequency_number': 6, 'frequency_unit': 'months'},
                'eye exam': {'frequency_number': 1, 'frequency_unit': 'years'}
            },
            'hypertension': {
                'blood pressure': {'frequency_number': 3, 'frequency_unit': 'months'},
                'cholesterol': {'frequency_number': 6, 'frequency_unit': 'months'}
            },
            'hyperlipidemia': {
                'cholesterol': {'frequency_number': 6, 'frequency_unit': 'months'}
            }
        }
        
        # Match trigger condition to variants
        for condition_key, variants in condition_variants.items():
            if condition_key in trigger_condition.lower():
                for screening_keyword in screening_type.keywords_list:
                    for variant_key, variant_config in variants.items():
                        if variant_key in screening_keyword.lower():
                            return {
                                'type': 'trigger',
                                'trigger_condition': trigger_condition,
                                'frequency_number': variant_config['frequency_number'],
                                'frequency_unit': variant_config['frequency_unit'],
                                'additional_keywords': []
                            }
        
        return None

class StatusCalculator:
    """Calculates screening status based on completion and frequency"""
    
    def calculate_status(self, screening: Screening, matched_documents: List[MedicalDocument], 
                        variant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate screening status and dates
        """
        status_info = {
            'status': 'Due',
            'last_completed': None,
            'next_due': None,
            'days_until_due': None
        }
        
        if not matched_documents:
            return status_info
        
        # Find most recent document
        latest_doc = self._find_latest_document(matched_documents)
        if not latest_doc or not latest_doc.document_date:
            return status_info
        
        status_info['last_completed'] = latest_doc.document_date
        
        # Calculate next due date based on frequency
        frequency_number = variant.get('frequency_number', screening.screening_type.frequency_number)
        frequency_unit = variant.get('frequency_unit', screening.screening_type.frequency_unit)
        
        next_due = self._calculate_next_due_date(latest_doc.document_date, frequency_number, frequency_unit)
        status_info['next_due'] = next_due
        
        # Calculate status based on current date
        today = date.today()
        
        if next_due <= today:
            status_info['status'] = 'Due'
            status_info['days_until_due'] = 0
        elif next_due <= today + timedelta(days=30):  # Due within 30 days
            status_info['status'] = 'Due Soon'
            status_info['days_until_due'] = (next_due - today).days
        else:
            status_info['status'] = 'Complete'
            status_info['days_until_due'] = (next_due - today).days
        
        return status_info
    
    def _find_latest_document(self, documents: List[MedicalDocument]) -> Optional[MedicalDocument]:
        """Find the document with the most recent date"""
        if not documents:
            return None
        
        # Filter documents with valid dates
        dated_docs = [doc for doc in documents if doc.document_date]
        if not dated_docs:
            return None
        
        # Return document with latest date
        return max(dated_docs, key=lambda doc: doc.document_date)
    
    def _calculate_next_due_date(self, last_date: date, frequency_number: int, frequency_unit: str) -> date:
        """Calculate next due date based on frequency"""
        if frequency_unit.lower() in ['year', 'years']:
            return last_date + relativedelta(years=frequency_number)
        elif frequency_unit.lower() in ['month', 'months']:
            return last_date + relativedelta(months=frequency_number)
        elif frequency_unit.lower() in ['day', 'days']:
            return last_date + timedelta(days=frequency_number)
        elif frequency_unit.lower() in ['week', 'weeks']:
            return last_date + timedelta(weeks=frequency_number)
        else:
            # Default to years
            return last_date + relativedelta(years=frequency_number)
    
    def get_status_summary(self, screenings: List[Screening]) -> Dict[str, int]:
        """Get summary of screening statuses"""
        summary = {
            'Complete': 0,
            'Due': 0,
            'Due Soon': 0,
            'Total': len(screenings)
        }
        
        for screening in screenings:
            status = screening.status or 'Due'
            if status in summary:
                summary[status] += 1
        
        return summary
