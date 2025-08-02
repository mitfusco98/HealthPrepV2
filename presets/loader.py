"""
Screening type preset import/export functionality
"""
import json
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from app import db
from models import ScreeningType

logger = logging.getLogger(__name__)

class PresetLoader:
    """Handles loading and managing screening type presets"""
    
    def __init__(self):
        self.presets_directory = os.path.join(os.path.dirname(__file__), 'examples')
        self.ensure_presets_directory()
    
    def ensure_presets_directory(self):
        """Ensure presets directory exists"""
        if not os.path.exists(self.presets_directory):
            os.makedirs(self.presets_directory)
    
    def load_preset_file(self, filename: str) -> Dict[str, Any]:
        """Load a specific preset file"""
        try:
            filepath = os.path.join(self.presets_directory, filename)
            
            if not os.path.exists(filepath):
                logger.error(f"Preset file not found: {filename}")
                return {'success': False, 'error': 'File not found'}
            
            with open(filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Validate preset structure
            validation_result = self._validate_preset(preset_data)
            if not validation_result['valid']:
                return {
                    'success': False, 
                    'error': f"Invalid preset format: {validation_result['errors']}"
                }
            
            return {
                'success': True,
                'data': preset_data,
                'filename': filename
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in preset {filename}: {str(e)}")
            return {'success': False, 'error': f'Invalid JSON format: {str(e)}'}
        except Exception as e:
            logger.error(f"Error loading preset {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def list_available_presets(self) -> List[Dict[str, Any]]:
        """List all available preset files"""
        presets = []
        
        try:
            for filename in os.listdir(self.presets_directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.presets_directory, filename)
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            preset_data = json.load(f)
                        
                        presets.append({
                            'filename': filename,
                            'name': preset_data.get('name', filename),
                            'description': preset_data.get('description', ''),
                            'specialty': preset_data.get('specialty', 'General'),
                            'screening_count': len(preset_data.get('screening_types', [])),
                            'version': preset_data.get('version', '1.0')
                        })
                    except Exception as e:
                        logger.warning(f"Error reading preset metadata from {filename}: {str(e)}")
                        presets.append({
                            'filename': filename,
                            'name': filename,
                            'description': 'Error reading file',
                            'specialty': 'Unknown',
                            'screening_count': 0,
                            'version': 'Unknown'
                        })
            
        except Exception as e:
            logger.error(f"Error listing preset files: {str(e)}")
        
        return sorted(presets, key=lambda x: x['name'])
    
    def import_preset(self, filename: str, overwrite: bool = False) -> Dict[str, Any]:
        """Import screening types from a preset file"""
        try:
            # Load preset data
            load_result = self.load_preset_file(filename)
            if not load_result['success']:
                return load_result
            
            preset_data = load_result['data']
            screening_types = preset_data.get('screening_types', [])
            
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for screening_data in screening_types:
                try:
                    result = self._import_single_screening(screening_data, overwrite)
                    if result['success']:
                        imported_count += 1
                    else:
                        skipped_count += 1
                        if result.get('error'):
                            errors.append(f"{screening_data.get('name', 'Unknown')}: {result['error']}")
                
                except Exception as e:
                    skipped_count += 1
                    errors.append(f"{screening_data.get('name', 'Unknown')}: {str(e)}")
            
            # Commit all changes
            try:
                db.session.commit()
                logger.info(f"Successfully imported {imported_count} screening types from {filename}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error committing preset import: {str(e)}")
                return {'success': False, 'error': f'Database error: {str(e)}'}
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'total_screenings': len(screening_types)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error importing preset {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _import_single_screening(self, screening_data: Dict[str, Any], overwrite: bool) -> Dict[str, Any]:
        """Import a single screening type"""
        try:
            name = screening_data.get('name')
            if not name:
                return {'success': False, 'error': 'Missing screening name'}
            
            # Check if screening type already exists
            existing = ScreeningType.query.filter_by(name=name).first()
            
            if existing and not overwrite:
                return {'success': False, 'error': 'Already exists (use overwrite to replace)'}
            
            # Create or update screening type
            if existing and overwrite:
                screening_type = existing
            else:
                screening_type = ScreeningType()
            
            # Set attributes
            screening_type.name = name
            screening_type.description = screening_data.get('description', '')
            screening_type.keywords = json.dumps(screening_data.get('keywords', []))
            screening_type.frequency_months = screening_data.get('frequency_months', 12)
            screening_type.frequency_unit = screening_data.get('frequency_unit', 'months')
            screening_type.min_age = screening_data.get('min_age')
            screening_type.max_age = screening_data.get('max_age')
            screening_type.gender_restrictions = screening_data.get('gender_restrictions')
            screening_type.trigger_conditions = json.dumps(screening_data.get('trigger_conditions', []))
            screening_type.is_active = screening_data.get('is_active', True)
            
            if not existing:
                db.session.add(screening_type)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error importing screening type: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def export_current_screenings(self, specialty: str = "Custom") -> Dict[str, Any]:
        """Export current screening types to preset format"""
        try:
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            export_data = {
                'name': f"{specialty} Screening Preset",
                'description': f"Exported screening types for {specialty}",
                'specialty': specialty,
                'version': '1.0',
                'created_date': datetime.utcnow().isoformat(),
                'screening_types': []
            }
            
            for screening in screening_types:
                screening_dict = {
                    'name': screening.name,
                    'description': screening.description,
                    'keywords': json.loads(screening.keywords) if screening.keywords else [],
                    'frequency_months': screening.frequency_months,
                    'frequency_unit': screening.frequency_unit,
                    'min_age': screening.min_age,
                    'max_age': screening.max_age,
                    'gender_restrictions': screening.gender_restrictions,
                    'trigger_conditions': json.loads(screening.trigger_conditions) if screening.trigger_conditions else [],
                    'is_active': screening.is_active
                }
                export_data['screening_types'].append(screening_dict)
            
            return {
                'success': True,
                'data': export_data,
                'count': len(screening_types)
            }
            
        except Exception as e:
            logger.error(f"Error exporting screenings: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def save_preset(self, preset_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Save preset data to file"""
        try:
            # Validate preset data
            validation_result = self._validate_preset(preset_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f"Invalid preset data: {validation_result['errors']}"
                }
            
            # Ensure filename has .json extension
            if not filename.endswith('.json'):
                filename += '.json'
            
            filepath = os.path.join(self.presets_directory, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved preset to {filename}")
            return {'success': True, 'filename': filename}
            
        except Exception as e:
            logger.error(f"Error saving preset {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _validate_preset(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate preset data structure"""
        errors = []
        
        # Check required fields
        required_fields = ['name', 'screening_types']
        for field in required_fields:
            if field not in preset_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate screening types
        if 'screening_types' in preset_data:
            if not isinstance(preset_data['screening_types'], list):
                errors.append("screening_types must be a list")
            else:
                for i, screening in enumerate(preset_data['screening_types']):
                    if not isinstance(screening, dict):
                        errors.append(f"Screening type {i} must be an object")
                        continue
                    
                    if 'name' not in screening:
                        errors.append(f"Screening type {i} missing name")
                    
                    # Validate frequency_months
                    if 'frequency_months' in screening:
                        if not isinstance(screening['frequency_months'], int) or screening['frequency_months'] <= 0:
                            errors.append(f"Screening type {i} has invalid frequency_months")
                    
                    # Validate keywords
                    if 'keywords' in screening:
                        if not isinstance(screening['keywords'], list):
                            errors.append(f"Screening type {i} keywords must be a list")
                    
                    # Validate trigger_conditions
                    if 'trigger_conditions' in screening:
                        if not isinstance(screening['trigger_conditions'], list):
                            errors.append(f"Screening type {i} trigger_conditions must be a list")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def get_preset_by_specialty(self, specialty: str) -> List[Dict[str, Any]]:
        """Get presets filtered by specialty"""
        all_presets = self.list_available_presets()
        return [p for p in all_presets if p['specialty'].lower() == specialty.lower()]
    
    def delete_preset(self, filename: str) -> Dict[str, Any]:
        """Delete a preset file"""
        try:
            filepath = os.path.join(self.presets_directory, filename)
            
            if not os.path.exists(filepath):
                return {'success': False, 'error': 'File not found'}
            
            os.remove(filepath)
            logger.info(f"Deleted preset file: {filename}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error deleting preset {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}

# Global preset loader instance
preset_loader = PresetLoader()
