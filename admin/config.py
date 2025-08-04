"""
Admin configurations and presets management
"""
from app import db
from models import ScreeningType, PrepSheetSettings, PHIFilterSettings
import json
import logging

class AdminConfig:
    """Manages system-wide configurations and presets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_system_config(self):
        """Get current system configuration"""
        prep_settings = PrepSheetSettings.query.first() or PrepSheetSettings()
        phi_settings = PHIFilterSettings.query.first() or PHIFilterSettings()
        
        config = {
            'prep_sheet_settings': {
                'labs_cutoff_months': prep_settings.labs_cutoff_months,
                'imaging_cutoff_months': prep_settings.imaging_cutoff_months,
                'consults_cutoff_months': prep_settings.consults_cutoff_months,
                'hospital_cutoff_months': prep_settings.hospital_cutoff_months
            },
            'phi_filter_settings': {
                'filter_enabled': phi_settings.filter_enabled,
                'filter_ssn': phi_settings.filter_ssn,
                'filter_phone': phi_settings.filter_phone,
                'filter_mrn': phi_settings.filter_mrn,
                'filter_insurance': phi_settings.filter_insurance,
                'filter_addresses': phi_settings.filter_addresses,
                'filter_names': phi_settings.filter_names,
                'filter_dates': phi_settings.filter_dates
            },
            'screening_types_count': ScreeningType.query.filter_by(is_active=True).count(),
            'last_updated': max(
                prep_settings.updated_at or prep_settings.created_at or datetime.utcnow(),
                phi_settings.updated_at or phi_settings.created_at or datetime.utcnow()
            )
        }
        
        return config
    
    def export_screening_presets(self, specialty=None):
        """Export screening type presets for a specialty"""
        query = ScreeningType.query.filter_by(is_active=True)
        
        if specialty:
            # Filter by specialty-specific screening types
            specialty_keywords = {
                'primary_care': ['annual', 'routine', 'preventive'],
                'cardiology': ['echo', 'stress', 'cardiac'],
                'endocrinology': ['a1c', 'glucose', 'thyroid'],
                'oncology': ['mammogram', 'colonoscopy', 'screening'],
                'women_health': ['pap', 'mammogram', 'bone density']
            }
            
            keywords = specialty_keywords.get(specialty.lower(), [])
            if keywords:
                filters = [ScreeningType.name.contains(kw) for kw in keywords]
                query = query.filter(db.or_(*filters))
        
        screening_types = query.all()
        
        presets = []
        for st in screening_types:
            preset = {
                'name': st.name,
                'description': st.description,
                'keywords': st.keywords_list,
                'min_age': st.min_age,
                'max_age': st.max_age,
                'gender': st.gender,
                'frequency_value': st.frequency_value,
                'frequency_unit': st.frequency_unit,
                'trigger_conditions': st.trigger_conditions_list
            }
            presets.append(preset)
        
        return {
            'specialty': specialty or 'all',
            'presets': presets,
            'count': len(presets),
            'exported_at': datetime.utcnow().isoformat()
        }
    
    def import_screening_presets(self, presets_data, overwrite=False):
        """Import screening type presets"""
        imported_count = 0
        updated_count = 0
        errors = []
        
        try:
            for preset in presets_data.get('presets', []):
                try:
                    # Check if screening type already exists
                    existing = ScreeningType.query.filter_by(name=preset['name']).first()
                    
                    if existing and not overwrite:
                        continue
                    
                    if existing:
                        # Update existing
                        for key, value in preset.items():
                            if key == 'keywords':
                                existing.keywords_list = value
                            elif key == 'trigger_conditions':
                                existing.trigger_conditions = '\n'.join(value) if isinstance(value, list) else value
                            elif hasattr(existing, key):
                                setattr(existing, key, value)
                        updated_count += 1
                    else:
                        # Create new
                        screening_type = ScreeningType(
                            name=preset['name'],
                            description=preset.get('description'),
                            min_age=preset.get('min_age'),
                            max_age=preset.get('max_age'),
                            gender=preset.get('gender'),
                            frequency_value=preset.get('frequency_value'),
                            frequency_unit=preset.get('frequency_unit'),
                            is_active=True
                        )
                        
                        # Set keywords
                        if preset.get('keywords'):
                            screening_type.keywords_list = preset['keywords']
                        
                        # Set trigger conditions
                        if preset.get('trigger_conditions'):
                            conditions = preset['trigger_conditions']
                            screening_type.trigger_conditions = '\n'.join(conditions) if isinstance(conditions, list) else conditions
                        
                        db.session.add(screening_type)
                        imported_count += 1
                
                except Exception as e:
                    errors.append(f"Error importing {preset.get('name', 'unknown')}: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'imported_count': imported_count,
                'updated_count': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'imported_count': 0,
                'updated_count': 0,
                'errors': errors
            }
    
    def get_default_presets(self):
        """Get default screening type presets for common specialties"""
        presets = {
            'primary_care': [
                {
                    'name': 'Annual Physical',
                    'description': 'Comprehensive annual examination',
                    'keywords': ['physical', 'annual', 'comprehensive'],
                    'min_age': 18,
                    'frequency_value': 1,
                    'frequency_unit': 'years'
                },
                {
                    'name': 'Mammogram',
                    'description': 'Breast cancer screening',
                    'keywords': ['mammogram', 'mammography', 'breast'],
                    'min_age': 40,
                    'max_age': 74,
                    'gender': 'F',
                    'frequency_value': 1,
                    'frequency_unit': 'years'
                },
                {
                    'name': 'Colonoscopy',
                    'description': 'Colorectal cancer screening',
                    'keywords': ['colonoscopy', 'colon', 'screening'],
                    'min_age': 50,
                    'max_age': 75,
                    'frequency_value': 10,
                    'frequency_unit': 'years'
                },
                {
                    'name': 'Bone Density (DXA)',
                    'description': 'Osteoporosis screening',
                    'keywords': ['dxa', 'dexa', 'bone density'],
                    'min_age': 65,
                    'gender': 'F',
                    'frequency_value': 2,
                    'frequency_unit': 'years'
                }
            ],
            'cardiology': [
                {
                    'name': 'Echocardiogram',
                    'description': 'Cardiac function assessment',
                    'keywords': ['echo', 'echocardiogram', 'cardiac'],
                    'frequency_value': 1,
                    'frequency_unit': 'years',
                    'trigger_conditions': ['heart failure', 'cardiomyopathy']
                },
                {
                    'name': 'Stress Test',
                    'description': 'Cardiac stress testing',
                    'keywords': ['stress test', 'exercise test', 'cardiac stress'],
                    'frequency_value': 2,
                    'frequency_unit': 'years',
                    'trigger_conditions': ['coronary artery disease', 'chest pain']
                }
            ],
            'endocrinology': [
                {
                    'name': 'A1C - Diabetic',
                    'description': 'Hemoglobin A1C for diabetics',
                    'keywords': ['a1c', 'hba1c', 'hemoglobin'],
                    'frequency_value': 3,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['diabetes', 'type 1 diabetes', 'type 2 diabetes']
                },
                {
                    'name': 'A1C - Pre-diabetic',
                    'description': 'Hemoglobin A1C for pre-diabetics',
                    'keywords': ['a1c', 'hba1c', 'hemoglobin'],
                    'frequency_value': 6,
                    'frequency_unit': 'months',
                    'trigger_conditions': ['prediabetes', 'impaired glucose tolerance']
                }
            ]
        }
        
        return presets
    
    def create_specialty_preset_package(self, specialty):
        """Create a complete preset package for a specialty"""
        default_presets = self.get_default_presets()
        
        if specialty not in default_presets:
            return None
        
        package = {
            'specialty': specialty,
            'presets': default_presets[specialty],
            'count': len(default_presets[specialty]),
            'created_at': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
        
        return package
    
    def backup_current_config(self):
        """Create a backup of current system configuration"""
        config = self.get_system_config()
        screening_presets = self.export_screening_presets()
        
        backup = {
            'backup_created': datetime.utcnow().isoformat(),
            'system_config': config,
            'screening_presets': screening_presets,
            'version': '1.0'
        }
        
        return backup
    
    def restore_from_backup(self, backup_data):
        """Restore system configuration from backup"""
        try:
            # Restore prep sheet settings
            prep_config = backup_data['system_config']['prep_sheet_settings']
            prep_settings = PrepSheetSettings.query.first()
            if not prep_settings:
                prep_settings = PrepSheetSettings()
                db.session.add(prep_settings)
            
            for key, value in prep_config.items():
                setattr(prep_settings, key, value)
            
            # Restore PHI filter settings
            phi_config = backup_data['system_config']['phi_filter_settings']
            phi_settings = PHIFilterSettings.query.first()
            if not phi_settings:
                phi_settings = PHIFilterSettings()
                db.session.add(phi_settings)
            
            for key, value in phi_config.items():
                setattr(phi_settings, key, value)
            
            # Restore screening presets
            preset_result = self.import_screening_presets(
                backup_data['screening_presets'],
                overwrite=True
            )
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Configuration restored successfully',
                'preset_import_result': preset_result
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_configuration(self):
        """Validate current system configuration"""
        issues = []
        
        # Check prep sheet settings
        prep_settings = PrepSheetSettings.query.first()
        if not prep_settings:
            issues.append("Prep sheet settings not configured")
        else:
            if not all([
                prep_settings.labs_cutoff_months,
                prep_settings.imaging_cutoff_months,
                prep_settings.consults_cutoff_months,
                prep_settings.hospital_cutoff_months
            ]):
                issues.append("Some prep sheet cutoff periods are not set")
        
        # Check PHI filter settings
        phi_settings = PHIFilterSettings.query.first()
        if not phi_settings:
            issues.append("PHI filter settings not configured")
        
        # Check screening types
        active_screenings = ScreeningType.query.filter_by(is_active=True).count()
        if active_screenings == 0:
            issues.append("No active screening types configured")
        
        # Check for screening types without keywords
        no_keywords = ScreeningType.query.filter(
            ScreeningType.is_active == True,
            db.or_(ScreeningType.keywords.is_(None), ScreeningType.keywords == '')
        ).count()
        
        if no_keywords > 0:
            issues.append(f"{no_keywords} screening types have no keywords defined")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'checked_at': datetime.utcnow().isoformat()
        }

from datetime import datetime
