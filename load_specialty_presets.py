#!/usr/bin/env python3
"""
Script to load all specialty screening presets into the database as global presets.
Creates comprehensive medical specialty packages for immediate deployment.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

# Add the current directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, create_app
from models import ScreeningPreset

# Create Flask app context
app = create_app()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_preset_from_file(filepath, preset_scope='global', shared=True):
    """Load a preset from a JSON file and create it in the database."""
    try:
        with open(filepath, 'r') as f:
            preset_data = json.load(f)
        
        # Extract metadata
        name = preset_data.get('name', 'Unknown Preset')
        description = preset_data.get('description', '')
        specialty = preset_data.get('specialty', 'General')
        
        # Check if preset already exists
        existing = ScreeningPreset.query.filter_by(
            name=name,
            preset_scope=preset_scope
        ).first()
        
        if existing:
            logger.info(f"Preset '{name}' already exists as global preset, updating...")
            # Update existing preset
            existing.description = description
            existing.specialty = specialty
            existing.screening_data = preset_data  # Store complete preset data
            existing.shared = shared
            existing.updated_at = datetime.now(timezone.utc)
            preset = existing
        else:
            # Create new preset
            preset = ScreeningPreset(
                name=name,
                description=description,
                specialty=specialty,
                screening_data=preset_data,  # Store complete preset data
                preset_scope=preset_scope,
                shared=shared,
                org_id=0,  # System Organization for global presets
                created_by=5,  # Root admin user ID
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(preset)
        
        db.session.commit()
        logger.info(f"✅ Successfully loaded preset: '{name}' ({specialty})")
        return preset
        
    except Exception as e:
        logger.error(f"❌ Failed to load preset from {filepath}: {str(e)}")
        db.session.rollback()
        return None

def main():
    """Load all specialty presets as global presets."""
    with app.app_context():
        logger.info("🚀 Starting specialty preset loading process...")
        
        # Define all preset files to load
        preset_files = [
            'presets/examples/primary_care.json',
            'presets/examples/cardiology.json', 
            'presets/examples/womens_health.json',
            'presets/examples/oncology.json',
            'presets/examples/endocrinology.json',
            'presets/examples/pulmonology.json',
            'presets/examples/gastroenterology.json',
            'presets/examples/neurology.json'
        ]
        
        loaded_count = 0
        failed_count = 0
        
        for preset_file in preset_files:
            if os.path.exists(preset_file):
                preset = load_preset_from_file(preset_file, preset_scope='global', shared=True)
                if preset:
                    loaded_count += 1
                else:
                    failed_count += 1
            else:
                logger.warning(f"⚠️  Preset file not found: {preset_file}")
                failed_count += 1
        
        # Summary
        logger.info(f"""
        🎉 SPECIALTY PRESET LOADING COMPLETE!
        ✅ Successfully loaded: {loaded_count} presets
        ❌ Failed to load: {failed_count} presets
        
        📋 Available Global Presets:
        """)
        
        # List all global presets
        global_presets = ScreeningPreset.query.filter_by(preset_scope='global').all()
        for preset in global_presets:
            screening_count = len(preset.get_screening_types())
            logger.info(f"   • {preset.name} ({preset.specialty}) - {screening_count} screening types")
        
        logger.info(f"""
        🌐 All presets are now globally available at:
        • /root-admin/presets (Root Admin Management)
        • /root-admin/presets/view/<id> (Detailed View)
        • Can be applied to any organization via "Apply" action
        
        🔥 VARIANT SYSTEM READY:
        Each preset includes condition-based variants for personalized screening protocols!
        """)

if __name__ == '__main__':
    main()