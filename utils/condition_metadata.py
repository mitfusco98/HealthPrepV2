"""
Condition Metadata Parser
Extracts severity, clinical modifiers, and base condition from medical condition strings.
Used for severity-aware screening variant selection.
"""
import re
from typing import Dict, Optional, Tuple
from utils.medical_conditions import medical_conditions_db


class ConditionMetadata:
    """Parses condition strings to extract severity and base condition for matching"""
    
    SEVERITY_RANKS = {
        'very_severe': 4,
        'severe': 3,
        'moderate': 2,
        'mild': 1,
        None: 0  # No severity specified
    }
    
    SEVERITY_PATTERNS = [
        (r'\bvery\s+severe\b', 'very_severe'),
        (r'\bsevere\b', 'severe'),
        (r'\bmoderate\b', 'moderate'),
        (r'\bmild\b', 'mild'),
    ]
    
    @classmethod
    def parse_condition(cls, condition_str: str) -> Dict:
        """Parse a condition string to extract metadata
        
        Returns dict with:
        - severity: 'mild', 'moderate', 'severe', 'very_severe', or None
        - severity_rank: numeric rank (0-4) for comparison
        - base_condition: normalized condition without severity modifiers
        - original: original input string
        
        Examples:
        - "severe persistent asthma" -> {severity: 'severe', severity_rank: 3, base_condition: 'asthma'}
        - "Type 2 diabetes" -> {severity: None, severity_rank: 0, base_condition: 'type 2 diabetes'}
        """
        if not condition_str:
            return {
                'severity': None,
                'severity_rank': 0,
                'base_condition': '',
                'original': ''
            }
        
        severity = cls.extract_severity(condition_str)
        base_condition = medical_conditions_db.normalize_condition_name(condition_str)
        
        return {
            'severity': severity,
            'severity_rank': cls.SEVERITY_RANKS.get(severity, 0),
            'base_condition': base_condition,
            'original': condition_str
        }
    
    @classmethod
    def extract_severity(cls, text: str) -> Optional[str]:
        """Extract severity level from text (condition name, trigger, or screening title)
        
        Returns: 'mild', 'moderate', 'severe', 'very_severe', or None
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        for pattern, severity in cls.SEVERITY_PATTERNS:
            if re.search(pattern, text_lower):
                return severity
        
        return None
    
    @classmethod
    def extract_severity_from_screening_title(cls, title: str) -> Optional[str]:
        """Extract severity from screening title (may be in parentheses or after hyphen)
        
        Examples:
        - "A1C Test (Severe Diabetic Protocol)" -> 'severe'
        - "Asthma Management - Moderate" -> 'moderate'
        - "Lipid Panel" -> None
        """
        return cls.extract_severity(title)
    
    @classmethod
    def severity_matches(cls, patient_severity: Optional[str], trigger_severity: Optional[str]) -> bool:
        """Check if patient severity matches or exceeds trigger requirement
        
        Rules:
        - If trigger has no severity requirement, any patient severity matches
        - If trigger requires specific severity, patient must have that exact severity
        - Exception: 'very_severe' also matches 'severe' triggers
        
        Examples:
        - patient='severe', trigger='severe' -> True
        - patient='moderate', trigger='severe' -> False  
        - patient='severe', trigger=None -> True (no requirement)
        - patient=None, trigger='severe' -> False (patient has no severity info)
        """
        if trigger_severity is None:
            return True
        
        if patient_severity is None:
            return False
        
        if patient_severity == trigger_severity:
            return True
        
        if patient_severity == 'very_severe' and trigger_severity == 'severe':
            return True
            
        return False
    
    @classmethod
    def calculate_variant_specificity(cls, screening_type) -> int:
        """Calculate specificity score for a screening variant
        
        Higher score = more specific variant
        
        Scoring:
        - Base: 0 (general population, no triggers)
        - Condition-triggered: 10 (has trigger conditions)
        - Severity-specific: +5 per severity level (mild=5, moderate=10, severe=15, very_severe=20)
        
        Example scores:
        - "A1C Test" (general) -> 0
        - "A1C Test" (diabetic) -> 10
        - "A1C Test" (moderate diabetic) -> 20
        - "A1C Test" (severe diabetic) -> 25
        """
        score = 0
        
        if not hasattr(screening_type, 'trigger_conditions_list'):
            return score
        
        if screening_type.trigger_conditions_list:
            score += 10
            
            severity = cls.get_variant_severity(screening_type)
            if severity:
                score += cls.SEVERITY_RANKS.get(severity, 0) * 5
        
        return score
    
    @classmethod
    def get_variant_severity(cls, screening_type) -> Optional[str]:
        """Get severity level for a screening variant
        
        Checks in order:
        1. Trigger conditions for severity terms
        2. Screening title for severity terms
        """
        if hasattr(screening_type, 'trigger_conditions_list') and screening_type.trigger_conditions_list:
            for trigger in screening_type.trigger_conditions_list:
                severity = cls.extract_severity(trigger)
                if severity:
                    return severity
        
        if hasattr(screening_type, 'name') and screening_type.name:
            severity = cls.extract_severity_from_screening_title(screening_type.name)
            if severity:
                return severity
        
        return None
    
    @classmethod
    def get_patient_condition_severity(cls, patient, base_condition: str) -> Optional[str]:
        """Get the severity level of a patient's condition that matches the base condition
        
        Searches patient's active conditions for one that fuzzy-matches the base condition,
        then extracts its severity.
        
        Example:
        - Patient has "severe persistent asthma"
        - Base condition query: "asthma"
        - Returns: 'severe'
        """
        if not hasattr(patient, 'conditions'):
            return None
            
        for condition in patient.conditions:
            if not condition.is_active:
                continue
                
            if medical_conditions_db.fuzzy_match_condition(condition.condition_name, base_condition):
                severity = cls.extract_severity(condition.condition_name)
                if severity:
                    return severity
        
        return None


condition_metadata = ConditionMetadata()
