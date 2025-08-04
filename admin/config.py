"""
Admin configuration and default data initialization
Handles system setup, screening type presets, and default configurations
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from app import db
from models import (ScreeningType, ChecklistSettings, PHISettings, 
                   User, Patient, PatientCondition)
from admin.logs import log_admin_action

logger = logging.getLogger(__name__)

def initialize_default_data():
    """Initialize default data for the application"""
    try:
        logger.info("Initializing default application data...")
        
        # Create default admin user if none exists
        create_default_admin_user()
        
        # Initialize default settings
        initialize_default_settings()
        
        # Create default screening types
        create_default_screening_types()
        
        # Create sample patients for demo purposes
        create_sample_patients()
        
        logger.info("Default data initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing default data: {str(e)}")
        db.session.rollback()

def create_default_admin_user():
    """Create default admin user if none exists"""
    try:
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@healthprep.local',
                role='admin',
                is_active=True
            )
            admin_user.set_password('healthprep2025')  # Default password - should be changed
            db.session.add(admin_user)
            db.session.commit()
            
            log_admin_action('default_admin_created', 'user', str(admin_user.id), 
                           'Default admin user created during initialization')
            logger.info("Default admin user created")
        
    except Exception as e:
        logger.error(f"Error creating default admin user: {str(e)}")
        db.session.rollback()

def initialize_default_settings():
    """Initialize default system settings"""
    try:
        # Initialize checklist settings
        if not ChecklistSettings.query.first():
            checklist_settings = ChecklistSettings(
                cutoff_months=12,
                lab_cutoff_months=12,
                imaging_cutoff_months=24,
                consult_cutoff_months=12,
                hospital_cutoff_months=24,
                phi_filtering_enabled=True,
                confidence_threshold=0.6
            )
            db.session.add(checklist_settings)
            logger.info("Default checklist settings created")
        
        # Initialize PHI filter settings
        if not PHISettings.query.first():
            phi_settings = PHISettings(
                filter_enabled=True,
                filter_ssn=True,
                filter_phone=True,
                filter_mrn=True,
                filter_addresses=True,
                filter_names=True,
                filter_dates=True
            )
            db.session.add(phi_settings)
            logger.info("Default PHI filter settings created")
        
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error initializing default settings: {str(e)}")
        db.session.rollback()

def create_default_screening_types():
    """Create default screening types based on standard medical guidelines"""
    try:
        # Check if screening types already exist
        if ScreeningType.query.count() > 0:
            logger.info("Screening types already exist, skipping default creation")
            return
        
        default_screenings = get_default_screening_configurations()
        
        for screening_config in default_screenings:
            screening_type = ScreeningType(
                name=screening_config['name'],
                description=screening_config['description'],
                keywords=screening_config['keywords'],
                gender_eligibility=screening_config['gender_eligibility'],
                min_age=screening_config['min_age'],
                max_age=screening_config['max_age'],
                frequency_number=screening_config['frequency_number'],
                frequency_unit=screening_config['frequency_unit'],
                trigger_conditions=screening_config.get('trigger_conditions', []),
                is_active=True
            )
            db.session.add(screening_type)
        
        db.session.commit()
        
        log_admin_action('default_screenings_created', 'system', None, 
                       f'Created {len(default_screenings)} default screening types')
        logger.info(f"Created {len(default_screenings)} default screening types")
        
    except Exception as e:
        logger.error(f"Error creating default screening types: {str(e)}")
        db.session.rollback()

def get_default_screening_configurations() -> List[Dict[str, Any]]:
    """Get default screening type configurations"""
    return [
        {
            'name': 'Mammography',
            'description': 'Breast cancer screening for women',
            'keywords': ['mammography', 'mammogram', 'breast imaging', 'breast screening'],
            'gender_eligibility': 'F',
            'min_age': 40,
            'max_age': 74,
            'frequency_number': 2,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Colonoscopy',
            'description': 'Colorectal cancer screening',
            'keywords': ['colonoscopy', 'colon screening', 'colorectal screening', 'colonoscopic'],
            'gender_eligibility': 'All',
            'min_age': 45,
            'max_age': 75,
            'frequency_number': 10,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Cervical Cancer Screening (Pap Smear)',
            'description': 'Cervical cancer screening for women',
            'keywords': ['pap smear', 'pap test', 'cervical screening', 'papanicolaou'],
            'gender_eligibility': 'F',
            'min_age': 21,
            'max_age': 65,
            'frequency_number': 3,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Bone Density (DEXA)',
            'description': 'Osteoporosis screening',
            'keywords': ['dexa', 'dxa', 'bone density', 'bone scan', 'densitometry'],
            'gender_eligibility': 'F',
            'min_age': 65,
            'max_age': None,
            'frequency_number': 2,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Prostate Screening (PSA)',
            'description': 'Prostate cancer screening for men',
            'keywords': ['psa', 'prostate screening', 'prostate specific antigen'],
            'gender_eligibility': 'M',
            'min_age': 50,
            'max_age': 70,
            'frequency_number': 1,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'A1C (Diabetic)',
            'description': 'Hemoglobin A1C for diabetic patients',
            'keywords': ['a1c', 'hemoglobin a1c', 'hba1c', 'glycated hemoglobin'],
            'gender_eligibility': 'All',
            'min_age': 18,
            'max_age': None,
            'frequency_number': 3,
            'frequency_unit': 'months',
            'trigger_conditions': ['diabetes mellitus', 'diabetes mellitus type 1', 'diabetes mellitus type 2']
        },
        {
            'name': 'A1C (Routine)',
            'description': 'Routine hemoglobin A1C screening',
            'keywords': ['a1c', 'hemoglobin a1c', 'hba1c', 'glycated hemoglobin'],
            'gender_eligibility': 'All',
            'min_age': 35,
            'max_age': None,
            'frequency_number': 1,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Lipid Panel',
            'description': 'Cholesterol and lipid screening',
            'keywords': ['lipid panel', 'cholesterol', 'lipid profile', 'lipids'],
            'gender_eligibility': 'All',
            'min_age': 20,
            'max_age': None,
            'frequency_number': 5,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Blood Pressure Check',
            'description': 'Hypertension screening',
            'keywords': ['blood pressure', 'bp check', 'hypertension screening'],
            'gender_eligibility': 'All',
            'min_age': 18,
            'max_age': None,
            'frequency_number': 1,
            'frequency_unit': 'years',
            'trigger_conditions': []
        },
        {
            'name': 'Eye Exam (Diabetic)',
            'description': 'Annual eye exam for diabetic patients',
            'keywords': ['eye exam', 'ophthalmology', 'retinal exam', 'diabetic eye'],
            'gender_eligibility': 'All',
            'min_age': 18,
            'max_age': None,
            'frequency_number': 1,
            'frequency_unit': 'years',
            'trigger_conditions': ['diabetes mellitus', 'diabetes mellitus type 1', 'diabetes mellitus type 2']
        }
    ]

def create_sample_patients():
    """Create sample patients for demonstration"""
    try:
        # Check if patients already exist
        if Patient.query.count() > 0:
            logger.info("Patients already exist, skipping sample creation")
            return
        
        sample_patients = [
            {
                'mrn': 'MRN001',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'date_of_birth': datetime(1975, 3, 15),
                'gender': 'F',
                'conditions': [
                    {'code': 'E11.9', 'name': 'Diabetes mellitus type 2'},
                    {'code': 'I10', 'name': 'Hypertension'}
                ]
            },
            {
                'mrn': 'MRN002',
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': datetime(1968, 8, 22),
                'gender': 'M',
                'conditions': [
                    {'code': 'E78.5', 'name': 'Hyperlipidemia'}
                ]
            },
            {
                'mrn': 'MRN003',
                'first_name': 'Mary',
                'last_name': 'Johnson',
                'date_of_birth': datetime(1955, 12, 5),
                'gender': 'F',
                'conditions': [
                    {'code': 'M81.0', 'name': 'Osteoporosis'},
                    {'code': 'I10', 'name': 'Hypertension'}
                ]
            }
        ]
        
        for patient_data in sample_patients:
            # Create patient
            patient = Patient(
                mrn=patient_data['mrn'],
                first_name=patient_data['first_name'],
                last_name=patient_data['last_name'],
                date_of_birth=patient_data['date_of_birth'],
                gender=patient_data['gender']
            )
            db.session.add(patient)
            db.session.flush()  # Get patient ID
            
            # Add conditions
            for condition_data in patient_data['conditions']:
                condition = PatientCondition(
                    patient_id=patient.id,
                    condition_code=condition_data['code'],
                    condition_name=condition_data['name'],
                    diagnosis_date=datetime.utcnow() - datetime.timedelta(days=365),
                    is_active=True
                )
                db.session.add(condition)
        
        db.session.commit()
        
        log_admin_action('sample_patients_created', 'system', None, 
                       f'Created {len(sample_patients)} sample patients')
        logger.info(f"Created {len(sample_patients)} sample patients")
        
    except Exception as e:
        logger.error(f"Error creating sample patients: {str(e)}")
        db.session.rollback()

class AdminConfig:
    """Admin configuration management"""
    
    def __init__(self):
        self.logger = logger
    
    def get_system_settings(self) -> Dict[str, Any]:
        """Get current system settings"""
        try:
            checklist_settings = ChecklistSettings.query.first()
            phi_settings = PHISettings.query.first()
            
            if not checklist_settings:
                # Create default settings if none exist
                initialize_default_settings()
                checklist_settings = ChecklistSettings.query.first()
            
            if not phi_settings:
                initialize_default_settings()
                phi_settings = PHISettings.query.first()
            
            return {
                'checklist_settings': {
                    'cutoff_months': checklist_settings.cutoff_months if checklist_settings else 12,
                    'lab_cutoff_months': checklist_settings.lab_cutoff_months if checklist_settings else 12,
                    'imaging_cutoff_months': checklist_settings.imaging_cutoff_months if checklist_settings else 24,
                    'consult_cutoff_months': checklist_settings.consult_cutoff_months if checklist_settings else 12,
                    'hospital_cutoff_months': checklist_settings.hospital_cutoff_months if checklist_settings else 24,
                    'phi_filtering_enabled': checklist_settings.phi_filtering_enabled if checklist_settings else True,
                    'confidence_threshold': checklist_settings.confidence_threshold if checklist_settings else 0.6
                },
                'phi_settings': {
                    'filter_enabled': phi_settings.filter_enabled if phi_settings else True,
                    'filter_ssn': phi_settings.filter_ssn if phi_settings else True,
                    'filter_phone': phi_settings.filter_phone if phi_settings else True,
                    'filter_mrn': phi_settings.filter_mrn if phi_settings else True,
                    'filter_addresses': phi_settings.filter_addresses if phi_settings else True,
                    'filter_names': phi_settings.filter_names if phi_settings else True,
                    'filter_dates': phi_settings.filter_dates if phi_settings else True
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system settings: {str(e)}")
            return {'error': str(e)}
    
    def update_checklist_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update checklist settings"""
        try:
            checklist_settings = ChecklistSettings.query.first()
            
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
            
            # Update settings
            if 'lab_cutoff_months' in settings_data:
                checklist_settings.lab_cutoff_months = settings_data['lab_cutoff_months']
            if 'imaging_cutoff_months' in settings_data:
                checklist_settings.imaging_cutoff_months = settings_data['imaging_cutoff_months']
            if 'consult_cutoff_months' in settings_data:
                checklist_settings.consult_cutoff_months = settings_data['consult_cutoff_months']
            if 'hospital_cutoff_months' in settings_data:
                checklist_settings.hospital_cutoff_months = settings_data['hospital_cutoff_months']
            if 'cutoff_months' in settings_data:
                checklist_settings.cutoff_months = settings_data['cutoff_months']
            if 'phi_filtering_enabled' in settings_data:
                checklist_settings.phi_filtering_enabled = settings_data['phi_filtering_enabled']
            if 'confidence_threshold' in settings_data:
                checklist_settings.confidence_threshold = settings_data['confidence_threshold']
            
            db.session.commit()
            
            log_admin_action('update_checklist_settings', 'system', None, 
                           f'Updated checklist settings: {settings_data}')
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def update_phi_settings(self, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHI filter settings"""
        try:
            phi_settings = PHISettings.query.first()
            
            if not phi_settings:
                phi_settings = PHISettings()
                db.session.add(phi_settings)
            
            # Update PHI settings
            if 'filter_enabled' in settings_data:
                phi_settings.filter_enabled = settings_data['filter_enabled']
            if 'filter_ssn' in settings_data:
                phi_settings.filter_ssn = settings_data['filter_ssn']
            if 'filter_phone' in settings_data:
                phi_settings.filter_phone = settings_data['filter_phone']
            if 'filter_mrn' in settings_data:
                phi_settings.filter_mrn = settings_data['filter_mrn']
            if 'filter_addresses' in settings_data:
                phi_settings.filter_addresses = settings_data['filter_addresses']
            if 'filter_names' in settings_data:
                phi_settings.filter_names = settings_data['filter_names']
            if 'filter_dates' in settings_data:
                phi_settings.filter_dates = settings_data['filter_dates']
            
            db.session.commit()
            
            log_admin_action('update_phi_settings', 'system', None, 
                           f'Updated PHI settings: {settings_data}')
            
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Error updating PHI settings: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}


class ScreeningPresetManager:
    """Manages screening type presets for different specialties"""
    
    def __init__(self):
        self.specialty_presets = {
            'family_medicine': self._get_family_medicine_presets(),
            'internal_medicine': self._get_internal_medicine_presets(),
            'womens_health': self._get_womens_health_presets(),
            'geriatrics': self._get_geriatrics_presets(),
            'cardiology': self._get_cardiology_presets(),
            'endocrinology': self._get_endocrinology_presets()
        }
    
    def get_available_presets(self) -> Dict[str, List[str]]:
        """Get list of available presets by specialty"""
        return {
            specialty: [preset['name'] for preset in presets]
            for specialty, presets in self.specialty_presets.items()
        }
    
    def import_specialty_preset(self, specialty: str, overwrite_existing: bool = False) -> Dict[str, Any]:
        """
        Import screening presets for a specific specialty
        
        Args:
            specialty: Specialty name (e.g., 'family_medicine')
            overwrite_existing: Whether to overwrite existing screening types
        
        Returns:
            Dict containing import results
        """
        try:
            if specialty not in self.specialty_presets:
                return {'success': False, 'error': f'Unknown specialty: {specialty}'}
            
            presets = self.specialty_presets[specialty]
            imported_count = 0
            skipped_count = 0
            
            for preset in presets:
                # Check if screening type already exists
                existing = ScreeningType.query.filter_by(name=preset['name']).first()
                
                if existing and not overwrite_existing:
                    skipped_count += 1
                    continue
                
                if existing and overwrite_existing:
                    # Update existing
                    existing.description = preset['description']
                    existing.keywords = preset['keywords']
                    existing.gender_eligibility = preset['gender_eligibility']
                    existing.min_age = preset['min_age']
                    existing.max_age = preset['max_age']
                    existing.frequency_number = preset['frequency_number']
                    existing.frequency_unit = preset['frequency_unit']
                    existing.trigger_conditions = preset.get('trigger_conditions', [])
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    screening_type = ScreeningType(
                        name=preset['name'],
                        description=preset['description'],
                        keywords=preset['keywords'],
                        gender_eligibility=preset['gender_eligibility'],
                        min_age=preset['min_age'],
                        max_age=preset['max_age'],
                        frequency_number=preset['frequency_number'],
                        frequency_unit=preset['frequency_unit'],
                        trigger_conditions=preset.get('trigger_conditions', []),
                        is_active=True
                    )
                    db.session.add(screening_type)
                
                imported_count += 1
            
            db.session.commit()
            
            log_admin_action('specialty_preset_imported', 'screening_preset', specialty,
                           f'Imported {imported_count} screening types for {specialty}')
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'specialty': specialty
            }
            
        except Exception as e:
            logger.error(f"Error importing specialty preset: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def export_current_screenings(self) -> Dict[str, Any]:
        """Export current screening types for backup or sharing"""
        try:
            screenings = ScreeningType.query.filter_by(is_active=True).all()
            
            export_data = []
            for screening in screenings:
                export_data.append({
                    'name': screening.name,
                    'description': screening.description,
                    'keywords': screening.keywords,
                    'gender_eligibility': screening.gender_eligibility,
                    'min_age': screening.min_age,
                    'max_age': screening.max_age,
                    'frequency_number': screening.frequency_number,
                    'frequency_unit': screening.frequency_unit,
                    'trigger_conditions': screening.trigger_conditions
                })
            
            return {
                'success': True,
                'export_date': datetime.utcnow().isoformat(),
                'screening_count': len(export_data),
                'screenings': export_data
            }
            
        except Exception as e:
            logger.error(f"Error exporting screenings: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_family_medicine_presets(self) -> List[Dict]:
        """Get family medicine screening presets"""
        return [
            {
                'name': 'Annual Physical Exam',
                'description': 'Comprehensive annual physical examination',
                'keywords': ['annual physical', 'yearly exam', 'wellness visit', 'preventive care'],
                'gender_eligibility': 'All',
                'min_age': 18,
                'max_age': None,
                'frequency_number': 1,
                'frequency_unit': 'years'
            },
            {
                'name': 'Childhood Immunizations',
                'description': 'Routine childhood vaccination schedule',
                'keywords': ['immunization', 'vaccination', 'vaccine', 'shots'],
                'gender_eligibility': 'All',
                'min_age': 0,
                'max_age': 18,
                'frequency_number': 6,
                'frequency_unit': 'months'
            }
        ]
    
    def _get_internal_medicine_presets(self) -> List[Dict]:
        """Get internal medicine screening presets"""
        return [
            {
                'name': 'Diabetes Screening',
                'description': 'Fasting glucose or A1C for diabetes screening',
                'keywords': ['glucose', 'diabetes screening', 'fasting glucose', 'a1c'],
                'gender_eligibility': 'All',
                'min_age': 35,
                'max_age': None,
                'frequency_number': 3,
                'frequency_unit': 'years'
            }
        ]
    
    def _get_womens_health_presets(self) -> List[Dict]:
        """Get women's health screening presets"""
        return [
            {
                'name': 'Well-Woman Visit',
                'description': 'Annual gynecological examination',
                'keywords': ['well woman', 'gynecology', 'annual gyn', 'womens health'],
                'gender_eligibility': 'F',
                'min_age': 18,
                'max_age': None,
                'frequency_number': 1,
                'frequency_unit': 'years'
            }
        ]
    
    def _get_geriatrics_presets(self) -> List[Dict]:
        """Get geriatrics screening presets"""
        return [
            {
                'name': 'Fall Risk Assessment',
                'description': 'Assessment of fall risk in elderly patients',
                'keywords': ['fall risk', 'balance assessment', 'gait assessment'],
                'gender_eligibility': 'All',
                'min_age': 65,
                'max_age': None,
                'frequency_number': 1,
                'frequency_unit': 'years'
            }
        ]
    
    def _get_cardiology_presets(self) -> List[Dict]:
        """Get cardiology screening presets"""
        return [
            {
                'name': 'Echocardiogram',
                'description': 'Cardiac ultrasound for heart function assessment',
                'keywords': ['echocardiogram', 'echo', 'cardiac ultrasound', 'heart ultrasound'],
                'gender_eligibility': 'All',
                'min_age': 18,
                'max_age': None,
                'frequency_number': 2,
                'frequency_unit': 'years',
                'trigger_conditions': ['heart failure', 'cardiomyopathy', 'heart disease']
            }
        ]
    
    def _get_endocrinology_presets(self) -> List[Dict]:
        """Get endocrinology screening presets"""
        return [
            {
                'name': 'Thyroid Function Test',
                'description': 'TSH and thyroid hormone levels',
                'keywords': ['tsh', 'thyroid function', 't3', 't4', 'thyroid test'],
                'gender_eligibility': 'All',
                'min_age': 35,
                'max_age': None,
                'frequency_number': 5,
                'frequency_unit': 'years'
            }
        ]

