"""
Enhanced specialty preset processing to handle base types and variants correctly
"""
import logging
from collections import defaultdict
from app import db
from models import ScreeningType, ScreeningPreset

class SpecialtyPresetEnhancer:
    """Enhances specialty presets to create proper base types and variants"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_specialty_preset(self, preset_data, org_id=None, created_by=None):
        """
        Process a specialty preset to create proper base types and variants
        
        Args:
            preset_data: The preset data dictionary
            org_id: Organization ID (None for global presets)
            created_by: User ID who created the preset
            
        Returns:
            List of created screening types
        """
        screening_types_data = preset_data.get('screening_types', [])
        created_types = []
        
        # Group screening types by base name
        base_groups = self._group_by_base_name(screening_types_data)
        
        for base_name, variants in base_groups.items():
            # Create base screening type if it doesn't exist
            base_type = self._create_or_get_base_type(base_name, variants, org_id, created_by)
            if base_type:
                created_types.append(base_type)
            
            # Create variants with proper categorization
            for variant_data in variants:
                variant_type = self._create_variant_type(variant_data, base_type, org_id, created_by)
                if variant_type:
                    created_types.append(variant_type)
        
        return created_types
    
    def _group_by_base_name(self, screening_types_data):
        """Group screening types by their base name (before the dash)"""
        groups = defaultdict(list)
        
        for st_data in screening_types_data:
            name = st_data.get('name', '')
            
            if ' - ' in name:
                # Extract base name (everything before first dash)
                base_name = name.split(' - ')[0].strip()
                groups[base_name].append(st_data)
            else:
                # This is already a base type
                groups[name].append(st_data)
        
        return dict(groups)
    
    def _create_or_get_base_type(self, base_name, variants, org_id, created_by):
        """Create or get the base screening type"""
        # Check if base type already exists
        existing = ScreeningType.query.filter_by(
            name=base_name,
            org_id=org_id
        ).first()
        
        if existing:
            return existing
        
        # Find the most general variant to use as base template
        general_variant = None
        for variant in variants:
            trigger_conditions = variant.get('trigger_conditions', [])
            if not trigger_conditions or len(trigger_conditions) == 0:
                general_variant = variant
                break
        
        # If no general variant found, use the first one as template
        if not general_variant:
            general_variant = variants[0]
        
        # Create base screening type
        base_type = ScreeningType(
            name=base_name,
            org_id=org_id,
            keywords=self._serialize_keywords(general_variant.get('keywords', [])),
            eligible_genders=general_variant.get('eligible_genders', 'both'),
            min_age=general_variant.get('min_age'),
            max_age=general_variant.get('max_age'),
            frequency_years=general_variant.get('frequency_years', 1.0),
            trigger_conditions='[]',  # Base types have no trigger conditions
            screening_category='general',  # Base types are general population
            is_active=True,
            created_by=created_by
        )
        
        db.session.add(base_type)
        db.session.flush()  # Get the ID
        
        self.logger.info(f"Created base screening type: {base_name}")
        return base_type
    
    def _create_variant_type(self, variant_data, base_type, org_id, created_by):
        """Create a variant screening type"""
        variant_name = variant_data.get('name', '')
        
        # Determine screening category based on trigger conditions
        trigger_conditions = variant_data.get('trigger_conditions', [])
        if trigger_conditions and len(trigger_conditions) > 0:
            screening_category = 'conditional'
        else:
            screening_category = 'general'
        
        # Check if variant already exists
        existing = ScreeningType.query.filter_by(
            name=variant_name,
            org_id=org_id
        ).first()
        
        if existing:
            # Update existing variant with new category
            existing.screening_category = screening_category
            return existing
        
        # Create variant screening type
        variant_type = ScreeningType(
            name=variant_name,
            org_id=org_id,
            keywords=self._serialize_keywords(variant_data.get('keywords', [])),
            eligible_genders=variant_data.get('eligible_genders', 'both'),
            min_age=variant_data.get('min_age'),
            max_age=variant_data.get('max_age'),
            frequency_years=variant_data.get('frequency_years', 1.0),
            trigger_conditions=self._serialize_trigger_conditions(trigger_conditions),
            screening_category=screening_category,
            is_active=variant_data.get('is_active', True),
            created_by=created_by
        )
        
        db.session.add(variant_type)
        self.logger.info(f"Created variant screening type: {variant_name} (category: {screening_category})")
        return variant_type
    
    def _serialize_keywords(self, keywords):
        """Serialize keywords to JSON string"""
        if not keywords:
            return '[]'
        import json
        return json.dumps(keywords)
    
    def _serialize_trigger_conditions(self, trigger_conditions):
        """Serialize trigger conditions to JSON string"""
        if not trigger_conditions:
            return '[]'
        import json
        return json.dumps(trigger_conditions)
    
    def enhance_existing_presets(self):
        """Enhance all existing specialty presets to create proper base types"""
        presets = ScreeningPreset.query.filter(
            ScreeningPreset.specialty.in_(['Oncology', 'Cardiology', 'Gastroenterology', 'Womens Health'])
        ).all()
        
        enhanced_count = 0
        
        for preset in presets:
            try:
                screening_data = preset.get_screening_types()
                if screening_data:
                    created_types = self.process_specialty_preset(
                        {'screening_types': screening_data},
                        org_id=preset.org_id,
                        created_by=preset.created_by
                    )
                    if created_types:
                        enhanced_count += 1
                        self.logger.info(f"Enhanced preset: {preset.name}")
            except Exception as e:
                self.logger.error(f"Error enhancing preset {preset.name}: {str(e)}")
        
        db.session.commit()
        self.logger.info(f"Enhanced {enhanced_count} specialty presets")
        return enhanced_count