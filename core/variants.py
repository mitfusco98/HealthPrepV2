"""
Handles screening type variants for different trigger conditions
"""
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import date
from dateutil.relativedelta import relativedelta
from models import Patient, ScreeningType, PatientCondition

logger = logging.getLogger(__name__)

class VariantProcessor:
    """Processes screening type variants based on patient trigger conditions"""
    
    def __init__(self):
        self.variant_rules = self._load_variant_rules()
    
    def _load_variant_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined variant rules for common conditions"""
        return {
            'diabetes': {
                'a1c': {'frequency_months': 3, 'priority': 'high'},
                'lipid panel': {'frequency_months': 6, 'priority': 'high'},
                'eye exam': {'frequency_months': 12, 'priority': 'high'},
                'foot exam': {'frequency_months': 6, 'priority': 'medium'}
            },
            'hypertension': {
                'blood pressure': {'frequency_months': 3, 'priority': 'high'},
                'lipid panel': {'frequency_months': 6, 'priority': 'medium'},
                'kidney function': {'frequency_months': 12, 'priority': 'medium'}
            },
            'high cholesterol': {
                'lipid panel': {'frequency_months': 6, 'priority': 'high'},
                'blood pressure': {'frequency_months': 6, 'priority': 'medium'}
            },
            'heart disease': {
                'blood pressure': {'frequency_months': 3, 'priority': 'high'},
                'lipid panel': {'frequency_months': 6, 'priority': 'high'},
                'ecg': {'frequency_months': 12, 'priority': 'medium'}
            },
            'family history of cancer': {
                'mammogram': {'frequency_months': 6, 'min_age': 40, 'priority': 'high'},
                'colonoscopy': {'frequency_months': 12, 'min_age': 45, 'priority': 'high'},
                'pap smear': {'frequency_months': 6, 'priority': 'medium'}
            },
            'osteoporosis': {
                'dexa': {'frequency_months': 12, 'priority': 'high'},
                'calcium': {'frequency_months': 6, 'priority': 'medium'},
                'vitamin d': {'frequency_months': 6, 'priority': 'medium'}
            }
        }
    
    def get_screening_variants(self, patient: Patient, screening_type: ScreeningType) -> List[Dict[str, Any]]:
        """
        Get all applicable variants for a screening type based on patient conditions
        Returns list of variant configurations
        """
        variants = []
        
        # Get patient conditions
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).all()
        
        if not patient_conditions:
            return [self._get_default_variant(screening_type)]
        
        # Check each condition for applicable variants
        for condition in patient_conditions:
            condition_variants = self._get_condition_variants(condition, screening_type)
            variants.extend(condition_variants)
        
        # If no condition-specific variants found, return default
        if not variants:
            variants.append(self._get_default_variant(screening_type))
        
        # Remove duplicates and prioritize
        return self._prioritize_variants(variants)
    
    def _get_condition_variants(self, condition: PatientCondition, screening_type: ScreeningType) -> List[Dict[str, Any]]:
        """Get variants for a specific condition"""
        variants = []
        condition_name_lower = condition.condition_name.lower()
        screening_name_lower = screening_type.name.lower()
        
        # Check predefined variant rules
        for rule_condition, screenings in self.variant_rules.items():
            if rule_condition in condition_name_lower:
                for screening_pattern, variant_config in screenings.items():
                    if screening_pattern in screening_name_lower:
                        variant = self._create_variant(
                            screening_type, 
                            variant_config, 
                            condition.condition_name,
                            rule_condition
                        )
                        variants.append(variant)
        
        return variants
    
    def _create_variant(self, screening_type: ScreeningType, config: Dict[str, Any], 
                       condition_name: str, rule_condition: str) -> Dict[str, Any]:
        """Create a variant configuration"""
        return {
            'screening_type_id': screening_type.id,
            'screening_name': screening_type.name,
            'original_frequency': screening_type.frequency_months,
            'variant_frequency': config.get('frequency_months', screening_type.frequency_months),
            'priority': config.get('priority', 'medium'),
            'min_age': config.get('min_age', screening_type.min_age),
            'max_age': config.get('max_age', screening_type.max_age),
            'trigger_condition': condition_name,
            'rule_condition': rule_condition,
            'description': f"Modified frequency due to {condition_name}",
            'is_variant': True
        }
    
    def _get_default_variant(self, screening_type: ScreeningType) -> Dict[str, Any]:
        """Get default (non-variant) configuration"""
        return {
            'screening_type_id': screening_type.id,
            'screening_name': screening_type.name,
            'original_frequency': screening_type.frequency_months,
            'variant_frequency': screening_type.frequency_months,
            'priority': 'standard',
            'min_age': screening_type.min_age,
            'max_age': screening_type.max_age,
            'trigger_condition': None,
            'rule_condition': None,
            'description': "Standard screening protocol",
            'is_variant': False
        }
    
    def _prioritize_variants(self, variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and prioritize variants"""
        # Group by screening type
        grouped = {}
        for variant in variants:
            screening_id = variant['screening_type_id']
            if screening_id not in grouped:
                grouped[screening_id] = []
            grouped[screening_id].append(variant)
        
        # Select highest priority variant for each screening type
        priority_order = {'high': 3, 'medium': 2, 'low': 1, 'standard': 0}
        final_variants = []
        
        for screening_id, variant_list in grouped.items():
            # Sort by priority and select highest
            variant_list.sort(key=lambda v: priority_order.get(v['priority'], 0), reverse=True)
            final_variants.append(variant_list[0])
        
        return final_variants
    
    def calculate_variant_next_due_date(self, last_completed_date: date, variant: Dict[str, Any]) -> date:
        """Calculate next due date using variant frequency"""
        frequency_months = variant['variant_frequency']
        return last_completed_date + relativedelta(months=frequency_months)
    
    def get_variant_urgency_level(self, variant: Dict[str, Any], next_due_date: date) -> str:
        """Determine urgency level considering variant priority"""
        today = date.today()
        days_until_due = (next_due_date - today).days
        priority = variant.get('priority', 'standard')
        
        # High priority conditions have stricter urgency thresholds
        if priority == 'high':
            if days_until_due <= 0:
                return 'critical'
            elif days_until_due <= 14:
                return 'urgent'
            elif days_until_due <= 30:
                return 'high'
            else:
                return 'medium'
        elif priority == 'medium':
            if days_until_due <= 0:
                return 'urgent'
            elif days_until_due <= 30:
                return 'high'
            elif days_until_due <= 60:
                return 'medium'
            else:
                return 'low'
        else:  # standard or low priority
            if days_until_due <= 0:
                return 'high'
            elif days_until_due <= 30:
                return 'medium'
            else:
                return 'low'
    
    def create_screening_variant(self, base_screening_type: ScreeningType, 
                               condition_name: str, variant_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new screening variant programmatically"""
        
        variant_name = f"{base_screening_type.name} (for {condition_name})"
        
        return {
            'name': variant_name,
            'description': f"Modified {base_screening_type.name} protocol for patients with {condition_name}",
            'keywords': base_screening_type.keywords,
            'frequency_months': variant_config.get('frequency_months', base_screening_type.frequency_months),
            'frequency_unit': base_screening_type.frequency_unit,
            'min_age': variant_config.get('min_age', base_screening_type.min_age),
            'max_age': variant_config.get('max_age', base_screening_type.max_age),
            'gender_restrictions': base_screening_type.gender_restrictions,
            'trigger_conditions': json.dumps([condition_name]),
            'is_active': True,
            'priority': variant_config.get('priority', 'medium'),
            'parent_screening_type_id': base_screening_type.id
        }
    
    def validate_variant_configuration(self, variant_config: Dict[str, Any]) -> List[str]:
        """Validate variant configuration and return list of errors"""
        errors = []
        
        required_fields = ['frequency_months', 'priority']
        for field in required_fields:
            if field not in variant_config:
                errors.append(f"Missing required field: {field}")
        
        if 'frequency_months' in variant_config:
            if not isinstance(variant_config['frequency_months'], int) or variant_config['frequency_months'] <= 0:
                errors.append("frequency_months must be a positive integer")
        
        if 'priority' in variant_config:
            valid_priorities = ['low', 'medium', 'high', 'critical']
            if variant_config['priority'] not in valid_priorities:
                errors.append(f"priority must be one of: {', '.join(valid_priorities)}")
        
        return errors
