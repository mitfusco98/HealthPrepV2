"""
Screening eligibility and frequency logic
"""
from datetime import date
import json
import logging

class EligibilityCriteria:
    
    def check_eligibility(self, patient, screening_type):
        """Check if patient meets all eligibility criteria for screening"""
        try:
            # Check gender criteria
            if not self._check_gender_eligibility(patient, screening_type):
                return False
            
            # Check age criteria
            if not self._check_age_eligibility(patient, screening_type):
                return False
            
            # Check trigger conditions (if any)
            if not self._check_condition_eligibility(patient, screening_type):
                return False
            
            return True
        
        except Exception as e:
            logging.error(f"Error checking eligibility for patient {patient.id} and screening {screening_type.id}: {e}")
            return False
    
    def _check_gender_eligibility(self, patient, screening_type):
        """Check if patient gender matches screening requirements"""
        if not screening_type.gender_filter:
            return True  # No gender restriction
        
        return patient.gender == screening_type.gender_filter
    
    def _check_age_eligibility(self, patient, screening_type):
        """Check if patient age is within screening range"""
        patient_age = patient.age
        
        # Check minimum age
        if screening_type.min_age and patient_age < screening_type.min_age:
            return False
        
        # Check maximum age
        if screening_type.max_age and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_condition_eligibility(self, patient, screening_type):
        """Check if patient has required trigger conditions"""
        if not screening_type.trigger_conditions:
            return True  # No condition requirements
        
        try:
            required_conditions = json.loads(screening_type.trigger_conditions)
        except (json.JSONDecodeError, TypeError):
            return True  # Invalid condition data, assume eligible
        
        if not required_conditions:
            return True
        
        # For now, we'll assume all patients are eligible
        # In a real implementation, this would check patient conditions from EMR
        # patient_conditions = self._get_patient_conditions(patient)
        # return any(condition in patient_conditions for condition in required_conditions)
        
        return True
    
    def _get_patient_conditions(self, patient):
        """Get patient's medical conditions from EMR/FHIR data"""
        # This would integrate with FHIR client to get patient conditions
        # For now, return empty list
        return []
    
    def calculate_next_due_date(self, last_screening_date, screening_type):
        """Calculate when the next screening is due"""
        if not last_screening_date:
            return date.today()  # Due now if never done
        
        try:
            if screening_type.frequency_unit == 'years':
                from dateutil.relativedelta import relativedelta
                return last_screening_date + relativedelta(years=screening_type.frequency_value)
            elif screening_type.frequency_unit == 'months':
                from dateutil.relativedelta import relativedelta
                return last_screening_date + relativedelta(months=screening_type.frequency_value)
            else:  # days
                from datetime import timedelta
                return last_screening_date + timedelta(days=screening_type.frequency_value)
        
        except Exception as e:
            logging.error(f"Error calculating next due date: {e}")
            return date.today()
    
    def get_screening_urgency(self, next_due_date):
        """Determine urgency level of screening"""
        if not next_due_date:
            return 'unknown'
        
        today = date.today()
        days_until_due = (next_due_date - today).days
        
        if days_until_due <= 0:
            return 'overdue'
        elif days_until_due <= 30:
            return 'due_soon'
        elif days_until_due <= 90:
            return 'upcoming'
        else:
            return 'future'
    
    def get_compliance_percentage(self, patient_screenings):
        """Calculate compliance percentage for patient screenings"""
        if not patient_screenings:
            return 0.0
        
        compliant_count = sum(1 for screening in patient_screenings 
                             if screening.status == 'Complete')
        
        return (compliant_count / len(patient_screenings)) * 100
