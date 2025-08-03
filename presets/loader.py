"""
Import/export logic for screening type presets
Handles specialty preset templates and configuration management
"""

import json
import os
import logging
from datetime import datetime
from app import db
from models import ScreeningType, AdminLog

class PresetLoader:
    """Handles loading and managing screening type presets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.presets_dir = os.path.join(os.path.dirname(__file__), 'examples')
    
    def load_preset_file(self, filename):
        """Load a preset file and return the screening types"""
        try:
            file_path = os.path.join(self.presets_dir, filename)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Preset file not found: {filename}")
            
            with open(file_path, 'r') as f:
                preset_data = json.load(f)
            
            return self._validate_preset_data(preset_data)
            
        except Exception as e:
            self.logger.error(f"Error loading preset file {filename}: {str(e)}")
            raise
    
    def _validate_preset_data(self, preset_data):
        """Validate preset data structure"""
        required_fields = ['name', 'description', 'version', 'screening_types']
        
        for field in required_fields:
            if field not in preset_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate screening types
        for screening_type in preset_data['screening_types']:
            self._validate_screening_type(screening_type)
        
        return preset_data
    
    def _validate_screening_type(self, screening_type):
        """Validate individual screening type data"""
        required_fields = ['name', 'keywords', 'eligible_genders']
        
        for field in required_fields:
            if field not in screening_type:
                raise ValueError(f"Screening type missing required field: {field}")
        
        # Validate frequency
        freq_years = screening_type.get('frequency_years', 0)
        freq_months = screening_type.get('frequency_months', 0)
        
        if freq_years == 0 and freq_months == 0:
            raise ValueError(f"Screening type '{screening_type['name']}' must have frequency specified")
    
    def import_preset(self, filename, overwrite_existing=False):
        """Import screening types from a preset file"""
        try:
            preset_data = self.load_preset_file(filename)
            
            imported_count = 0
            skipped_count = 0
            updated_count = 0
            
            for screening_data in preset_data['screening_types']:
                result = self._import_screening_type(screening_data, overwrite_existing)
                
                if result == 'imported':
                    imported_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1
            
            # Log the import
            self._log_preset_import(preset_data['name'], imported_count, updated_count, skipped_count)
            
            db.session.commit()
            
            return {
                'success': True,
                'preset_name': preset_data['name'],
                'imported': imported_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'total': len(preset_data['screening_types'])
            }
            
        except Exception as e:
            self.logger.error(f"Error importing preset {filename}: {str(e)}")
            db.session.rollback()
            raise
    
    def _import_screening_type(self, screening_data, overwrite_existing):
        """Import a single screening type"""
        # Check if screening type already exists
        existing = ScreeningType.query.filter_by(name=screening_data['name']).first()
        
        if existing and not overwrite_existing:
            return 'skipped'
        
        if existing and overwrite_existing:
            # Update existing screening type
            self._update_screening_type(existing, screening_data)
            return 'updated'
        else:
            # Create new screening type
            self._create_screening_type(screening_data)
            return 'imported'
    
    def _create_screening_type(self, screening_data):
        """Create a new screening type from preset data"""
        screening_type = ScreeningType(
            name=screening_data['name'],
            description=screening_data.get('description'),
            keywords=screening_data['keywords'],
            eligible_genders=screening_data['eligible_genders'],
            min_age=screening_data.get('min_age'),
            max_age=screening_data.get('max_age'),
            frequency_years=screening_data.get('frequency_years'),
            frequency_months=screening_data.get('frequency_months'),
            trigger_conditions=screening_data.get('trigger_conditions', []),
            is_active=screening_data.get('is_active', True)
        )
        
        db.session.add(screening_type)
    
    def _update_screening_type(self, existing, screening_data):
        """Update an existing screening type with preset data"""
        existing.description = screening_data.get('description', existing.description)
        existing.keywords = screening_data['keywords']
        existing.eligible_genders = screening_data['eligible_genders']
        existing.min_age = screening_data.get('min_age')
        existing.max_age = screening_data.get('max_age')
        existing.frequency_years = screening_data.get('frequency_years')
        existing.frequency_months = screening_data.get('frequency_months')
        existing.trigger_conditions = screening_data.get('trigger_conditions', [])
        existing.is_active = screening_data.get('is_active', True)
        existing.updated_at = datetime.utcnow()
    
    def export_screening_types(self, screening_type_ids=None, preset_name=None):
        """Export screening types to preset format"""
        try:
            query = ScreeningType.query
            
            if screening_type_ids:
                query = query.filter(ScreeningType.id.in_(screening_type_ids))
            
            screening_types = query.all()
            
            if not screening_types:
                raise ValueError("No screening types found to export")
            
            preset_data = {
                'name': preset_name or f"Custom Preset {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'description': 'Exported screening types',
                'version': '1.0',
                'created_at': datetime.utcnow().isoformat(),
                'screening_types': []
            }
            
            for screening_type in screening_types:
                screening_data = {
                    'name': screening_type.name,
                    'description': screening_type.description,
                    'keywords': screening_type.keywords or [],
                    'eligible_genders': screening_type.eligible_genders or [],
                    'min_age': screening_type.min_age,
                    'max_age': screening_type.max_age,
                    'frequency_years': screening_type.frequency_years,
                    'frequency_months': screening_type.frequency_months,
                    'trigger_conditions': screening_type.trigger_conditions or [],
                    'is_active': screening_type.is_active
                }
                
                preset_data['screening_types'].append(screening_data)
            
            return preset_data
            
        except Exception as e:
            self.logger.error(f"Error exporting screening types: {str(e)}")
            raise
    
    def get_available_presets(self):
        """Get list of available preset files"""
        try:
            presets = []
            
            if not os.path.exists(self.presets_dir):
                return presets
            
            for filename in os.listdir(self.presets_dir):
                if filename.endswith('.json'):
                    try:
                        preset_data = self.load_preset_file(filename)
                        presets.append({
                            'filename': filename,
                            'name': preset_data['name'],
                            'description': preset_data['description'],
                            'version': preset_data.get('version', '1.0'),
                            'screening_count': len(preset_data['screening_types'])
                        })
                    except Exception as e:
                        self.logger.warning(f"Could not load preset {filename}: {str(e)}")
            
            return presets
            
        except Exception as e:
            self.logger.error(f"Error getting available presets: {str(e)}")
            return []
    
    def preview_preset(self, filename):
        """Preview a preset file without importing"""
        try:
            preset_data = self.load_preset_file(filename)
            
            # Check for conflicts with existing screening types
            conflicts = []
            for screening_data in preset_data['screening_types']:
                existing = ScreeningType.query.filter_by(name=screening_data['name']).first()
                if existing:
                    conflicts.append({
                        'name': screening_data['name'],
                        'existing_id': existing.id,
                        'existing_active': existing.is_active
                    })
            
            return {
                'preset_info': {
                    'name': preset_data['name'],
                    'description': preset_data['description'],
                    'version': preset_data.get('version', '1.0'),
                    'screening_count': len(preset_data['screening_types'])
                },
                'screening_types': preset_data['screening_types'],
                'conflicts': conflicts,
                'has_conflicts': len(conflicts) > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error previewing preset {filename}: {str(e)}")
            raise
    
    def _log_preset_import(self, preset_name, imported, updated, skipped):
        """Log preset import activity"""
        try:
            log_entry = AdminLog(
                action='preset_import',
                description=f"Imported preset '{preset_name}': {imported} new, {updated} updated, {skipped} skipped"
            )
            
            db.session.add(log_entry)
            
        except Exception as e:
            self.logger.error(f"Error logging preset import: {str(e)}")
    
    def create_custom_preset(self, preset_name, description, screening_types_data):
        """Create a custom preset from provided data"""
        try:
            preset_data = {
                'name': preset_name,
                'description': description,
                'version': '1.0',
                'created_at': datetime.utcnow().isoformat(),
                'screening_types': screening_types_data
            }
            
            # Validate the preset data
            validated_data = self._validate_preset_data(preset_data)
            
            # Save to file
            filename = f"custom_{preset_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = os.path.join(self.presets_dir, filename)
            
            os.makedirs(self.presets_dir, exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(validated_data, f, indent=2)
            
            self.logger.info(f"Created custom preset: {filename}")
            
            return {
                'success': True,
                'filename': filename,
                'preset_name': preset_name
            }
            
        except Exception as e:
            self.logger.error(f"Error creating custom preset: {str(e)}")
            raise
    
    def delete_preset_file(self, filename):
        """Delete a preset file"""
        try:
            file_path = os.path.join(self.presets_dir, filename)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Preset file not found: {filename}")
            
            os.remove(file_path)
            
            # Log the deletion
            log_entry = AdminLog(
                action='preset_deleted',
                description=f"Deleted preset file: {filename}"
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            self.logger.info(f"Deleted preset file: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting preset file {filename}: {str(e)}")
            raise
