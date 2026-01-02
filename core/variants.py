"""
Handles screening type variants for different patient conditions
"""
from app import db
from models import ScreeningType, Patient, PatientCondition
import logging

class ScreeningVariants:
    """Manages screening type variants based on patient trigger conditions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_applicable_variant(self, patient, base_screening_type):
        """Get the most applicable screening variant for a patient
        
        DETERMINISTIC: Uses consistent ordering (specificity desc, then id) to ensure
        the same patient + same criteria always produces the same result.
        """
        
        # Get all variants of this screening type (including the base type itself)
        # DETERMINISTIC ORDERING: Sort by specificity (desc) then ID for consistent results
        # Note: specificity_score is a computed @property, so we sort in Python, not SQL
        variants = ScreeningType.query.filter(
            ScreeningType.name.like(f"{base_screening_type.name}%"),
            ScreeningType.is_active == True
        ).all()
        
        # Sort by specificity_score (desc), then id (asc) for deterministic ordering
        variants.sort(key=lambda v: (-v.specificity_score, v.id))
        
        if not variants:
            return base_screening_type
        
        # Separate general population and conditional variants
        # Lists maintain the deterministic ordering from the query
        general_variants = []
        conditional_variants = []
        
        for variant in variants:
            screening_category = getattr(variant, 'screening_category', 'general')
            if screening_category == 'general':
                general_variants.append(variant)
            else:
                conditional_variants.append(variant)
        
        # First try to find a matching conditional variant
        # DETERMINISTIC: On ties, prefer higher specificity, then lower ID (from query order)
        best_conditional = None
        max_matched_conditions = 0
        
        for variant in conditional_variants:
            matched_conditions = self._count_matched_conditions(patient, variant)
            
            if matched_conditions > max_matched_conditions:
                max_matched_conditions = matched_conditions
                best_conditional = variant
            elif matched_conditions == max_matched_conditions and matched_conditions > 0:
                # Tie-breaker: already in deterministic order, first one wins
                # (higher specificity or lower ID from query ordering)
                pass
        
        # If patient has conditions matching a conditional variant, use it
        if best_conditional and max_matched_conditions > 0:
            return best_conditional
        
        # Otherwise, use the most appropriate general variant
        # DETERMINISTIC: Prefer variants over base types, already sorted by specificity/id
        preferred_general = None
        for variant in general_variants:
            if variant.name != base_screening_type.name:  # Prefer variants over base
                preferred_general = variant
                break
        
        return preferred_general or general_variants[0] if general_variants else base_screening_type
    
    def create_screening_variant(self, base_screening_type, variant_name, trigger_conditions, 
                               frequency_value=None, frequency_unit=None):
        """Create a new screening variant"""
        
        variant = ScreeningType(
            name=f"{base_screening_type.name} - {variant_name}",
            description=f"{base_screening_type.description} (Variant: {variant_name})",
            keywords=base_screening_type.keywords,
            min_age=base_screening_type.min_age,
            max_age=base_screening_type.max_age,
            gender=base_screening_type.gender,
            frequency_value=frequency_value or base_screening_type.frequency_value,
            frequency_unit=frequency_unit or base_screening_type.frequency_unit,
            trigger_conditions='\n'.join(trigger_conditions) if isinstance(trigger_conditions, list) else trigger_conditions,
            is_active=True
        )
        
        db.session.add(variant)
        db.session.commit()
        
        self.logger.info(f"Created screening variant: {variant.name}")
        return variant
    
    def get_variant_recommendations(self, screening_type_name):
        """Get common variant recommendations for a screening type"""
        
        variant_recommendations = {
            'A1C': [
                {
                    'name': 'Diabetic',
                    'trigger_conditions': ['diabetes', 'type 1 diabetes', 'type 2 diabetes'],
                    'frequency_value': 3,
                    'frequency_unit': 'months'
                },
                {
                    'name': 'Pre-diabetic',
                    'trigger_conditions': ['prediabetes', 'impaired glucose tolerance'],
                    'frequency_value': 6,
                    'frequency_unit': 'months'
                }
            ],
            'Mammogram': [
                {
                    'name': 'High Risk',
                    'trigger_conditions': ['BRCA', 'family history breast cancer', 'breast cancer history'],
                    'frequency_value': 6,
                    'frequency_unit': 'months'
                }
            ],
            'Colonoscopy': [
                {
                    'name': 'High Risk',
                    'trigger_conditions': ['family history colon cancer', 'inflammatory bowel disease', 'polyps'],
                    'frequency_value': 3,
                    'frequency_unit': 'years'
                }
            ],
            'Echocardiogram': [
                {
                    'name': 'Heart Disease',
                    'trigger_conditions': ['heart failure', 'coronary artery disease', 'cardiomyopathy'],
                    'frequency_value': 6,
                    'frequency_unit': 'months'
                }
            ]
        }
        
        return variant_recommendations.get(screening_type_name, [])
    
    def _count_matched_conditions(self, patient, screening_type):
        """Count how many trigger conditions match patient conditions"""
        if not screening_type.trigger_conditions_list:
            return 0
        
        patient_conditions = [c.condition_name.lower() for c in patient.conditions if c.is_active]
        matched_count = 0
        
        for trigger_condition in screening_type.trigger_conditions_list:
            trigger_condition = trigger_condition.lower().strip()
            
            for patient_condition in patient_conditions:
                if (trigger_condition in patient_condition or 
                    patient_condition in trigger_condition):
                    matched_count += 1
                    break
        
        return matched_count
    
    def apply_variants_to_patient(self, patient_id):
        """Apply appropriate screening variants to a patient"""
        patient = Patient.query.get(patient_id)
        if not patient:
            return
        
        # Get all base screening types
        base_screening_types = ScreeningType.query.filter(
            ~ScreeningType.name.contains(' - '),  # Exclude variants
            ScreeningType.is_active == True
        ).all()
        
        updated_screenings = []
        
        for base_type in base_screening_types:
            applicable_variant = self.get_applicable_variant(patient, base_type)
            
            if applicable_variant.id != base_type.id:
                # Update or create screening with the variant
                from models import Screening
                
                screening = Screening.query.filter_by(
                    patient_id=patient_id,
                    screening_type_id=base_type.id
                ).first()
                
                if screening:
                    screening.screening_type_id = applicable_variant.id
                    updated_screenings.append(applicable_variant.name)
                else:
                    # Create new screening with variant
                    new_screening = Screening(
                        patient_id=patient_id,
                        screening_type_id=applicable_variant.id,
                        org_id=patient.org_id,
                        status='due'
                    )
                    db.session.add(new_screening)
                    updated_screenings.append(applicable_variant.name)
        
        db.session.commit()
        
        self.logger.info(f"Applied variants to patient {patient.full_name}: {', '.join(updated_screenings)}")
        return updated_screenings
