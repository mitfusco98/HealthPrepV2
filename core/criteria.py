"""
Screening eligibility and frequency logic
"""
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

class EligibilityCriteria:
    """Handles screening eligibility and frequency calculations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_patient_eligible(self, patient, screening_type):
        """Check if a patient is eligible for a specific screening type
        
        Implements mutual exclusivity: if a patient qualifies for a condition-triggered
        variant of a screening (e.g., diabetic A1C), they are excluded from the
        general population variant (e.g., general A1C) to prevent duplicate screenings.
        """
        
        # Check age criteria
        if not self._check_age_eligibility(patient, screening_type):
            return False
        
        # Check gender criteria
        if not self._check_gender_eligibility(patient, screening_type):
            return False
        
        # Check trigger conditions (with severity awareness)
        if not self._check_trigger_conditions(patient, screening_type):
            return False
        
        # MUTUAL EXCLUSIVITY: Check if patient qualifies for a MORE SPECIFIC variant
        # This applies to both general AND condition-triggered variants
        # Example: Patient with "severe diabetes" should get severity-specific variant,
        # not the general diabetic variant or the general population variant
        if self._patient_has_more_specific_variant(patient, screening_type):
            self.logger.debug(
                f"Mutual exclusivity: Patient excluded from '{screening_type.name}' "
                f"(specificity: {screening_type.specificity_score}) "
                f"because they qualify for a more specific variant"
            )
            return False
        
        return True
    
    def _patient_has_more_specific_variant(self, patient, current_screening_type):
        """Check if patient qualifies for a more specific variant of this screening
        
        Uses specificity scoring to determine which variant is most appropriate:
        - General (no triggers): specificity 0
        - Condition-triggered: specificity 10
        - Severity-specific (mild): specificity 15
        - Severity-specific (moderate): specificity 20
        - Severity-specific (severe): specificity 25
        - Severity-specific (very_severe): specificity 30
        
        Patients receive only the highest-scoring variant they qualify for.
        """
        from models import ScreeningType
        from utils.condition_metadata import condition_metadata
        
        current_specificity = current_screening_type.specificity_score
        
        # Find all other screening types with the same name in this organization
        # DETERMINISTIC ORDERING: Sort by specificity (desc) then ID for consistent results
        # Note: specificity_score is a computed @property, so we sort in Python, not SQL
        same_name_variants = ScreeningType.query.filter(
            ScreeningType.org_id == current_screening_type.org_id,
            ScreeningType.name == current_screening_type.name,
            ScreeningType.id != current_screening_type.id,
            ScreeningType.is_active == True
        ).all()
        
        # Sort by specificity_score (desc), then id (asc) for deterministic ordering
        same_name_variants.sort(key=lambda v: (-v.specificity_score, v.id))
        
        # Check if patient qualifies for any MORE SPECIFIC variant
        for variant in same_name_variants:
            variant_specificity = variant.specificity_score
            
            # Only consider variants that are MORE specific than current
            if variant_specificity <= current_specificity:
                continue
            
            # Check basic eligibility (age, gender)
            if not self._check_age_eligibility(patient, variant):
                continue
            if not self._check_gender_eligibility(patient, variant):
                continue
            
            # Check if patient matches trigger conditions with severity awareness
            if self._patient_matches_trigger_conditions_with_severity(patient, variant):
                self.logger.debug(
                    f"Patient qualifies for more specific variant: {variant.name} "
                    f"(specificity: {variant_specificity} > {current_specificity})"
                )
                return True
        
        return False
    
    def _patient_matches_trigger_conditions_with_severity(self, patient, screening_variant):
        """Check if patient matches trigger conditions including severity requirements
        
        If trigger has severity modifier (e.g., "severe diabetes"), patient must have
        matching severity. If no severity in trigger, any severity matches.
        """
        from utils.medical_conditions import medical_conditions_db
        from utils.condition_metadata import condition_metadata
        
        trigger_conditions = screening_variant.trigger_conditions_list
        if not trigger_conditions:
            return False
        
        # Get patient conditions
        patient_conditions = [c.condition_name for c in patient.conditions if c.is_active]
        if not patient_conditions:
            return False
        
        variant_severity = screening_variant.variant_severity
        
        for trigger_condition in trigger_conditions:
            trigger_condition = trigger_condition.strip()
            trigger_severity = condition_metadata.extract_severity(trigger_condition)
            
            for patient_condition in patient_conditions:
                # First check base condition match
                if not medical_conditions_db.fuzzy_match_condition(patient_condition, trigger_condition):
                    continue
                
                # Base condition matches - now check severity if variant has severity requirement
                if variant_severity:
                    patient_severity = condition_metadata.extract_severity(patient_condition)
                    
                    # Check if patient severity matches the variant's severity requirement
                    if condition_metadata.severity_matches(patient_severity, variant_severity):
                        return True
                else:
                    # No severity requirement - condition match is sufficient
                    return True
        
        return False
    
    def _patient_matches_trigger_conditions(self, patient, trigger_conditions):
        """Direct check if patient has any of the specified trigger conditions
        
        Unlike _check_trigger_conditions which returns True for empty triggers,
        this method requires at least one trigger match.
        """
        from utils.medical_conditions import medical_conditions_db
        
        if not trigger_conditions:
            return False
        
        # Get patient conditions
        patient_conditions = [c.condition_name for c in patient.conditions if c.is_active]
        
        if not patient_conditions:
            return False
        
        # Check if any trigger condition matches patient conditions
        for trigger_condition in trigger_conditions:
            trigger_condition = trigger_condition.strip()
            for patient_condition in patient_conditions:
                if medical_conditions_db.fuzzy_match_condition(patient_condition, trigger_condition):
                    return True
        
        return False
    
    def calculate_screening_status(self, screening_type, last_completed_date):
        """Calculate screening status based on frequency and last completion date"""
        if not last_completed_date:
            return 'due'
        
        if not screening_type.frequency_value or not screening_type.frequency_unit:
            return 'complete'  # No frequency defined, assume complete
        
        # Calculate next due date
        next_due_date = self._calculate_next_due_date(
            last_completed_date, 
            screening_type.frequency_value, 
            screening_type.frequency_unit
        )
        
        today = date.today()
        
        # Calculate due soon threshold (30 days before due date)
        due_soon_threshold = next_due_date - timedelta(days=30)
        
        if today >= next_due_date:
            return 'due'
        elif today >= due_soon_threshold:
            return 'due_soon'
        else:
            return 'complete'
    
    def _check_age_eligibility(self, patient, screening_type):
        """Check if patient age meets screening criteria"""
        if not screening_type.min_age and not screening_type.max_age:
            return True
        
        patient_age = patient.age
        
        if screening_type.min_age and patient_age < screening_type.min_age:
            return False
        
        if screening_type.max_age and patient_age > screening_type.max_age:
            return False
        
        return True
    
    def _check_gender_eligibility(self, patient, screening_type):
        """Check if patient gender meets screening criteria
        
        Handles both FHIR format ('female', 'male') and normalized format ('F', 'M')
        """
        if not screening_type.eligible_genders or screening_type.eligible_genders == 'both':
            return True
        
        # Normalize patient gender to single letter format
        patient_gender = self._normalize_gender(patient.gender)
        screening_gender = screening_type.eligible_genders
        
        return patient_gender == screening_gender
    
    def _normalize_gender(self, gender):
        """Normalize gender to single letter format (F/M)
        
        Handles various input formats:
        - 'female', 'Female', 'FEMALE' -> 'F'
        - 'male', 'Male', 'MALE' -> 'M'
        - 'F', 'M' -> unchanged
        - None, 'unknown', 'other' -> None
        """
        if not gender:
            return None
        
        gender_lower = gender.lower().strip()
        
        if gender_lower in ('f', 'female'):
            return 'F'
        elif gender_lower in ('m', 'male'):
            return 'M'
        else:
            return None
    
    def _check_trigger_conditions(self, patient, screening_type):
        """Check if patient has required trigger conditions using severity-aware fuzzy matching
        
        Uses medical_conditions_db.fuzzy_match_condition() for base condition matching:
        - Strips clinical modifiers (mild, moderate, severe, chronic, acute, etc.)
        - Handles medical abbreviations (PCOS, COPD, MI, CAD, etc.)
        - Uses word boundaries to prevent false matches (diabetes ≠ prediabetes)
        - Matches condition variants (Type 2 diabetes = diabetes mellitus type 2 = T2DM)
        
        SEVERITY-AWARE: If screening variant has severity requirement (e.g., "severe asthma"),
        patient must have matching severity to qualify. This prevents patients with
        "moderate asthma" from matching a "severe asthma" protocol.
        
        Examples:
        - "Moderate persistent asthma" matches trigger "asthma" ✓ (no severity requirement)
        - "Moderate persistent asthma" does NOT match "severe asthma" ✗ (severity mismatch)
        - "Severe persistent asthma" matches "severe asthma" ✓
        """
        from utils.medical_conditions import medical_conditions_db
        from utils.condition_metadata import condition_metadata
        
        # If no trigger conditions defined, screening applies to all patients
        if not screening_type.trigger_conditions_list:
            return True
        
        # Get patient conditions (keep original case for logging)
        patient_conditions = [c.condition_name for c in patient.conditions if c.is_active]
        
        # Get variant's severity requirement (if any)
        variant_severity = screening_type.variant_severity
        
        # Check if any trigger condition is met using enhanced fuzzy matching
        for trigger_condition in screening_type.trigger_conditions_list:
            trigger_condition = trigger_condition.strip()
            
            # Check against each patient condition using fuzzy matcher
            for patient_condition in patient_conditions:
                if not medical_conditions_db.fuzzy_match_condition(patient_condition, trigger_condition):
                    continue
                
                # Base condition matches - now check severity if variant has severity requirement
                if variant_severity:
                    patient_severity = condition_metadata.extract_severity(patient_condition)
                    
                    # Patient must have matching severity for severity-specific variants
                    if not condition_metadata.severity_matches(patient_severity, variant_severity):
                        self.logger.debug(
                            f"Severity mismatch: Patient '{patient_condition}' (severity: {patient_severity}) "
                            f"does not match variant severity requirement '{variant_severity}' for {screening_type.name}"
                        )
                        continue
                
                # Match found (base condition + severity if required)
                self.logger.debug(
                    f"Trigger condition match: Patient '{patient_condition}' matches "
                    f"screening trigger '{trigger_condition}' for {screening_type.name}"
                    f"{f' (severity: {variant_severity})' if variant_severity else ''}"
                )
                return True
        
        # Patient doesn't have required trigger conditions (or severity mismatch)
        self.logger.debug(
            f"No trigger match for {screening_type.name}. Patient has: {patient_conditions}, "
            f"Screening requires: {screening_type.trigger_conditions_list}"
            f"{f' with severity: {variant_severity}' if variant_severity else ''}"
        )
        return False
    
    def _calculate_next_due_date(self, last_completed_date, frequency_value, frequency_unit):
        """Calculate the next due date based on frequency with proper fractional handling"""
        if not frequency_value or not last_completed_date:
            return None
        
        try:
            # Sanitize frequency_value for relativedelta compatibility
            if frequency_unit == 'years':
                if isinstance(frequency_value, float) and frequency_value != int(frequency_value):
                    # Convert fractional years to integer months
                    months = round(frequency_value * 12)
                    return last_completed_date + relativedelta(months=months)
                else:
                    return last_completed_date + relativedelta(years=int(frequency_value))
            elif frequency_unit == 'months':
                # Convert to integer months
                months = int(round(frequency_value))
                return last_completed_date + relativedelta(months=months)
            else:
                # Default to years, convert fractional to months if needed
                if isinstance(frequency_value, float) and frequency_value != int(frequency_value):
                    months = round(frequency_value * 12)
                    return last_completed_date + relativedelta(months=months)
                else:
                    return last_completed_date + relativedelta(years=int(frequency_value))
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error calculating next due date: {e}. Using default 1 year interval.")
            return last_completed_date + relativedelta(years=1)
    
    def get_screening_schedule(self, patient, screening_type):
        """Get recommended screening schedule for a patient"""
        if not self.is_patient_eligible(patient, screening_type):
            return None
        
        schedule = {
            'screening_type': screening_type.name,
            'frequency': screening_type.frequency_display,
            'eligible': True,
            'eligibility_reasons': []
        }
        
        # Add eligibility details
        if screening_type.min_age or screening_type.max_age:
            age_range = f"Ages {screening_type.min_age or 'any'}-{screening_type.max_age or 'any'}"
            schedule['eligibility_reasons'].append(age_range)
        
        if screening_type.gender:
            gender_text = 'Male' if screening_type.gender == 'M' else 'Female'
            schedule['eligibility_reasons'].append(f"{gender_text} only")
        
        if screening_type.trigger_conditions_list:
            schedule['eligibility_reasons'].append(f"Requires: {', '.join(screening_type.trigger_conditions_list)}")
        
        return schedule
    
    def get_overdue_screenings(self, patient_id, days_overdue=30):
        """Get screenings that are overdue by specified number of days"""
        from models import Screening, ScreeningType
        
        overdue_screenings = []
        screenings = Screening.query.filter_by(patient_id=patient_id).join(ScreeningType).all()
        
        cutoff_date = date.today() - timedelta(days=days_overdue)
        
        for screening in screenings:
            if screening.status == 'due' and screening.last_completed_date:
                next_due = self._calculate_next_due_date(
                    screening.last_completed_date,
                    screening.screening_type.frequency_value,
                    screening.screening_type.frequency_unit
                )
                
                if next_due <= cutoff_date:
                    overdue_screenings.append({
                        'screening': screening,
                        'days_overdue': (date.today() - next_due).days
                    })
        
        return sorted(overdue_screenings, key=lambda x: x['days_overdue'], reverse=True)
