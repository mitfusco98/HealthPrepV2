"""
Screening eligibility and frequency logic
Determines if patients are eligible for specific screenings
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional
from models import Patient, ScreeningType, PatientCondition
from core.matcher import FuzzyMatcher

class EligibilityCriteria:
    """Handles screening eligibility determination"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
    
    def is_eligible(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """
        Determine if a patient is eligible for a specific screening type
        """
        # Check age eligibility
        if not self._check_age_eligibility(patient, screening_type):
            return False
        
        # Check gender eligibility
        if not self._check_gender_eligibility(patient, screening_type):
            return False
        
        # Check condition-based triggers
        if not self._check_condition_triggers(patient, screening_type):
            return False
        
        return True
    
    def _check_age_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient age meets screening criteria"""
        if not patient.date_of_birth:
            return True  # Assume eligible if DOB unknown
        
        # Calculate current age
        today = date.today()
        age = today.year - patient.date_of_birth.year
        
        # Adjust for birthday not yet occurred this year
        if today < date(today.year, patient.date_of_birth.month, patient.date_of_birth.day):
            age -= 1
        
        # Check minimum age
        if screening_type.min_age is not None and age < screening_type.min_age:
            return False
        
        # Check maximum age
        if screening_type.max_age is not None and age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient gender meets screening criteria"""
        if not screening_type.gender:
            return True  # No gender restriction
        
        if not patient.gender:
            return True  # Assume eligible if gender unknown
        
        return patient.gender.upper() == screening_type.gender.upper()
    
    def _check_condition_triggers(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient has conditions that trigger this screening"""
        if not screening_type.trigger_conditions:
            return True  # No specific conditions required
        
        # Get patient conditions
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        condition_names = [cond.condition_name for cond in patient_conditions if cond.condition_name]
        condition_codes = [cond.condition_code for cond in patient_conditions if cond.condition_code]
        
        all_patient_conditions = condition_names + condition_codes
        
        # Use fuzzy matcher to check condition matches
        return self.matcher.find_condition_matches(all_patient_conditions, screening_type.trigger_conditions)
    
    def get_screening_frequency_description(self, screening_type: ScreeningType) -> str:
        """Get human-readable description of screening frequency"""
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return "As needed"
        
        unit = screening_type.frequency_unit
        number = screening_type.frequency_number
        
        if number == 1:
            return f"Every {unit[:-1]}"  # Remove 's' from plural
        else:
            return f"Every {number} {unit}"
    
    def calculate_next_screening_date(self, last_screening_date: Optional[date], 
                                    screening_type: ScreeningType) -> Optional[date]:
        """Calculate when the next screening should occur"""
        if not last_screening_date:
            return date.today()  # Due now if never done
        
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return None  # No specific frequency
        
        if screening_type.frequency_unit == 'years':
            return last_screening_date + relativedelta(years=screening_type.frequency_number)
        elif screening_type.frequency_unit == 'months':
            return last_screening_date + relativedelta(months=screening_type.frequency_number)
        else:  # days
            from datetime import timedelta
            return last_screening_date + timedelta(days=screening_type.frequency_number)
    
    def get_screening_status_color(self, status: str) -> str:
        """Get Bootstrap color class for screening status"""
        status_colors = {
            'Complete': 'success',
            'Due Soon': 'warning', 
            'Due': 'danger',
            'N/A': 'secondary'
        }
        return status_colors.get(status, 'secondary')
    
    def is_screening_overdue(self, next_due_date: Optional[date]) -> bool:
        """Check if a screening is overdue"""
        if not next_due_date:
            return False
        
        return next_due_date < date.today()
    
    def get_days_until_due(self, next_due_date: Optional[date]) -> Optional[int]:
        """Get number of days until screening is due"""
        if not next_due_date:
            return None
        
        return (next_due_date - date.today()).days
    
    def get_overdue_days(self, next_due_date: Optional[date]) -> Optional[int]:
        """Get number of days screening is overdue"""
        if not next_due_date:
            return None
        
        days_diff = (date.today() - next_due_date).days
        return days_diff if days_diff > 0 else None
    
    def get_eligibility_summary(self, patient: Patient, screening_type: ScreeningType) -> dict:
        """Get detailed eligibility information for a patient and screening type"""
        summary = {
            'is_eligible': True,
            'age_eligible': True,
            'gender_eligible': True,
            'condition_eligible': True,
            'reasons': []
        }
        
        # Check age
        if not self._check_age_eligibility(patient, screening_type):
            summary['is_eligible'] = False
            summary['age_eligible'] = False
            
            if patient.date_of_birth:
                age = date.today().year - patient.date_of_birth.year
                if screening_type.min_age and age < screening_type.min_age:
                    summary['reasons'].append(f"Patient age {age} is below minimum age {screening_type.min_age}")
                if screening_type.max_age and age > screening_type.max_age:
                    summary['reasons'].append(f"Patient age {age} is above maximum age {screening_type.max_age}")
        
        # Check gender
        if not self._check_gender_eligibility(patient, screening_type):
            summary['is_eligible'] = False
            summary['gender_eligible'] = False
            summary['reasons'].append(f"Screening is for {screening_type.gender} patients only")
        
        # Check conditions
        if not self._check_condition_triggers(patient, screening_type):
            summary['is_eligible'] = False
            summary['condition_eligible'] = False
            summary['reasons'].append("Patient does not have required trigger conditions")
        
        return summary
