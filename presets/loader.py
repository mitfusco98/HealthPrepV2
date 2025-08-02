"""
Screening type preset loader and management.
Handles import/export of screening type configurations and specialty presets.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from models import ScreeningType, db

logger = logging.getLogger(__name__)

class PresetLoader:
    """Manages screening type presets and configurations."""
    
    def __init__(self):
        self.presets_directory = os.path.join(os.path.dirname(__file__), 'examples')
        
        # Ensure presets directory exists
        os.makedirs(self.presets_directory, exist_ok=True)
        
        # Built-in preset categories
        self.preset_categories = {
            'primary_care': 'Primary Care Practice',
            'cardiology': 'Cardiology Specialty',
            'endocrinology': 'Endocrinology Specialty',
            'gynecology': 'Gynecology/Women\'s Health',
            'geriatrics': 'Geriatric Medicine',
            'preventive': 'Preventive Medicine'
        }
    
    def load_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Load a specific preset configuration.
        
        Args:
            preset_name: Name of the preset to load
            
        Returns:
            Preset configuration dictionary
        """
        try:
            preset_file = os.path.join(self.presets_directory, f"{preset_name}.json")
            
            if not os.path.exists(preset_file):
                logger.error(f"Preset file not found: {preset_file}")
                return {
                    'success': False,
                    'error': f'Preset "{preset_name}" not found'
                }
            
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Validate preset structure
            validation_result = self._validate_preset(preset_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f'Invalid preset format: {validation_result["errors"]}'
                }
            
            logger.info(f"Successfully loaded preset: {preset_name}")
            return {
                'success': True,
                'preset_data': preset_data
            }
            
        except Exception as e:
            logger.error(f"Error loading preset {preset_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def import_preset_to_database(self, preset_name: str, overwrite_existing: bool = False) -> Dict[str, Any]:
        """
        Import a preset into the database as screening types.
        
        Args:
            preset_name: Name of the preset to import
            overwrite_existing: Whether to overwrite existing screening types
            
        Returns:
            Import results dictionary
        """
        try:
            # Load preset
            preset_result = self.load_preset(preset_name)
            if not preset_result['success']:
                return preset_result
            
            preset_data = preset_result['preset_data']
            screening_types = preset_data.get('screening_types', [])
            
            import_results = {
                'success': True,
                'imported_count': 0,
                'skipped_count': 0,
                'errors': [],
                'imported_screenings': []
            }
            
            for screening_config in screening_types:
                try:
                    # Check if screening type already exists
                    existing = ScreeningType.query.filter_by(
                        name=screening_config['name']
                    ).first()
                    
                    if existing and not overwrite_existing:
                        import_results['skipped_count'] += 1
                        logger.info(f"Skipped existing screening type: {screening_config['name']}")
                        continue
                    
                    # Create or update screening type
                    if existing and overwrite_existing:
                        screening_type = existing
                        logger.info(f"Updating existing screening type: {screening_config['name']}")
                    else:
                        screening_type = ScreeningType()
                        db.session.add(screening_type)
                        logger.info(f"Creating new screening type: {screening_config['name']}")
                    
                    # Set screening type attributes
                    screening_type.name = screening_config['name']
                    screening_type.description = screening_config.get('description', '')
                    screening_type.keywords = json.dumps(screening_config.get('keywords', []))
                    screening_type.gender_requirement = screening_config.get('gender_requirement')
                    screening_type.min_age = screening_config.get('min_age')
                    screening_type.max_age = screening_config.get('max_age')
                    screening_type.frequency_years = screening_config.get('frequency_years')
                    screening_type.frequency_months = screening_config.get('frequency_months')
                    screening_type.trigger_conditions = json.dumps(
                        screening_config.get('trigger_conditions', [])
                    )
                    screening_type.is_active = screening_config.get('is_active', True)
                    
                    import_results['imported_count'] += 1
                    import_results['imported_screenings'].append(screening_config['name'])
                    
                except Exception as e:
                    error_msg = f"Error importing {screening_config.get('name', 'unknown')}: {str(e)}"
                    import_results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Commit changes
            if import_results['imported_count'] > 0:
                db.session.commit()
                logger.info(f"Successfully imported {import_results['imported_count']} screening types")
            
            return import_results
            
        except Exception as e:
            logger.error(f"Error importing preset {preset_name}: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_current_screenings(self, filename: str = None) -> Dict[str, Any]:
        """
        Export current screening types to a preset file.
        
        Args:
            filename: Optional filename for the export
            
        Returns:
            Export results dictionary
        """
        try:
            # Get all active screening types
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            if not screening_types:
                return {
                    'success': False,
                    'error': 'No active screening types found to export'
                }
            
            # Build export data
            export_data = {
                'metadata': {
                    'name': 'Custom Export',
                    'description': 'Exported screening types from current system',
                    'category': 'custom',
                    'export_date': datetime.utcnow().isoformat(),
                    'version': '1.0'
                },
                'screening_types': []
            }
            
            for screening_type in screening_types:
                screening_config = {
                    'name': screening_type.name,
                    'description': screening_type.description,
                    'keywords': json.loads(screening_type.keywords) if screening_type.keywords else [],
                    'gender_requirement': screening_type.gender_requirement,
                    'min_age': screening_type.min_age,
                    'max_age': screening_type.max_age,
                    'frequency_years': screening_type.frequency_years,
                    'frequency_months': screening_type.frequency_months,
                    'trigger_conditions': json.loads(screening_type.trigger_conditions) if screening_type.trigger_conditions else [],
                    'is_active': screening_type.is_active
                }
                
                export_data['screening_types'].append(screening_config)
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"custom_export_{timestamp}.json"
            
            if not filename.endswith('.json'):
                filename += '.json'
            
            # Save to presets directory
            export_path = os.path.join(self.presets_directory, filename)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully exported {len(screening_types)} screening types to {filename}")
            
            return {
                'success': True,
                'filename': filename,
                'export_path': export_path,
                'screening_count': len(screening_types),
                'export_data': export_data
            }
            
        except Exception as e:
            logger.error(f"Error exporting screening types: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_available_presets(self) -> Dict[str, Any]:
        """
        List all available preset files.
        
        Returns:
            Dictionary of available presets
        """
        try:
            presets = []
            
            # Scan presets directory for JSON files
            if os.path.exists(self.presets_directory):
                for filename in os.listdir(self.presets_directory):
                    if filename.endswith('.json'):
                        preset_name = filename[:-5]  # Remove .json extension
                        preset_info = self._get_preset_info(preset_name)
                        presets.append(preset_info)
            
            return {
                'success': True,
                'presets': presets,
                'categories': self.preset_categories
            }
            
        except Exception as e:
            logger.error(f"Error listing presets: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_preset_info(self, preset_name: str) -> Dict[str, Any]:
        """Get basic information about a preset."""
        try:
            preset_result = self.load_preset(preset_name)
            
            if preset_result['success']:
                preset_data = preset_result['preset_data']
                metadata = preset_data.get('metadata', {})
                
                return {
                    'name': preset_name,
                    'display_name': metadata.get('name', preset_name),
                    'description': metadata.get('description', 'No description available'),
                    'category': metadata.get('category', 'uncategorized'),
                    'screening_count': len(preset_data.get('screening_types', [])),
                    'version': metadata.get('version', '1.0'),
                    'valid': True
                }
            else:
                return {
                    'name': preset_name,
                    'display_name': preset_name,
                    'description': 'Error loading preset',
                    'category': 'error',
                    'screening_count': 0,
                    'version': 'unknown',
                    'valid': False,
                    'error': preset_result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'name': preset_name,
                'display_name': preset_name,
                'description': f'Error: {str(e)}',
                'category': 'error',
                'screening_count': 0,
                'version': 'unknown',
                'valid': False,
                'error': str(e)
            }
    
    def _validate_preset(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate preset data structure.
        
        Args:
            preset_data: Preset data to validate
            
        Returns:
            Validation results
        """
        errors = []
        
        # Check required top-level keys
        if 'screening_types' not in preset_data:
            errors.append('Missing required key: screening_types')
        
        if 'metadata' not in preset_data:
            errors.append('Missing required key: metadata')
        
        # Validate screening types
        screening_types = preset_data.get('screening_types', [])
        if not isinstance(screening_types, list):
            errors.append('screening_types must be a list')
        else:
            for i, screening in enumerate(screening_types):
                if not isinstance(screening, dict):
                    errors.append(f'Screening type {i} must be a dictionary')
                    continue
                
                # Check required fields
                required_fields = ['name']
                for field in required_fields:
                    if field not in screening:
                        errors.append(f'Screening type {i} missing required field: {field}')
                
                # Validate field types
                if 'keywords' in screening and not isinstance(screening['keywords'], list):
                    errors.append(f'Screening type {i}: keywords must be a list')
                
                if 'trigger_conditions' in screening and not isinstance(screening['trigger_conditions'], list):
                    errors.append(f'Screening type {i}: trigger_conditions must be a list')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def create_custom_preset(self, name: str, description: str, screening_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a custom preset from screening configurations.
        
        Args:
            name: Preset name
            description: Preset description
            screening_configs: List of screening type configurations
            
        Returns:
            Creation results
        """
        try:
            # Build preset data
            preset_data = {
                'metadata': {
                    'name': name,
                    'description': description,
                    'category': 'custom',
                    'created_date': datetime.utcnow().isoformat(),
                    'version': '1.0'
                },
                'screening_types': screening_configs
            }
            
            # Validate preset
            validation_result = self._validate_preset(preset_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f'Invalid preset configuration: {validation_result["errors"]}'
                }
            
            # Save preset
            filename = f"{name.lower().replace(' ', '_')}.json"
            preset_path = os.path.join(self.presets_directory, filename)
            
            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully created custom preset: {name}")
            
            return {
                'success': True,
                'preset_name': name,
                'filename': filename,
                'screening_count': len(screening_configs)
            }
            
        except Exception as e:
            logger.error(f"Error creating custom preset: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Delete a preset file.
        
        Args:
            preset_name: Name of preset to delete
            
        Returns:
            Deletion results
        """
        try:
            preset_file = os.path.join(self.presets_directory, f"{preset_name}.json")
            
            if not os.path.exists(preset_file):
                return {
                    'success': False,
                    'error': f'Preset "{preset_name}" not found'
                }
            
            os.remove(preset_file)
            
            logger.info(f"Successfully deleted preset: {preset_name}")
            
            return {
                'success': True,
                'message': f'Preset "{preset_name}" deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Error deleting preset {preset_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
