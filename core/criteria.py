"""
Screening eligibility and frequency logic module.
Handles patient eligibility determination based on age, gender, and conditions.
"""

import logging
from datetime import datetime, date
from typing import Optional, List
from dateutil.relativedelta import relativedelta
import json

from models import Patient, ScreeningType

class EligibilityCriteria:
    """Handles screening eligibility logic"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_patient_eligible(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if a patient is eligible for a specific screening type"""
        try:
            # Check if screening type is active
            if not screening_type.is_active:
                return False
            
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
            self.logger.error(f"Error checking eligibility for patient {patient.id} and screening {screening_type.id}: {str(e)}")
            return False
    
    def _check_gender_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient's gender matches screening eligibility"""
        if not screening_type.eligible_genders or screening_type.eligible_genders == 'both':
            return True
        
        return patient.gender.upper() == screening_type.eligible_genders.upper()
    
    def _check_age_eligibility(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient's age falls within screening age range"""
        if not patient.date_of_birth:
            return False
        
        # Calculate current age
        today = date.today()
        age = today.year - patient.date_of_birth.year
        
        # Adjust for birthday not yet reached this year
        if (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day):
            age -= 1
        
        # Check minimum age
        if screening_type.min_age is not None and age < screening_type.min_age:
            return False
        
        # Check maximum age
        if screening_type.max_age is not None and age > screening_type.max_age:
            return False
        
        return True
    
    def _check_trigger_conditions(self, patient: Patient, screening_type: ScreeningType) -> bool:
        """Check if patient has any required trigger conditions"""
        # If no trigger conditions specified, patient is eligible
        if not screening_type.trigger_conditions:
            return True
        
        try:
            # Parse trigger conditions (assuming JSON format for now)
            # In a full implementation, this would check against patient's condition history
            trigger_conditions = json.loads(screening_type.trigger_conditions)
            
            # For now, return True as we don't have patient condition tracking implemented
            # In full implementation, this would check patient's medical conditions
            return True
            
        except (json.JSONDecodeError, TypeError):
            # If trigger conditions is just a string, treat as simple condition check
            # This is a simplified implementation
            return True
    
    def calculate_patient_age(self, patient: Patient, reference_date: Optional[date] = None) -> Optional[int]:
        """Calculate patient's age at a specific date"""
        if not patient.date_of_birth:
            return None
        
        if reference_date is None:
            reference_date = date.today()
        
        age = reference_date.year - patient.date_of_birth.year
        
        # Adjust if birthday hasn't occurred yet this year
        if (reference_date.month, reference_date.day) < (patient.date_of_birth.month, patient.date_of_birth.day):
            age -= 1
        
        return age
    
    def get_eligible_screening_types(self, patient: Patient) -> List[ScreeningType]:
        """Get all screening types that a patient is eligible for"""
        try:
            all_screening_types = ScreeningType.query.filter_by(is_active=True).all()
            eligible_types = []
            
            for screening_type in all_screening_types:
                if self.is_patient_eligible(patient, screening_type):
                    eligible_types.append(screening_type)
            
            return eligible_types
            
        except Exception as e:
            self.logger.error(f"Error getting eligible screening types for patient {patient.id}: {str(e)}")
            return []
    
    def get_age_based_recommendations(self, patient: Patient) -> List[dict]:
        """Get screening recommendations based on patient's age and gender"""
        age = self.calculate_patient_age(patient)
        if age is None:
            return []
        
        recommendations = []
        
        # Standard age-based screening recommendations
        age_guidelines = {
            'Mammogram': {'gender': 'F', 'min_age': 40, 'frequency': 'annual'},
            'Colonoscopy': {'gender': 'both', 'min_age': 45, 'frequency': '10 years'},
            'Cervical Cancer Screening': {'gender': 'F', 'min_age': 21, 'max_age': 65, 'frequency': '3 years'},
            'Prostate Screening': {'gender': 'M', 'min_age': 50, 'frequency': 'annual'},
            'Bone Density': {'gender': 'F', 'min_age': 65, 'frequency': '2 years'},
            'Cardiovascular Screening': {'gender': 'both', 'min_age': 40, 'frequency': 'annual'},
            'Diabetes Screening': {'gender': 'both', 'min_age': 35, 'frequency': '3 years'}
        }
        
        for screening_name, criteria in age_guidelines.items():
            # Check gender
            if criteria['gender'] != 'both' and patient.gender.upper() != criteria['gender'].upper():
                continue
            
            # Check age range
            if age < criteria['min_age']:
                continue
            
            if 'max_age' in criteria and age > criteria['max_age']:
                continue
            
            recommendations.append({
                'screening': screening_name,
                'reason': f"Recommended for {patient.gender} patients age {age}",
                'frequency': criteria['frequency']
            })
        
        return recommendations
    
    def validate_screening_criteria(self, screening_type: ScreeningType) -> List[str]:
        """Validate screening type criteria and return any issues"""
        issues = []
        
        # Check required fields
        if not screening_type.name:
            issues.append("Screening name is required")
        
        if not screening_type.frequency_number or screening_type.frequency_number <= 0:
            issues.append("Frequency number must be positive")
        
        if not screening_type.frequency_unit:
            issues.append("Frequency unit is required")
        elif screening_type.frequency_unit not in ['months', 'years']:
            issues.append("Frequency unit must be 'months' or 'years'")
        
        # Check age ranges
        if screening_type.min_age is not None and screening_type.min_age < 0:
            issues.append("Minimum age cannot be negative")
        
        if screening_type.max_age is not None and screening_type.max_age > 120:
            issues.append("Maximum age cannot be greater than 120")
        
        if (screening_type.min_age is not None and 
            screening_type.max_age is not None and 
            screening_type.min_age > screening_type.max_age):
            issues.append("Minimum age cannot be greater than maximum age")
        
        # Check gender specification
        if screening_type.eligible_genders not in ['M', 'F', 'both', None]:
            issues.append("Eligible genders must be 'M', 'F', or 'both'")
        
        return issues
    
    def get_frequency_description(self, screening_type: ScreeningType) -> str:
        """Get human-readable frequency description"""
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return "Frequency not specified"
        
        number = screening_type.frequency_number
        unit = screening_type.frequency_unit
        
        if number == 1:
            unit_name = "year" if unit == "years" else "month"
            return f"Every {unit_name}"
        else:
            return f"Every {number} {unit}"
