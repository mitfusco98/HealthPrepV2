"""
Admin configurations and presets management.
Handles system configuration and screening presets.
"""

from models import ScreeningType, ChecklistSettings, PHIFilterSettings
from app import db
from admin.logs import log_admin_action
import json
import logging

logger = logging.getLogger(__name__)

class ScreeningPresetManager:
    """Manages screening type presets for different medical specialties"""
    
    def __init__(self):
        self.specialty_presets = {
            'primary_care': {
                'name': 'Primary Care Screening Package',
                'description': 'Standard screenings for primary care practice',
                'screening_types': [
                    {
                        'name': 'Annual Physical',
                        'description': 'Comprehensive annual physical examination',
                        'keywords': ['physical', 'annual', 'wellness', 'checkup'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 18,
                        'eligibility_max_age': None,
                        'frequency_value': 1,
                        'frequency_unit': 'years',
                        'trigger_conditions': []
                    },
                    {
                        'name': 'Mammogram',
                        'description': 'Breast cancer screening',
                        'keywords': ['mammogram', 'mammography', 'breast', 'mammo'],
                        'eligibility_gender': 'F',
                        'eligibility_min_age': 50,
                        'eligibility_max_age': 74,
                        'frequency_value': 2,
                        'frequency_unit': 'years',
                        'trigger_conditions': []
                    },
                    {
                        'name': 'Colonoscopy',
                        'description': 'Colorectal cancer screening',
                        'keywords': ['colonoscopy', 'colon', 'colorectal', 'endoscopy'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 50,
                        'eligibility_max_age': 75,
                        'frequency_value': 10,
                        'frequency_unit': 'years',
                        'trigger_conditions': []
                    },
                    {
                        'name': 'Pap Smear',
                        'description': 'Cervical cancer screening',
                        'keywords': ['pap', 'cervical', 'pap smear', 'cytology'],
                        'eligibility_gender': 'F',
                        'eligibility_min_age': 21,
                        'eligibility_max_age': 65,
                        'frequency_value': 3,
                        'frequency_unit': 'years',
                        'trigger_conditions': []
                    }
                ]
            },
            'cardiology': {
                'name': 'Cardiology Screening Package',
                'description': 'Cardiac screening protocols',
                'screening_types': [
                    {
                        'name': 'Echocardiogram',
                        'description': 'Heart function assessment',
                        'keywords': ['echo', 'echocardiogram', 'cardiac', 'heart'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 18,
                        'eligibility_max_age': None,
                        'frequency_value': 1,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['heart disease', 'hypertension']
                    },
                    {
                        'name': 'Stress Test',
                        'description': 'Cardiac stress testing',
                        'keywords': ['stress test', 'exercise test', 'cardiac stress'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 35,
                        'eligibility_max_age': None,
                        'frequency_value': 2,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['heart disease', 'chest pain']
                    },
                    {
                        'name': 'Lipid Panel',
                        'description': 'Cholesterol screening',
                        'keywords': ['lipid', 'cholesterol', 'hdl', 'ldl', 'triglycerides'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 20,
                        'eligibility_max_age': None,
                        'frequency_value': 5,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['diabetes', 'heart disease']
                    }
                ]
            },
            'endocrinology': {
                'name': 'Endocrinology Screening Package',
                'description': 'Diabetes and endocrine screenings',
                'screening_types': [
                    {
                        'name': 'HbA1c',
                        'description': 'Diabetes monitoring',
                        'keywords': ['a1c', 'hba1c', 'hemoglobin a1c', 'glycated'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 18,
                        'eligibility_max_age': None,
                        'frequency_value': 3,
                        'frequency_unit': 'months',
                        'trigger_conditions': ['diabetes']
                    },
                    {
                        'name': 'Thyroid Function',
                        'description': 'Thyroid screening',
                        'keywords': ['tsh', 'thyroid', 't3', 't4', 'thyroid function'],
                        'eligibility_gender': None,
                        'eligibility_min_age': 35,
                        'eligibility_max_age': None,
                        'frequency_value': 1,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['hypothyroidism', 'hyperthyroidism']
                    },
                    {
                        'name': 'DEXA Scan',
                        'description': 'Bone density screening',
                        'keywords': ['dexa', 'dxa', 'bone density', 'osteoporosis'],
                        'eligibility_gender': 'F',
                        'eligibility_min_age': 65,
                        'eligibility_max_age': None,
                        'frequency_value': 2,
                        'frequency_unit': 'years',
                        'trigger_conditions': ['osteoporosis', 'menopause']
                    }
                ]
            }
        }
    
    def get_available_presets(self):
        """Get list of available screening presets"""
        return list(self.specialty_presets.keys())
    
    def get_preset_details(self, preset_name):
        """Get details for a specific preset"""
        return self.specialty_presets.get(preset_name)
    
    def import_preset(self, preset_name, user_id):
        """Import a screening preset into the system"""
        try:
            preset = self.specialty_presets.get(preset_name)
            if not preset:
                raise ValueError(f"Preset '{preset_name}' not found")
            
            imported_count = 0
            skipped_count = 0
            
            for screening_data in preset['screening_types']:
                # Check if screening type already exists
                existing = ScreeningType.query.filter_by(
                    name=screening_data['name']
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new screening type
                screening_type = ScreeningType(
                    name=screening_data['name'],
                    description=screening_data['description'],
                    eligibility_gender=screening_data['eligibility_gender'],
                    eligibility_min_age=screening_data['eligibility_min_age'],
                    eligibility_max_age=screening_data['eligibility_max_age'],
                    frequency_value=screening_data['frequency_value'],
                    frequency_unit=screening_data['frequency_unit'],
                    is_active=True
                )
                
                # Set keywords and trigger conditions
                screening_type.set_keywords(screening_data['keywords'])
                screening_type.set_trigger_conditions(screening_data['trigger_conditions'])
                
                db.session.add(screening_type)
                imported_count += 1
            
            db.session.commit()
            
            # Log the import
            log_admin_action(
                user_id=user_id,
                action='Screening Preset Imported',
                details=f'Imported {preset_name} preset: {imported_count} new, {skipped_count} skipped'
            )
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'message': f'Successfully imported {imported_count} screening types'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error importing preset {preset_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_current_screenings(self):
        """Export current screening types as a preset"""
        try:
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            export_data = {
                'name': 'Custom Export',
                'description': 'Exported screening types',
                'screening_types': []
            }
            
            for st in screening_types:
                export_data['screening_types'].append({
                    'name': st.name,
                    'description': st.description,
                    'keywords': st.get_keywords(),
                    'eligibility_gender': st.eligibility_gender,
                    'eligibility_min_age': st.eligibility_min_age,
                    'eligibility_max_age': st.eligibility_max_age,
                    'frequency_value': st.frequency_value,
                    'frequency_unit': st.frequency_unit,
                    'trigger_conditions': st.get_trigger_conditions()
                })
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting current screenings: {str(e)}")
            return None

class SystemConfigManager:
    """Manages system-wide configuration settings"""
    
    def get_prep_sheet_defaults(self):
        """Get default prep sheet settings"""
        return {
            'lab_cutoff_months': 12,
            'imaging_cutoff_months': 24,
            'consult_cutoff_months': 12,
            'hospital_cutoff_months': 24
        }
    
    def get_phi_filter_defaults(self):
        """Get default PHI filter settings"""
        return {
            'enabled': True,
            'filter_ssn': True,
            'filter_phone': True,
            'filter_mrn': True,
            'filter_insurance': True,
            'filter_addresses': True,
            'filter_names': True,
            'filter_dates': True
        }
    
    def reset_to_defaults(self, setting_type, user_id):
        """Reset settings to default values"""
        try:
            if setting_type == 'prep_sheet':
                settings = ChecklistSettings.query.first()
                if not settings:
                    settings = ChecklistSettings()
                    db.session.add(settings)
                
                defaults = self.get_prep_sheet_defaults()
                for key, value in defaults.items():
                    setattr(settings, key, value)
                
            elif setting_type == 'phi_filter':
                settings = PHIFilterSettings.query.first()
                if not settings:
                    settings = PHIFilterSettings()
                    db.session.add(settings)
                
                defaults = self.get_phi_filter_defaults()
                for key, value in defaults.items():
                    setattr(settings, key, value)
            
            else:
                raise ValueError(f"Unknown setting type: {setting_type}")
            
            db.session.commit()
            
            # Log the reset
            log_admin_action(
                user_id=user_id,
                action='Settings Reset',
                details=f'Reset {setting_type} settings to defaults'
            )
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resetting {setting_type} settings: {str(e)}")
            return False
    
    def backup_settings(self):
        """Create backup of current settings"""
        try:
            backup_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'prep_sheet_settings': {},
                'phi_filter_settings': {},
                'screening_types': []
            }
            
            # Backup prep sheet settings
            prep_settings = ChecklistSettings.query.first()
            if prep_settings:
                backup_data['prep_sheet_settings'] = {
                    'lab_cutoff_months': prep_settings.lab_cutoff_months,
                    'imaging_cutoff_months': prep_settings.imaging_cutoff_months,
                    'consult_cutoff_months': prep_settings.consult_cutoff_months,
                    'hospital_cutoff_months': prep_settings.hospital_cutoff_months
                }
            
            # Backup PHI filter settings
            phi_settings = PHIFilterSettings.query.first()
            if phi_settings:
                backup_data['phi_filter_settings'] = {
                    'enabled': phi_settings.enabled,
                    'filter_ssn': phi_settings.filter_ssn,
                    'filter_phone': phi_settings.filter_phone,
                    'filter_mrn': phi_settings.filter_mrn,
                    'filter_insurance': phi_settings.filter_insurance,
                    'filter_addresses': phi_settings.filter_addresses,
                    'filter_names': phi_settings.filter_names,
                    'filter_dates': phi_settings.filter_dates
                }
            
            # Backup screening types
            screening_types = ScreeningType.query.all()
            for st in screening_types:
                backup_data['screening_types'].append({
                    'name': st.name,
                    'description': st.description,
                    'keywords': st.get_keywords(),
                    'eligibility_gender': st.eligibility_gender,
                    'eligibility_min_age': st.eligibility_min_age,
                    'eligibility_max_age': st.eligibility_max_age,
                    'frequency_value': st.frequency_value,
                    'frequency_unit': st.frequency_unit,
                    'trigger_conditions': st.get_trigger_conditions(),
                    'is_active': st.is_active
                })
            
            return backup_data
            
        except Exception as e:
            logger.error(f"Error creating settings backup: {str(e)}")
            return None


class AdminConfig:
    """Admin configuration and system management"""
    
    def __init__(self):
        self.preset_manager = ScreeningPresetManager()
        self.config_manager = SystemConfigManager()
    
    def get_app_info(self):
        """Get application information"""
        return {
            'version': '1.0.0',
            'environment': 'development',
            'database_connected': True,
            'uptime': 'N/A'
        }
    
    def get_security_info(self):
        """Get security configuration info"""
        return {
            'session_timeout': 480,
            'max_login_attempts': 5,
            'phi_filtering_enabled': True,
            'audit_logging_enabled': True
        }

