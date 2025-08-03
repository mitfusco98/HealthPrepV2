"""
Handles screening type variants based on patient conditions
Allows different protocols for the same screening based on trigger conditions
"""
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class VariantHandler:
    """Manages screening type variants for different patient populations"""
    
    def __init__(self):
        # Define condition-specific variants
        self.variants = {
            'a1c': {
                'diabetes': {
                    'frequency_value': 3,
                    'frequency_unit': 'months',
                    'description': 'More frequent monitoring for diabetic patients'
                },
                'prediabetes': {
                    'frequency_value': 6,
                    'frequency_unit': 'months',
                    'description': 'Semi-annual monitoring for prediabetic patients'
                }
            },
            'lipid panel': {
                'hyperlipidemia': {
                    'frequency_value': 6,
                    'frequency_unit': 'months',
                    'description': 'More frequent monitoring for patients with dyslipidemia'
                },
                'diabetes': {
                    'frequency_value': 12,
                    'frequency_unit': 'months',
                    'description': 'Annual monitoring for diabetic patients'
                }
            },
            'microalbumin': {
                'diabetes': {
                    'frequency_value': 12,
                    'frequency_unit': 'months',
                    'description': 'Annual screening for diabetic nephropathy'
                },
                'hypertension': {
                    'frequency_value': 12,
                    'frequency_unit': 'months',
                    'description': 'Annual screening for hypertensive patients'
                }
            },
            'eye exam': {
                'diabetes': {
                    'frequency_value': 12,
                    'frequency_unit': 'months',
                    'description': 'Annual diabetic eye exam'
                }
            },
            'foot exam': {
                'diabetes': {
                    'frequency_value': 6,
                    'frequency_unit': 'months',
                    'description': 'Semi-annual diabetic foot exam'
                }
            }
        }
    
    def get_variant_for_patient(self, patient, screening_type):
        """Get the appropriate screening variant for a patient"""
        from models import Condition
        
        screening_name = screening_type.name.lower()
        
        if screening_name not in self.variants:
            return self.get_default_frequency(screening_type)
        
        # Get patient's active conditions
        patient_conditions = Condition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).all()
        
        condition_names = [self.normalize_condition_name(c.condition_name) for c in patient_conditions]
        
        # Check for matching variants (prioritize by order)
        for condition_name in condition_names:
            if condition_name in self.variants[screening_name]:
                variant = self.variants[screening_name][condition_name]
                return {
                    'frequency_value': variant['frequency_value'],
                    'frequency_unit': variant['frequency_unit'],
                    'description': variant['description'],
                    'is_variant': True,
                    'trigger_condition': condition_name
                }
        
        return self.get_default_frequency(screening_type)
    
    def get_default_frequency(self, screening_type):
        """Get the default frequency for a screening type"""
        return {
            'frequency_value': screening_type.frequency_value,
            'frequency_unit': screening_type.frequency_unit,
            'description': 'Standard frequency',
            'is_variant': False,
            'trigger_condition': None
        }
    
    def normalize_condition_name(self, condition_name):
        """Normalize condition names for matching"""
        condition_name = condition_name.lower().strip()
        
        # Common condition mappings
        mappings = {
            'diabetes mellitus': 'diabetes',
            'type 1 diabetes': 'diabetes',
            'type 2 diabetes': 'diabetes',
            'dm': 'diabetes',
            'diabetic': 'diabetes',
            'pre-diabetes': 'prediabetes',
            'impaired glucose tolerance': 'prediabetes',
            'high cholesterol': 'hyperlipidemia',
            'dyslipidemia': 'hyperlipidemia',
            'elevated cholesterol': 'hyperlipidemia',
            'high blood pressure': 'hypertension',
            'htn': 'hypertension',
            'elevated bp': 'hypertension'
        }
        
        return mappings.get(condition_name, condition_name)
    
    def calculate_next_due_date(self, last_completed, frequency_config):
        """Calculate the next due date based on frequency configuration"""
        if not last_completed:
            return datetime.utcnow()  # Due now if never completed
        
        frequency_value = frequency_config['frequency_value']
        frequency_unit = frequency_config['frequency_unit']
        
        if frequency_unit == 'months':
            next_due = last_completed + timedelta(days=frequency_value * 30)
        elif frequency_unit == 'years':
            next_due = last_completed + timedelta(days=frequency_value * 365)
        else:
            # Default to months if unit is unclear
            next_due = last_completed + timedelta(days=frequency_value * 30)
        
        return next_due
    
    def get_all_variants_for_screening(self, screening_name):
        """Get all available variants for a screening type"""
        screening_name = screening_name.lower()
        
        if screening_name not in self.variants:
            return []
        
        variants = []
        for condition, config in self.variants[screening_name].items():
            variants.append({
                'condition': condition,
                'frequency_value': config['frequency_value'],
                'frequency_unit': config['frequency_unit'],
                'description': config['description']
            })
        
        return variants
    
    def add_custom_variant(self, screening_name, condition, frequency_value, frequency_unit, description):
        """Add a custom variant for a screening type"""
        screening_name = screening_name.lower()
        condition = self.normalize_condition_name(condition)
        
        if screening_name not in self.variants:
            self.variants[screening_name] = {}
        
        self.variants[screening_name][condition] = {
            'frequency_value': frequency_value,
            'frequency_unit': frequency_unit,
            'description': description
        }
        
        logger.info(f"Added custom variant for {screening_name} with condition {condition}")
