"""
Import/export logic for screening type presets
Handles loading specialty-specific screening configurations
"""
import json
import os
import logging
from app import db
from models import ScreeningType, AdminLog
from datetime import datetime

logger = logging.getLogger(__name__)

class PresetLoader:
    """Handles loading and managing screening type presets"""
    
    def __init__(self):
        self.presets_directory = os.path.join(os.path.dirname(__file__), 'examples')
        
    def get_available_presets(self):
        """Get list of available preset files"""
        presets = []
        
        if not os.path.exists(self.presets_directory):
            return presets
        
        for filename in os.listdir(self.presets_directory):
            if filename.endswith('.json'):
                preset_path = os.path.join(self.presets_directory, filename)
                try:
                    with open(preset_path, 'r') as f:
                        preset_data = json.load(f)
                        presets.append({
                            'filename': filename,
                            'name': preset_data.get('name', filename),
                            'description': preset_data.get('description', ''),
                            'specialty': preset_data.get('specialty', 'General'),
                            'screening_count': len(preset_data.get('screenings', []))
                        })
                except Exception as e:
                    logger.error(f"Error reading preset {filename}: {e}")
        
        return presets
    
    def load_preset(self, filename, user_id=None, replace_existing=False):
        """Load a screening preset from file"""
        preset_path = os.path.join(self.presets_directory, filename)
        
        if not os.path.exists(preset_path):
            raise FileNotFoundError(f"Preset file not found: {filename}")
        
        try:
            with open(preset_path, 'r') as f:
                preset_data = json.load(f)
            
            results = {
                'loaded': 0,
                'skipped': 0,
                'errors': [],
                'preset_info': {
                    'name': preset_data.get('name', filename),
                    'description': preset_data.get('description', ''),
                    'specialty': preset_data.get('specialty', 'General')
                }
            }
            
            screenings = preset_data.get('screenings', [])
            
            for screening_config in screenings:
                try:
                    success = self.create_screening_type(screening_config, replace_existing)
                    if success:
                        results['loaded'] += 1
                    else:
                        results['skipped'] += 1
                except Exception as e:
                    results['errors'].append(f"Error creating {screening_config.get('name', 'unknown')}: {str(e)}")
            
            # Log the preset loading
            if user_id:
                AdminLog.create_log(
                    user_id=user_id,
                    action='load_preset',
                    resource_type='screening_preset',
                    details={
                        'filename': filename,
                        'loaded': results['loaded'],
                        'skipped': results['skipped'],
                        'errors': len(results['errors'])
                    }
                )
            
            db.session.commit()
            logger.info(f"Loaded preset {filename}: {results['loaded']} screenings created, {results['skipped']} skipped")
            
            return results
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in preset file: {e}")
        except Exception as e:
            logger.error(f"Error loading preset {filename}: {e}")
            raise
    
    def create_screening_type(self, config, replace_existing=False):
        """Create a screening type from configuration"""
        name = config.get('name')
        if not name:
            raise ValueError("Screening name is required")
        
        # Check if screening type already exists
        existing = ScreeningType.query.filter_by(name=name).first()
        
        if existing and not replace_existing:
            logger.info(f"Screening type '{name}' already exists, skipping")
            return False
        
        if existing and replace_existing:
            # Update existing screening type
            screening_type = existing
        else:
            # Create new screening type
            screening_type = ScreeningType()
        
        # Set properties from config
        screening_type.name = name
        screening_type.description = config.get('description', '')
        screening_type.keywords = config.get('keywords', [])
        
        # Parse eligibility criteria
        eligibility = config.get('eligibility', {})
        screening_type.eligibility_criteria = {
            'gender': eligibility.get('gender', 'any'),
            'min_age': eligibility.get('min_age'),
            'max_age': eligibility.get('max_age')
        }
        
        # Parse frequency
        frequency = config.get('frequency', {})
        screening_type.frequency_value = frequency.get('value', 12)
        screening_type.frequency_unit = frequency.get('unit', 'months')
        
        # Parse trigger conditions
        screening_type.trigger_conditions = config.get('trigger_conditions', [])
        
        # Set status
        screening_type.status = config.get('status', 'active')
        
        if not existing:
            db.session.add(screening_type)
        
        return True
    
    def export_screening_types(self, screening_type_ids=None, specialty_name="Custom"):
        """Export screening types to preset format"""
        if screening_type_ids:
            screening_types = ScreeningType.query.filter(
                ScreeningType.id.in_(screening_type_ids)
            ).all()
        else:
            screening_types = ScreeningType.query.filter_by(status='active').all()
        
        preset_data = {
            'name': f"{specialty_name} Screening Preset",
            'description': f"Exported screening types for {specialty_name}",
            'specialty': specialty_name,
            'version': "1.0",
            'created_date': datetime.utcnow().isoformat(),
            'screenings': []
        }
        
        for st in screening_types:
            screening_config = {
                'name': st.name,
                'description': st.description,
                'keywords': st.keywords or [],
                'eligibility': st.eligibility_criteria or {},
                'frequency': {
                    'value': st.frequency_value,
                    'unit': st.frequency_unit
                },
                'trigger_conditions': st.trigger_conditions or [],
                'status': st.status
            }
            preset_data['screenings'].append(screening_config)
        
        return preset_data
    
    def save_preset_to_file(self, preset_data, filename):
        """Save preset data to file"""
        if not filename.endswith('.json'):
            filename += '.json'
        
        preset_path = os.path.join(self.presets_directory, filename)
        
        # Ensure directory exists
        os.makedirs(self.presets_directory, exist_ok=True)
        
        with open(preset_path, 'w') as f:
            json.dump(preset_data, f, indent=2, default=str)
        
        logger.info(f"Saved preset to {preset_path}")
        return preset_path
    
    def validate_preset_format(self, preset_data):
        """Validate preset data format"""
        errors = []
        
        if not isinstance(preset_data, dict):
            errors.append("Preset data must be a JSON object")
            return errors
        
        # Check required fields
        if 'screenings' not in preset_data:
            errors.append("Preset must contain 'screenings' array")
            return errors
        
        if not isinstance(preset_data['screenings'], list):
            errors.append("'screenings' must be an array")
            return errors
        
        # Validate each screening
        for i, screening in enumerate(preset_data['screenings']):
            if not isinstance(screening, dict):
                errors.append(f"Screening {i+1} must be an object")
                continue
            
            if 'name' not in screening:
                errors.append(f"Screening {i+1} missing required 'name' field")
            
            if 'frequency' in screening:
                freq = screening['frequency']
                if not isinstance(freq, dict) or 'value' not in freq or 'unit' not in freq:
                    errors.append(f"Screening {i+1} has invalid frequency format")
                
                if freq.get('unit') not in ['months', 'years']:
                    errors.append(f"Screening {i+1} frequency unit must be 'months' or 'years'")
        
        return errors
    
    def get_preset_details(self, filename):
        """Get detailed information about a preset file"""
        preset_path = os.path.join(self.presets_directory, filename)
        
        if not os.path.exists(preset_path):
            raise FileNotFoundError(f"Preset file not found: {filename}")
        
        with open(preset_path, 'r') as f:
            preset_data = json.load(f)
        
        # Validate format
        validation_errors = self.validate_preset_format(preset_data)
        
        details = {
            'name': preset_data.get('name', filename),
            'description': preset_data.get('description', ''),
            'specialty': preset_data.get('specialty', 'General'),
            'version': preset_data.get('version', '1.0'),
            'created_date': preset_data.get('created_date'),
            'screening_count': len(preset_data.get('screenings', [])),
            'screenings': [],
            'validation_errors': validation_errors,
            'is_valid': len(validation_errors) == 0
        }
        
        # Get screening details
        for screening in preset_data.get('screenings', []):
            screening_detail = {
                'name': screening.get('name', 'Unknown'),
                'description': screening.get('description', ''),
                'frequency': screening.get('frequency', {}),
                'eligibility': screening.get('eligibility', {}),
                'keywords_count': len(screening.get('keywords', [])),
                'trigger_conditions_count': len(screening.get('trigger_conditions', []))
            }
            details['screenings'].append(screening_detail)
        
        return details
