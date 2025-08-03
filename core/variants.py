"""
Handles screening type variants for different trigger conditions
Allows different screening protocols based on patient conditions
"""

from typing import List, Dict, Optional, Any
from models import ScreeningType, PatientCondition
from core.matcher import FuzzyMatcher

class ScreeningVariants:
    """Manages screening type variants and conditional protocols"""
    
    def __init__(self):
        self.matcher = FuzzyMatcher()
    
    def get_applicable_variant(self, base_screening_type: ScreeningType, 
                             patient_conditions: List[PatientCondition]) -> ScreeningType:
        """
        Get the most applicable screening variant based on patient conditions
        """
        # For now, return the base screening type
        # This can be extended to handle complex variant logic
        return base_screening_type
    
    def create_screening_variant(self, base_screening_id: int, 
                               variant_name: str, 
                               modifications: Dict[str, Any]) -> ScreeningType:
        """
        Create a variant of a screening type with modified parameters
        """
        base_screening = ScreeningType.query.get(base_screening_id)
        if not base_screening:
            raise ValueError("Base screening type not found")
        
        # Create new screening type as variant
        variant = ScreeningType(
            name=f"{base_screening.name} - {variant_name}",
            description=f"{base_screening.description} (Variant: {variant_name})",
            keywords=modifications.get('keywords', base_screening.keywords),
            min_age=modifications.get('min_age', base_screening.min_age),
            max_age=modifications.get('max_age', base_screening.max_age),
            gender=modifications.get('gender', base_screening.gender),
            frequency_number=modifications.get('frequency_number', base_screening.frequency_number),
            frequency_unit=modifications.get('frequency_unit', base_screening.frequency_unit),
            trigger_conditions=modifications.get('trigger_conditions', base_screening.trigger_conditions),
            is_active=modifications.get('is_active', True)
        )
        
        return variant
    
    def get_diabetic_variants(self) -> List[Dict[str, Any]]:
        """Get common diabetic screening variants"""
        return [
            {
                'name': 'Diabetic A1C',
                'base_screening': 'A1C',
                'modifications': {
                    'frequency_number': 3,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['diabetes', 'diabetes mellitus', 'dm']
                }
            },
            {
                'name': 'Diabetic Eye Exam',
                'base_screening': 'Eye Exam',
                'modifications': {
                    'frequency_number': 1,
                    'frequency_unit': 'years',
                    'trigger_conditions': ['diabetes', 'diabetes mellitus', 'dm']
                }
            },
            {
                'name': 'Diabetic Foot Exam',
                'base_screening': 'Foot Exam',
                'modifications': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['diabetes', 'diabetes mellitus', 'dm']
                }
            }
        ]
    
    def get_cardiac_variants(self) -> List[Dict[str, Any]]:
        """Get common cardiac screening variants"""
        return [
            {
                'name': 'Cardiac Lipid Panel',
                'base_screening': 'Lipid Panel',
                'modifications': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['heart disease', 'coronary artery disease', 'cad', 'hyperlipidemia']
                }
            },
            {
                'name': 'Cardiac Stress Test - High Risk',
                'base_screening': 'Stress Test',
                'modifications': {
                    'frequency_number': 2,
                    'frequency_unit': 'years',
                    'trigger_conditions': ['heart disease', 'coronary artery disease', 'cad']
                }
            }
        ]
    
    def get_hypertension_variants(self) -> List[Dict[str, Any]]:
        """Get common hypertension screening variants"""
        return [
            {
                'name': 'Hypertensive BMP/CMP',
                'base_screening': 'Basic Metabolic Panel',
                'modifications': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['hypertension', 'high blood pressure', 'htn']
                }
            },
            {
                'name': 'Hypertensive EKG',
                'base_screening': 'EKG',
                'modifications': {
                    'frequency_number': 1,
                    'frequency_unit': 'years',
                    'trigger_conditions': ['hypertension', 'high blood pressure', 'htn']
                }
            }
        ]
    
    def get_all_preset_variants(self) -> List[Dict[str, Any]]:
        """Get all available preset variants"""
        variants = []
        variants.extend(self.get_diabetic_variants())
        variants.extend(self.get_cardiac_variants())
        variants.extend(self.get_hypertension_variants())
        return variants
    
    def apply_variant_preset(self, preset_name: str) -> List[ScreeningType]:
        """Apply a preset of screening variants"""
        created_variants = []
        
        if preset_name == 'diabetic':
            variants = self.get_diabetic_variants()
        elif preset_name == 'cardiac':
            variants = self.get_cardiac_variants()
        elif preset_name == 'hypertension':
            variants = self.get_hypertension_variants()
        else:
            return created_variants
        
        for variant_data in variants:
            # Check if base screening exists
            base_name = variant_data['base_screening']
            base_screening = ScreeningType.query.filter_by(name=base_name).first()
            
            if base_screening:
                variant = self.create_screening_variant(
                    base_screening.id,
                    variant_data['name'],
                    variant_data['modifications']
                )
                created_variants.append(variant)
        
        return created_variants
    
    def get_variant_suggestions(self, screening_type: ScreeningType) -> List[Dict[str, Any]]:
        """Get suggested variants for a screening type"""
        suggestions = []
        
        # Age-based variants
        if screening_type.min_age:
            suggestions.append({
                'name': 'Senior Variant',
                'description': f'Modified frequency for patients over 65',
                'modifications': {
                    'min_age': 65,
                    'frequency_number': max(1, screening_type.frequency_number - 1) if screening_type.frequency_number else 1
                }
            })
        
        # Gender-specific variants
        if not screening_type.gender:
            suggestions.extend([
                {
                    'name': 'Male-Specific',
                    'description': 'Male-only version of this screening',
                    'modifications': {'gender': 'M'}
                },
                {
                    'name': 'Female-Specific', 
                    'description': 'Female-only version of this screening',
                    'modifications': {'gender': 'F'}
                }
            ])
        
        # High-risk variants
        suggestions.append({
            'name': 'High-Risk',
            'description': 'More frequent screening for high-risk patients',
            'modifications': {
                'frequency_number': max(1, (screening_type.frequency_number or 1) // 2),
                'trigger_conditions': ['high risk', 'family history']
            }
        })
        
        return suggestions
