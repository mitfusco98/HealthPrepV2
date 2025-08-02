"""
Handles screening type variants for different trigger conditions
Allows different screening protocols based on patient conditions
"""
import logging
import json
from typing import List, Dict, Optional

from models import ScreeningType, Patient, PatientCondition

logger = logging.getLogger(__name__)

class VariantManager:
    """Manages screening type variants based on trigger conditions"""
    
    def __init__(self):
        self.variant_rules = {
            'a1c': {
                'default': {'frequency_number': 12, 'frequency_unit': 'months'},
                'diabetes': {'frequency_number': 3, 'frequency_unit': 'months'}
            },
            'lipid_panel': {
                'default': {'frequency_number': 5, 'frequency_unit': 'years'},
                'diabetes': {'frequency_number': 12, 'frequency_unit': 'months'},
                'hypertension': {'frequency_number': 12, 'frequency_unit': 'months'}
            },
            'eye_exam': {
                'default': {'frequency_number': 2, 'frequency_unit': 'years'},
                'diabetes': {'frequency_number': 12, 'frequency_unit': 'months'}
            },
            'mammogram': {
                'default': {'frequency_number': 2, 'frequency_unit': 'years'},
                'family_history_breast': {'frequency_number': 1, 'frequency_unit': 'years'}
            },
            'colonoscopy': {
                'default': {'frequency_number': 10, 'frequency_unit': 'years'},
                'family_history_colon': {'frequency_number': 5, 'frequency_unit': 'years'}
            }
        }
    
    def get_variant_for_patient(self, screening_type: ScreeningType, patient: Patient) -> Dict:
        """
        Get the appropriate screening variant for a patient
        
        Args:
            screening_type: ScreeningType object
            patient: Patient object
            
        Returns:
            Dictionary with variant parameters
        """
        try:
            screening_name = screening_type.name.lower().replace(' ', '_')
            
            # Check if this screening type has variants
            if screening_name not in self.variant_rules:
                return self._get_default_variant(screening_type)
            
            # Get patient conditions
            patient_conditions = self._get_patient_condition_names(patient)
            
            # Find matching variant
            variant_rules = self.variant_rules[screening_name]
            
            for condition in patient_conditions:
                if condition in variant_rules:
                    variant = variant_rules[condition].copy()
                    variant['variant_type'] = condition
                    return variant
            
            # Return default if no condition matches
            default_variant = variant_rules.get('default', self._get_default_variant(screening_type))
            default_variant['variant_type'] = 'default'
            return default_variant
            
        except Exception as e:
            logger.error(f"Error getting variant for patient: {str(e)}")
            return self._get_default_variant(screening_type)
    
    def _get_default_variant(self, screening_type: ScreeningType) -> Dict:
        """Get default variant from screening type"""
        return {
            'frequency_number': screening_type.frequency_number or 12,
            'frequency_unit': screening_type.frequency_unit or 'months',
            'variant_type': 'default'
        }
    
    def _get_patient_condition_names(self, patient: Patient) -> List[str]:
        """Get standardized condition names for patient"""
        conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        condition_names = []
        
        # Map ICD codes to condition names
        code_mappings = {
            'E11': 'diabetes',
            'E10': 'diabetes',
            'I10': 'hypertension',
            'I15': 'hypertension',
            'E66': 'obesity',
            'F17': 'smoking',
            'Z80.3': 'family_history_breast',
            'Z80.0': 'family_history_colon'
        }
        
        for condition in conditions:
            if condition.code:
                # Try exact match first
                if condition.code in code_mappings:
                    condition_names.append(code_mappings[condition.code])
                else:
                    # Try prefix match for ICD codes
                    for code_prefix, name in code_mappings.items():
                        if condition.code.startswith(code_prefix):
                            condition_names.append(name)
                            break
        
        return list(set(condition_names))  # Remove duplicates
    
    def create_screening_variant(self, base_screening_type: ScreeningType, 
                                variant_config: Dict) -> ScreeningType:
        """
        Create a variant of a screening type
        
        Args:
            base_screening_type: Base ScreeningType to create variant from
            variant_config: Configuration for the variant
            
        Returns:
            New ScreeningType object (not saved to database)
        """
        variant = ScreeningType(
            name=f"{base_screening_type.name} ({variant_config.get('variant_name', 'Variant')})",
            description=f"Variant: {base_screening_type.description}",
            keywords=base_screening_type.keywords,
            gender_criteria=base_screening_type.gender_criteria,
            min_age=variant_config.get('min_age', base_screening_type.min_age),
            max_age=variant_config.get('max_age', base_screening_type.max_age),
            frequency_number=variant_config.get('frequency_number', base_screening_type.frequency_number),
            frequency_unit=variant_config.get('frequency_unit', base_screening_type.frequency_unit),
            trigger_conditions=variant_config.get('trigger_conditions', base_screening_type.trigger_conditions),
            is_active=variant_config.get('is_active', True)
        )
        
        return variant
    
    def get_available_variants(self, screening_name: str) -> Dict:
        """
        Get available variants for a screening type
        
        Args:
            screening_name: Name of screening type
            
        Returns:
            Dictionary of available variants
        """
        screening_name = screening_name.lower().replace(' ', '_')
        return self.variant_rules.get(screening_name, {})
    
    def suggest_variants(self, screening_type: ScreeningType, 
                        patient_population: List[Patient]) -> List[Dict]:
        """
        Suggest variants based on patient population analysis
        
        Args:
            screening_type: ScreeningType to analyze
            patient_population: List of patients to analyze
            
        Returns:
            List of suggested variants
        """
        suggestions = []
        
        # Analyze patient conditions
        condition_counts = {}
        
        for patient in patient_population:
            conditions = self._get_patient_condition_names(patient)
            for condition in conditions:
                condition_counts[condition] = condition_counts.get(condition, 0) + 1
        
        # Suggest variants for common conditions
        total_patients = len(patient_population)
        threshold = max(1, total_patients * 0.1)  # 10% threshold
        
        for condition, count in condition_counts.items():
            if count >= threshold:
                suggestion = {
                    'condition': condition,
                    'patient_count': count,
                    'percentage': (count / total_patients) * 100,
                    'suggested_frequency': self._get_suggested_frequency(screening_type.name, condition)
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _get_suggested_frequency(self, screening_name: str, condition: str) -> Dict:
        """Get suggested frequency for a condition"""
        screening_name = screening_name.lower().replace(' ', '_')
        
        if screening_name in self.variant_rules:
            variant_rules = self.variant_rules[screening_name]
            if condition in variant_rules:
                return variant_rules[condition]
        
        # Default suggestions based on condition type
        condition_defaults = {
            'diabetes': {'frequency_number': 3, 'frequency_unit': 'months'},
            'hypertension': {'frequency_number': 6, 'frequency_unit': 'months'},
            'family_history_breast': {'frequency_number': 1, 'frequency_unit': 'years'},
            'family_history_colon': {'frequency_number': 5, 'frequency_unit': 'years'}
        }
        
        return condition_defaults.get(condition, {'frequency_number': 12, 'frequency_unit': 'months'})
