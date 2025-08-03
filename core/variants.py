"""
Handles screening type variants for different trigger conditions.
Allows different screening protocols for the same screening type based on patient conditions.
"""

import logging
from typing import List, Dict, Optional, Any
import json

from models import ScreeningType, Patient, Screening

class ScreeningVariants:
    """Manages screening type variants based on trigger conditions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_applicable_variant(self, screening_type: ScreeningType, patient: Patient) -> Dict[str, Any]:
        """Get the applicable screening variant for a patient"""
        try:
            # If no trigger conditions, return base screening parameters
            if not screening_type.trigger_conditions:
                return self._get_base_variant(screening_type)
            
            # Parse trigger conditions to find matching variant
            trigger_conditions = self._parse_trigger_conditions(screening_type.trigger_conditions)
            
            # For each variant, check if patient matches the conditions
            for variant in trigger_conditions:
                if self._patient_matches_variant(patient, variant):
                    return self._merge_variant_with_base(screening_type, variant)
            
            # If no variant matches, return base variant
            return self._get_base_variant(screening_type)
            
        except Exception as e:
            self.logger.error(f"Error getting variant for screening {screening_type.id} and patient {patient.id}: {str(e)}")
            return self._get_base_variant(screening_type)
    
    def _get_base_variant(self, screening_type: ScreeningType) -> Dict[str, Any]:
        """Get base screening parameters without any variants"""
        return {
            'name': screening_type.name,
            'description': screening_type.description,
            'frequency_number': screening_type.frequency_number,
            'frequency_unit': screening_type.frequency_unit,
            'keywords': screening_type.get_keywords_list(),
            'min_age': screening_type.min_age,
            'max_age': screening_type.max_age,
            'variant_type': 'base'
        }
    
    def _parse_trigger_conditions(self, trigger_conditions: str) -> List[Dict[str, Any]]:
        """Parse trigger conditions string into structured variants"""
        try:
            # Try to parse as JSON first
            parsed = json.loads(trigger_conditions)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
            else:
                return []
        except (json.JSONDecodeError, TypeError):
            # If not JSON, try to parse as simple condition list
            return self._parse_simple_conditions(trigger_conditions)
    
    def _parse_simple_conditions(self, conditions_text: str) -> List[Dict[str, Any]]:
        """Parse simple text-based condition specifications"""
        variants = []
        
        # Example parsing for conditions like:
        # "diabetes: 3 months"
        # "hypertension: 6 months"
        
        lines = conditions_text.split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line:
                condition, frequency = line.split(':', 1)
                condition = condition.strip().lower()
                frequency = frequency.strip()
                
                # Parse frequency (e.g., "3 months", "1 year")
                freq_parts = frequency.split()
                if len(freq_parts) >= 2:
                    try:
                        freq_number = int(freq_parts[0])
                        freq_unit = freq_parts[1].lower()
                        if freq_unit.endswith('s'):
                            freq_unit = freq_unit[:-1]  # Remove plural 's'
                        
                        variants.append({
                            'conditions': [condition],
                            'frequency_number': freq_number,
                            'frequency_unit': freq_unit + 's',  # Ensure plural for consistency
                            'variant_type': f'{condition}_variant'
                        })
                    except ValueError:
                        continue
        
        return variants
    
    def _patient_matches_variant(self, patient: Patient, variant: Dict[str, Any]) -> bool:
        """Check if a patient matches the conditions for a variant"""
        if 'conditions' not in variant:
            return False
        
        required_conditions = variant['conditions']
        if not required_conditions:
            return False
        
        # In a full implementation, this would check against patient's actual medical conditions
        # For now, we'll use a simplified approach
        
        # This is where you would integrate with patient condition data
        # For example, checking if patient has diabetes, hypertension, etc.
        # patient_conditions = self._get_patient_conditions(patient)
        
        # Simplified implementation - always return False for now
        # In production, implement proper condition matching
        return False
    
    def _merge_variant_with_base(self, screening_type: ScreeningType, variant: Dict[str, Any]) -> Dict[str, Any]:
        """Merge variant parameters with base screening type"""
        base = self._get_base_variant(screening_type)
        
        # Override base parameters with variant-specific ones
        if 'frequency_number' in variant:
            base['frequency_number'] = variant['frequency_number']
        
        if 'frequency_unit' in variant:
            base['frequency_unit'] = variant['frequency_unit']
        
        if 'keywords' in variant:
            # Merge keywords (variant keywords take precedence)
            base_keywords = set(base['keywords'])
            variant_keywords = set(variant['keywords'])
            base['keywords'] = list(base_keywords.union(variant_keywords))
        
        if 'min_age' in variant:
            base['min_age'] = variant['min_age']
        
        if 'max_age' in variant:
            base['max_age'] = variant['max_age']
        
        base['variant_type'] = variant.get('variant_type', 'custom')
        base['variant_conditions'] = variant.get('conditions', [])
        
        return base
    
    def create_screening_variant(self, base_screening_type: ScreeningType, variant_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new screening variant configuration"""
        try:
            # Validate variant configuration
            if not self._validate_variant_config(variant_config):
                raise ValueError("Invalid variant configuration")
            
            # Get current trigger conditions
            current_conditions = []
            if base_screening_type.trigger_conditions:
                current_conditions = self._parse_trigger_conditions(base_screening_type.trigger_conditions)
            
            # Add new variant
            current_conditions.append(variant_config)
            
            # Update screening type
            base_screening_type.trigger_conditions = json.dumps(current_conditions)
            
            return variant_config
            
        except Exception as e:
            self.logger.error(f"Error creating screening variant: {str(e)}")
            raise
    
    def _validate_variant_config(self, config: Dict[str, Any]) -> bool:
        """Validate variant configuration"""
        required_fields = ['conditions', 'frequency_number', 'frequency_unit']
        
        for field in required_fields:
            if field not in config:
                return False
        
        # Validate frequency
        if not isinstance(config['frequency_number'], int) or config['frequency_number'] <= 0:
            return False
        
        if config['frequency_unit'] not in ['months', 'years']:
            return False
        
        # Validate conditions
        if not isinstance(config['conditions'], list) or not config['conditions']:
            return False
        
        return True
    
    def get_variant_description(self, variant: Dict[str, Any]) -> str:
        """Get human-readable description of a variant"""
        if variant.get('variant_type') == 'base':
            return "Standard screening schedule"
        
        conditions = variant.get('variant_conditions', [])
        frequency_number = variant.get('frequency_number')
        frequency_unit = variant.get('frequency_unit')
        
        if conditions and frequency_number and frequency_unit:
            condition_text = ', '.join(conditions)
            unit_text = frequency_unit if frequency_number > 1 else frequency_unit.rstrip('s')
            return f"For patients with {condition_text}: every {frequency_number} {unit_text}"
        
        return "Custom variant"
    
    def get_all_variants(self, screening_type: ScreeningType) -> List[Dict[str, Any]]:
        """Get all variants for a screening type"""
        variants = [self._get_base_variant(screening_type)]
        
        if screening_type.trigger_conditions:
            condition_variants = self._parse_trigger_conditions(screening_type.trigger_conditions)
            for variant in condition_variants:
                merged_variant = self._merge_variant_with_base(screening_type, variant)
                variants.append(merged_variant)
        
        return variants
    
    def remove_variant(self, screening_type: ScreeningType, variant_index: int) -> bool:
        """Remove a variant from a screening type"""
        try:
            if not screening_type.trigger_conditions:
                return False
            
            current_conditions = self._parse_trigger_conditions(screening_type.trigger_conditions)
            
            if variant_index < 0 or variant_index >= len(current_conditions):
                return False
            
            # Remove the variant
            current_conditions.pop(variant_index)
            
            # Update screening type
            if current_conditions:
                screening_type.trigger_conditions = json.dumps(current_conditions)
            else:
                screening_type.trigger_conditions = None
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing variant: {str(e)}")
            return False
