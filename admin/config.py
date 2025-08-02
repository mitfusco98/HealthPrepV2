"""
Admin configuration management
Handles system settings, presets, and configuration options
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from models import ScreeningType, ChecklistSettings, PHISettings, db

class AdminConfig:
    """Manages administrative configuration and settings"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_system_settings(self) -> Dict[str, Any]:
        """Get current system configuration settings"""
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
            
            # Get screening type statistics
            total_screening_types = ScreeningType.query.count()
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            
            return {
                "checklist_settings": {
                    "labs_cutoff_months": checklist_settings.labs_cutoff_months,
                    "imaging_cutoff_months": checklist_settings.imaging_cutoff_months,
                    "consults_cutoff_months": checklist_settings.consults_cutoff_months,
                    "hospital_cutoff_months": checklist_settings.hospital_cutoff_months,
                    "default_items": json.loads(checklist_settings.default_items) if checklist_settings.default_items else [],
                    "last_updated": checklist_settings.updated_at
                },
                "phi_settings": {
                    "filter_enabled": phi_settings.filter_enabled,
                    "filter_ssn": phi_settings.filter_ssn,
                    "filter_phone": phi_settings.filter_phone,
                    "filter_mrn": phi_settings.filter_mrn,
                    "filter_addresses": phi_settings.filter_addresses,
                    "filter_names": phi_settings.filter_names,
                    "filter_dates": phi_settings.filter_dates,
                    "custom_patterns": json.loads(phi_settings.custom_patterns) if phi_settings.custom_patterns else [],
                    "last_updated": phi_settings.updated_at
                },
                "screening_types": {
                    "total": total_screening_types,
                    "active": active_screening_types,
                    "inactive": total_screening_types - active_screening_types
                },
                "system_info": {
                    "version": "2.0",
                    "last_config_check": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system settings: {str(e)}")
            return {"error": str(e)}
    
    def update_checklist_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update checklist/prep sheet settings"""
        try:
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                checklist_settings = ChecklistSettings()
                db.session.add(checklist_settings)
            
            # Update settings
            if 'labs_cutoff_months' in settings:
                checklist_settings.labs_cutoff_months = settings['labs_cutoff_months']
            
            if 'imaging_cutoff_months' in settings:
                checklist_settings.imaging_cutoff_months = settings['imaging_cutoff_months']
            
            if 'consults_cutoff_months' in settings:
                checklist_settings.consults_cutoff_months = settings['consults_cutoff_months']
            
            if 'hospital_cutoff_months' in settings:
                checklist_settings.hospital_cutoff_months = settings['hospital_cutoff_months']
            
            if 'default_items' in settings:
                checklist_settings.default_items = json.dumps(settings['default_items'])
            
            checklist_settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.info("Checklist settings updated successfully")
            
            return {
                "success": True,
                "message": "Checklist settings updated successfully",
                "updated_at": checklist_settings.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating checklist settings: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}
    
    def update_phi_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update PHI filtering settings"""
        try:
            phi_settings = PHISettings.query.first()
            if not phi_settings:
                phi_settings = PHISettings()
                db.session.add(phi_settings)
            
            # Update settings
            if 'filter_enabled' in settings:
                phi_settings.filter_enabled = settings['filter_enabled']
            
            if 'filter_ssn' in settings:
                phi_settings.filter_ssn = settings['filter_ssn']
            
            if 'filter_phone' in settings:
                phi_settings.filter_phone = settings['filter_phone']
            
            if 'filter_mrn' in settings:
                phi_settings.filter_mrn = settings['filter_mrn']
            
            if 'filter_addresses' in settings:
                phi_settings.filter_addresses = settings['filter_addresses']
            
            if 'filter_names' in settings:
                phi_settings.filter_names = settings['filter_names']
            
            if 'filter_dates' in settings:
                phi_settings.filter_dates = settings['filter_dates']
            
            if 'custom_patterns' in settings:
                phi_settings.custom_patterns = json.dumps(settings['custom_patterns'])
            
            phi_settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.info("PHI settings updated successfully")
            
            return {
                "success": True,
                "message": "PHI settings updated successfully",
                "updated_at": phi_settings.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating PHI settings: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}
    
    def get_screening_presets(self) -> Dict[str, Any]:
        """Get available screening type presets"""
        try:
            # Define common screening presets for different specialties
            presets = {
                "primary_care": {
                    "name": "Primary Care Basic",
                    "description": "Essential screenings for primary care practice",
                    "screening_types": [
                        {
                            "name": "Mammogram",
                            "keywords": ["mammogram", "mammo", "mammography", "breast screening"],
                            "gender_criteria": "F",
                            "min_age": 40,
                            "max_age": 74,
                            "frequency_years": 1,
                            "description": "Annual mammogram screening for breast cancer"
                        },
                        {
                            "name": "Colonoscopy",
                            "keywords": ["colonoscopy", "colon screening", "colorectal screening"],
                            "gender_criteria": "ALL",
                            "min_age": 50,
                            "max_age": 75,
                            "frequency_years": 10,
                            "description": "Colorectal cancer screening"
                        },
                        {
                            "name": "Pap Smear",
                            "keywords": ["pap smear", "pap test", "cervical screening", "papanicolaou"],
                            "gender_criteria": "F",
                            "min_age": 21,
                            "max_age": 65,
                            "frequency_years": 3,
                            "description": "Cervical cancer screening"
                        },
                        {
                            "name": "DEXA Scan",
                            "keywords": ["dexa", "dxa", "bone density", "osteoporosis screening"],
                            "gender_criteria": "F",
                            "min_age": 65,
                            "frequency_years": 2,
                            "description": "Bone density screening"
                        },
                        {
                            "name": "Lipid Panel",
                            "keywords": ["lipid panel", "cholesterol", "lipids", "cholesterol screening"],
                            "gender_criteria": "ALL",
                            "min_age": 20,
                            "frequency_years": 5,
                            "description": "Cholesterol and lipid screening"
                        }
                    ]
                },
                "cardiology": {
                    "name": "Cardiology Focused",
                    "description": "Heart-focused screening protocols",
                    "screening_types": [
                        {
                            "name": "Echocardiogram",
                            "keywords": ["echo", "echocardiogram", "cardiac echo"],
                            "gender_criteria": "ALL",
                            "frequency_years": 3,
                            "trigger_conditions": ["heart disease", "hypertension", "diabetes"],
                            "description": "Heart function assessment"
                        },
                        {
                            "name": "Stress Test",
                            "keywords": ["stress test", "cardiac stress", "exercise stress"],
                            "gender_criteria": "ALL",
                            "min_age": 40,
                            "frequency_years": 2,
                            "trigger_conditions": ["heart disease", "chest pain"],
                            "description": "Cardiac stress testing"
                        },
                        {
                            "name": "Lipid Panel - High Risk",
                            "keywords": ["lipid panel", "cholesterol", "lipids"],
                            "gender_criteria": "ALL",
                            "frequency_months": 6,
                            "trigger_conditions": ["heart disease", "diabetes", "hypertension"],
                            "description": "Frequent lipid monitoring for high-risk patients"
                        }
                    ]
                },
                "endocrinology": {
                    "name": "Endocrinology Focused",
                    "description": "Diabetes and hormone-focused screenings",
                    "screening_types": [
                        {
                            "name": "Hemoglobin A1C",
                            "keywords": ["a1c", "hemoglobin a1c", "hba1c", "glycated hemoglobin"],
                            "gender_criteria": "ALL",
                            "frequency_months": 3,
                            "trigger_conditions": ["diabetes", "diabetic"],
                            "description": "Diabetes monitoring - diabetic patients"
                        },
                        {
                            "name": "Hemoglobin A1C - Pre-diabetic",
                            "keywords": ["a1c", "hemoglobin a1c", "hba1c"],
                            "gender_criteria": "ALL",
                            "frequency_months": 6,
                            "trigger_conditions": ["pre-diabetes", "prediabetes"],
                            "description": "Diabetes monitoring - pre-diabetic patients"
                        },
                        {
                            "name": "Thyroid Function",
                            "keywords": ["tsh", "thyroid", "t3", "t4", "thyroid function"],
                            "gender_criteria": "ALL",
                            "frequency_years": 2,
                            "description": "Thyroid function screening"
                        }
                    ]
                },
                "womens_health": {
                    "name": "Women's Health",
                    "description": "Women's health focused screenings",
                    "screening_types": [
                        {
                            "name": "Mammogram - Standard",
                            "keywords": ["mammogram", "mammo", "mammography"],
                            "gender_criteria": "F",
                            "min_age": 50,
                            "max_age": 74,
                            "frequency_years": 2,
                            "description": "Biennial mammogram screening"
                        },
                        {
                            "name": "Mammogram - High Risk",
                            "keywords": ["mammogram", "mammo", "mammography"],
                            "gender_criteria": "F",
                            "min_age": 40,
                            "frequency_years": 1,
                            "trigger_conditions": ["family history breast cancer", "brca", "high risk"],
                            "description": "Annual mammogram for high-risk patients"
                        },
                        {
                            "name": "Pap Smear",
                            "keywords": ["pap smear", "pap test", "cervical screening"],
                            "gender_criteria": "F",
                            "min_age": 21,
                            "max_age": 65,
                            "frequency_years": 3,
                            "description": "Cervical cancer screening"
                        },
                        {
                            "name": "DEXA Scan",
                            "keywords": ["dexa", "dxa", "bone density"],
                            "gender_criteria": "F",
                            "min_age": 65,
                            "frequency_years": 2,
                            "description": "Bone density screening"
                        }
                    ]
                }
            }
            
            return {
                "presets": presets,
                "total_presets": len(presets),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting screening presets: {str(e)}")
            return {"error": str(e)}
    
    def import_screening_preset(self, preset_name: str) -> Dict[str, Any]:
        """Import a screening preset"""
        try:
            presets = self.get_screening_presets()
            if "error" in presets:
                return presets
            
            if preset_name not in presets["presets"]:
                return {"error": f"Preset '{preset_name}' not found"}
            
            preset = presets["presets"][preset_name]
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for screening_data in preset["screening_types"]:
                try:
                    # Check if screening type already exists
                    existing = ScreeningType.query.filter_by(name=screening_data["name"]).first()
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Create new screening type
                    screening_type = ScreeningType(
                        name=screening_data["name"],
                        description=screening_data.get("description", ""),
                        keywords="\n".join(screening_data.get("keywords", [])),
                        gender_criteria=screening_data.get("gender_criteria", "ALL"),
                        min_age=screening_data.get("min_age"),
                        max_age=screening_data.get("max_age"),
                        frequency_years=screening_data.get("frequency_years"),
                        frequency_months=screening_data.get("frequency_months"),
                        trigger_conditions="\n".join(screening_data.get("trigger_conditions", [])),
                        is_active=True
                    )
                    
                    db.session.add(screening_type)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Error importing '{screening_data['name']}': {str(e)}")
            
            db.session.commit()
            
            self.logger.info(f"Imported {imported_count} screening types from preset '{preset_name}'")
            
            return {
                "success": True,
                "preset_name": preset_name,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "errors": errors,
                "total_attempted": len(preset["screening_types"])
            }
            
        except Exception as e:
            self.logger.error(f"Error importing screening preset: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}
    
    def export_current_config(self) -> Dict[str, Any]:
        """Export current system configuration for backup"""
        try:
            # Get all current screening types
            screening_types = ScreeningType.query.all()
            
            # Get system settings
            settings = self.get_system_settings()
            if "error" in settings:
                return settings
            
            export_data = {
                "export_info": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "version": "2.0",
                    "export_type": "full_config"
                },
                "system_settings": settings,
                "screening_types": [
                    {
                        "name": st.name,
                        "description": st.description,
                        "keywords": st.keywords.split('\n') if st.keywords else [],
                        "gender_criteria": st.gender_criteria,
                        "min_age": st.min_age,
                        "max_age": st.max_age,
                        "frequency_years": st.frequency_years,
                        "frequency_months": st.frequency_months,
                        "trigger_conditions": st.trigger_conditions.split('\n') if st.trigger_conditions else [],
                        "is_active": st.is_active,
                        "created_at": st.created_at.isoformat() if st.created_at else None
                    } for st in screening_types
                ]
            }
            
            return export_data
            
        except Exception as e:
            self.logger.error(f"Error exporting current config: {str(e)}")
            return {"error": str(e)}
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current system configuration"""
        try:
            validation_results = {
                "valid": True,
                "warnings": [],
                "errors": [],
                "recommendations": []
            }
            
            # Check screening types
            screening_types = ScreeningType.query.all()
            active_screenings = ScreeningType.query.filter_by(is_active=True).all()
            
            if len(screening_types) == 0:
                validation_results["errors"].append("No screening types defined")
                validation_results["valid"] = False
            
            if len(active_screenings) == 0:
                validation_results["errors"].append("No active screening types")
                validation_results["valid"] = False
            
            # Check for screenings without keywords
            no_keywords = [st.name for st in active_screenings if not st.keywords]
            if no_keywords:
                validation_results["warnings"].append(f"Screening types without keywords: {', '.join(no_keywords)}")
            
            # Check for screenings without frequency
            no_frequency = [st.name for st in active_screenings if not st.frequency_years and not st.frequency_months]
            if no_frequency:
                validation_results["warnings"].append(f"Screening types without frequency: {', '.join(no_frequency)}")
            
            # Check PHI settings
            phi_settings = PHISettings.query.first()
            if not phi_settings or not phi_settings.filter_enabled:
                validation_results["warnings"].append("PHI filtering is disabled - may not be HIPAA compliant")
            
            # Check checklist settings
            checklist_settings = ChecklistSettings.query.first()
            if not checklist_settings:
                validation_results["warnings"].append("No checklist settings configured - using defaults")
            
            # Generate recommendations
            if len(active_screenings) < 5:
                validation_results["recommendations"].append("Consider importing a specialty preset to add more screening types")
            
            if validation_results["valid"] and not validation_results["warnings"]:
                validation_results["recommendations"].append("Configuration is valid and complete")
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error validating config: {str(e)}")
            return {"error": str(e)}

# Global config instance
admin_config = AdminConfig()
