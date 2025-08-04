from models import ScreeningType, ChecklistSettings, PHIFilterSettings
from app import db
from presets.loader import ScreeningPresetLoader
import logging

class AdminConfig:
    """Administrative configuration management"""
    
    def __init__(self):
        self.preset_loader = ScreeningPresetLoader()
    
    def get_system_settings(self):
        """Get all system configuration settings"""
        try:
            # Checklist settings
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
                db.session.commit()
            
            # PHI filter settings
            phi_settings = PHIFilterSettings.query.first()
            if not phi_settings:
                phi_settings = PHIFilterSettings()
                db.session.add(phi_settings)
                db.session.commit()
            
            # Screening type counts
            total_screening_types = ScreeningType.query.count()
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            
            return {
                'checklist_settings': {
                    'labs_cutoff_months': checklist_settings.labs_cutoff_months,
                    'imaging_cutoff_months': checklist_settings.imaging_cutoff_months,
                    'consults_cutoff_months': checklist_settings.consults_cutoff_months,
                    'hospital_cutoff_months': checklist_settings.hospital_cutoff_months
                },
                'phi_settings': {
                    'filter_enabled': phi_settings.filter_enabled,
                    'filter_ssn': phi_settings.filter_ssn,
                    'filter_phone': phi_settings.filter_phone,
                    'filter_mrn': phi_settings.filter_mrn,
                    'filter_insurance': phi_settings.filter_insurance,
                    'filter_addresses': phi_settings.filter_addresses,
                    'filter_names': phi_settings.filter_names,
                    'filter_dates': phi_settings.filter_dates
                },
                'screening_types': {
                    'total': total_screening_types,
                    'active': active_screening_types,
                    'inactive': total_screening_types - active_screening_types
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting system settings: {str(e)}")
            return None
    
    def update_checklist_settings(self, settings_data):
        """Update checklist cutoff settings"""
        try:
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
            
            # Update settings
            if 'labs_cutoff_months' in settings_data:
                checklist_settings.labs_cutoff_months = settings_data['labs_cutoff_months']
            if 'imaging_cutoff_months' in settings_data:
                checklist_settings.imaging_cutoff_months = settings_data['imaging_cutoff_months']
            if 'consults_cutoff_months' in settings_data:
                checklist_settings.consults_cutoff_months = settings_data['consults_cutoff_months']
            if 'hospital_cutoff_months' in settings_data:
                checklist_settings.hospital_cutoff_months = settings_data['hospital_cutoff_months']
            
            db.session.commit()
            
            from admin.logs import log_admin_action
            log_admin_action('UPDATE_CHECKLIST_SETTINGS', 'Updated prep sheet data cutoff settings')
            
            return True
            
        except Exception as e:
            logging.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return False
    
    def update_phi_settings(self, settings_data):
        """Update PHI filtering settings"""
        try:
            phi_settings = PHIFilterSettings.query.first()
            if not phi_settings:
                phi_settings = PHIFilterSettings()
                db.session.add(phi_settings)
            
            # Update settings
            for key, value in settings_data.items():
                if hasattr(phi_settings, key):
                    setattr(phi_settings, key, value)
            
            db.session.commit()
            
            from admin.logs import log_admin_action
            log_admin_action('UPDATE_PHI_SETTINGS', 'Updated PHI filtering settings')
            
            return True
            
        except Exception as e:
            logging.error(f"Error updating PHI settings: {str(e)}")
            db.session.rollback()
            return False
    
    def import_screening_preset(self, preset_name, overwrite=False):
        """Import screening type preset"""
        try:
            result = self.preset_loader.import_preset(preset_name, overwrite)
            
            from admin.logs import log_admin_action
            log_admin_action(
                'IMPORT_SCREENING_PRESET',
                f'Imported {result["imported_count"]} screening types from {preset_name}'
            )
            
            return result
            
        except Exception as e:
            logging.error(f"Error importing screening preset: {str(e)}")
            return {
                'imported_count': 0,
                'errors': [str(e)]
            }
    
    def export_screening_types(self, screening_type_ids, preset_name):
        """Export screening types to preset"""
        try:
            filename = self.preset_loader.export_preset(screening_type_ids, preset_name)
            
            from admin.logs import log_admin_action
            log_admin_action(
                'EXPORT_SCREENING_PRESET',
                f'Exported {len(screening_type_ids)} screening types to {filename}'
            )
            
            return filename
            
        except Exception as e:
            logging.error(f"Error exporting screening types: {str(e)}")
            return None
    
    def get_available_presets(self):
        """Get list of available screening presets"""
        try:
            return self.preset_loader.list_available_presets()
        except Exception as e:
            logging.error(f"Error getting available presets: {str(e)}")
            return []
    
    def toggle_screening_type_status(self, screening_type_id, active=None):
        """Toggle or set screening type active status"""
        try:
            screening_type = ScreeningType.query.get(screening_type_id)
            if not screening_type:
                return False
            
            if active is not None:
                screening_type.is_active = active
            else:
                screening_type.is_active = not screening_type.is_active
            
            db.session.commit()
            
            from admin.logs import log_admin_action
            status = 'activated' if screening_type.is_active else 'deactivated'
            log_admin_action(
                'TOGGLE_SCREENING_TYPE',
                f'Screening type "{screening_type.name}" {status}'
            )
            
            return True
            
        except Exception as e:
            logging.error(f"Error toggling screening type status: {str(e)}")
            db.session.rollback()
            return False
    
    def delete_screening_type(self, screening_type_id):
        """Delete screening type and associated data"""
        try:
            screening_type = ScreeningType.query.get(screening_type_id)
            if not screening_type:
                return False
            
            # Delete associated patient screenings first
            from models import PatientScreening
            PatientScreening.query.filter_by(screening_type_id=screening_type_id).delete()
            
            screening_name = screening_type.name
            db.session.delete(screening_type)
            db.session.commit()
            
            from admin.logs import log_admin_action
            log_admin_action(
                'DELETE_SCREENING_TYPE',
                f'Deleted screening type "{screening_name}" and associated data'
            )
            
            return True
            
        except Exception as e:
            logging.error(f"Error deleting screening type: {str(e)}")
            db.session.rollback()
            return False
    
    def backup_configuration(self):
        """Create backup of current system configuration"""
        try:
            config_data = {
                'backup_date': datetime.utcnow().isoformat(),
                'system_settings': self.get_system_settings(),
                'screening_types': []
            }
            
            # Export all active screening types
            active_screenings = ScreeningType.query.filter_by(is_active=True).all()
            for screening in active_screenings:
                config_data['screening_types'].append({
                    'name': screening.name,
                    'description': screening.description,
                    'keywords': screening.keywords,
                    'min_age': screening.min_age,
                    'max_age': screening.max_age,
                    'gender_restriction': screening.gender_restriction,
                    'frequency_value': screening.frequency_value,
                    'frequency_unit': screening.frequency_unit,
                    'trigger_conditions': screening.trigger_conditions,
                    'created_at': screening.created_at.isoformat()
                })
            
            from admin.logs import log_admin_action
            log_admin_action('BACKUP_CONFIGURATION', f'Created system configuration backup')
            
            return config_data
            
        except Exception as e:
            logging.error(f"Error creating configuration backup: {str(e)}")
            return None
