import json
import os
from models import ScreeningType
from app import db
import logging

class ScreeningPresetLoader:
    """Loads and manages screening type presets"""
    
    def __init__(self):
        self.presets_dir = os.path.join(os.path.dirname(__file__), 'examples')
    
    def load_preset_file(self, filename):
        """Load screening types from a preset file"""
        file_path = os.path.join(self.presets_dir, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Preset file not found: {filename}")
        
        try:
            with open(file_path, 'r') as f:
                preset_data = json.load(f)
            
            return self._process_preset_data(preset_data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in preset file {filename}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error loading preset file {filename}: {str(e)}")
    
    def import_preset(self, preset_name, overwrite=False):
        """Import a preset into the database"""
        filename = f"{preset_name}.json"
        screening_types = self.load_preset_file(filename)
        
        imported_count = 0
        errors = []
        
        for screening_data in screening_types:
            try:
                # Check if screening type already exists
                existing = ScreeningType.query.filter_by(name=screening_data['name']).first()
                
                if existing and not overwrite:
                    continue
                
                if existing and overwrite:
                    # Update existing
                    for key, value in screening_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    screening_type = existing
                else:
                    # Create new
                    screening_type = ScreeningType(**screening_data)
                    db.session.add(screening_type)
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Error importing {screening_data.get('name', 'Unknown')}: {str(e)}")
        
        try:
            db.session.commit()
            logging.info(f"Successfully imported {imported_count} screening types from {preset_name}")
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Database error during import: {str(e)}")
        
        return {
            'imported_count': imported_count,
            'errors': errors
        }
    
    def export_preset(self, screening_type_ids, preset_name):
        """Export screening types to a preset file"""
        screening_types = ScreeningType.query.filter(
            ScreeningType.id.in_(screening_type_ids)
        ).all()
        
        if not screening_types:
            raise ValueError("No screening types found with provided IDs")
        
        preset_data = {
            'name': preset_name,
            'description': f'Exported screening types preset - {preset_name}',
            'created_at': datetime.utcnow().isoformat(),
            'screening_types': []
        }
        
        for screening_type in screening_types:
            screening_data = {
                'name': screening_type.name,
                'description': screening_type.description,
                'keywords': screening_type.keywords,
                'min_age': screening_type.min_age,
                'max_age': screening_type.max_age,
                'gender_restriction': screening_type.gender_restriction,
                'frequency_value': screening_type.frequency_value,
                'frequency_unit': screening_type.frequency_unit,
                'trigger_conditions': screening_type.trigger_conditions,
                'is_active': screening_type.is_active
            }
            preset_data['screening_types'].append(screening_data)
        
        # Save to file
        filename = f"{preset_name.lower().replace(' ', '_')}.json"
        file_path = os.path.join(self.presets_dir, filename)
        
        try:
            with open(file_path, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            logging.info(f"Exported {len(screening_types)} screening types to {filename}")
            return filename
            
        except Exception as e:
            raise Exception(f"Error saving preset file: {str(e)}")
    
    def list_available_presets(self):
        """List all available preset files"""
        if not os.path.exists(self.presets_dir):
            return []
        
        presets = []
        for filename in os.listdir(self.presets_dir):
            if filename.endswith('.json'):
                try:
                    preset_info = self._get_preset_info(filename)
                    presets.append(preset_info)
                except Exception as e:
                    logging.warning(f"Could not read preset file {filename}: {str(e)}")
        
        return presets
    
    def _process_preset_data(self, preset_data):
        """Process raw preset data into screening type objects"""
        if 'screening_types' not in preset_data:
            raise ValueError("Preset file must contain 'screening_types' array")
        
        screening_types = []
        
        for item in preset_data['screening_types']:
            # Validate required fields
            required_fields = ['name', 'frequency_value', 'frequency_unit']
            for field in required_fields:
                if field not in item:
                    raise ValueError(f"Missing required field '{field}' in screening type")
            
            # Set defaults for optional fields
            screening_data = {
                'name': item['name'],
                'description': item.get('description', ''),
                'keywords': item.get('keywords', []),
                'min_age': item.get('min_age'),
                'max_age': item.get('max_age'),
                'gender_restriction': item.get('gender_restriction'),
                'frequency_value': item['frequency_value'],
                'frequency_unit': item['frequency_unit'],
                'trigger_conditions': item.get('trigger_conditions', []),
                'is_active': item.get('is_active', True)
            }
            
            screening_types.append(screening_data)
        
        return screening_types
    
    def _get_preset_info(self, filename):
        """Get basic information about a preset file"""
        file_path = os.path.join(self.presets_dir, filename)
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        screening_count = len(data.get('screening_types', []))
        
        return {
            'filename': filename,
            'name': data.get('name', filename.replace('.json', '')),
            'description': data.get('description', 'No description available'),
            'screening_count': screening_count,
            'created_at': data.get('created_at')
        }
