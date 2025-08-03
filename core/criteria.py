"""
Screening eligibility and frequency logic
Handles determining patient eligibility for screening types
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from models import Condition
import logging

class EligibilityCriteria:
    """Handles screening eligibility logic for patients"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_patient_eligible(self, patient, screening_type):
        """Check if a patient is eligible for a specific screening type"""
        try:
            # Check gender eligibility
            if not self._check_gender_eligibility(patient, screening_type):
                return False
            
            # Check age eligibility
            if not self._check_age_eligibility(patient, screening_type):
                return False
            
            # Check trigger conditions if specified
            if not self._check_trigger_conditions(patient, screening_type):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking eligibility for {patient.mrn} and {screening_type.name}: {str(e)}")
            return False
    
    def _check_gender_eligibility(self, patient, screening_type):
        """Check if patient's gender matches screening eligibility"""
        if not screening_type.eligible_genders:
            return True  # No gender restriction
        
        # Handle different formats of gender eligibility
        eligible_genders = screening_type.eligible_genders
        
        # If it's a list, check if patient gender is in the list
        if isinstance(eligible_genders, list):
            return patient.gender in eligible_genders
        
        # If it's a string, check direct match or 'all'
        if isinstance(eligible_genders, str):
            return eligible_genders.lower() == 'all' or patient.gender == eligible_genders
        
        return True
    
    def _check_age_eligibility(self, patient, screening_type):
        """Check if patient's age falls within screening age range"""
        if patient.age is None:
            return True  # Can't determine age, assume eligible
        
        # Check minimum age
        if screening_type.min_age is not None and patient.age < screening_type.min_age:
            return False
        
        # Check maximum age
        if screening_type.max_age is not None and patient.age > screening_type.max_age:
            return False
        
        return True
    
    def _check_trigger_conditions(self, patient, screening_type):
        """Check if patient has required trigger conditions"""
        if not screening_type.trigger_conditions:
            return True  # No trigger conditions required
        
        trigger_conditions = screening_type.trigger_conditions
        if not isinstance(trigger_conditions, list):
            return True
        
        if not trigger_conditions:  # Empty list
            return True
        
        # Get patient's active conditions
        patient_conditions = Condition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        patient_condition_names = [
            condition.condition_name.lower() 
            for condition in patient_conditions
        ]
        
        # Check if any trigger condition matches patient conditions
        for trigger_condition in trigger_conditions:
            trigger_condition_lower = trigger_condition.lower().strip()
            
            # Direct match
            if trigger_condition_lower in patient_condition_names:
                return True
            
            # Partial match (for flexibility)
            for patient_condition in patient_condition_names:
                if (trigger_condition_lower in patient_condition or 
                    patient_condition in trigger_condition_lower):
                    return True
        
        return False
    
    def get_frequency_for_patient(self, patient, screening_type):
        """Get the appropriate frequency for a patient based on conditions"""
        # Default frequency from screening type
        default_years = screening_type.frequency_years or 0
        default_months = screening_type.frequency_months or 0
        
        # Check for variants based on patient conditions
        from core.variants import VariantProcessor
        variant_processor = VariantProcessor()
        variant = variant_processor.get_applicable_variant(patient, screening_type)
        
        if variant:
            variant_years = variant.frequency_years or 0
            variant_months = variant.frequency_months or 0
            return variant_years, variant_months
        
        return default_years, default_months
    
    def calculate_next_due_date(self, patient, screening_type, last_completed_date=None):
        """Calculate when a screening is next due for a patient"""
        if not last_completed_date:
            # If never completed, use current date
            last_completed_date = date.today()
        
        frequency_years, frequency_months = self.get_frequency_for_patient(patient, screening_type)
        
        next_due = last_completed_date
        if frequency_years > 0:
            next_due = next_due + relativedelta(years=frequency_years)
        if frequency_months > 0:
            next_due = next_due + relativedelta(months=frequency_months)
        
        return next_due
    
    def determine_screening_status(self, patient, screening_type, last_completed_date=None):
        """Determine the current status of a screening"""
        if not last_completed_date:
            return 'Due'
        
        next_due_date = self.calculate_next_due_date(patient, screening_type, last_completed_date)
        today = date.today()
        
        if today < next_due_date:
            # Check if due soon (within 30 days)
            days_until_due = (next_due_date - today).days
            if days_until_due <= 30:
                return 'Due Soon'
            else:
                return 'Complete'
        else:
            # Overdue
            return 'Overdue'
    
    def get_eligibility_summary(self, patient, screening_type):
        """Get a summary of eligibility factors for a patient and screening"""
        summary = {
            'eligible': self.is_patient_eligible(patient, screening_type),
            'gender_eligible': self._check_gender_eligibility(patient, screening_type),
            'age_eligible': self._check_age_eligibility(patient, screening_type),
            'conditions_met': self._check_trigger_conditions(patient, screening_type),
            'patient_age': patient.age,
            'patient_gender': patient.gender,
            'required_gender': screening_type.eligible_genders,
            'age_range': f"{screening_type.min_age or 'any'}-{screening_type.max_age or 'any'}",
            'trigger_conditions': screening_type.trigger_conditions or []
        }
        
        return summary
    
    def get_patients_eligible_for_screening(self, screening_type):
        """Get all patients eligible for a specific screening type"""
        from models import Patient
        
        patients = Patient.query.all()
        eligible_patients = []
        
        for patient in patients:
            if self.is_patient_eligible(patient, screening_type):
                eligible_patients.append(patient)
        
        return eligible_patients
    
    def validate_screening_criteria(self, screening_type_data):
        """Validate screening type criteria for consistency"""
        errors = []
        
        # Check age range consistency
        min_age = screening_type_data.get('min_age')
        max_age = screening_type_data.get('max_age')
        
        if min_age is not None and max_age is not None:
            if min_age > max_age:
                errors.append("Minimum age cannot be greater than maximum age")
        
        # Check frequency validity
        freq_years = screening_type_data.get('frequency_years', 0) or 0
        freq_months = screening_type_data.get('frequency_months', 0) or 0
        
        if freq_years == 0 and freq_months == 0:
            errors.append("Screening frequency must be specified (years or months)")
        
        if freq_years > 10:
            errors.append("Frequency in years should not exceed 10")
        
        if freq_months > 60:
            errors.append("Frequency in months should not exceed 60")
        
        # Check gender eligibility format
        eligible_genders = screening_type_data.get('eligible_genders')
        if eligible_genders and isinstance(eligible_genders, str):
            valid_genders = ['all', 'M', 'F', 'Other']
            if eligible_genders not in valid_genders:
                errors.append(f"Invalid gender specification: {eligible_genders}")
        
        return errors
