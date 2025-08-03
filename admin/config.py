"""
Admin configurations and presets
System configuration management and administrative settings
"""

from datetime import datetime
from app import db
from models import ChecklistSettings, PHIFilterSettings, ScreeningType, AdminLog
from presets.loader import PresetLoader
import logging
import json

class AdminConfigManager:
    """Manages administrative configurations and system settings"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.preset_loader = PresetLoader()
    
    def get_system_configuration(self):
        """Get current system configuration"""
        try:
            # Checklist settings
            checklist_settings = ChecklistSettings.query.filter_by(is_active=True).first()
            
            # PHI filter settings
            phi_settings = PHIFilterSettings.query.first()
            
            # Screening types count
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            total_screening_types = ScreeningType.query.count()
            
            # System stats
            from models import Patient, MedicalDocument, User
            total_patients = Patient.query.count()
            total_documents = MedicalDocument.query.count()
            total_users = User.query.count()
            
            config = {
                'checklist_settings': {
                    'name': checklist_settings.name if checklist_settings else 'Default',
                    'lab_cutoff_months': checklist_settings.lab_cutoff_months if checklist_settings else 12,
                    'imaging_cutoff_months': checklist_settings.imaging_cutoff_months if checklist_settings else 24,
                    'consult_cutoff_months': checklist_settings.consult_cutoff_months if checklist_settings else 12,
                    'hospital_cutoff_months': checklist_settings.hospital_cutoff_months if checklist_settings else 24,
                    'is_active': checklist_settings.is_active if checklist_settings else True
                },
                'phi_filter_settings': {
                    'is_enabled': phi_settings.is_enabled if phi_settings else True,
                    'filter_ssn': phi_settings.filter_ssn if phi_settings else True,
                    'filter_phone': phi_settings.filter_phone if phi_settings else True,
                    'filter_mrn': phi_settings.filter_mrn if phi_settings else True,
                    'filter_insurance': phi_settings.filter_insurance if phi_settings else True,
                    'filter_addresses': phi_settings.filter_addresses if phi_settings else True,
                    'filter_names': phi_settings.filter_names if phi_settings else False,
                    'filter_dates': phi_settings.filter_dates if phi_settings else False,
                    'preserve_medical_terms': phi_settings.preserve_medical_terms if phi_settings else True,
                    'confidence_threshold': phi_settings.confidence_threshold if phi_settings else 80
                },
                'screening_types': {
                    'active_count': active_screening_types,
                    'total_count': total_screening_types,
                    'inactive_count': total_screening_types - active_screening_types
                },
                'system_stats': {
                    'total_patients': total_patients,
                    'total_documents': total_documents,
                    'total_users': total_users
                },
                'last_updated': datetime.utcnow()
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error getting system configuration: {str(e)}")
            return {}
    
    def update_checklist_settings(self, settings_data, user_id=None):
        """Update checklist settings"""
        try:
            # Get or create settings
            settings = ChecklistSettings.query.filter_by(is_active=True).first()
            
            if settings:
                # Deactivate old settings
                settings.is_active = False
            
            # Create new settings
            new_settings = ChecklistSettings(
                name=settings_data.get('name', 'Updated Settings'),
                lab_cutoff_months=settings_data.get('lab_cutoff_months', 12),
                imaging_cutoff_months=settings_data.get('imaging_cutoff_months', 24),
                consult_cutoff_months=settings_data.get('consult_cutoff_months', 12),
                hospital_cutoff_months=settings_data.get('hospital_cutoff_months', 24),
                default_prep_items=settings_data.get('default_prep_items', []),
                status_options=settings_data.get('status_options', ['Due', 'Due Soon', 'Complete', 'Overdue']),
                is_active=True
            )
            
            db.session.add(new_settings)
            db.session.commit()
            
            # Log the update
            self._log_config_change('checklist_settings_updated', 
                                  f"Updated checklist settings: {new_settings.name}", user_id)
            
            return {'success': True, 'settings_id': new_settings.id}
            
        except Exception as e:
            self.logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def update_phi_settings(self, settings_data, user_id=None):
        """Update PHI filter settings"""
        try:
            settings = PHIFilterSettings.query.first()
            
            if not settings:
                settings = PHIFilterSettings()
                db.session.add(settings)
            
            # Update fields
            settings.is_enabled = settings_data.get('is_enabled', True)
            settings.filter_ssn = settings_data.get('filter_ssn', True)
            settings.filter_phone = settings_data.get('filter_phone', True)
            settings.filter_mrn = settings_data.get('filter_mrn', True)
            settings.filter_insurance = settings_data.get('filter_insurance', True)
            settings.filter_addresses = settings_data.get('filter_addresses', True)
            settings.filter_names = settings_data.get('filter_names', False)
            settings.filter_dates = settings_data.get('filter_dates', False)
            settings.preserve_medical_terms = settings_data.get('preserve_medical_terms', True)
            settings.confidence_threshold = settings_data.get('confidence_threshold', 80)
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log the update
            self._log_config_change('phi_settings_updated', 
                                  "Updated PHI filter settings", user_id)
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating PHI settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def manage_screening_type_presets(self):
        """Get available screening type presets"""
        try:
            available_presets = self.preset_loader.get_available_presets()
            
            return {
                'available_presets': available_presets,
                'total_presets': len(available_presets)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting screening type presets: {str(e)}")
            return {'available_presets': [], 'total_presets': 0}
    
    def import_screening_preset(self, filename, overwrite_existing=False, user_id=None):
        """Import a screening type preset"""
        try:
            result = self.preset_loader.import_preset(filename, overwrite_existing)
            
            if result['success']:
                # Log the import
                self._log_config_change('preset_imported', 
                                      f"Imported preset '{result['preset_name']}': "
                                      f"{result['imported']} new, {result['updated']} updated, "
                                      f"{result['skipped']} skipped", user_id)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error importing preset {filename}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'imported': 0,
                'updated': 0,
                'skipped': 0
            }
    
    def export_screening_types(self, screening_type_ids=None, preset_name=None, user_id=None):
        """Export screening types as preset"""
        try:
            preset_data = self.preset_loader.export_screening_types(screening_type_ids, preset_name)
            
            # Log the export
            self._log_config_change('screening_types_exported', 
                                  f"Exported {len(preset_data['screening_types'])} screening types", user_id)
            
            return {
                'success': True,
                'preset_data': preset_data,
                'screening_count': len(preset_data['screening_types'])
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting screening types: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_screening_type_management_data(self):
        """Get data for screening type management interface"""
        try:
            screening_types = ScreeningType.query.order_by(ScreeningType.name).all()
            
            management_data = []
            for st in screening_types:
                # Count associated screenings
                from models import Screening
                associated_screenings = Screening.query.filter_by(screening_type_id=st.id).count()
                
                management_data.append({
                    'id': st.id,
                    'name': st.name,
                    'description': st.description,
                    'is_active': st.is_active,
                    'keywords_count': len(st.keywords) if st.keywords else 0,
                    'eligible_genders': st.eligible_genders,
                    'age_range': f"{st.min_age or 'any'}-{st.max_age or 'any'}",
                    'frequency': self._format_frequency(st),
                    'trigger_conditions_count': len(st.trigger_conditions) if st.trigger_conditions else 0,
                    'associated_screenings': associated_screenings,
                    'created_at': st.created_at,
                    'updated_at': st.updated_at
                })
            
            return {
                'screening_types': management_data,
                'summary': {
                    'total_types': len(management_data),
                    'active_types': len([st for st in management_data if st['is_active']]),
                    'inactive_types': len([st for st in management_data if not st['is_active']])
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting screening type management data: {str(e)}")
            return {}
    
    def _format_frequency(self, screening_type):
        """Format screening frequency for display"""
        parts = []
        if screening_type.frequency_years:
            parts.append(f"{screening_type.frequency_years}y")
        if screening_type.frequency_months:
            parts.append(f"{screening_type.frequency_months}m")
        return " ".join(parts) if parts else "Not set"
    
    def backup_configuration(self, user_id=None):
        """Create a backup of current system configuration"""
        try:
            config_backup = {
                'backup_timestamp': datetime.utcnow().isoformat(),
                'backup_version': '1.0',
                'system_configuration': self.get_system_configuration(),
                'screening_types': [],
                'checklist_settings': [],
                'phi_settings': {}
            }
            
            # Backup screening types
            screening_types = ScreeningType.query.all()
            for st in screening_types:
                config_backup['screening_types'].append({
                    'name': st.name,
                    'description': st.description,
                    'keywords': st.keywords,
                    'eligible_genders': st.eligible_genders,
                    'min_age': st.min_age,
                    'max_age': st.max_age,
                    'frequency_years': st.frequency_years,
                    'frequency_months': st.frequency_months,
                    'trigger_conditions': st.trigger_conditions,
                    'is_active': st.is_active
                })
            
            # Backup checklist settings
            checklist_settings = ChecklistSettings.query.all()
            for cs in checklist_settings:
                config_backup['checklist_settings'].append({
                    'name': cs.name,
                    'lab_cutoff_months': cs.lab_cutoff_months,
                    'imaging_cutoff_months': cs.imaging_cutoff_months,
                    'consult_cutoff_months': cs.consult_cutoff_months,
                    'hospital_cutoff_months': cs.hospital_cutoff_months,
                    'default_prep_items': cs.default_prep_items,
                    'status_options': cs.status_options,
                    'is_active': cs.is_active
                })
            
            # Backup PHI settings
            phi_settings = PHIFilterSettings.query.first()
            if phi_settings:
                config_backup['phi_settings'] = {
                    'is_enabled': phi_settings.is_enabled,
                    'filter_ssn': phi_settings.filter_ssn,
                    'filter_phone': phi_settings.filter_phone,
                    'filter_mrn': phi_settings.filter_mrn,
                    'filter_insurance': phi_settings.filter_insurance,
                    'filter_addresses': phi_settings.filter_addresses,
                    'filter_names': phi_settings.filter_names,
                    'filter_dates': phi_settings.filter_dates,
                    'preserve_medical_terms': phi_settings.preserve_medical_terms,
                    'confidence_threshold': phi_settings.confidence_threshold
                }
            
            # Log the backup
            self._log_config_change('configuration_backup', 
                                  f"Created system configuration backup with {len(config_backup['screening_types'])} screening types", 
                                  user_id)
            
            return {
                'success': True,
                'backup_data': config_backup,
                'backup_size': len(json.dumps(config_backup))
            }
            
        except Exception as e:
            self.logger.error(f"Error creating configuration backup: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def restore_configuration(self, backup_data, user_id=None):
        """Restore system configuration from backup"""
        try:
            # This is a complex operation that would need careful implementation
            # For now, return a placeholder response
            
            self._log_config_change('configuration_restore_attempted', 
                                  f"Configuration restore attempted", user_id)
            
            return {
                'success': False,
                'error': 'Configuration restore is not yet implemented. Please import presets individually.',
                'recommendation': 'Use the preset import functionality to restore screening types'
            }
            
        except Exception as e:
            self.logger.error(f"Error restoring configuration: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_system_health_check(self):
        """Perform system health check"""
        try:
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
                health_status['errors'].append(f'Database connectivity: FAILED - {str(e)}')
                health_status['overall_status'] = 'error'
            
            # Check essential configurations
            checklist_settings = ChecklistSettings.query.filter_by(is_active=True).first()
            if not checklist_settings:
                health_status['warnings'].append('No active checklist settings found')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            else:
                health_status['checks'].append('Active checklist settings: OK')
            
            # Check screening types
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            if active_screening_types == 0:
                health_status['warnings'].append('No active screening types configured')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            else:
                health_status['checks'].append(f'Active screening types: {active_screening_types}')
            
            # Check PHI settings
            phi_settings = PHIFilterSettings.query.first()
            if not phi_settings:
                health_status['warnings'].append('PHI filter settings not configured')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            else:
                health_status['checks'].append('PHI filter settings: OK')
            
            health_status['checked_at'] = datetime.utcnow()
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall_status': 'error',
                'errors': [f'Health check failed: {str(e)}'],
                'checked_at': datetime.utcnow()
            }
    
    def _log_config_change(self, action, description, user_id=None):
        """Log configuration changes"""
        try:
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                description=description
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging configuration change: {str(e)}")
