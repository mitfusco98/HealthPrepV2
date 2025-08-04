from models import ScreeningType, PatientCondition
from core.criteria import EligibilityCriteria

class ScreeningVariants:
    """Handles screening type variants based on trigger conditions"""
    
    def __init__(self):
        self.criteria = EligibilityCriteria()
    
    def get_variant_for_patient(self, base_screening_type, patient):
        """Get the appropriate screening variant for a patient"""
        # Check for condition-specific variants
        variants = self._get_screening_variants(base_screening_type)
        
        # Find the most specific variant that applies
        best_variant = base_screening_type
        max_specificity = 0
        
        for variant in variants:
            if self.criteria.is_eligible(patient, variant):
                specificity = len(variant.trigger_conditions or [])
                if specificity > max_specificity:
                    best_variant = variant
                    max_specificity = specificity
        
        return best_variant
    
    def _get_screening_variants(self, base_screening_type):
        """Get all variants of a screening type"""
        # For now, return the base type
        # In a more complex implementation, this would query for related variants
        return [base_screening_type]
    
    def create_variant(self, base_screening_type, variant_data):
        """Create a new variant of a screening type"""
        variant = ScreeningType(
            name=f"{base_screening_type.name} ({variant_data['condition']})",
            description=variant_data.get('description', base_screening_type.description),
            keywords=variant_data.get('keywords', base_screening_type.keywords),
            min_age=variant_data.get('min_age', base_screening_type.min_age),
            max_age=variant_data.get('max_age', base_screening_type.max_age),
            gender_restriction=variant_data.get('gender_restriction', base_screening_type.gender_restriction),
            frequency_value=variant_data['frequency_value'],
            frequency_unit=variant_data['frequency_unit'],
            trigger_conditions=variant_data['trigger_conditions'],
            is_active=True
        )
        
        return variant
    
    def get_frequency_adjustments(self, screening_type, patient):
        """Get frequency adjustments based on patient conditions"""
        adjustments = {}
        
        # Common frequency adjustments for conditions
        condition_adjustments = {
            'diabetes': {
                'A1C': {'frequency_value': 3, 'frequency_unit': 'months'},
                'Eye Exam': {'frequency_value': 1, 'frequency_unit': 'years'},
                'Foot Exam': {'frequency_value': 6, 'frequency_unit': 'months'}
            },
            'hypertension': {
                'Blood Pressure Check': {'frequency_value': 3, 'frequency_unit': 'months'}
            },
            'hyperlipidemia': {
                'Lipid Panel': {'frequency_value': 6, 'frequency_unit': 'months'}
            }
        }
        
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        for condition in patient_conditions:
            condition_name = condition.condition_name.lower()
            if condition_name in condition_adjustments:
                screening_adjustments = condition_adjustments[condition_name]
                if screening_type.name in screening_adjustments:
                    adjustments.update(screening_adjustments[screening_type.name])
        
        return adjustments
