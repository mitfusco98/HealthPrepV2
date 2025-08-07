"""
Screening type preset management for admin dashboard
"""
from datetime import datetime
from app import db
from models import ScreeningPreset, ScreeningType, User
import json
import yaml
import logging

class PresetManager:
    """Manage screening type presets for import/export"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_preset(self, name, description, specialty, screening_types, user_id):
        """Create a new screening preset"""
        try:
            preset = ScreeningPreset()
            preset.name = name
            preset.description = description
            preset.specialty = specialty
            preset.created_by = user_id
            preset.set_screening_types(screening_types)
            
            db.session.add(preset)
            db.session.commit()
            
            return {'success': True, 'preset_id': preset.id}
            
        except Exception as e:
            self.logger.error(f"Error creating preset: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_all_presets(self):
        """Get all available presets"""
        try:
            presets = ScreeningPreset.query.filter_by(is_active=True).order_by(ScreeningPreset.name).all()
            return [self._serialize_preset(preset) for preset in presets]
        except Exception as e:
            self.logger.error(f"Error getting presets: {str(e)}")
            return []
    
    def get_preset_by_id(self, preset_id):
        """Get specific preset by ID"""
        try:
            preset = ScreeningPreset.query.get(preset_id)
            return self._serialize_preset(preset) if preset else None
        except Exception as e:
            self.logger.error(f"Error getting preset {preset_id}: {str(e)}")
            return None
    
    def update_preset(self, preset_id, data, user_id):
        """Update existing preset"""
        try:
            preset = ScreeningPreset.query.get(preset_id)
            if not preset:
                return {'success': False, 'error': 'Preset not found'}
            
            preset.name = data.get('name', preset.name)
            preset.description = data.get('description', preset.description)
            preset.specialty = data.get('specialty', preset.specialty)
            preset.updated_at = datetime.utcnow()
            
            if 'screening_types' in data:
                preset.set_screening_types(data['screening_types'])
            
            db.session.commit()
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating preset: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def delete_preset(self, preset_id):
        """Delete preset"""
        try:
            preset = ScreeningPreset.query.get(preset_id)
            if not preset:
                return {'success': False, 'error': 'Preset not found'}
            
            preset.is_active = False
            db.session.commit()
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error deleting preset: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def export_preset_json(self, preset_id):
        """Export preset as JSON"""
        try:
            preset = ScreeningPreset.query.get(preset_id)
            if not preset:
                return {'success': False, 'error': 'Preset not found'}
            
            export_data = {
                'name': preset.name,
                'description': preset.description,
                'specialty': preset.specialty,
                'version': preset.version,
                'created_at': preset.created_at.isoformat(),
                'screening_types': preset.get_screening_types()
            }
            
            return {'success': True, 'data': export_data}
            
        except Exception as e:
            self.logger.error(f"Error exporting preset: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def import_preset_from_data(self, data, user_id):
        """Import preset from JSON/YAML data"""
        try:
            # Validate required fields
            required_fields = ['name', 'screening_types']
            for field in required_fields:
                if field not in data:
                    return {'success': False, 'error': f'Missing required field: {field}'}
            
            # Check if preset name already exists
            existing = ScreeningPreset.query.filter_by(name=data['name']).first()
            if existing:
                data['name'] = f"{data['name']} (Imported {datetime.now().strftime('%Y%m%d_%H%M')})"
            
            return self.create_preset(
                name=data['name'],
                description=data.get('description', ''),
                specialty=data.get('specialty', 'general'),
                screening_types=data['screening_types'],
                user_id=user_id
            )
            
        except Exception as e:
            self.logger.error(f"Error importing preset: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def apply_preset_to_system(self, preset_id, user_id):
        """Apply preset screening types to the system"""
        try:
            preset = ScreeningPreset.query.get(preset_id)
            if not preset:
                return {'success': False, 'error': 'Preset not found'}
            
            screening_types = preset.get_screening_types()
            applied_count = 0
            
            for st_data in screening_types:
                # Check if screening type already exists
                existing = ScreeningType.query.filter_by(name=st_data['name']).first()
                
                if existing:
                    # Update existing
                    existing.keywords = json.dumps(st_data.get('keywords', []))
                    existing.eligible_genders = st_data.get('eligible_genders', 'both')
                    existing.min_age = st_data.get('min_age')
                    existing.max_age = st_data.get('max_age')
                    existing.frequency_years = st_data.get('frequency_years', 1.0)
                    existing.trigger_conditions = json.dumps(st_data.get('trigger_conditions', []))
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    new_st = ScreeningType()
                    new_st.name = st_data['name']
                    new_st.keywords = json.dumps(st_data.get('keywords', []))
                    new_st.eligible_genders = st_data.get('eligible_genders', 'both')
                    new_st.min_age = st_data.get('min_age')
                    new_st.max_age = st_data.get('max_age')
                    new_st.frequency_years = st_data.get('frequency_years', 1.0)
                    new_st.trigger_conditions = json.dumps(st_data.get('trigger_conditions', []))
                    db.session.add(new_st)
                
                applied_count += 1
            
            db.session.commit()
            return {'success': True, 'applied_count': applied_count}
            
        except Exception as e:
            self.logger.error(f"Error applying preset: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def generate_preset_from_current(self, name, description, specialty, user_id):
        """Generate a preset from current screening types"""
        try:
            current_types = ScreeningType.query.filter_by(is_active=True).all()
            
            screening_types = []
            for st in current_types:
                screening_types.append({
                    'name': st.name,
                    'keywords': st.keywords_list,
                    'eligible_genders': st.eligible_genders,
                    'min_age': st.min_age,
                    'max_age': st.max_age,
                    'frequency_years': st.frequency_years,
                    'trigger_conditions': st.trigger_conditions_list
                })
            
            return self.create_preset(name, description, specialty, screening_types, user_id)
            
        except Exception as e:
            self.logger.error(f"Error generating preset from current: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_preset_statistics(self):
        """Get statistics about presets"""
        try:
            total_presets = ScreeningPreset.query.filter_by(is_active=True).count()
            
            # Get presets by specialty
            specialty_counts = db.session.query(
                ScreeningPreset.specialty,
                db.func.count(ScreeningPreset.id).label('count')
            ).filter_by(is_active=True).group_by(ScreeningPreset.specialty).all()
            
            # Get most recent presets
            recent_presets = ScreeningPreset.query.filter_by(is_active=True).order_by(
                ScreeningPreset.created_at.desc()
            ).limit(5).all()
            
            return {
                'total_presets': total_presets,
                'by_specialty': {specialty: count for specialty, count in specialty_counts},
                'recent_presets': [self._serialize_preset(p, minimal=True) for p in recent_presets]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting preset statistics: {str(e)}")
            return {
                'total_presets': 0,
                'by_specialty': {},
                'recent_presets': []
            }
    
    def _serialize_preset(self, preset, minimal=False):
        """Serialize preset for API response"""
        if not preset:
            return None
        
        data = {
            'id': preset.id,
            'name': preset.name,
            'description': preset.description,
            'specialty': preset.specialty,
            'version': preset.version,
            'is_public': preset.is_public,
            'created_at': preset.created_at.isoformat(),
            'updated_at': preset.updated_at.isoformat(),
            'creator': preset.creator.username if preset.creator else 'Unknown'
        }
        
        if not minimal:
            data['screening_types'] = preset.get_screening_types()
            data['screening_count'] = len(preset.get_screening_types())
        
        return data