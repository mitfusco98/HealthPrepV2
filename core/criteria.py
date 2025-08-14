"""
Screening eligibility and frequency logic
"""
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

class EligibilityCriteria:
    """Handles screening eligibility and frequency calculations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_patient_eligible(self, patient, screening_type):
        """Check if a patient is eligible for a specific screening type"""
        
        # Check age criteria
        if not self._check_age_eligibility(patient, screening_type):
            return False
        
        # Check gender criteria
        if not self._check_gender_eligibility(patient, screening_type):
            return False
        
        # Check trigger conditions
        if not self._check_trigger_conditions(patient, screening_type):
            return False
        
        return True
    
    def calculate_screening_status(self, screening_type, last_completed_date):
        """Calculate screening status based on frequency and last completion date"""
        if not last_completed_date:
            return 'due'
        
        if not screening_type.frequency_value or not screening_type.frequency_unit:
            return 'complete'  # No frequency defined, assume complete
        
        # Calculate next due date
        next_due_date = self._calculate_next_due_date(
            last_completed_date, 
            screening_type.frequency_value, 
            screening_type.frequency_unit
        )
        
        today = date.today()
        
        # Calculate due soon threshold (30 days before due date)
        due_soon_threshold = next_due_date - timedelta(days=30)
        
        if today >= next_due_date:
            return 'due'
        elif today >= due_soon_threshold:
            return 'due_soon'
        else:
            return 'complete'
    
    def _check_age_eligibility(self, patient, screening_type):
        """Check if patient age meets screening criteria"""
        if not screening_type.min_age and not screening_type.max_age:
            return True
        
        patient_age = patient.age
        
        if screening_type.min_age and patient_age < screening_type.min_age:
            return False
        
        if screening_type.max_age and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient, screening_type):
        """Check if patient gender meets screening criteria"""
        if not screening_type.gender:
            return True
        
        return patient.gender == screening_type.gender
    
    def _check_trigger_conditions(self, patient, screening_type):
        """Check if patient has required trigger conditions"""
        # Handle different screening categories
        screening_category = getattr(screening_type, 'screening_category', 'general')
        
        # General population screenings apply to all eligible patients
        if screening_category == 'general':
            return True
        
        # If no trigger conditions defined but category is conditional/risk_based, 
        # treat as general population screening
        if not screening_type.trigger_conditions_list:
            return screening_category == 'general'
        
        # Get patient conditions
        patient_conditions = [c.condition_name.lower() for c in patient.conditions if c.is_active]
        
        # Check if any trigger condition is met
        for trigger_condition in screening_type.trigger_conditions_list:
            trigger_condition = trigger_condition.lower().strip()
            
            # Check for exact matches or partial matches
            for patient_condition in patient_conditions:
                if (trigger_condition in patient_condition or 
                    patient_condition in trigger_condition):
                    return True
        
        # For conditional/risk_based screenings, patient must have trigger conditions
        # For general screenings, they apply regardless
        return screening_category == 'general'
    
    def _calculate_next_due_date(self, last_completed_date, frequency_value, frequency_unit):
        """Calculate the next due date based on frequency"""
        if frequency_unit == 'years':
            return last_completed_date + relativedelta(years=frequency_value)
        elif frequency_unit == 'months':
            return last_completed_date + relativedelta(months=frequency_value)
        else:
            # Default to years if unit is unclear
            return last_completed_date + relativedelta(years=frequency_value)
    
    def get_screening_schedule(self, patient, screening_type):
        """Get recommended screening schedule for a patient"""
        if not self.is_patient_eligible(patient, screening_type):
            return None
        
        schedule = {
            'screening_type': screening_type.name,
            'frequency': screening_type.frequency_display,
            'eligible': True,
            'eligibility_reasons': []
        }
        
        # Add eligibility details
        if screening_type.min_age or screening_type.max_age:
            age_range = f"Ages {screening_type.min_age or 'any'}-{screening_type.max_age or 'any'}"
            schedule['eligibility_reasons'].append(age_range)
        
        if screening_type.gender:
            gender_text = 'Male' if screening_type.gender == 'M' else 'Female'
            schedule['eligibility_reasons'].append(f"{gender_text} only")
        
        if screening_type.trigger_conditions_list:
            schedule['eligibility_reasons'].append(f"Requires: {', '.join(screening_type.trigger_conditions_list)}")
        
        return schedule
    
    def get_overdue_screenings(self, patient_id, days_overdue=30):
        """Get screenings that are overdue by specified number of days"""
        from models import Screening, ScreeningType
        
        overdue_screenings = []
        screenings = Screening.query.filter_by(patient_id=patient_id).join(ScreeningType).all()
        
        cutoff_date = date.today() - timedelta(days=days_overdue)
        
        for screening in screenings:
            if screening.status == 'due' and screening.last_completed_date:
                next_due = self._calculate_next_due_date(
                    screening.last_completed_date,
                    screening.screening_type.frequency_value,
                    screening.screening_type.frequency_unit
                )
                
                if next_due <= cutoff_date:
                    overdue_screenings.append({
                        'screening': screening,
                        'days_overdue': (date.today() - next_due).days
                    })
        
        return sorted(overdue_screenings, key=lambda x: x['days_overdue'], reverse=True)
