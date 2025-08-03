"""
Admin configurations and presets management
Handles system-wide configuration and preset operations
"""
import logging
from app import db
from models import ChecklistSettings, PHISettings, ScreeningType
from presets.loader import PresetLoader

logger = logging.getLogger(__name__)

class AdminConfigManager:
    """Manages administrative configurations and settings"""
    
    def __init__(self):
        self.preset_loader = PresetLoader()
    
    def get_system_settings(self):
        """Get all system settings in one call"""
        checklist_settings = ChecklistSettings.query.first()
        phi_settings = PHISettings.query.first()
        
        if not checklist_settings:
            checklist_settings = ChecklistSettings()
            db.session.add(checklist_settings)
            db.session.commit()
        
        if not phi_settings:
            phi_settings = PHISettings()
            db.session.add(phi_settings)
            db.session.commit()
        
        return {
            'checklist_settings': {
                'labs_cutoff_months': checklist_settings.labs_cutoff_months,
                'imaging_cutoff_months': checklist_settings.imaging_cutoff_months,
                'consults_cutoff_months': checklist_settings.consults_cutoff_months,
                'hospital_cutoff_months': checklist_settings.hospital_cutoff_months,
                'default_items': checklist_settings.default_items or [],
                'status_options': checklist_settings.status_options or []
            },
            'phi_settings': {
                'phi_filtering_enabled': phi_settings.phi_filtering_enabled,
                'filter_ssn': phi_settings.filter_ssn,
                'filter_phone': phi_settings.filter_phone,
                'filter_mrn': phi_settings.filter_mrn,
                'filter_insurance': phi_settings.filter_insurance,
                'filter_addresses': phi_settings.filter_addresses,
                'filter_names': phi_settings.filter_names,
                'filter_dates': phi_settings.filter_dates,
                'preserve_medical_terms': phi_settings.preserve_medical_terms
            }
        }
    
    def update_checklist_settings(self, settings_data):
        """Update checklist settings"""
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
            db.session.add(settings)
        
        # Update cutoff months
        if 'labs_cutoff_months' in settings_data:
            settings.labs_cutoff_months = int(settings_data['labs_cutoff_months'])
        if 'imaging_cutoff_months' in settings_data:
            settings.imaging_cutoff_months = int(settings_data['imaging_cutoff_months'])
        if 'consults_cutoff_months' in settings_data:
            settings.consults_cutoff_months = int(settings_data['consults_cutoff_months'])
        if 'hospital_cutoff_months' in settings_data:
            settings.hospital_cutoff_months = int(settings_data['hospital_cutoff_months'])
        
        # Update default items
        if 'default_items' in settings_data:
            settings.default_items = settings_data['default_items']
        
        # Update status options
        if 'status_options' in settings_data:
            settings.status_options = settings_data['status_options']
        
        settings.updated_at = db.func.now()
        db.session.commit()
        
        logger.info("Checklist settings updated")
        return settings
    
    def update_phi_settings(self, settings_data):
        """Update PHI filtering settings"""
        settings = PHISettings.query.first()
        if not settings:
            settings = PHISettings()
            db.session.add(settings)
        
        # Update each setting
        boolean_fields = [
            'phi_filtering_enabled', 'filter_ssn', 'filter_phone', 'filter_mrn',
            'filter_insurance', 'filter_addresses', 'filter_names', 'filter_dates',
            'preserve_medical_terms'
        ]
        
        for field in boolean_fields:
            if field in settings_data:
                setattr(settings, field, bool(settings_data[field]))
        
        settings.updated_at = db.func.now()
        db.session.commit()
        
        logger.info("PHI settings updated")
        return settings
    
    def get_screening_presets_info(self):
        """Get information about available screening presets"""
        try:
            available_presets = self.preset_loader.get_available_presets()
            
            # Add current system info
            active_screening_types = ScreeningType.query.filter_by(status='active').count()
            total_screening_types = ScreeningType.query.count()
            
            return {
                'available_presets': available_presets,
                'current_system': {
                    'active_screening_types': active_screening_types,
                    'total_screening_types': total_screening_types
                }
            }
        except Exception as e:
            logger.error(f"Error getting preset info: {e}")
            return {
                'available_presets': [],
                'current_system': {
                    'active_screening_types': 0,
                    'total_screening_types': 0
                },
                'error': str(e)
            }
    
    def load_screening_preset(self, filename, user_id, replace_existing=False):
        """Load a screening preset"""
        try:
            result = self.preset_loader.load_preset(
                filename=filename,
                user_id=user_id,
                replace_existing=replace_existing
            )
            
            logger.info(f"Preset {filename} loaded by user {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error loading preset {filename}: {e}")
            raise
    
    def export_current_screenings(self, specialty_name="Current System"):
        """Export current screening types as a preset"""
        try:
            preset_data = self.preset_loader.export_screening_types(
                specialty_name=specialty_name
            )
            
            return preset_data
            
        except Exception as e:
            logger.error(f"Error exporting screenings: {e}")
            raise
    
    def get_system_health_check(self):
        """Perform a system health check"""
        health_status = {
            'overall_status': 'healthy',
            'checks': [],
            'warnings': [],
            'errors': []
        }
        
        # Check database connectivity
        try:
            db.session.execute('SELECT 1')
            health_status['checks'].append('Database connectivity: OK')
        except Exception as e:
            health_status['errors'].append(f'Database connectivity: FAILED - {e}')
            health_status['overall_status'] = 'critical'
        
        # Check essential settings
        checklist_settings = ChecklistSettings.query.first()
        phi_settings = PHISettings.query.first()
        
        if not checklist_settings:
            health_status['warnings'].append('Checklist settings not configured')
            health_status['overall_status'] = 'warning'
        else:
            health_status['checks'].append('Checklist settings: OK')
        
        if not phi_settings:
            health_status['warnings'].append('PHI settings not configured')
            health_status['overall_status'] = 'warning'
        else:
            health_status['checks'].append('PHI settings: OK')
        
        # Check screening types
        active_screenings = ScreeningType.query.filter_by(status='active').count()
        if active_screenings == 0:
            health_status['warnings'].append('No active screening types configured')
            if health_status['overall_status'] == 'healthy':
                health_status['overall_status'] = 'warning'
        else:
            health_status['checks'].append(f'Active screening types: {active_screenings}')
        
        # Check for processing backlogs
        from models import Document
        unprocessed_docs = Document.query.filter_by(ocr_processed=False).count()
        if unprocessed_docs > 100:
            health_status['warnings'].append(f'Large OCR processing backlog: {unprocessed_docs} documents')
            if health_status['overall_status'] == 'healthy':
                health_status['overall_status'] = 'warning'
        elif unprocessed_docs > 0:
            health_status['checks'].append(f'OCR backlog: {unprocessed_docs} documents (normal)')
        else:
            health_status['checks'].append('OCR processing: Up to date')
        
        return health_status
    
    def reset_system_settings(self, confirm_reset=False):
        """Reset system settings to defaults (dangerous operation)"""
        if not confirm_reset:
            raise ValueError("Reset confirmation required")
        
        try:
            # Reset checklist settings
            ChecklistSettings.query.delete()
            default_checklist = ChecklistSettings()
            db.session.add(default_checklist)
            
            # Reset PHI settings
            PHISettings.query.delete()
            default_phi = PHISettings()
            db.session.add(default_phi)
            
            db.session.commit()
            
            logger.warning("System settings reset to defaults")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to reset system settings: {e}")
            raise
    
    def backup_settings(self):
        """Create a backup of current settings"""
        import json
        from datetime import datetime
        
        settings = self.get_system_settings()
        
        backup_data = {
            'backup_date': datetime.utcnow().isoformat(),
            'version': '1.0',
            'settings': settings
        }
        
        return json.dumps(backup_data, indent=2, default=str)
    
    def restore_settings(self, backup_data):
        """Restore settings from backup"""
        import json
        
        try:
            if isinstance(backup_data, str):
                backup_data = json.loads(backup_data)
            
            settings = backup_data.get('settings', {})
            
            # Restore checklist settings
            if 'checklist_settings' in settings:
                self.update_checklist_settings(settings['checklist_settings'])
            
            # Restore PHI settings
            if 'phi_settings' in settings:
                self.update_phi_settings(settings['phi_settings'])
            
            logger.info("Settings restored from backup")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore settings: {e}")
            raise
