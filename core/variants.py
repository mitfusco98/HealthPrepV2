"""
Handles screening type variants for different patient conditions and protocols.
Allows creation of condition-specific screening protocols under the same screening type.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import date

from models import Patient, ScreeningType, PatientCondition

@dataclass
class ScreeningVariant:
    """Represents a variant of a screening type for specific conditions."""
    condition: str
    frequency_value: int
    frequency_unit: str
    keywords: List[str]
    description: str
    priority: int = 0  # Higher priority variants override lower ones

class ScreeningVariantManager:
    """Manages screening type variants and determines which variant applies to a patient."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define built-in variant rules
        self.built_in_variants = {
            'a1c': [
                ScreeningVariant(
                    condition='diabetes',
                    frequency_value=3,
                    frequency_unit='months',
                    keywords=['a1c', 'hba1c', 'hemoglobin a1c'],
                    description='Diabetic patients require A1C every 3 months',
                    priority=10
                ),
                ScreeningVariant(
                    condition='prediabetes',
                    frequency_value=6,
                    frequency_unit='months',
                    keywords=['a1c', 'hba1c', 'hemoglobin a1c'],
                    description='Prediabetic patients require A1C every 6 months',
                    priority=5
                )
            ],
            'lipid panel': [
                ScreeningVariant(
                    condition='diabetes',
                    frequency_value=6,
                    frequency_unit='months',
                    keywords=['lipid', 'cholesterol', 'lipid panel', 'lipid profile'],
                    description='Diabetic patients require lipid panel every 6 months',
                    priority=8
                ),
                ScreeningVariant(
                    condition='heart disease',
                    frequency_value=3,
                    frequency_unit='months',
                    keywords=['lipid', 'cholesterol', 'lipid panel', 'lipid profile'],
                    description='Heart disease patients require lipid panel every 3 months',
                    priority=10
                ),
                ScreeningVariant(
                    condition='hypertension',
                    frequency_value=6,
                    frequency_unit='months',
                    keywords=['lipid', 'cholesterol', 'lipid panel', 'lipid profile'],
                    description='Hypertensive patients require lipid panel every 6 months',
                    priority=6
                )
            ],
            'eye exam': [
                ScreeningVariant(
                    condition='diabetes',
                    frequency_value=12,
                    frequency_unit='months',
                    keywords=['eye exam', 'ophthalmology', 'retinal', 'dilated fundus'],
                    description='Diabetic patients require annual eye exams',
                    priority=10
                )
            ],
            'foot exam': [
                ScreeningVariant(
                    condition='diabetes',
                    frequency_value=6,
                    frequency_unit='months',
                    keywords=['foot exam', 'diabetic foot', 'podiatry'],
                    description='Diabetic patients require foot exams every 6 months',
                    priority=10
                )
            ],
            'microalbumin': [
                ScreeningVariant(
                    condition='diabetes',
                    frequency_value=12,
                    frequency_unit='months',
                    keywords=['microalbumin', 'urine albumin', 'proteinuria'],
                    description='Diabetic patients require annual microalbumin testing',
                    priority=10
                )
            ]
        }
    
    def get_applicable_variant(self, patient: Patient, screening_type: ScreeningType) -> Optional[ScreeningVariant]:
        """Get the most applicable variant for a patient and screening type."""
        
        # Get patient's active conditions
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        if not patient_conditions:
            return None
        
        condition_names = [c.condition_name.lower().strip() for c in patient_conditions]
        screening_name = screening_type.name.lower().strip()
        
        # Find matching variants
        applicable_variants = []
        
        # Check built-in variants
        for variant_key, variants in self.built_in_variants.items():
            if variant_key in screening_name or any(keyword in screening_name for keyword in variant_key.split()):
                for variant in variants:
                    if any(variant.condition.lower() in condition for condition in condition_names):
                        applicable_variants.append(variant)
        
        # Return highest priority variant
        if applicable_variants:
            return max(applicable_variants, key=lambda v: v.priority)
        
        return None
    
    def apply_variant_to_screening(self, screening_type: ScreeningType, variant: ScreeningVariant) -> Dict:
        """Apply a variant to a screening type and return the modified parameters."""
        
        # Create modified screening parameters
        modified_params = {
            'original_frequency_value': screening_type.frequency_value,
            'original_frequency_unit': screening_type.frequency_unit,
            'original_keywords': screening_type.get_keywords_list(),
            
            # Applied variant parameters
            'frequency_value': variant.frequency_value,
            'frequency_unit': variant.frequency_unit,
            'keywords': variant.keywords,
            'variant_condition': variant.condition,
            'variant_description': variant.description,
            'variant_applied': True
        }
        
        return modified_params
    
    def get_variant_summary(self, patient: Patient, screening_type: ScreeningType) -> Dict:
        """Get a summary of variant application for a patient and screening."""
        
        variant = self.get_applicable_variant(patient, screening_type)
        
        if variant:
            modified_params = self.apply_variant_to_screening(screening_type, variant)
            
            return {
                'has_variant': True,
                'variant': variant,
                'modified_params': modified_params,
                'frequency_changed': (variant.frequency_value != screening_type.frequency_value or 
                                    variant.frequency_unit != screening_type.frequency_unit),
                'keywords_changed': set(variant.keywords) != set(screening_type.get_keywords_list())
            }
        else:
            return {
                'has_variant': False,
                'variant': None,
                'modified_params': None,
                'frequency_changed': False,
                'keywords_changed': False
            }
    
    def create_custom_variant(self, screening_type_name: str, condition: str, 
                            frequency_value: int, frequency_unit: str,
                            keywords: List[str], description: str = None) -> ScreeningVariant:
        """Create a custom variant for specific use cases."""
        
        if description is None:
            description = f"Custom variant for {condition} patients"
        
        variant = ScreeningVariant(
            condition=condition.lower().strip(),
            frequency_value=frequency_value,
            frequency_unit=frequency_unit,
            keywords=keywords,
            description=description,
            priority=5  # Medium priority for custom variants
        )
        
        # Add to built-in variants if not exists
        screening_key = screening_type_name.lower().strip()
        if screening_key not in self.built_in_variants:
            self.built_in_variants[screening_key] = []
        
        self.built_in_variants[screening_key].append(variant)
        
        self.logger.info(f"Created custom variant for {screening_type_name} with condition {condition}")
        
        return variant
    
    def get_all_variants_for_screening(self, screening_type_name: str) -> List[ScreeningVariant]:
        """Get all available variants for a screening type."""
        screening_key = screening_type_name.lower().strip()
        
        variants = []
        for variant_key, variant_list in self.built_in_variants.items():
            if variant_key in screening_key or any(keyword in screening_key for keyword in variant_key.split()):
                variants.extend(variant_list)
        
        # Sort by priority (highest first)
        return sorted(variants, key=lambda v: v.priority, reverse=True)
    
    def validate_variant_logic(self, patient: Patient) -> Dict:
        """Validate variant logic for a patient across all their conditions."""
        
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        condition_names = [c.condition_name.lower().strip() for c in patient_conditions]
        applicable_variants = {}
        conflicts = []
        
        # Check each screening type for applicable variants
        for screening_key, variants in self.built_in_variants.items():
            screening_variants = []
            
            for variant in variants:
                if any(variant.condition.lower() in condition for condition in condition_names):
                    screening_variants.append(variant)
            
            if screening_variants:
                # Sort by priority
                screening_variants.sort(key=lambda v: v.priority, reverse=True)
                applicable_variants[screening_key] = screening_variants
                
                # Check for conflicts (multiple high-priority variants)
                high_priority = [v for v in screening_variants if v.priority >= 8]
                if len(high_priority) > 1:
                    conflicts.append({
                        'screening': screening_key,
                        'variants': high_priority,
                        'reason': 'Multiple high-priority variants applicable'
                    })
        
        return {
            'applicable_variants': applicable_variants,
            'conflicts': conflicts,
            'total_applicable': len(applicable_variants),
            'has_conflicts': len(conflicts) > 0,
            'patient_conditions': condition_names
        }
    
    def export_variant_configuration(self) -> Dict:
        """Export current variant configuration for backup or transfer."""
        
        config = {}
        for screening_key, variants in self.built_in_variants.items():
            config[screening_key] = []
            for variant in variants:
                config[screening_key].append({
                    'condition': variant.condition,
                    'frequency_value': variant.frequency_value,
                    'frequency_unit': variant.frequency_unit,
                    'keywords': variant.keywords,
                    'description': variant.description,
                    'priority': variant.priority
                })
        
        return {
            'version': '1.0',
            'created_at': date.today().isoformat(),
            'variants': config
        }
