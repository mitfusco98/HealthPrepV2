"""
Screening eligibility and frequency logic
"""
import json
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from models import Patient, ScreeningType, PatientCondition

logger = logging.getLogger(__name__)

class EligibilityCriteria:
    """Handles screening eligibility determination based on patient demographics and conditions"""
    
    def __init__(self):
        pass
    
    def is_eligible(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """
        Determine if a patient is eligible for a specific screening type
        Based on age, gender, and trigger conditions
        """
        try:
            # Check age eligibility
            if not self._check_age_eligibility(patient, screening_type):
                logger.debug(f"Patient {patient.id} age {patient.age} not eligible for {screening_type.name}")
                return False
            
            # Check gender eligibility
            if not self._check_gender_eligibility(patient, screening_type):
                logger.debug(f"Patient {patient.id} gender {patient.gender} not eligible for {screening_type.name}")
                return False
            
            # Check trigger conditions if specified
            if not self._check_trigger_conditions(patient, screening_type):
                logger.debug(f"Patient {patient.id} does not meet trigger conditions for {screening_type.name}")
                return False
            
            logger.debug(f"Patient {patient.id} is eligible for {screening_type.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking eligibility for patient {patient.id}, screening {screening_type.name}: {str(e)}")
            return False
    
    def _check_age_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient age meets screening criteria"""
        patient_age = patient.age
        
        if screening_type.min_age is not None and patient_age < screening_type.min_age:
            return False
        
        if screening_type.max_age is not None and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient gender meets screening criteria"""
        if not screening_type.gender_restrictions:
            return True
        
        patient_gender = patient.gender.lower()
        allowed_genders = [g.strip().lower() for g in screening_type.gender_restrictions.split(',')]
        
        return patient_gender in allowed_genders
    
    def _check_trigger_conditions(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient has required trigger conditions"""
        if not screening_type.trigger_conditions:
            return True  # No trigger conditions required
        
        try:
            trigger_conditions = json.loads(screening_type.trigger_conditions)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid trigger conditions JSON for screening type {screening_type.id}")
            return True
        
        if not trigger_conditions:
            return True
        
        # Get patient conditions
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        patient_condition_codes = {condition.condition_code for condition in patient_conditions if condition.condition_code}
        patient_condition_names = {condition.condition_name.lower() for condition in patient_conditions}
        
        # Check if any trigger condition is met
        for trigger in trigger_conditions:
            trigger_lower = trigger.lower()
            
            # Check by condition code
            if trigger in patient_condition_codes:
                return True
            
            # Check by condition name (fuzzy matching)
            for condition_name in patient_condition_names:
                if trigger_lower in condition_name or condition_name in trigger_lower:
                    return True
        
        return False
    
    def get_variant_criteria(self, patient: Patient, screening_type: ScreeningType) -> Optional[Dict[str, Any]]:
        """
        Get variant criteria for screening type based on patient conditions
        Returns modified frequency/requirements for patients with trigger conditions
        """
        if not screening_type.trigger_conditions:
            return None
        
        try:
            trigger_conditions = json.loads(screening_type.trigger_conditions)
        except (json.JSONDecodeError, TypeError):
            return None
        
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        # Define variant rules for common conditions
        variant_rules = {
            'diabetes': {'frequency_months': 3, 'description': 'Diabetic patients require more frequent monitoring'},
            'hypertension': {'frequency_months': 6, 'description': 'Hypertensive patients need regular monitoring'},
            'high cholesterol': {'frequency_months': 6, 'description': 'Patients with dyslipidemia need frequent lipid checks'},
            'heart disease': {'frequency_months': 6, 'description': 'Cardiac patients require closer monitoring'},
            'family history of cancer': {'frequency_months': 6, 'description': 'Family history requires more frequent screening'}
        }
        
        # Check if patient has any conditions that modify screening frequency
        for condition in patient_conditions:
            condition_name_lower = condition.condition_name.lower()
            
            for rule_condition, modifications in variant_rules.items():
                if rule_condition in condition_name_lower:
                    return {
                        'original_frequency': screening_type.frequency_months,
                        'modified_frequency': modifications['frequency_months'],
                        'reason': modifications['description'],
                        'trigger_condition': condition.condition_name
                    }
        
        return None
    
    def calculate_next_due_date(self, last_completed_date: date, screening_type: ScreeningType, 
                              patient: Optional[Patient] = None) -> date:
        """Calculate next due date considering variant criteria"""
        
        frequency_months = screening_type.frequency_months
        
        # Check for variant criteria if patient provided
        if patient:
            variant_criteria = self.get_variant_criteria(patient, screening_type)
            if variant_criteria:
                frequency_months = variant_criteria['modified_frequency']
        
        if screening_type.frequency_unit == 'months':
            return last_completed_date + relativedelta(months=frequency_months)
        else:  # years
            return last_completed_date + relativedelta(years=frequency_months)
    
    def get_screening_urgency(self, next_due_date: date) -> Dict[str, Any]:
        """Determine screening urgency based on due date"""
        today = date.today()
        days_until_due = (next_due_date - today).days
        
        if days_until_due <= 0:
            return {
                'status': 'Overdue',
                'urgency': 'high',
                'days': abs(days_until_due),
                'message': f'Overdue by {abs(days_until_due)} days'
            }
        elif days_until_due <= 30:
            return {
                'status': 'Due Soon',
                'urgency': 'medium',
                'days': days_until_due,
                'message': f'Due in {days_until_due} days'
            }
        elif days_until_due <= 90:
            return {
                'status': 'Upcoming',
                'urgency': 'low',
                'days': days_until_due,
                'message': f'Due in {days_until_due} days'
            }
        else:
            return {
                'status': 'Complete',
                'urgency': 'none',
                'days': days_until_due,
                'message': f'Not due for {days_until_due} days'
            }
    
    def batch_eligibility_check(self, patients: List[Patient], screening_type: ScreeningType) -> Dict[int, bool]:
        """Check eligibility for multiple patients efficiently"""
        eligibility_results = {}
        
        for patient in patients:
            try:
                eligibility_results[patient.id] = self.is_eligible(patient, screening_type)
            except Exception as e:
                logger.error(f"Error checking eligibility for patient {patient.id}: {str(e)}")
                eligibility_results[patient.id] = False
        
        return eligibility_results
