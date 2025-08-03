"""
Admin configuration management module.
Handles system-wide configuration settings and admin preferences.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import os

from app import db
from models import ScreeningType, ChecklistSettings, PHISettings
from admin.logs import log_admin_action

class AdminConfigManager:
    """Manages admin configuration settings"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get current system configuration"""
        try:
            # Get checklist settings
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
                db.session.commit()
            
            # Get PHI settings
            phi_settings = PHISettings.query.first()
            if not phi_settings:
                phi_settings = PHISettings()
                db.session.add(phi_settings)
                db.session.commit()
            
            # Get screening types configuration
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            total_screening_types = ScreeningType.query.count()
            
            return {
                'checklist_settings': {
                    'cutoff_labs': checklist_settings.cutoff_labs,
                    'cutoff_imaging': checklist_settings.cutoff_imaging,
                    'cutoff_consults': checklist_settings.cutoff_consults,
                    'cutoff_hospital': checklist_settings.cutoff_hospital,
                    'last_updated': checklist_settings.updated_at.isoformat() if checklist_settings.updated_at else None
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
                    'last_updated': phi_settings.updated_at.isoformat() if phi_settings.updated_at else None
                },
                'screening_configuration': {
                    'active_screening_types': active_screening_types,
                    'total_screening_types': total_screening_types,
                    'inactive_screening_types': total_screening_types - active_screening_types
                },
                'system_info': {
                    'config_retrieved_at': datetime.utcnow().isoformat(),
                    'upload_folder': os.getenv('UPLOAD_FOLDER', 'uploads'),
                    'max_file_size_mb': 16,
                    'supported_file_types': ['pdf', 'jpg', 'jpeg', 'png', 'tiff']
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system config: {str(e)}")
            return {}
    
    def update_checklist_settings(self, settings: Dict[str, int], user_id: int) -> bool:
        """Update checklist cutoff settings"""
        try:
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
            
            # Update settings
            old_values = {
                'cutoff_labs': checklist_settings.cutoff_labs,
                'cutoff_imaging': checklist_settings.cutoff_imaging,
                'cutoff_consults': checklist_settings.cutoff_consults,
                'cutoff_hospital': checklist_settings.cutoff_hospital
            }
            
            checklist_settings.cutoff_labs = settings.get('cutoff_labs', checklist_settings.cutoff_labs)
            checklist_settings.cutoff_imaging = settings.get('cutoff_imaging', checklist_settings.cutoff_imaging)
            checklist_settings.cutoff_consults = settings.get('cutoff_consults', checklist_settings.cutoff_consults)
            checklist_settings.cutoff_hospital = settings.get('cutoff_hospital', checklist_settings.cutoff_hospital)
            checklist_settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log the change
            changes = {k: {'old': old_values[k], 'new': getattr(checklist_settings, k)} 
                      for k in old_values if old_values[k] != getattr(checklist_settings, k)}
            
            log_admin_action(user_id, 'Checklist Settings Updated', f'Changes: {changes}')
            
            self.logger.info(f"Checklist settings updated by user {user_id}: {changes}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return False
    
    def update_phi_settings(self, settings: Dict[str, bool], user_id: int) -> bool:
        """Update PHI filtering settings"""
        try:
            phi_settings = PHISettings.query.first()
            if not phi_settings:
                phi_settings = PHISettings()
                db.session.add(phi_settings)
            
            # Track changes
            old_values = {
                'phi_filtering_enabled': phi_settings.phi_filtering_enabled,
                'filter_ssn': phi_settings.filter_ssn,
                'filter_phone': phi_settings.filter_phone,
                'filter_mrn': phi_settings.filter_mrn,
                'filter_insurance': phi_settings.filter_insurance,
                'filter_addresses': phi_settings.filter_addresses,
                'filter_names': phi_settings.filter_names,
                'filter_dates': phi_settings.filter_dates
            }
            
            # Update settings
            phi_settings.phi_filtering_enabled = settings.get('phi_filtering_enabled', phi_settings.phi_filtering_enabled)
            phi_settings.filter_ssn = settings.get('filter_ssn', phi_settings.filter_ssn)
            phi_settings.filter_phone = settings.get('filter_phone', phi_settings.filter_phone)
            phi_settings.filter_mrn = settings.get('filter_mrn', phi_settings.filter_mrn)
            phi_settings.filter_insurance = settings.get('filter_insurance', phi_settings.filter_insurance)
            phi_settings.filter_addresses = settings.get('filter_addresses', phi_settings.filter_addresses)
            phi_settings.filter_names = settings.get('filter_names', phi_settings.filter_names)
            phi_settings.filter_dates = settings.get('filter_dates', phi_settings.filter_dates)
            phi_settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Log the change
            changes = {k: {'old': old_values[k], 'new': getattr(phi_settings, k)} 
                      for k in old_values if old_values[k] != getattr(phi_settings, k)}
            
            log_admin_action(user_id, 'PHI Settings Updated', f'Changes: {changes}')
            
            self.logger.info(f"PHI settings updated by user {user_id}: {changes}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating PHI settings: {str(e)}")
            db.session.rollback()
            return False
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export complete system configuration for backup"""
        try:
            config = self.get_system_config()
            
            # Add screening types configuration
            screening_types = ScreeningType.query.all()
            screening_config = []
            
            for st in screening_types:
                screening_config.append({
                    'name': st.name,
                    'description': st.description,
                    'keywords': st.get_keywords_list(),
                    'eligible_genders': st.eligible_genders,
                    'min_age': st.min_age,
                    'max_age': st.max_age,
                    'frequency_number': st.frequency_number,
                    'frequency_unit': st.frequency_unit,
                    'trigger_conditions': st.trigger_conditions,
                    'is_active': st.is_active
                })
            
            config['screening_types_export'] = screening_config
            config['export_metadata'] = {
                'exported_at': datetime.utcnow().isoformat(),
                'export_version': '1.0',
                'total_screening_types': len(screening_config)
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {str(e)}")
            return {}
    
    def import_screening_presets(self, presets: List[Dict[str, Any]], user_id: int) -> Dict[str, Any]:
        """Import screening type presets"""
        try:
            imported_count = 0
            failed_count = 0
            errors = []
            
            for preset in presets:
                try:
                    # Check if screening type already exists
                    existing = ScreeningType.query.filter_by(name=preset['name']).first()
                    if existing:
                        errors.append(f"Screening type '{preset['name']}' already exists")
                        failed_count += 1
                        continue
                    
                    # Create new screening type
                    screening_type = ScreeningType(
                        name=preset['name'],
                        description=preset.get('description', ''),
                        keywords=json.dumps(preset.get('keywords', [])),
                        eligible_genders=preset.get('eligible_genders', 'both'),
                        min_age=preset.get('min_age'),
                        max_age=preset.get('max_age'),
                        frequency_number=preset.get('frequency_number', 12),
                        frequency_unit=preset.get('frequency_unit', 'months'),
                        trigger_conditions=preset.get('trigger_conditions'),
                        is_active=preset.get('is_active', True)
                    )
                    
                    db.session.add(screening_type)
                    imported_count += 1
                    
                except Exception as preset_error:
                    errors.append(f"Failed to import '{preset.get('name', 'Unknown')}': {str(preset_error)}")
                    failed_count += 1
            
            db.session.commit()
            
            # Log the import
            log_admin_action(user_id, 'Screening Presets Imported', 
                           f'Imported: {imported_count}, Failed: {failed_count}')
            
            return {
                'imported_count': imported_count,
                'failed_count': failed_count,
                'total_processed': len(presets),
                'errors': errors,
                'success': imported_count > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error importing screening presets: {str(e)}")
            db.session.rollback()
            return {
                'imported_count': 0,
                'failed_count': len(presets),
                'total_processed': len(presets),
                'errors': [f"Import failed: {str(e)}"],
                'success': False
            }
    
    def get_default_screening_presets(self) -> List[Dict[str, Any]]:
        """Get default screening type presets for common medical screenings"""
        return [
            {
                'name': 'Mammogram',
                'description': 'Breast cancer screening for women',
                'keywords': ['mammogram', 'mammography', 'breast screening', 'breast imaging'],
                'eligible_genders': 'F',
                'min_age': 40,
                'max_age': None,
                'frequency_number': 12,
                'frequency_unit': 'months',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Colonoscopy',
                'description': 'Colorectal cancer screening',
                'keywords': ['colonoscopy', 'colon screening', 'colorectal screening'],
                'eligible_genders': 'both',
                'min_age': 45,
                'max_age': 75,
                'frequency_number': 10,
                'frequency_unit': 'years',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Cervical Cancer Screening',
                'description': 'Pap smear and HPV testing',
                'keywords': ['pap smear', 'cervical screening', 'cytology', 'hpv test'],
                'eligible_genders': 'F',
                'min_age': 21,
                'max_age': 65,
                'frequency_number': 3,
                'frequency_unit': 'years',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Bone Density Screening',
                'description': 'DEXA scan for osteoporosis screening',
                'keywords': ['dexa', 'dxa', 'bone density', 'bone densitometry', 'osteoporosis screening'],
                'eligible_genders': 'F',
                'min_age': 65,
                'max_age': None,
                'frequency_number': 2,
                'frequency_unit': 'years',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Prostate Screening',
                'description': 'PSA testing for prostate cancer screening',
                'keywords': ['psa', 'prostate specific antigen', 'prostate screening'],
                'eligible_genders': 'M',
                'min_age': 50,
                'max_age': 70,
                'frequency_number': 12,
                'frequency_unit': 'months',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Diabetes Screening',
                'description': 'A1C and glucose testing for diabetes monitoring',
                'keywords': ['a1c', 'hemoglobin a1c', 'hba1c', 'glucose', 'diabetes screening'],
                'eligible_genders': 'both',
                'min_age': 35,
                'max_age': None,
                'frequency_number': 3,
                'frequency_unit': 'years',
                'trigger_conditions': None,
                'is_active': True
            },
            {
                'name': 'Lipid Screening',
                'description': 'Cholesterol and lipid panel testing',
                'keywords': ['lipid panel', 'cholesterol', 'ldl', 'hdl', 'triglycerides'],
                'eligible_genders': 'both',
                'min_age': 20,
                'max_age': None,
                'frequency_number': 5,
                'frequency_unit': 'years',
                'trigger_conditions': None,
                'is_active': True
            }
        ]
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current system configuration"""
        try:
            validation_results = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'recommendations': []
            }
            
            # Check checklist settings
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                validation_results['warnings'].append('No checklist settings configured')
            else:
                if any(getattr(checklist_settings, field) <= 0 for field in 
                      ['cutoff_labs', 'cutoff_imaging', 'cutoff_consults', 'cutoff_hospital']):
                    validation_results['errors'].append('All cutoff periods must be positive')
                    validation_results['valid'] = False
            
            # Check PHI settings
            phi_settings = PHISettings.query.first()
            if not phi_settings:
                validation_results['warnings'].append('No PHI settings configured')
            elif not phi_settings.phi_filtering_enabled:
                validation_results['warnings'].append('PHI filtering is disabled - consider enabling for HIPAA compliance')
            
            # Check screening types
            active_screenings = ScreeningType.query.filter_by(is_active=True).count()
            if active_screenings == 0:
                validation_results['errors'].append('No active screening types configured')
                validation_results['valid'] = False
            elif active_screenings < 3:
                validation_results['warnings'].append('Very few screening types configured - consider adding more')
            
            # Check for screening types without keywords
            no_keywords = ScreeningType.query.filter(
                ScreeningType.is_active == True,
                ScreeningType.keywords.is_(None)
            ).count()
            
            if no_keywords > 0:
                validation_results['warnings'].append(f'{no_keywords} active screening types have no keywords defined')
            
            # Generate recommendations
            if validation_results['valid']:
                validation_results['recommendations'].append('Configuration is valid and ready for production use')
            
            if not validation_results['errors'] and not validation_results['warnings']:
                validation_results['recommendations'].append('Excellent configuration - all settings are optimal')
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error validating configuration: {str(e)}")
            return {
                'valid': False,
                'warnings': [],
                'errors': [f'Configuration validation failed: {str(e)}'],
                'recommendations': ['Review system configuration and fix errors']
            }
