"""
Import/export logic for screening type presets
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from models import ScreeningType, db

logger = logging.getLogger(__name__)

class PresetLoader:
    """Handles import/export of screening type presets"""
    
    def __init__(self):
        self.presets_directory = os.path.join(os.path.dirname(__file__), 'examples')
        
        # Ensure presets directory exists
        os.makedirs(self.presets_directory, exist_ok=True)
    
    def load_preset_file(self, filename: str) -> Dict[str, Any]:
        """
        Load a preset file and return its contents
        """
        try:
            file_path = os.path.join(self.presets_directory, filename)
            
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'Preset file {filename} not found'}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Validate preset structure
            validation_result = self._validate_preset_structure(preset_data)
            if not validation_result['valid']:
                return {'success': False, 'error': f'Invalid preset structure: {validation_result["errors"]}'}
            
            return {'success': True, 'data': preset_data}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in preset {filename}: {str(e)}")
            return {'success': False, 'error': f'Invalid JSON format: {str(e)}'}
        except Exception as e:
            logger.error(f"Error loading preset {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def import_preset(self, preset_data: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        """
        Import screening types from preset data
        """
        try:
            if 'screening_types' not in preset_data:
                return {'success': False, 'error': 'No screening_types found in preset data'}
            
            screening_types = preset_data['screening_types']
            imported_count = 0
            skipped_count = 0
            updated_count = 0
            errors = []
            
            for screening_data in screening_types:
                try:
                    result = self._import_single_screening_type(screening_data, overwrite)
                    if result['action'] == 'imported':
                        imported_count += 1
                    elif result['action'] == 'updated':
                        updated_count += 1
                    elif result['action'] == 'skipped':
                        skipped_count += 1
                        
                except Exception as e:
                    errors.append(f"Error importing {screening_data.get('name', 'unknown')}: {str(e)}")
                    logger.error(f"Error importing screening type: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'summary': {
                    'imported': imported_count,
                    'updated': updated_count,
                    'skipped': skipped_count,
                    'errors': len(errors)
                },
                'errors': errors,
                'preset_info': {
                    'name': preset_data.get('name', 'Unknown'),
                    'description': preset_data.get('description', ''),
                    'specialty': preset_data.get('specialty', '')
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error importing preset: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _import_single_screening_type(self, screening_data: Dict[str, Any], overwrite: bool) -> Dict[str, str]:
        """Import a single screening type"""
        
        name = screening_data.get('name')
        if not name:
            raise ValueError("Screening type name is required")
        
        # Check if screening type already exists
        existing_screening = ScreeningType.query.filter_by(name=name).first()
        
        if existing_screening and not overwrite:
            return {'action': 'skipped', 'reason': 'Already exists'}
        
        # Create or update screening type
        if existing_screening:
            screening_type = existing_screening
            action = 'updated'
        else:
            screening_type = ScreeningType()
            action = 'imported'
        
        # Set attributes
        screening_type.name = name
        screening_type.description = screening_data.get('description', '')
        screening_type.keywords_list = screening_data.get('keywords', [])
        screening_type.gender_criteria = screening_data.get('gender_criteria', 'Both')
        screening_type.min_age = screening_data.get('min_age')
        screening_type.max_age = screening_data.get('max_age')
        screening_type.frequency_number = screening_data.get('frequency_number', 1)
        screening_type.frequency_unit = screening_data.get('frequency_unit', 'years')
        screening_type.trigger_conditions_list = screening_data.get('trigger_conditions', [])
        screening_type.is_active = screening_data.get('is_active', True)
        screening_type.updated_at = datetime.utcnow()
        
        if action == 'imported':
            db.session.add(screening_type)
        
        return {'action': action}
    
    def export_screening_types(self, screening_type_ids: List[int] = None, 
                              preset_name: str = "Custom Export", 
                              specialty: str = "") -> Dict[str, Any]:
        """
        Export screening types to preset format
        """
        try:
            # Get screening types to export
            if screening_type_ids:
                screening_types = ScreeningType.query.filter(ScreeningType.id.in_(screening_type_ids)).all()
            else:
                screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            if not screening_types:
                return {'success': False, 'error': 'No screening types found to export'}
            
            # Build export data
            export_data = {
                'name': preset_name,
                'description': f'Exported screening types for {specialty}' if specialty else 'Custom screening types export',
                'specialty': specialty,
                'version': '1.0',
                'exported_at': datetime.utcnow().isoformat(),
                'screening_types': []
            }
            
            for screening_type in screening_types:
                screening_data = {
                    'name': screening_type.name,
                    'description': screening_type.description,
                    'keywords': screening_type.keywords_list,
                    'gender_criteria': screening_type.gender_criteria,
                    'min_age': screening_type.min_age,
                    'max_age': screening_type.max_age,
                    'frequency_number': screening_type.frequency_number,
                    'frequency_unit': screening_type.frequency_unit,
                    'trigger_conditions': screening_type.trigger_conditions_list,
                    'is_active': screening_type.is_active
                }
                export_data['screening_types'].append(screening_data)
            
            return {'success': True, 'data': export_data}
            
        except Exception as e:
            logger.error(f"Error exporting screening types: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def save_preset_file(self, preset_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Save preset data to file
        """
        try:
            file_path = os.path.join(self.presets_directory, filename)
            
            # Ensure filename has .json extension
            if not filename.endswith('.json'):
                filename += '.json'
                file_path = os.path.join(self.presets_directory, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Preset saved to {filename}")
            return {'success': True, 'filename': filename, 'file_path': file_path}
            
        except Exception as e:
            logger.error(f"Error saving preset file {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def list_available_presets(self) -> List[Dict[str, Any]]:
        """
        List all available preset files
        """
        presets = []
        
        try:
            for filename in os.listdir(self.presets_directory):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.presets_directory, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            preset_data = json.load(f)
                        
                        file_stats = os.stat(file_path)
                        
                        preset_info = {
                            'filename': filename,
                            'name': preset_data.get('name', filename),
                            'description': preset_data.get('description', ''),
                            'specialty': preset_data.get('specialty', ''),
                            'version': preset_data.get('version', ''),
                            'screening_count': len(preset_data.get('screening_types', [])),
                            'file_size': file_stats.st_size,
                            'modified_date': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                        }
                        
                        presets.append(preset_info)
                        
                    except Exception as e:
                        logger.error(f"Error reading preset file {filename}: {str(e)}")
                        # Add error entry
                        presets.append({
                            'filename': filename,
                            'name': filename,
                            'description': f'Error reading file: {str(e)}',
                            'specialty': '',
                            'version': '',
                            'screening_count': 0,
                            'file_size': 0,
                            'modified_date': '',
                            'error': True
                        })
            
        except Exception as e:
            logger.error(f"Error listing preset files: {str(e)}")
        
        return sorted(presets, key=lambda x: x.get('modified_date', ''), reverse=True)
    
    def delete_preset_file(self, filename: str) -> Dict[str, Any]:
        """
        Delete a preset file
        """
        try:
            file_path = os.path.join(self.presets_directory, filename)
            
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'Preset file {filename} not found'}
            
            os.remove(file_path)
            logger.info(f"Preset file {filename} deleted")
            
            return {'success': True, 'message': f'Preset file {filename} deleted successfully'}
            
        except Exception as e:
            logger.error(f"Error deleting preset file {filename}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _validate_preset_structure(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the structure of preset data
        """
        errors = []
        
        # Check required top-level fields
        if 'screening_types' not in preset_data:
            errors.append("Missing 'screening_types' field")
        
        if 'screening_types' in preset_data:
            if not isinstance(preset_data['screening_types'], list):
                errors.append("'screening_types' must be a list")
            else:
                # Validate each screening type
                for i, screening in enumerate(preset_data['screening_types']):
                    if not isinstance(screening, dict):
                        errors.append(f"Screening type {i} must be an object")
                        continue
                    
                    # Check required fields
                    if 'name' not in screening:
                        errors.append(f"Screening type {i} missing 'name' field")
                    
                    # Validate field types
                    if 'keywords' in screening and not isinstance(screening['keywords'], list):
                        errors.append(f"Screening type {i} 'keywords' must be a list")
                    
                    if 'trigger_conditions' in screening and not isinstance(screening['trigger_conditions'], list):
                        errors.append(f"Screening type {i} 'trigger_conditions' must be a list")
                    
                    # Validate frequency fields
                    if 'frequency_number' in screening:
                        try:
                            int(screening['frequency_number'])
                        except (ValueError, TypeError):
                            errors.append(f"Screening type {i} 'frequency_number' must be an integer")
                    
                    if 'frequency_unit' in screening:
                        valid_units = ['days', 'weeks', 'months', 'years']
                        if screening['frequency_unit'] not in valid_units:
                            errors.append(f"Screening type {i} 'frequency_unit' must be one of: {valid_units}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def create_specialty_preset(self, specialty_name: str) -> Dict[str, Any]:
        """
        Create a preset for a specific medical specialty with common screening types
        """
        specialty_configs = {
            'primary_care': {
                'name': 'Primary Care Screening Package',
                'description': 'Common screening types for primary care practice',
                'screening_types': [
                    {
                        'name': 'Annual Physical Exam',
                        'description': 'Comprehensive annual physical examination',
                        'keywords': ['physical exam', 'annual exam', 'wellness visit'],
                        'gender_criteria': 'Both',
                        'min_age': 18,
                        'max_age': None,
                        'frequency_number': 1,
                        'frequency_unit': 'years',
                        'trigger_conditions': [],
                        'is_active': True
                    },
                    {
                        'name': 'Mammogram',
                        'description': 'Breast cancer screening mammography',
                        'keywords': ['mammogram', 'mammography', 'breast imaging'],
                        'gender_criteria': 'F',
                        'min_age': 40,
                        'max_age': None,
                        'frequency_number': 1,
                        'frequency_unit': 'years',
                        'trigger_conditions': [],
                        'is_active': True
                    },
                    {
                        'name': 'Colonoscopy',
                        'description': 'Colorectal cancer screening',
                        'keywords': ['colonoscopy', 'colon screening', 'endoscopy'],
                        'gender_criteria': 'Both',
                        'min_age': 45,
                        'max_age': None,
                        'frequency_number': 10,
                        'frequency_unit': 'years',
                        'trigger_conditions': [],
                        'is_active': True
                    },
                    {
                        'name': 'Lipid Panel',
                        'description': 'Cholesterol and lipid screening',
                        'keywords': ['lipid panel', 'cholesterol', 'hdl', 'ldl'],
                        'gender_criteria': 'Both',
                        'min_age': 20,
                        'max_age': None,
                        'frequency_number': 5,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['diabetes', 'hypertension'],
                        'is_active': True
                    }
                ]
            },
            'cardiology': {
                'name': 'Cardiology Screening Package',
                'description': 'Screening types for cardiovascular health',
                'screening_types': [
                    {
                        'name': 'Echocardiogram',
                        'description': 'Cardiac ultrasound evaluation',
                        'keywords': ['echo', 'echocardiogram', 'cardiac ultrasound'],
                        'gender_criteria': 'Both',
                        'min_age': 18,
                        'max_age': None,
                        'frequency_number': 2,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['heart failure', 'cardiomyopathy'],
                        'is_active': True
                    },
                    {
                        'name': 'Stress Test',
                        'description': 'Cardiac stress testing',
                        'keywords': ['stress test', 'treadmill test', 'exercise test'],
                        'gender_criteria': 'Both',
                        'min_age': 18,
                        'max_age': None,
                        'frequency_number': 3,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['coronary artery disease', 'chest pain'],
                        'is_active': True
                    }
                ]
            }
        }
        
        if specialty_name.lower() not in specialty_configs:
            return {'success': False, 'error': f'Specialty "{specialty_name}" not available'}
        
        specialty_config = specialty_configs[specialty_name.lower()]
        specialty_config['specialty'] = specialty_name
        specialty_config['version'] = '1.0'
        specialty_config['created_at'] = datetime.utcnow().isoformat()
        
        return {'success': True, 'data': specialty_config}

