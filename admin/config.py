"""
Admin configuration management
"""
from datetime import datetime
from app import db
from models import PrepSheetSettings, ScreeningSettings, PHIFilterSettings, User
import json
import logging

class AdminConfig:
    """Handles admin configuration management"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_system_settings(self):
        """Get current system settings"""
        try:
            settings = {
                'prep_sheet': PrepSheetSettings.query.first(),
                'screening': ScreeningSettings.query.first(),
                'phi_filter': PHIFilterSettings.query.first()
            }
            
            # Create defaults if not exist
            if not settings['prep_sheet']:
                settings['prep_sheet'] = PrepSheetSettings()
                db.session.add(settings['prep_sheet'])
            
            if not settings['screening']:
                settings['screening'] = ScreeningSettings()
                db.session.add(settings['screening'])
            
            if not settings['phi_filter']:
                settings['phi_filter'] = PHIFilterSettings()
                db.session.add(settings['phi_filter'])
            
            db.session.commit()
            return settings
            
        except Exception as e:
            self.logger.error(f"Error getting system settings: {str(e)}")
            return None
    
    def update_checklist_settings(self, settings_data):
        """Update checklist/screening settings"""
        try:
            settings = ScreeningSettings.query.first()
            if not settings:
                settings = ScreeningSettings()
                db.session.add(settings)
            
            # Update settings
            for key, value in settings_data.items():
                if hasattr(settings, key) and value is not None:
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def update_prep_sheet_settings(self, settings_data):
        """Update prep sheet settings"""
        try:
            settings = PrepSheetSettings.query.first()
            if not settings:
                settings = PrepSheetSettings()
                db.session.add(settings)
            
            # Update settings
            for key, value in settings_data.items():
                if hasattr(settings, key) and value is not None:
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating prep sheet settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def export_configuration(self):
        """Export all system configuration"""
        try:
            settings = self.get_system_settings()
            if not settings:
                return {'success': False, 'error': 'Could not retrieve settings'}
            
            config_export = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'version': '1.0',
                'prep_sheet_settings': {
                    'labs_cutoff_months': settings['prep_sheet'].labs_cutoff_months,
                    'imaging_cutoff_months': settings['prep_sheet'].imaging_cutoff_months,
                    'consults_cutoff_months': settings['prep_sheet'].consults_cutoff_months,
                    'hospital_cutoff_months': settings['prep_sheet'].hospital_cutoff_months
                },
                'screening_settings': {
                    'lab_cutoff_months': settings['screening'].lab_cutoff_months,
                    'imaging_cutoff_months': settings['screening'].imaging_cutoff_months,
                    'consult_cutoff_months': settings['screening'].consult_cutoff_months,
                    'hospital_cutoff_months': settings['screening'].hospital_cutoff_months,
                    'default_status_options': settings['screening'].default_status_options,
                    'default_checklist_items': settings['screening'].default_checklist_items
                },
                'phi_filter_settings': {
                    'enabled': settings['phi_filter'].enabled,
                    'filter_ssn': settings['phi_filter'].filter_ssn,
                    'filter_phone': settings['phi_filter'].filter_phone,
                    'filter_mrn': settings['phi_filter'].filter_mrn,
                    'filter_insurance': settings['phi_filter'].filter_insurance,
                    'filter_addresses': settings['phi_filter'].filter_addresses,
                    'filter_names': settings['phi_filter'].filter_names,
                    'filter_dates': settings['phi_filter'].filter_dates
                }
            }
            
            return {'success': True, 'data': config_export}
            
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def import_configuration(self, config_data):
        """Import system configuration"""
        try:
            # Validate configuration data
            if not isinstance(config_data, dict):
                return {'success': False, 'error': 'Invalid configuration format'}
            
            if 'prep_sheet_settings' in config_data:
                result = self.update_prep_sheet_settings(config_data['prep_sheet_settings'])
                if not result['success']:
                    return result
            
            if 'screening_settings' in config_data:
                result = self.update_checklist_settings(config_data['screening_settings'])
                if not result['success']:
                    return result
            
            if 'phi_filter_settings' in config_data:
                phi_settings = PHIFilterSettings.query.first()
                if not phi_settings:
                    phi_settings = PHIFilterSettings()
                    db.session.add(phi_settings)
                
                phi_data = config_data['phi_filter_settings']
                for key, value in phi_data.items():
                    if hasattr(phi_settings, key):
                        setattr(phi_settings, key, value)
                
                phi_settings.updated_at = datetime.utcnow()
                db.session.commit()
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error importing configuration: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_user_summary(self):
        """Get user management summary"""
        try:
            total_users = User.query.count()
            admin_users = User.query.filter_by(is_admin=True).count()
            active_users = User.query.filter_by(is_active=True).count()
            
            role_counts = {}
            for role in ['admin', 'nurse', 'ma']:
                role_counts[role] = User.query.filter_by(role=role).count()
            
            return {
                'total_users': total_users,
                'admin_users': admin_users,
                'active_users': active_users,
                'role_distribution': role_counts
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user summary: {str(e)}")
            return None
    
    def validate_system_health(self):
        """Validate system health and configuration"""
        try:
            health_checks = {
                'database_connection': True,
                'settings_configured': True,
                'users_exist': True,
                'admin_user_exists': True
            }
            
            # Check if admin user exists
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count == 0:
                health_checks['admin_user_exists'] = False
            
            # Check if settings are configured
            settings = self.get_system_settings()
            if not settings:
                health_checks['settings_configured'] = False
            
            # Check if any users exist
            user_count = User.query.count()
            if user_count == 0:
                health_checks['users_exist'] = False
            
            overall_health = all(health_checks.values())
            
            return {
                'overall_healthy': overall_health,
                'checks': health_checks,
                'checked_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error validating system health: {str(e)}")
            return {
                'overall_healthy': False,
                'checks': {'database_connection': False},
                'error': str(e)
            }