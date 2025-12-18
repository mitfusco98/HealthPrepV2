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
        
        # Check trigger conditions
        if not self._check_trigger_conditions(patient, screening_type):
            return False
        
        # MUTUAL EXCLUSIVITY: If this is a general population screening (no trigger conditions),
        # check if patient qualifies for a condition-triggered variant of the same screening
        if not screening_type.trigger_conditions_list:
            if self._patient_has_condition_specific_variant(patient, screening_type):
                self.logger.debug(
                    f"Mutual exclusivity: Patient excluded from general '{screening_type.name}' "
                    f"because they qualify for a condition-triggered variant"
                )
                return False
        
        return True
    
    def _patient_has_condition_specific_variant(self, patient, general_screening_type):
        """Check if patient qualifies for a condition-triggered variant of this screening
        
        Used for mutual exclusivity - patients should only receive one variant of a screening.
        For example, a diabetic patient should get the diabetes-specific A1C protocol,
        not both the diabetes A1C AND the general population A1C.
        """
        from models import ScreeningType
        
        # Find all other screening types with the same name in this organization
        same_name_variants = ScreeningType.query.filter(
            ScreeningType.org_id == general_screening_type.org_id,
            ScreeningType.name == general_screening_type.name,
            ScreeningType.id != general_screening_type.id,
            ScreeningType.is_active == True
        ).all()
        
        # Check if patient qualifies for any condition-triggered variant
        for variant in same_name_variants:
            # Skip variants that don't have trigger conditions (also general population)
            if not variant.trigger_conditions_list:
                continue
            
            # Check basic eligibility (age, gender) without recursion
            if not self._check_age_eligibility(patient, variant):
                continue
            if not self._check_gender_eligibility(patient, variant):
                continue
            
            # Check if patient has the required trigger conditions
            # Use direct trigger check (not is_patient_eligible to avoid recursion)
            if self._patient_matches_trigger_conditions(patient, variant.trigger_conditions_list):
                self.logger.debug(
                    f"Patient qualifies for condition-triggered variant: {variant.name} "
                    f"(triggers: {variant.trigger_conditions_list})"
                )
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
        """Check if patient has required trigger conditions using enhanced fuzzy matching
        
        Uses medical_conditions_db.fuzzy_match_condition() which:
        - Strips clinical modifiers (mild, moderate, severe, chronic, acute, etc.)
        - Handles medical abbreviations (PCOS, COPD, MI, CAD, etc.)
        - Uses word boundaries to prevent false matches (diabetes ≠ prediabetes)
        - Matches condition variants (Type 2 diabetes = diabetes mellitus type 2 = T2DM)
        
        Examples:
        - "Moderate persistent asthma, uncomplicated" matches trigger "asthma" ✓
        - "Polycystic ovarian syndrome" matches trigger "PCOS" ✓
        - "Old myocardial infarction" matches trigger "heart disease" ✓
        - "diabetes" does NOT match trigger "prediabetes" ✗
        """
        from utils.medical_conditions import medical_conditions_db
        
        # If no trigger conditions defined, screening applies to all patients
        if not screening_type.trigger_conditions_list:
            return True
        
        # Get patient conditions (keep original case for logging)
        patient_conditions = [c.condition_name for c in patient.conditions if c.is_active]
        
        # Check if any trigger condition is met using enhanced fuzzy matching
        for trigger_condition in screening_type.trigger_conditions_list:
            trigger_condition = trigger_condition.strip()
            
            # Check against each patient condition using fuzzy matcher
            for patient_condition in patient_conditions:
                if medical_conditions_db.fuzzy_match_condition(patient_condition, trigger_condition):
                    self.logger.debug(
                        f"Trigger condition match: Patient '{patient_condition}' matches "
                        f"screening trigger '{trigger_condition}' for {screening_type.name}"
                    )
                    return True
        
        # Patient doesn't have required trigger conditions
        self.logger.debug(
            f"No trigger match for {screening_type.name}. Patient has: {patient_conditions}, "
            f"Screening requires: {screening_type.trigger_conditions_list}"
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
