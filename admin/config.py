"""
Configuration management for admin settings
Handles system configuration and preference management
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from models import ChecklistSettings, OCRSettings, AdminLog
from app import db

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages system configuration and settings"""
    
    def __init__(self):
        self.config_cache = {}
        self.cache_timestamp = None
        self.cache_duration = 300  # 5 minutes
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get complete system configuration"""
        try:
            config = {
                'checklist_settings': self._get_checklist_config(),
                'ocr_settings': self._get_ocr_config(),
                'general_settings': self._get_general_config(),
                'last_updated': datetime.utcnow()
            }
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting system config: {str(e)}")
            return self._get_default_config()
    
    def update_checklist_settings(self, settings_data: Dict[str, Any], user_id: int) -> bool:
        """Update checklist settings"""
        try:
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
                db.session.add(settings)
            
            # Update settings
            if 'cutoff_months' in settings_data:
                settings.cutoff_months = settings_data['cutoff_months']
            if 'lab_cutoff' in settings_data:
                settings.lab_cutoff = settings_data['lab_cutoff']
            if 'imaging_cutoff' in settings_data:
                settings.imaging_cutoff = settings_data['imaging_cutoff']
            if 'consult_cutoff' in settings_data:
                settings.consult_cutoff = settings_data['consult_cutoff']
            if 'hospital_cutoff' in settings_data:
                settings.hospital_cutoff = settings_data['hospital_cutoff']
            if 'phi_filtering_enabled' in settings_data:
                settings.phi_filtering_enabled = settings_data['phi_filtering_enabled']
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Log configuration change
            self._log_config_change(user_id, 'CHECKLIST_SETTINGS_UPDATE', settings_data)
            
            # Clear cache
            self._clear_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return False
    
    def update_ocr_settings(self, settings_data: Dict[str, Any], user_id: int) -> bool:
        """Update OCR settings"""
        try:
            settings = OCRSettings.query.first()
            if not settings:
                settings = OCRSettings()
                db.session.add(settings)
            
            # Update settings
            if 'confidence_threshold' in settings_data:
                settings.confidence_threshold = settings_data['confidence_threshold']
            if 'auto_process' in settings_data:
                settings.auto_process = settings_data['auto_process']
            if 'tesseract_config' in settings_data:
                settings.tesseract_config = json.dumps(settings_data['tesseract_config'])
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Log configuration change
            self._log_config_change(user_id, 'OCR_SETTINGS_UPDATE', settings_data)
            
            # Clear cache
            self._clear_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating OCR settings: {str(e)}")
            db.session.rollback()
            return False
    
    def export_configuration(self) -> str:
        """Export system configuration as JSON"""
        try:
            config = self.get_system_config()
            
            # Remove sensitive information
            export_config = {
                'version': '2.0',
                'export_date': datetime.utcnow().isoformat(),
                'checklist_settings': config['checklist_settings'],
                'ocr_settings': config['ocr_settings'],
                'general_settings': config['general_settings']
            }
            
            return json.dumps(export_config, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {str(e)}")
            return "{}"
    
    def import_configuration(self, config_json: str, user_id: int) -> bool:
        """Import system configuration from JSON"""
        try:
            config = json.loads(config_json)
            
            # Validate configuration version
            if config.get('version') != '2.0':
                logger.warning(f"Configuration version mismatch: {config.get('version')}")
            
            # Import checklist settings
            if 'checklist_settings' in config:
                success = self.update_checklist_settings(config['checklist_settings'], user_id)
                if not success:
                    return False
            
            # Import OCR settings
            if 'ocr_settings' in config:
                success = self.update_ocr_settings(config['ocr_settings'], user_id)
                if not success:
                    return False
            
            # Log import
            self._log_config_change(user_id, 'CONFIG_IMPORT', {'source': 'import'})
            
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration import: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error importing configuration: {str(e)}")
            return False
    
    def get_configuration_presets(self) -> List[Dict[str, Any]]:
        """Get predefined configuration presets"""
        return [
            {
                'name': 'General Medicine',
                'description': 'Standard configuration for general medicine practice',
                'checklist_settings': {
                    'cutoff_months': 12,
                    'lab_cutoff': 6,
                    'imaging_cutoff': 12,
                    'consult_cutoff': 12,
                    'hospital_cutoff': 24,
                    'phi_filtering_enabled': True
                },
                'ocr_settings': {
                    'confidence_threshold': 0.7,
                    'auto_process': True
                }
            },
            {
                'name': 'Specialty Care',
                'description': 'Configuration optimized for specialty care practices',
                'checklist_settings': {
                    'cutoff_months': 18,
                    'lab_cutoff': 12,
                    'imaging_cutoff': 18,
                    'consult_cutoff': 18,
                    'hospital_cutoff': 36,
                    'phi_filtering_enabled': True
                },
                'ocr_settings': {
                    'confidence_threshold': 0.8,
                    'auto_process': True
                }
            },
            {
                'name': 'High Volume Practice',
                'description': 'Configuration for high-volume practices requiring fast processing',
                'checklist_settings': {
                    'cutoff_months': 6,
                    'lab_cutoff': 3,
                    'imaging_cutoff': 6,
                    'consult_cutoff': 6,
                    'hospital_cutoff': 12,
                    'phi_filtering_enabled': True
                },
                'ocr_settings': {
                    'confidence_threshold': 0.6,
                    'auto_process': True
                }
            }
        ]
    
    def apply_configuration_preset(self, preset_name: str, user_id: int) -> bool:
        """Apply a configuration preset"""
        try:
            presets = self.get_configuration_presets()
            preset = next((p for p in presets if p['name'] == preset_name), None)
            
            if not preset:
                logger.error(f"Configuration preset not found: {preset_name}")
                return False
            
            # Apply checklist settings
            success = self.update_checklist_settings(preset['checklist_settings'], user_id)
            if not success:
                return False
            
            # Apply OCR settings
            success = self.update_ocr_settings(preset['ocr_settings'], user_id)
            if not success:
                return False
            
            # Log preset application
            self._log_config_change(user_id, 'PRESET_APPLIED', {'preset_name': preset_name})
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying configuration preset: {str(e)}")
            return False
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate configuration settings"""
        errors = {}
        
        # Validate checklist settings
        if 'checklist_settings' in config:
            checklist_errors = []
            cs = config['checklist_settings']
            
            if 'cutoff_months' in cs and (cs['cutoff_months'] < 1 or cs['cutoff_months'] > 60):
                checklist_errors.append('Cutoff months must be between 1 and 60')
            
            if 'lab_cutoff' in cs and (cs['lab_cutoff'] < 1 or cs['lab_cutoff'] > 24):
                checklist_errors.append('Lab cutoff must be between 1 and 24 months')
            
            if 'imaging_cutoff' in cs and (cs['imaging_cutoff'] < 1 or cs['imaging_cutoff'] > 60):
                checklist_errors.append('Imaging cutoff must be between 1 and 60 months')
            
            if checklist_errors:
                errors['checklist_settings'] = checklist_errors
        
        # Validate OCR settings
        if 'ocr_settings' in config:
            ocr_errors = []
            os = config['ocr_settings']
            
            if 'confidence_threshold' in os and (os['confidence_threshold'] < 0.1 or os['confidence_threshold'] > 1.0):
                ocr_errors.append('Confidence threshold must be between 0.1 and 1.0')
            
            if ocr_errors:
                errors['ocr_settings'] = ocr_errors
        
        return errors
    
    def reset_to_defaults(self, user_id: int) -> bool:
        """Reset configuration to default values"""
        try:
            # Reset checklist settings
            default_checklist = {
                'cutoff_months': 12,
                'lab_cutoff': 6,
                'imaging_cutoff': 12,
                'consult_cutoff': 12,
                'hospital_cutoff': 24,
                'phi_filtering_enabled': True
            }
            
            # Reset OCR settings
            default_ocr = {
                'confidence_threshold': 0.7,
                'auto_process': True,
                'tesseract_config': {}
            }
            
            # Apply defaults
            success = self.update_checklist_settings(default_checklist, user_id)
            if not success:
                return False
            
            success = self.update_ocr_settings(default_ocr, user_id)
            if not success:
                return False
            
            # Log reset
            self._log_config_change(user_id, 'CONFIG_RESET', {'action': 'reset_to_defaults'})
            
            return True
            
        except Exception as e:
            logger.error(f"Error resetting configuration: {str(e)}")
            return False
    
    def _get_checklist_config(self) -> Dict[str, Any]:
        """Get checklist configuration"""
        try:
            settings = ChecklistSettings.query.first()
            if not settings:
                return self._get_default_checklist_config()
            
            return {
                'cutoff_months': settings.cutoff_months,
                'lab_cutoff': settings.lab_cutoff,
                'imaging_cutoff': settings.imaging_cutoff,
                'consult_cutoff': settings.consult_cutoff,
                'hospital_cutoff': settings.hospital_cutoff,
                'phi_filtering_enabled': settings.phi_filtering_enabled,
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None
            }
        except:
            return self._get_default_checklist_config()
    
    def _get_ocr_config(self) -> Dict[str, Any]:
        """Get OCR configuration"""
        try:
            settings = OCRSettings.query.first()
            if not settings:
                return self._get_default_ocr_config()
            
            tesseract_config = {}
            if settings.tesseract_config:
                try:
                    tesseract_config = json.loads(settings.tesseract_config)
                except:
                    pass
            
            return {
                'confidence_threshold': settings.confidence_threshold,
                'auto_process': settings.auto_process,
                'tesseract_config': tesseract_config,
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None
            }
        except:
            return self._get_default_ocr_config()
    
    def _get_general_config(self) -> Dict[str, Any]:
        """Get general system configuration"""
        return {
            'system_name': 'HealthPrep',
            'version': '2.0',
            'timezone': 'UTC',
            'session_timeout': 28800,  # 8 hours
            'max_upload_size': 52428800,  # 50MB
            'supported_file_types': ['.pdf', '.png', '.jpg', '.jpeg', '.tiff'],
            'maintenance_mode': False
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when errors occur"""
        return {
            'checklist_settings': self._get_default_checklist_config(),
            'ocr_settings': self._get_default_ocr_config(),
            'general_settings': self._get_general_config(),
            'last_updated': datetime.utcnow(),
            'error': 'Using default configuration'
        }
    
    def _get_default_checklist_config(self) -> Dict[str, Any]:
        """Get default checklist configuration"""
        return {
            'cutoff_months': 12,
            'lab_cutoff': 6,
            'imaging_cutoff': 12,
            'consult_cutoff': 12,
            'hospital_cutoff': 24,
            'phi_filtering_enabled': True
        }
    
    def _get_default_ocr_config(self) -> Dict[str, Any]:
        """Get default OCR configuration"""
        return {
            'confidence_threshold': 0.7,
            'auto_process': True,
            'tesseract_config': {}
        }
    
    def _log_config_change(self, user_id: int, action: str, details: Dict[str, Any]) -> None:
        """Log configuration changes"""
        try:
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                details=json.dumps(details),
                timestamp=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error logging config change: {str(e)}")
    
    def _clear_cache(self) -> None:
        """Clear configuration cache"""
        self.config_cache = {}
        self.cache_timestamp = None

# Global config manager instance
config_manager = ConfigManager()
