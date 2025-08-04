from datetime import datetime
from models import Patient, ScreeningType, PatientCondition

class EligibilityCriteria:
    """Handles screening eligibility logic based on patient demographics and conditions"""
    
    def __init__(self):
        pass
    
    def is_eligible(self, patient, screening_type):
        """Determine if patient is eligible for screening type"""
        # Age eligibility
        if not self._check_age_eligibility(patient, screening_type):
            return False
        
        # Gender eligibility
        if not self._check_gender_eligibility(patient, screening_type):
            return False
        
        # Trigger conditions eligibility
        if not self._check_trigger_conditions(patient, screening_type):
            return False
        
        return True
    
    def _check_age_eligibility(self, patient, screening_type):
        """Check if patient age meets screening criteria"""
        patient_age = patient.age
        
        if screening_type.min_age and patient_age < screening_type.min_age:
            return False
        
        if screening_type.max_age and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient, screening_type):
        """Check if patient gender meets screening criteria"""
        if not screening_type.gender_restriction:
            return True
        
        return patient.gender.lower() == screening_type.gender_restriction.lower()
    
    def _check_trigger_conditions(self, patient, screening_type):
        """Check if patient has required trigger conditions"""
        if not screening_type.trigger_conditions:
            return True  # No conditions required
        
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        patient_condition_names = [c.condition_name.lower() for c in patient_conditions]
        
        # Check if patient has any of the trigger conditions
        for trigger_condition in screening_type.trigger_conditions:
            if self._condition_matches(trigger_condition.lower(), patient_condition_names):
                return True
        
        return False
    
    def _condition_matches(self, trigger_condition, patient_conditions):
        """Check if trigger condition matches any patient condition"""
        # Direct match
        if trigger_condition in patient_conditions:
            return True
        
        # Fuzzy matching for common condition variants
        condition_variants = {
            'diabetes': ['diabetes mellitus', 'dm', 'type 1 diabetes', 'type 2 diabetes'],
            'hypertension': ['high blood pressure', 'htn', 'elevated bp'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'lipid disorder'],
            'copd': ['chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis'],
            'cad': ['coronary artery disease', 'coronary heart disease', 'ischemic heart disease']
        }
        
        if trigger_condition in condition_variants:
            for variant in condition_variants[trigger_condition]:
                if any(variant in pc for pc in patient_conditions):
                    return True
        
        return False
    
    def get_eligibility_summary(self, patient, screening_type):
        """Get detailed eligibility summary for debugging"""
        summary = {
            'eligible': self.is_eligible(patient, screening_type),
            'age_check': self._check_age_eligibility(patient, screening_type),
            'gender_check': self._check_gender_eligibility(patient, screening_type),
            'conditions_check': self._check_trigger_conditions(patient, screening_type),
            'patient_age': patient.age,
            'required_conditions': screening_type.trigger_conditions
        }
        
        return summary
