"""
Handles screening type variants
Manages different screening protocols based on patient trigger conditions
"""

from models import ScreeningVariant, Condition
import logging

class VariantProcessor:
    """Handles screening type variants based on patient conditions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_applicable_variant(self, patient, screening_type):
        """Get the most applicable variant for a patient and screening type"""
        try:
            # Get all active variants for this screening type
            variants = ScreeningVariant.query.filter_by(
                screening_type_id=screening_type.id,
                is_active=True
            ).all()
            
            if not variants:
                return None
            
            # Get patient's active conditions
            patient_conditions = Condition.query.filter_by(
                patient_id=patient.id,
                status='active'
            ).all()
            
            patient_condition_names = [
                condition.condition_name.lower().strip()
                for condition in patient_conditions
            ]
            
            # Find the best matching variant
            best_variant = None
            best_match_count = 0
            
            for variant in variants:
                if not variant.trigger_conditions:
                    continue
                
                match_count = self._count_condition_matches(
                    variant.trigger_conditions, 
                    patient_condition_names
                )
                
                if match_count > best_match_count:
                    best_variant = variant
                    best_match_count = match_count
            
            if best_variant:
                self.logger.debug(f"Found variant {best_variant.name} for patient {patient.mrn} "
                               f"and screening {screening_type.name}")
            
            return best_variant
            
        except Exception as e:
            self.logger.error(f"Error getting applicable variant: {str(e)}")
            return None
    
    def _count_condition_matches(self, variant_conditions, patient_conditions):
        """Count how many variant conditions match patient conditions"""
        if not variant_conditions or not isinstance(variant_conditions, list):
            return 0
        
        match_count = 0
        
        for variant_condition in variant_conditions:
            variant_condition_lower = variant_condition.lower().strip()
            
            for patient_condition in patient_conditions:
                if self._conditions_match(variant_condition_lower, patient_condition):
                    match_count += 1
                    break  # Count each variant condition only once
        
        return match_count
    
    def _conditions_match(self, variant_condition, patient_condition):
        """Check if a variant condition matches a patient condition"""
        # Exact match
        if variant_condition == patient_condition:
            return True
        
        # Partial match (either contains the other)
        if (variant_condition in patient_condition or 
            patient_condition in variant_condition):
            return True
        
        # Check for common condition synonyms
        synonyms = self._get_condition_synonyms()
        
        for synonym_group in synonyms:
            if (variant_condition in synonym_group and 
                patient_condition in synonym_group):
                return True
        
        return False
    
    def _get_condition_synonyms(self):
        """Get groups of condition synonyms for matching"""
        return [
            ['diabetes', 'diabetes mellitus', 'dm', 'diabetic'],
            ['hypertension', 'high blood pressure', 'htn'],
            ['hyperlipidemia', 'high cholesterol', 'dyslipidemia'],
            ['coronary artery disease', 'cad', 'heart disease', 'cardiac disease'],
            ['chronic kidney disease', 'ckd', 'kidney disease', 'renal disease'],
            ['copd', 'chronic obstructive pulmonary disease', 'emphysema'],
            ['depression', 'major depressive disorder', 'mdd'],
            ['anxiety', 'anxiety disorder', 'generalized anxiety'],
            ['osteoporosis', 'bone loss', 'low bone density'],
            ['arthritis', 'osteoarthritis', 'rheumatoid arthritis'],
        ]
    
    def create_variant(self, screening_type_id, variant_data):
        """Create a new screening variant"""
        try:
            variant = ScreeningVariant(
                screening_type_id=screening_type_id,
                name=variant_data['name'],
                description=variant_data.get('description'),
                trigger_conditions=variant_data.get('trigger_conditions', []),
                frequency_years=variant_data.get('frequency_years'),
                frequency_months=variant_data.get('frequency_months'),
                keywords=variant_data.get('keywords', []),
                is_active=variant_data.get('is_active', True)
            )
            
            from app import db
            db.session.add(variant)
            db.session.commit()
            
            self.logger.info(f"Created variant {variant.name} for screening type {screening_type_id}")
            return variant
            
        except Exception as e:
            self.logger.error(f"Error creating variant: {str(e)}")
            raise
    
    def update_variant(self, variant_id, variant_data):
        """Update an existing screening variant"""
        try:
            variant = ScreeningVariant.query.get(variant_id)
            if not variant:
                raise ValueError(f"Variant {variant_id} not found")
            
            # Update fields
            for field in ['name', 'description', 'trigger_conditions', 
                         'frequency_years', 'frequency_months', 'keywords', 'is_active']:
                if field in variant_data:
                    setattr(variant, field, variant_data[field])
            
            from app import db
            db.session.commit()
            
            self.logger.info(f"Updated variant {variant.name}")
            return variant
            
        except Exception as e:
            self.logger.error(f"Error updating variant {variant_id}: {str(e)}")
            raise
    
    def delete_variant(self, variant_id):
        """Delete a screening variant"""
        try:
            variant = ScreeningVariant.query.get(variant_id)
            if not variant:
                raise ValueError(f"Variant {variant_id} not found")
            
            variant_name = variant.name
            
            from app import db
            db.session.delete(variant)
            db.session.commit()
            
            self.logger.info(f"Deleted variant {variant_name}")
            
        except Exception as e:
            self.logger.error(f"Error deleting variant {variant_id}: {str(e)}")
            raise
    
    def get_variants_for_screening_type(self, screening_type_id):
        """Get all variants for a screening type"""
        return ScreeningVariant.query.filter_by(
            screening_type_id=screening_type_id
        ).order_by(ScreeningVariant.name).all()
    
    def validate_variant_data(self, variant_data):
        """Validate variant data for consistency"""
        errors = []
        
        # Check required fields
        if not variant_data.get('name'):
            errors.append("Variant name is required")
        
        # Check frequency validity
        freq_years = variant_data.get('frequency_years', 0) or 0
        freq_months = variant_data.get('frequency_months', 0) or 0
        
        if freq_years == 0 and freq_months == 0:
            errors.append("Variant frequency must be specified (years or months)")
        
        if freq_years > 10:
            errors.append("Frequency in years should not exceed 10")
        
        if freq_months > 60:
            errors.append("Frequency in months should not exceed 60")
        
        # Check trigger conditions
        trigger_conditions = variant_data.get('trigger_conditions')
        if trigger_conditions and not isinstance(trigger_conditions, list):
            errors.append("Trigger conditions must be a list")
        
        # Check keywords
        keywords = variant_data.get('keywords')
        if keywords and not isinstance(keywords, list):
            errors.append("Keywords must be a list")
        
        return errors
    
    def get_patient_applicable_variants(self, patient):
        """Get all variants that apply to a patient across all screening types"""
        try:
            from models import ScreeningType
            
            applicable_variants = []
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            for screening_type in screening_types:
                variant = self.get_applicable_variant(patient, screening_type)
                if variant:
                    applicable_variants.append({
                        'screening_type': screening_type,
                        'variant': variant
                    })
            
            return applicable_variants
            
        except Exception as e:
            self.logger.error(f"Error getting patient applicable variants: {str(e)}")
            return []
