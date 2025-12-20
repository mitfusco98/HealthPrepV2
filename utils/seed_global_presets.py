"""
Global Screening Presets Seeder

Ensures system-level screening presets exist on startup, similar to root admin seeding.
These presets are owned by the System Organization (org_id=0) and the root admin user.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Hardcoded global preset definitions
# These are seeded on app startup if they don't exist
GLOBAL_PRESETS = [
    {
        "name": "36 N U",
        "description": "Standard nursing unit screening preset with essential preventive care screenings",
        "specialty": "primary_care",
        "screening_data": {
            "name": "36 N U",
            "description": "Standard nursing unit screening preset",
            "specialty": "primary_care",
            "version": "2.0",
            "screening_types": [
                {
                    "name": "Lipid Panel",
                    "description": "Cardiovascular risk assessment",
                    "keywords": ["lipid", "HDL", "LDL", "cholesterol", "triglycerides"],
                    "gender_criteria": "both",
                    "age_min": 30,
                    "age_max": None,
                    "frequency_number": 1,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                },
                {
                    "name": "Colonoscopy",
                    "description": "Colorectal cancer screening",
                    "keywords": ["cologuard", "colonoscopy", "upper endoscopy", "colorectal"],
                    "gender_criteria": "both",
                    "age_min": 45,
                    "age_max": None,
                    "frequency_number": 5,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                },
                {
                    "name": "Immunization Review",
                    "description": "Annual immunization status review",
                    "keywords": ["tetanus", "tdap", "flu", "influenza", "shingrix", "pneumonia", "vaccine"],
                    "gender_criteria": "both",
                    "age_min": 50,
                    "age_max": None,
                    "frequency_number": 1,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                },
                {
                    "name": "A1C Test",
                    "description": "Diabetes screening for general population",
                    "keywords": ["HbA1c", "A1C", "glucose", "hemoglobin a1c"],
                    "gender_criteria": "both",
                    "age_min": 40,
                    "age_max": None,
                    "frequency_number": 1,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                },
                {
                    "name": "A1C Test - Diabetic",
                    "description": "Diabetes monitoring for diabetic patients",
                    "keywords": ["HbA1c", "A1C"],
                    "gender_criteria": "both",
                    "age_min": None,
                    "age_max": None,
                    "frequency_number": 3,
                    "frequency_unit": "months",
                    "trigger_conditions": ["diabetes mellitus type I", "diabetes mellitus type 2", "diabetes"],
                    "is_active": True
                },
                {
                    "name": "Mammogram",
                    "description": "Breast cancer screening",
                    "keywords": ["mammogram", "breast imaging", "breast US", "mammography"],
                    "gender_criteria": "F",
                    "age_min": 45,
                    "age_max": None,
                    "frequency_number": 1,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                },
                {
                    "name": "Cervical Cancer Screening",
                    "description": "Pap smear and HPV screening",
                    "keywords": ["pap", "sureprep", "thinprep", "cervical", "hpv"],
                    "gender_criteria": "F",
                    "age_min": 21,
                    "age_max": None,
                    "frequency_number": 2,
                    "frequency_unit": "years",
                    "trigger_conditions": [],
                    "is_active": True
                }
            ]
        }
    }
]


def ensure_global_presets(db, ScreeningPreset, User):
    """
    Ensure global screening presets exist and are properly owned on startup.
    
    This function:
    1. Finds or creates the root admin user as the preset owner
    2. Seeds any missing global presets from GLOBAL_PRESETS constant
    3. Ensures ALL existing global presets are owned by the system (org_id=0, created_by=root_admin)
    
    Called during app initialization after _ensure_system_organization.
    
    Global presets with org_id=0 and preset_scope='global' are protected from deletion
    and will persist across AWS migrations.
    """
    try:
        # Find root admin user to own the presets
        root_admin = User.query.filter_by(is_root_admin=True).first()
        
        if not root_admin:
            logger.warning("No root admin found - skipping global preset seeding")
            return
        
        changes_made = False
        
        # Step 1: Ensure ALL existing global presets have correct ownership
        # This covers presets that weren't in GLOBAL_PRESETS but are marked as global
        existing_globals = ScreeningPreset.query.filter_by(preset_scope='global').all()
        
        for preset in existing_globals:
            needs_update = False
            
            # Ensure org_id=0 for system ownership
            if preset.org_id != 0:
                logger.info(f"Updating global preset '{preset.name}' (ID: {preset.id}) org_id from {preset.org_id} to 0")
                preset.org_id = 0
                needs_update = True
            
            # Ensure created_by points to root admin
            if preset.created_by != root_admin.id:
                logger.info(f"Updating global preset '{preset.name}' (ID: {preset.id}) created_by from {preset.created_by} to {root_admin.id}")
                preset.created_by = root_admin.id
                needs_update = True
            
            # Ensure shared flag is set
            if not preset.shared:
                preset.shared = True
                needs_update = True
            
            if needs_update:
                preset.updated_at = datetime.utcnow()
                changes_made = True
        
        # Step 2: Seed any missing presets from GLOBAL_PRESETS constant
        for preset_def in GLOBAL_PRESETS:
            existing = ScreeningPreset.query.filter_by(
                name=preset_def["name"],
                preset_scope='global'
            ).first()
            
            if not existing:
                # Create new global preset
                new_preset = ScreeningPreset(
                    name=preset_def["name"],
                    description=preset_def.get("description", ""),
                    specialty=preset_def.get("specialty", "primary_care"),
                    org_id=0,  # System organization
                    shared=True,
                    preset_scope='global',
                    screening_data=preset_def["screening_data"],
                    created_by=root_admin.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_preset)
                changes_made = True
                logger.info(f"Created global preset: {preset_def['name']}")
        
        if changes_made:
            db.session.commit()
            logger.info("Global presets ownership verification completed")
        else:
            logger.info("Global presets verified - no changes needed")
            
    except Exception as e:
        logger.error(f"Error seeding global presets: {str(e)}")
        db.session.rollback()


def reassign_user_global_presets(db, ScreeningPreset, user_id, root_admin_id):
    """
    Reassign global presets from a user to the root admin before user deletion.
    
    This ensures global presets persist when their creator is deleted.
    
    Args:
        db: Database session
        ScreeningPreset: ScreeningPreset model class
        user_id: ID of the user being deleted
        root_admin_id: ID of the root admin to receive ownership
    
    Returns:
        int: Number of presets reassigned
    """
    try:
        # Find all global presets created by this user
        global_presets = ScreeningPreset.query.filter_by(
            created_by=user_id,
            preset_scope='global'
        ).all()
        
        count = 0
        for preset in global_presets:
            preset.created_by = root_admin_id
            preset.org_id = 0  # Ensure system org
            preset.updated_at = datetime.utcnow()
            count += 1
            logger.info(f"Reassigned global preset '{preset.name}' (ID: {preset.id}) from user {user_id} to root admin {root_admin_id}")
        
        if count > 0:
            db.session.flush()
            logger.info(f"Reassigned {count} global presets from user {user_id} to root admin")
        
        return count
        
    except Exception as e:
        logger.error(f"Error reassigning global presets: {str(e)}")
        return 0
