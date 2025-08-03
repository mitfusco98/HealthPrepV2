"""
Screening eligibility and frequency logic
Handles patient eligibility for different screening types
"""
from datetime import datetime, date
from models import Condition
import logging

logger = logging.getLogger(__name__)

class EligibilityCriteria:
    """Handles eligibility criteria for screenings"""
    
    def __init__(self):
        pass
    
    def is_eligible(self, patient, screening_type):
        """Check if a patient is eligible for a screening type"""
        criteria = screening_type.eligibility_criteria or {}
        
        # Check gender eligibility
        if not self.check_gender_eligibility(patient, criteria):
            return False
        
        # Check age eligibility
        if not self.check_age_eligibility(patient, criteria):
            return False
        
        # Check trigger conditions if specified
        if not self.check_trigger_conditions(patient, screening_type):
            return False
        
        return True
    
    def check_gender_eligibility(self, patient, criteria):
        """Check if patient gender meets criteria"""
        required_gender = criteria.get('gender', 'any')
        
        if required_gender == 'any':
            return True
        
        return patient.gender == required_gender
    
    def check_age_eligibility(self, patient, criteria):
        """Check if patient age meets criteria"""
        min_age = criteria.get('min_age')
        max_age = criteria.get('max_age')
        
        if min_age is None and max_age is None:
            return True
        
        patient_age = self.calculate_age(patient.date_of_birth)
        
        if min_age is not None and patient_age < min_age:
            return False
        
        if max_age is not None and patient_age > max_age:
            return False
        
        return True
    
    def check_trigger_conditions(self, patient, screening_type):
        """Check if patient has required trigger conditions"""
        trigger_conditions = screening_type.trigger_conditions or []
        
        if not trigger_conditions:
            return True  # No specific conditions required
        
        # Get patient's active conditions
        patient_conditions = Condition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        patient_condition_names = [c.condition_name.lower() for c in patient_conditions]
        
        # Check if patient has any of the trigger conditions
        for trigger in trigger_conditions:
            if self.fuzzy_condition_match(trigger.lower().strip(), patient_condition_names):
                return True
        
        return False
    
    def fuzzy_condition_match(self, trigger_condition, patient_conditions):
        """Fuzzy match trigger condition against patient conditions"""
        # Common condition aliases
        condition_aliases = {
            'diabetes': ['diabetes mellitus', 'dm', 'diabetic', 'type 1 diabetes', 'type 2 diabetes'],
            'hypertension': ['high blood pressure', 'htn', 'elevated bp'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'elevated cholesterol'],
            'copd': ['chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis'],
            'cad': ['coronary artery disease', 'coronary heart disease', 'ischemic heart disease'],
            'ckd': ['chronic kidney disease', 'chronic renal disease', 'kidney disease']
        }
        
        # Direct match
        if trigger_condition in patient_conditions:
            return True
        
        # Check aliases
        if trigger_condition in condition_aliases:
            for alias in condition_aliases[trigger_condition]:
                if alias in patient_conditions:
                    return True
        
        # Check if trigger is an alias
        for main_condition, aliases in condition_aliases.items():
            if trigger_condition in aliases:
                if main_condition in patient_conditions:
                    return True
                for alias in aliases:
                    if alias in patient_conditions:
                        return True
        
        # Fuzzy string matching
        for patient_condition in patient_conditions:
            if trigger_condition in patient_condition or patient_condition in trigger_condition:
                return True
        
        return False
    
    def calculate_age(self, birth_date):
        """Calculate current age from birth date"""
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    def get_variant_for_patient(self, patient, screening_type):
        """Get the appropriate screening variant for a patient"""
        # This would handle different screening protocols based on patient conditions
        # For example, diabetics might need A1C every 3 months vs 6 months for others
        
        base_frequency = {
            'value': screening_type.frequency_value,
            'unit': screening_type.frequency_unit
        }
        
        # Check for condition-specific variants
        if screening_type.trigger_conditions:
            patient_conditions = Condition.query.filter_by(
                patient_id=patient.id,
                status='active'
            ).all()
            
            condition_names = [c.condition_name.lower() for c in patient_conditions]
            
            # Example: More frequent A1C for diabetics
            if screening_type.name.lower() in ['a1c', 'hemoglobin a1c']:
                if self.fuzzy_condition_match('diabetes', condition_names):
                    return {'value': 3, 'unit': 'months'}  # Every 3 months for diabetics
        
        return base_frequency
