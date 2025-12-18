#!/usr/bin/env python3
"""
Backfill script to fix global presets with org_id=None to use org_id=0 (System Organization).

This ensures all global presets are properly protected from organization deletion
and consistently owned by the System Organization.

Run with: python backfill_global_presets.py
"""

import os
import sys

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models import ScreeningPreset
from datetime import datetime

# Create the app instance
app = create_app()

def backfill_global_presets():
    """Update all global presets with org_id=None to org_id=0"""
    with app.app_context():
        # Find all global presets with org_id=None
        orphaned_global_presets = ScreeningPreset.query.filter(
            ScreeningPreset.preset_scope == 'global',
            ScreeningPreset.org_id == None
        ).all()
        
        if not orphaned_global_presets:
            print("No global presets with org_id=None found. All presets are properly configured.")
            return 0
        
        print(f"Found {len(orphaned_global_presets)} global presets with org_id=None")
        
        updated_count = 0
        for preset in orphaned_global_presets:
            print(f"  - Updating preset '{preset.name}' (ID: {preset.id})")
            
            # Store original info in metadata if not already present
            if not preset.preset_metadata:
                preset.preset_metadata = {}
            
            if 'backfill_info' not in preset.preset_metadata:
                preset.preset_metadata['backfill_info'] = {
                    'backfilled_at': datetime.utcnow().isoformat(),
                    'previous_org_id': None,
                    'reason': 'Migrated from org_id=None to org_id=0 for System Organization ownership'
                }
            
            # Update org_id to System Organization
            preset.org_id = 0
            updated_count += 1
        
        db.session.commit()
        print(f"\nSuccessfully updated {updated_count} global presets to use org_id=0 (System Organization)")
        return updated_count

def verify_global_presets():
    """Verify all global presets are now properly configured"""
    with app.app_context():
        # Check for any remaining issues
        still_orphaned = ScreeningPreset.query.filter(
            ScreeningPreset.preset_scope == 'global',
            ScreeningPreset.org_id == None
        ).count()
        
        system_owned = ScreeningPreset.query.filter(
            ScreeningPreset.preset_scope == 'global',
            ScreeningPreset.org_id == 0
        ).count()
        
        print(f"\nVerification:")
        print(f"  - Global presets owned by System Organization (org_id=0): {system_owned}")
        print(f"  - Global presets still orphaned (org_id=None): {still_orphaned}")
        
        if still_orphaned > 0:
            print("  WARNING: Some global presets are still orphaned!")
            return False
        else:
            print("  SUCCESS: All global presets are properly configured!")
            return True

if __name__ == '__main__':
    print("=" * 60)
    print("Global Preset Backfill Script")
    print("=" * 60)
    print()
    
    updated = backfill_global_presets()
    success = verify_global_presets()
    
    print()
    print("=" * 60)
    sys.exit(0 if success else 1)
