"""
Screening eligibility and frequency logic.
Determines patient eligibility for screenings based on age, gender, and conditions.
"""

import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional

from models import Patient, ScreeningType, PatientCondition

class EligibilityCriteria:
    """Handles screening eligibility determination and frequency calculations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_eligible(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Determine if a patient is eligible for a screening type."""
        
        # Check if screening type is active
        if not screening_type.is_active:
            return False
        
        # Check age criteria
        if not self._check_age_eligibility(patient, screening_type):
            return False
        
        # Check gender criteria
        if not self._check_gender_eligibility(patient, screening_type):
            return False
        
        # Check trigger conditions if specified
        if not self._check_trigger_conditions(patient, screening_type):
            return False
        
        return True
    
    def _check_age_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient meets age criteria."""
        patient_age = patient.age
        
        # Check minimum age
        if screening_type.min_age is not None and patient_age < screening_type.min_age:
            return False
        
        # Check maximum age
        if screening_type.max_age is not None and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient meets gender criteria."""
        if screening_type.gender_restriction is None:
            return True
        
        return patient.gender == screening_type.gender_restriction
    
    def _check_trigger_conditions(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient has required trigger conditions."""
        trigger_conditions = screening_type.get_trigger_conditions_list()
        
        # If no trigger conditions specified, patient is eligible
        if not trigger_conditions:
            return True
        
        # Get patient's active conditions
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id, 
            is_active=True
        ).all()
        
        patient_condition_names = [c.condition_name.lower() for c in patient_conditions]
        
        # Check if patient has any of the trigger conditions
        for trigger_condition in trigger_conditions:
            trigger_lower = trigger_condition.lower().strip()
            if any(trigger_lower in condition for condition in patient_condition_names):
                return True
        
        return False
    
    def get_frequency_in_days(self, screening_type: ScreeningType) -> int:
        """Convert screening frequency to days."""
        if screening_type.frequency_unit == 'years':
            return screening_type.frequency_value * 365
        elif screening_type.frequency_unit == 'months':
            return screening_type.frequency_value * 30
        else:
            # Default to months if unit is unknown
            return screening_type.frequency_value * 30
    
    def calculate_next_due_date(self, last_completed_date: date, screening_type: ScreeningType) -> date:
        """Calculate when screening is next due."""
        if screening_type.frequency_unit == 'years':
            return last_completed_date + relativedelta(years=screening_type.frequency_value)
        else:  # months
            return last_completed_date + relativedelta(months=screening_type.frequency_value)
    
    def determine_screening_status(self, screening_type: ScreeningType, last_completed_date: Optional[date] = None) -> str:
        """Determine screening status based on last completion and frequency."""
        if last_completed_date is None:
            return 'Due'
        
        next_due_date = self.calculate_next_due_date(last_completed_date, screening_type)
        today = date.today()
        
        if next_due_date > today:
            return 'Complete'
        elif next_due_date <= today - relativedelta(months=3):  # 3 months overdue
            return 'Overdue'
        elif next_due_date <= today + relativedelta(days=30):  # Due within 30 days
            return 'Due Soon'
        else:
            return 'Due'
    
    def get_screening_variants(self, patient: Patient, screening_type: ScreeningType) -> dict:
        """Get screening variants based on patient conditions."""
        base_frequency = {
            'value': screening_type.frequency_value,
            'unit': screening_type.frequency_unit
        }
        
        # Check for condition-specific variants
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id, 
            is_active=True
        ).all()
        
        condition_names = [c.condition_name.lower() for c in patient_conditions]
        
        # Define variant rules (this could be moved to database configuration)
        variant_rules = {
            'a1c': {
                'diabetes': {'value': 3, 'unit': 'months'},  # Diabetics need A1C every 3 months
                'prediabetes': {'value': 6, 'unit': 'months'}
            },
            'lipid': {
                'diabetes': {'value': 6, 'unit': 'months'},
                'heart disease': {'value': 3, 'unit': 'months'}
            },
            'eye exam': {
                'diabetes': {'value': 12, 'unit': 'months'}  # Annual for diabetics
            }
        }
        
        screening_name = screening_type.name.lower()
        
        # Check if any variant rules apply
        for condition in condition_names:
            for screening_key, rules in variant_rules.items():
                if screening_key in screening_name:
                    for rule_condition, frequency in rules.items():
                        if rule_condition in condition:
                            return {
                                'base_frequency': base_frequency,
                                'variant_frequency': frequency,
                                'reason': f"Modified frequency due to {condition}",
                                'applied': True
                            }
        
        return {
            'base_frequency': base_frequency,
            'variant_frequency': base_frequency,
            'reason': 'Standard frequency applied',
            'applied': False
        }
    
    def validate_screening_criteria(self, screening_type: ScreeningType) -> dict:
        """Validate screening type criteria for completeness and logic."""
        issues = []
        warnings = []
        
        # Check required fields
        if not screening_type.name:
            issues.append("Screening name is required")
        
        if screening_type.frequency_value <= 0:
            issues.append("Frequency value must be positive")
        
        if screening_type.frequency_unit not in ['months', 'years']:
            issues.append("Frequency unit must be 'months' or 'years'")
        
        # Check age logic
        if (screening_type.min_age is not None and 
            screening_type.max_age is not None and 
            screening_type.min_age >= screening_type.max_age):
            issues.append("Minimum age must be less than maximum age")
        
        # Check for unreasonable age ranges
        if screening_type.min_age is not None and screening_type.min_age > 120:
            warnings.append("Minimum age seems unusually high")
        
        if screening_type.max_age is not None and screening_type.max_age < 0:
            issues.append("Maximum age cannot be negative")
        
        # Check keywords
        keywords = screening_type.get_keywords_list()
        if not keywords:
            warnings.append("No keywords defined - screening may not match documents")
        
        # Check for very short keywords that might cause false matches
        short_keywords = [k for k in keywords if len(k.strip()) < 3]
        if short_keywords:
            warnings.append(f"Very short keywords may cause false matches: {', '.join(short_keywords)}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'keyword_count': len(keywords),
            'has_age_restrictions': screening_type.min_age is not None or screening_type.max_age is not None,
            'has_gender_restrictions': screening_type.gender_restriction is not None,
            'has_trigger_conditions': len(screening_type.get_trigger_conditions_list()) > 0
        }
