"""
Handles screening type variants based on trigger conditions
"""

import logging
from typing import Dict, List, Any, Optional
from models import ScreeningType

logger = logging.getLogger(__name__)

class VariantHandler:
    """Manages screening type variants for different trigger conditions"""
    
    def __init__(self):
        # Define standard variant configurations
        self.variant_configs = {
            'diabetes': {
                'a1c': {
                    'frequency_number': 3,
                    'frequency_unit': 'months',
                    'description': 'Diabetic A1C monitoring - every 3 months'
                },
                'cholesterol': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'description': 'Diabetic lipid monitoring - every 6 months'
                },
                'eye_exam': {
                    'frequency_number': 1,
                    'frequency_unit': 'years',
                    'description': 'Diabetic retinal screening - annually'
                },
                'kidney_function': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'description': 'Diabetic nephropathy screening - every 6 months'
                }
            },
            'hypertension': {
                'blood_pressure': {
                    'frequency_number': 3,
                    'frequency_unit': 'months',
                    'description': 'Hypertensive BP monitoring - every 3 months'
                },
                'cholesterol': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'description': 'Hypertensive lipid monitoring - every 6 months'
                },
                'kidney_function': {
                    'frequency_number': 12,
                    'frequency_unit': 'months',
                    'description': 'Hypertensive renal monitoring - annually'
                }
            },
            'hyperlipidemia': {
                'cholesterol': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'description': 'Hyperlipidemia monitoring - every 6 months'
                }
            },
            'osteoporosis': {
                'dexa': {
                    'frequency_number': 2,
                    'frequency_unit': 'years',
                    'description': 'Osteoporosis monitoring - every 2 years'
                }
            },
            'copd': {
                'pulmonary_function': {
                    'frequency_number': 6,
                    'frequency_unit': 'months',
                    'description': 'COPD monitoring - every 6 months'
                },
                'chest_xray': {
                    'frequency_number': 12,
                    'frequency_unit': 'months',
                    'description': 'COPD imaging - annually'
                }
            }
        }
    
    def get_variant_for_condition(self, screening_type: ScreeningType, condition: str) -> Optional[Dict[str, Any]]:
        """
        Get variant configuration for a specific condition and screening type
        """
        condition_lower = condition.lower()
        
        # Find matching condition in variant configs
        for config_condition, variants in self.variant_configs.items():
            if config_condition in condition_lower or condition_lower in config_condition:
                # Find matching screening variant
                for variant_key, variant_config in variants.items():
                    if self._screening_matches_variant(screening_type, variant_key):
                        return {
                            'condition': condition,
                            'variant_type': variant_key,
                            'frequency_number': variant_config['frequency_number'],
                            'frequency_unit': variant_config['frequency_unit'],
                            'description': variant_config['description'],
                            'additional_keywords': self._get_additional_keywords(variant_key)
                        }
        
        return None
    
    def _screening_matches_variant(self, screening_type: ScreeningType, variant_key: str) -> bool:
        """Check if screening type matches the variant"""
        
        # Define keyword mappings for variants
        variant_keywords = {
            'a1c': ['a1c', 'hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'cholesterol': ['cholesterol', 'lipid', 'lipid panel', 'hdl', 'ldl'],
            'eye_exam': ['eye', 'ophthalmology', 'retinal', 'fundus'],
            'kidney_function': ['creatinine', 'bun', 'kidney', 'renal', 'microalbumin'],
            'blood_pressure': ['blood pressure', 'bp', 'hypertension'],
            'dexa': ['dexa', 'dxa', 'bone density', 'densitometry'],
            'pulmonary_function': ['pulmonary function', 'pft', 'spirometry'],
            'chest_xray': ['chest xray', 'cxr', 'chest x-ray']
        }
        
        if variant_key not in variant_keywords:
            return False
        
        # Check if any screening keywords match variant keywords
        screening_keywords = [kw.lower() for kw in screening_type.keywords_list]
        variant_kws = variant_keywords[variant_key]
        
        for screening_kw in screening_keywords:
            for variant_kw in variant_kws:
                if variant_kw in screening_kw or screening_kw in variant_kw:
                    return True
        
        return False
    
    def _get_additional_keywords(self, variant_key: str) -> List[str]:
        """Get additional keywords for variant matching"""
        
        additional_keywords = {
            'a1c': ['diabetes', 'diabetic'],
            'cholesterol': ['cardiac', 'cardiovascular'],
            'eye_exam': ['diabetic retinopathy', 'retinal screening'],
            'kidney_function': ['diabetic nephropathy', 'proteinuria'],
            'blood_pressure': ['hypertensive', 'antihypertensive'],
            'dexa': ['osteoporotic', 'fracture risk'],
            'pulmonary_function': ['copd', 'asthma', 'respiratory'],
            'chest_xray': ['pulmonary', 'lung']
        }
        
        return additional_keywords.get(variant_key, [])
    
    def get_all_variants_for_screening(self, screening_type: ScreeningType) -> List[Dict[str, Any]]:
        """Get all possible variants for a screening type"""
        variants = []
        
        for condition, condition_variants in self.variant_configs.items():
            for variant_key, variant_config in condition_variants.items():
                if self._screening_matches_variant(screening_type, variant_key):
                    variants.append({
                        'condition': condition,
                        'variant_type': variant_key,
                        'frequency_number': variant_config['frequency_number'],
                        'frequency_unit': variant_config['frequency_unit'],
                        'description': variant_config['description']
                    })
        
        return variants
    
    def suggest_variants(self, screening_name: str) -> List[Dict[str, Any]]:
        """Suggest variants based on screening name"""
        suggestions = []
        screening_lower = screening_name.lower()
        
        for condition, condition_variants in self.variant_configs.items():
            for variant_key, variant_config in condition_variants.items():
                # Check if screening name suggests this variant
                if any(kw in screening_lower for kw in self._get_variant_detection_keywords(variant_key)):
                    suggestions.append({
                        'condition': condition,
                        'variant_type': variant_key,
                        'frequency_number': variant_config['frequency_number'],
                        'frequency_unit': variant_config['frequency_unit'],
                        'description': variant_config['description'],
                        'confidence': self._calculate_suggestion_confidence(screening_lower, variant_key)
                    })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions
    
    def _get_variant_detection_keywords(self, variant_key: str) -> List[str]:
        """Get keywords that help detect if a screening should use this variant"""
        detection_keywords = {
            'a1c': ['a1c', 'hba1c', 'hemoglobin', 'glycated'],
            'cholesterol': ['cholesterol', 'lipid', 'hdl', 'ldl', 'triglyceride'],
            'eye_exam': ['eye', 'ophthalmology', 'retinal', 'vision', 'fundus'],
            'kidney_function': ['kidney', 'renal', 'creatinine', 'bun', 'albumin'],
            'blood_pressure': ['blood pressure', 'bp', 'hypertension'],
            'dexa': ['dexa', 'dxa', 'bone', 'density', 'osteoporosis'],
            'pulmonary_function': ['pulmonary', 'lung', 'respiratory', 'spirometry'],
            'chest_xray': ['chest', 'cxr', 'radiograph', 'xray']
        }
        
        return detection_keywords.get(variant_key, [])
    
    def _calculate_suggestion_confidence(self, screening_name: str, variant_key: str) -> float:
        """Calculate confidence score for variant suggestion"""
        keywords = self._get_variant_detection_keywords(variant_key)
        matches = sum(1 for kw in keywords if kw in screening_name)
        return matches / len(keywords) if keywords else 0.0
"""
Screening variant handling
Manages different screening variants based on patient conditions
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

class VariantHandler:
    """Handles screening variant logic and frequency modifications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_variant_frequency(self, base_frequency_number: int, base_frequency_unit: str,
                            variant_type: str, trigger_condition: str = None) -> Dict[str, Any]:
        """
        Get modified frequency for a screening variant
        """
        if variant_type == 'base':
            return {
                'frequency_number': base_frequency_number,
                'frequency_unit': base_frequency_unit
            }
        
        if variant_type == 'trigger' and trigger_condition:
            return self._get_trigger_frequency(trigger_condition, base_frequency_number, base_frequency_unit)
        
        # Default to base frequency
        return {
            'frequency_number': base_frequency_number,
            'frequency_unit': base_frequency_unit
        }
    
    def _get_trigger_frequency(self, trigger_condition: str, base_frequency_number: int, 
                              base_frequency_unit: str) -> Dict[str, Any]:
        """Get frequency modification for trigger conditions"""
        
        trigger_lower = trigger_condition.lower()
        
        # Diabetes modifications
        if 'diabetes' in trigger_lower:
            if base_frequency_unit == 'years':
                return {'frequency_number': 6, 'frequency_unit': 'months'}
            elif base_frequency_unit == 'months' and base_frequency_number > 6:
                return {'frequency_number': 6, 'frequency_unit': 'months'}
        
        # Hypertension modifications
        if 'hypertension' in trigger_lower or 'high blood pressure' in trigger_lower:
            if base_frequency_unit == 'years':
                return {'frequency_number': 6, 'frequency_unit': 'months'}
            elif base_frequency_unit == 'months' and base_frequency_number > 3:
                return {'frequency_number': 3, 'frequency_unit': 'months'}
        
        # Hyperlipidemia modifications
        if 'hyperlipidemia' in trigger_lower or 'cholesterol' in trigger_lower:
            if base_frequency_unit == 'years':
                return {'frequency_number': 6, 'frequency_unit': 'months'}
        
        # Default to base frequency if no specific modification
        return {
            'frequency_number': base_frequency_number,
            'frequency_unit': base_frequency_unit
        }
    
    def apply_variant_rules(self, screening_type, patient_conditions: List[str]) -> List[Dict[str, Any]]:
        """
        Apply variant rules to determine all applicable screening variants
        """
        variants = []
        
        # Always include base variant
        base_variant = {
            'type': 'base',
            'frequency_number': screening_type.frequency_number,
            'frequency_unit': screening_type.frequency_unit,
            'trigger_condition': None,
            'priority': 0
        }
        variants.append(base_variant)
        
        # Check for trigger condition variants
        if screening_type.trigger_conditions_list:
            for trigger_condition in screening_type.trigger_conditions_list:
                if self._has_matching_condition(patient_conditions, trigger_condition):
                    frequency_mod = self._get_trigger_frequency(
                        trigger_condition, 
                        screening_type.frequency_number,
                        screening_type.frequency_unit
                    )
                    
                    trigger_variant = {
                        'type': 'trigger',
                        'frequency_number': frequency_mod['frequency_number'],
                        'frequency_unit': frequency_mod['frequency_unit'],
                        'trigger_condition': trigger_condition,
                        'priority': 1  # Higher priority than base
                    }
                    variants.append(trigger_variant)
        
        # Sort by priority (higher priority first)
        variants.sort(key=lambda x: x['priority'], reverse=True)
        
        return variants
    
    def _has_matching_condition(self, patient_conditions: List[str], trigger_condition: str) -> bool:
        """Check if patient has matching condition for trigger"""
        trigger_lower = trigger_condition.lower()
        
        for condition in patient_conditions:
            condition_lower = condition.lower()
            
            # Direct match
            if trigger_lower in condition_lower or condition_lower in trigger_lower:
                return True
            
            # Condition-specific matching
            if self._condition_matches(condition_lower, trigger_lower):
                return True
        
        return False
    
    def _condition_matches(self, patient_condition: str, trigger_condition: str) -> bool:
        """Enhanced condition matching with medical terminology"""
        
        # Diabetes variations
        if 'diabetes' in trigger_condition:
            diabetes_terms = ['diabetes', 'diabetic', 'dm', 'diabetes mellitus', 'type 1', 'type 2']
            return any(term in patient_condition for term in diabetes_terms)
        
        # Hypertension variations
        if 'hypertension' in trigger_condition:
            htn_terms = ['hypertension', 'high blood pressure', 'htn', 'elevated bp', 'bp']
            return any(term in patient_condition for term in htn_terms)
        
        # Hyperlipidemia variations
        if 'hyperlipidemia' in trigger_condition or 'cholesterol' in trigger_condition:
            cholesterol_terms = ['hyperlipidemia', 'high cholesterol', 'dyslipidemia', 'elevated cholesterol', 'lipid']
            return any(term in patient_condition for term in cholesterol_terms)
        
        return False
    
    def get_most_urgent_variant(self, variants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get the most urgent variant (shortest frequency interval)
        """
        if not variants:
            return None
        
        def frequency_to_days(freq_num: int, freq_unit: str) -> int:
            """Convert frequency to days for comparison"""
            if freq_unit.lower().startswith('day'):
                return freq_num
            elif freq_unit.lower().startswith('week'):
                return freq_num * 7
            elif freq_unit.lower().startswith('month'):
                return freq_num * 30
            elif freq_unit.lower().startswith('year'):
                return freq_num * 365
            return freq_num * 365
        
        # Sort by frequency in days (shortest first)
        sorted_variants = sorted(variants, key=lambda v: frequency_to_days(v['frequency_number'], v['frequency_unit']))
        
        return sorted_variants[0]
