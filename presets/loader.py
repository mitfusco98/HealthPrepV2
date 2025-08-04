"""
Screening type preset loader
Handles importing and managing screening presets for different specialties
"""
import logging
import json
import os
from typing import Dict, List, Any, Optional

from app import db
from models import ScreeningType, User

class PresetLoader:
    """Loads and manages screening type presets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.presets_dir = os.path.join(os.path.dirname(__file__), 'examples')
    
    def get_available_presets(self) -> List[Dict[str, Any]]:
        """Get list of available preset files"""
        
        presets = []
        
        try:
            if not os.path.exists(self.presets_dir):
                self.logger.warning(f"Presets directory not found: {self.presets_dir}")
                return []
            
            for filename in os.listdir(self.presets_dir):
                if filename.endswith('.json'):
                    preset_path = os.path.join(self.presets_dir, filename)
                    
                    try:
                        with open(preset_path, 'r') as f:
                            preset_data = json.load(f)
                        
                        presets.append({
                            'filename': filename,
                            'name': preset_data.get('name', filename.replace('.json', '')),
                            'description': preset_data.get('description', 'No description available'),
                            'specialty': preset_data.get('specialty', 'General'),
                            'screening_count': len(preset_data.get('screening_types', [])),
                            'version': preset_data.get('version', '1.0')
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Error reading preset file {filename}: {str(e)}")
            
            return sorted(presets, key=lambda x: x['name'])
            
        except Exception as e:
            self.logger.error(f"Error getting available presets: {str(e)}")
            return []
    
    def load_preset(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load a specific preset file"""
        
        try:
            preset_path = os.path.join(self.presets_dir, filename)
            
            if not os.path.exists(preset_path):
                self.logger.error(f"Preset file not found: {filename}")
                return None
            
            with open(preset_path, 'r') as f:
                preset_data = json.load(f)
            
            # Validate preset structure
            if not self._validate_preset(preset_data):
                self.logger.error(f"Invalid preset format: {filename}")
                return None
            
            return preset_data
            
        except Exception as e:
            self.logger.error(f"Error loading preset {filename}: {str(e)}")
            return None
    
    def import_preset(self, filename: str, user_id: int, 
                     overwrite_existing: bool = False) -> Dict[str, Any]:
        """
        Import a preset into the database
        
        Args:
            filename: Preset filename to import
            user_id: ID of user importing the preset
            overwrite_existing: Whether to overwrite existing screening types
            
        Returns:
            Import results
        """
        
        results = {
            'success': False,
            'imported_count': 0,
            'skipped_count': 0,
            'updated_count': 0,
            'errors': []
        }
        
        try:
            preset_data = self.load_preset(filename)
            if not preset_data:
                results['errors'].append(f"Failed to load preset: {filename}")
                return results
            
            screening_types = preset_data.get('screening_types', [])
            
            for st_data in screening_types:
                try:
                    result = self._import_screening_type(st_data, user_id, overwrite_existing)
                    
                    if result == 'imported':
                        results['imported_count'] += 1
                    elif result == 'updated':
                        results['updated_count'] += 1
                    elif result == 'skipped':
                        results['skipped_count'] += 1
                        
                except Exception as e:
                    error_msg = f"Error importing {st_data.get('name', 'unknown')}: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
            
            if results['imported_count'] > 0 or results['updated_count'] > 0:
                db.session.commit()
                results['success'] = True
                
                self.logger.info(f"Preset import completed: {results['imported_count']} imported, "
                               f"{results['updated_count']} updated, {results['skipped_count']} skipped")
            else:
                db.session.rollback()
                if not results['errors']:
                    results['errors'].append("No screening types were imported")
            
            return results
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Critical error importing preset: {str(e)}"
            results['errors'].append(error_msg)
            self.logger.error(error_msg)
            return results
    
    def _import_screening_type(self, st_data: Dict[str, Any], user_id: int, 
                              overwrite_existing: bool) -> str:
        """Import a single screening type"""
        
        name = st_data.get('name')
        if not name:
            raise ValueError("Screening type name is required")
        
        # Check if exists
        existing = ScreeningType.query.filter_by(name=name).first()
        
        if existing:
            if not overwrite_existing:
                return 'skipped'
            
            # Update existing
            screening_type = existing
            action = 'updated'
        else:
            # Create new
            screening_type = ScreeningType(created_by=user_id)
            db.session.add(screening_type)
            action = 'imported'
        
        # Set properties
        screening_type.name = name
        screening_type.description = st_data.get('description', '')
        screening_type.gender_criteria = st_data.get('gender_criteria', 'both')
        screening_type.age_min = st_data.get('age_min')
        screening_type.age_max = st_data.get('age_max')
        screening_type.frequency_number = st_data.get('frequency_number')
        screening_type.frequency_unit = st_data.get('frequency_unit')
        screening_type.is_active = st_data.get('is_active', True)
        
        # Set keywords and trigger conditions
        screening_type.set_keywords(st_data.get('keywords', []))
        screening_type.set_trigger_conditions(st_data.get('trigger_conditions', []))
        
        return action
    
    def export_preset(self, screening_type_ids: List[int], preset_name: str,
                     description: str = '', specialty: str = 'Custom') -> Dict[str, Any]:
        """
        Export selected screening types as a preset
        
        Args:
            screening_type_ids: List of screening type IDs to export
            preset_name: Name for the preset
            description: Description of the preset
            specialty: Specialty category
            
        Returns:
            Preset data for export
        """
        
        try:
            screening_types = ScreeningType.query.filter(
                ScreeningType.id.in_(screening_type_ids)
            ).all()
            
            if not screening_types:
                return {'error': 'No screening types found to export'}
            
            preset_data = {
                'name': preset_name,
                'description': description,
                'specialty': specialty,
                'version': '2.0',
                'created_date': datetime.utcnow().isoformat(),
                'screening_types': []
            }
            
            for st in screening_types:
                st_export = {
                    'name': st.name,
                    'description': st.description,
                    'keywords': st.get_keywords(),
                    'gender_criteria': st.gender_criteria,
                    'age_min': st.age_min,
                    'age_max': st.age_max,
                    'frequency_number': st.frequency_number,
                    'frequency_unit': st.frequency_unit,
                    'trigger_conditions': st.get_trigger_conditions(),
                    'is_active': st.is_active
                }
                preset_data['screening_types'].append(st_export)
            
            return preset_data
            
        except Exception as e:
            self.logger.error(f"Error exporting preset: {str(e)}")
            return {'error': str(e)}
    
    def save_preset_file(self, preset_data: Dict[str, Any], filename: str) -> bool:
        """Save preset data to a file"""
        
        try:
            # Ensure presets directory exists
            os.makedirs(self.presets_dir, exist_ok=True)
            
            preset_path = os.path.join(self.presets_dir, filename)
            
            with open(preset_path, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            self.logger.info(f"Preset saved to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving preset file {filename}: {str(e)}")
            return False
    
    def delete_preset_file(self, filename: str) -> bool:
        """Delete a preset file"""
        
        try:
            preset_path = os.path.join(self.presets_dir, filename)
            
            if os.path.exists(preset_path):
                os.remove(preset_path)
                self.logger.info(f"Preset file deleted: {filename}")
                return True
            else:
                self.logger.warning(f"Preset file not found: {filename}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error deleting preset file {filename}: {str(e)}")
            return False
    
    def _validate_preset(self, preset_data: Dict[str, Any]) -> bool:
        """Validate preset data structure"""
        
        required_fields = ['name', 'screening_types']
        
        # Check top-level required fields
        for field in required_fields:
            if field not in preset_data:
                self.logger.error(f"Missing required field: {field}")
                return False
        
        # Validate screening types
        screening_types = preset_data.get('screening_types', [])
        if not isinstance(screening_types, list):
            self.logger.error("screening_types must be a list")
            return False
        
        # Validate each screening type
        required_st_fields = ['name', 'frequency_number', 'frequency_unit']
        
        for i, st in enumerate(screening_types):
            if not isinstance(st, dict):
                self.logger.error(f"Screening type {i} must be a dictionary")
                return False
            
            for field in required_st_fields:
                if field not in st:
                    self.logger.error(f"Screening type {i} missing required field: {field}")
                    return False
            
            # Validate frequency unit
            valid_units = ['days', 'months', 'years']
            if st.get('frequency_unit') not in valid_units:
                self.logger.error(f"Screening type {i} has invalid frequency_unit")
                return False
            
            # Validate gender criteria
            valid_genders = ['M', 'F', 'both']
            if st.get('gender_criteria', 'both') not in valid_genders:
                self.logger.error(f"Screening type {i} has invalid gender_criteria")
                return False
        
        return True
    
    def get_preset_preview(self, filename: str) -> Dict[str, Any]:
        """Get a preview of preset contents without importing"""
        
        try:
            preset_data = self.load_preset(filename)
            if not preset_data:
                return {'error': 'Failed to load preset'}
            
            preview = {
                'name': preset_data.get('name'),
                'description': preset_data.get('description'),
                'specialty': preset_data.get('specialty'),
                'version': preset_data.get('version'),
                'screening_count': len(preset_data.get('screening_types', [])),
                'screening_types': []
            }
            
            # Add screening type summaries
            for st in preset_data.get('screening_types', []):
                st_summary = {
                    'name': st.get('name'),
                    'description': st.get('description', ''),
                    'frequency': f"Every {st.get('frequency_number')} {st.get('frequency_unit')}",
                    'gender_criteria': st.get('gender_criteria', 'both'),
                    'age_range': self._format_age_range(st.get('age_min'), st.get('age_max')),
                    'keyword_count': len(st.get('keywords', [])),
                    'has_conditions': bool(st.get('trigger_conditions'))
                }
                preview['screening_types'].append(st_summary)
            
            return preview
            
        except Exception as e:
            self.logger.error(f"Error getting preset preview: {str(e)}")
            return {'error': str(e)}
    
    def _format_age_range(self, age_min: Optional[int], age_max: Optional[int]) -> str:
        """Format age range for display"""
        
        if age_min is not None and age_max is not None:
            return f"{age_min}-{age_max} years"
        elif age_min is not None:
            return f"{age_min}+ years"
        elif age_max is not None:
            return f"Up to {age_max} years"
        else:
            return "All ages"
