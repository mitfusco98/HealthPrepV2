"""
Fuzzy matching utilities for Health-Prep system.
Handles medical terminology matching and text normalization.
"""

import re
from difflib import SequenceMatcher
from typing import List, Set, Tuple, Dict
import unicodedata
import logging

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    """Normalize text for consistent matching"""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove accents and normalize unicode
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    
    # Replace common medical abbreviations and variations
    medical_replacements = {
        r'\ba1c\b': 'hemoglobin a1c',
        r'\bhba1c\b': 'hemoglobin a1c',
        r'\btsh\b': 'thyroid stimulating hormone',
        r'\bldl\b': 'low density lipoprotein',
        r'\bhdl\b': 'high density lipoprotein',
        r'\bbp\b': 'blood pressure',
        r'\bhr\b': 'heart rate',
        r'\bbmi\b': 'body mass index',
        r'\becg\b': 'electrocardiogram',
        r'\bekg\b': 'electrocardiogram',
        r'\bmri\b': 'magnetic resonance imaging',
        r'\bct\b': 'computed tomography',
        r'\bdexa\b': 'dual energy x-ray absorptiometry',
        r'\bdxa\b': 'dual energy x-ray absorptiometry',
        r'\bpap\b': 'papanicolaou',
        r'\bpsa\b': 'prostate specific antigen',
        r'\bcopd\b': 'chronic obstructive pulmonary disease',
        r'\bckd\b': 'chronic kidney disease',
        r'\bdm\b': 'diabetes mellitus',
        r'\bhtn\b': 'hypertension',
        r'\bmi\b': 'myocardial infarction',
        r'\bcad\b': 'coronary artery disease'
    }
    
    for pattern, replacement in medical_replacements.items():
        text = re.sub(pattern, replacement, text)
    
    # Remove extra whitespace and special characters
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def get_similarity_score(text1: str, text2: str) -> float:
    """Calculate similarity score between two text strings"""
    if not text1 or not text2:
        return 0.0
    
    # Normalize both texts
    norm_text1 = normalize_text(text1)
    norm_text2 = normalize_text(text2)
    
    # Use SequenceMatcher for basic similarity
    basic_similarity = SequenceMatcher(None, norm_text1, norm_text2).ratio()
    
    # Boost score for exact substring matches
    substring_boost = 0.0
    if norm_text1 in norm_text2 or norm_text2 in norm_text1:
        substring_boost = 0.2
    
    # Boost score for word-level matches
    words1 = set(norm_text1.split())
    words2 = set(norm_text2.split())
    
    if words1 and words2:
        word_similarity = len(words1.intersection(words2)) / len(words1.union(words2))
        word_boost = word_similarity * 0.3
    else:
        word_boost = 0.0
    
    # Calculate final score
    final_score = basic_similarity + substring_boost + word_boost
    return min(1.0, final_score)

def extract_medical_terms(text: str) -> List[str]:
    """Extract medical terms from text"""
    if not text:
        return []
    
    normalized_text = normalize_text(text)
    
    # Medical term patterns
    medical_patterns = [
        r'\b\w*(?:ology|ography|ectomy|otomy|oscopy|itis|osis|emia|uria)\b',  # Medical suffixes
        r'\b(?:pre|post|anti|pro|meta|hyper|hypo|inter|intra|extra)\w+\b',   # Medical prefixes
        r'\b\d+\s*(?:mg|mcg|ml|kg|lb|cm|mm|inch|year|month|day)s?\b',        # Measurements
        r'\b\d+/\d+\s*mmhg\b',                                                # Blood pressure
        r'\b\d+\.\d+\s*(?:mg/dl|g/dl|mmol/l)\b',                            # Lab values
        r'\b(?:type\s+[12]|stage\s+[iv]+)\b',                                # Disease stages
    ]
    
    # Common medical terms
    medical_keywords = {
        'anatomy': ['heart', 'lung', 'liver', 'kidney', 'brain', 'stomach', 'intestine', 'bone', 'muscle', 'skin'],
        'procedures': ['surgery', 'biopsy', 'endoscopy', 'ultrasound', 'mammography', 'colonoscopy', 'bronchoscopy'],
        'tests': ['laboratory', 'radiology', 'pathology', 'culture', 'assay', 'screening'],
        'conditions': ['diabetes', 'hypertension', 'cancer', 'infection', 'inflammation', 'disease', 'syndrome'],
        'medications': ['antibiotic', 'analgesic', 'insulin', 'beta blocker', 'ace inhibitor', 'statin'],
        'specialties': ['cardiology', 'neurology', 'oncology', 'gastroenterology', 'pulmonology', 'nephrology']
    }
    
    terms = []
    
    # Extract terms using patterns
    for pattern in medical_patterns:
        matches = re.findall(pattern, normalized_text, re.IGNORECASE)
        terms.extend(matches)
    
    # Extract known medical keywords
    words = normalized_text.split()
    for word in words:
        for category, keywords in medical_keywords.items():
            for keyword in keywords:
                if get_similarity_score(word, keyword) > 0.8:
                    terms.append(word)
                    break
    
    # Remove duplicates and sort by length (longer terms first)
    unique_terms = list(set(terms))
    unique_terms.sort(key=len, reverse=True)
    
    return unique_terms

def find_best_matches(query: str, candidates: List[str], threshold: float = 0.7, max_results: int = 5) -> List[Tuple[str, float]]:
    """Find best fuzzy matches for a query string"""
    if not query or not candidates:
        return []
    
    matches = []
    
    for candidate in candidates:
        score = get_similarity_score(query, candidate)
        if score >= threshold:
            matches.append((candidate, score))
    
    # Sort by score (highest first) and limit results
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:max_results]

def expand_medical_synonyms(term: str) -> List[str]:
    """Expand a medical term with its known synonyms"""
    synonym_map = {
        'mammogram': ['mammography', 'breast imaging', 'breast screening'],
        'colonoscopy': ['colon screening', 'colorectal screening', 'endoscopy'],
        'pap smear': ['papanicolaou', 'cervical screening', 'cytology'],
        'dexa scan': ['bone density', 'dxa', 'densitometry', 'osteoporosis screening'],
        'a1c': ['hemoglobin a1c', 'hba1c', 'glycated hemoglobin'],
        'cholesterol': ['lipid panel', 'lipid profile', 'lipids'],
        'blood pressure': ['bp', 'hypertension screening'],
        'diabetes screening': ['glucose test', 'blood sugar', 'diabetic screening'],
        'eye exam': ['ophthalmology', 'vision screening', 'retinal exam'],
        'thyroid': ['tsh', 'thyroid function', 'thyroid screening'],
        'prostate': ['psa', 'prostate screening', 'prostate specific antigen'],
        'skin cancer': ['dermatology', 'skin screening', 'melanoma screening'],
        'depression': ['mental health', 'phq', 'mood screening'],
        'immunization': ['vaccination', 'vaccine', 'shots'],
        'physical exam': ['annual exam', 'wellness visit', 'checkup']
    }
    
    normalized_term = normalize_text(term)
    synonyms = [term]  # Include original term
    
    # Direct lookup
    if normalized_term in synonym_map:
        synonyms.extend(synonym_map[normalized_term])
    
    # Reverse lookup
    for key, values in synonym_map.items():
        if normalized_term in [normalize_text(v) for v in values]:
            synonyms.append(key)
            synonyms.extend(values)
    
    # Fuzzy lookup for close matches
    for key, values in synonym_map.items():
        if get_similarity_score(normalized_term, key) > 0.8:
            synonyms.append(key)
            synonyms.extend(values)
    
    # Remove duplicates while preserving order
    unique_synonyms = []
    seen = set()
    for synonym in synonyms:
        normalized_synonym = normalize_text(synonym)
        if normalized_synonym not in seen:
            unique_synonyms.append(synonym)
            seen.add(normalized_synonym)
    
    return unique_synonyms

def match_medical_condition(condition: str, known_conditions: List[str]) -> Tuple[str, float]:
    """Match a medical condition against known conditions"""
    if not condition or not known_conditions:
        return None, 0.0
    
    # Expand condition with synonyms
    expanded_conditions = expand_medical_synonyms(condition)
    
    best_match = None
    best_score = 0.0
    
    for expanded_condition in expanded_conditions:
        for known_condition in known_conditions:
            score = get_similarity_score(expanded_condition, known_condition)
            if score > best_score:
                best_score = score
                best_match = known_condition
    
    return best_match, best_score

def normalize_medical_value(value: str) -> str:
    """Normalize medical values and units"""
    if not value:
        return ""
    
    # Common unit normalizations
    unit_normalizations = {
        r'mg/dl': 'mg/dL',
        r'g/dl': 'g/dL',
        r'mmol/l': 'mmol/L',
        r'mg/l': 'mg/L',
        r'ng/ml': 'ng/mL',
        r'iu/l': 'IU/L',
        r'u/l': 'U/L',
        r'mmhg': 'mmHg',
        r'bpm': 'BPM',
        r'celsius': '°C',
        r'fahrenheit': '°F'
    }
    
    normalized = value.lower()
    
    for pattern, replacement in unit_normalizations.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    
    # Standardize spacing around units
    normalized = re.sub(r'(\d)\s*([a-zA-Z/%°]+)', r'\1 \2', normalized)
    
    return normalized.strip()

class MedicalTermMatcher:
    """Advanced medical term matching with context awareness"""
    
    def __init__(self):
        self.term_categories = {
            'procedures': self._load_procedure_terms(),
            'conditions': self._load_condition_terms(),
            'medications': self._load_medication_terms(),
            'anatomy': self._load_anatomy_terms(),
            'lab_tests': self._load_lab_test_terms()
        }
    
    def _load_procedure_terms(self) -> Set[str]:
        """Load medical procedure terms"""
        return {
            'mammogram', 'mammography', 'breast imaging',
            'colonoscopy', 'endoscopy', 'sigmoidoscopy',
            'pap smear', 'papanicolaou', 'cervical screening',
            'dexa', 'dxa', 'bone density', 'densitometry',
            'ultrasound', 'sonography', 'echocardiogram',
            'ct scan', 'computed tomography', 'cat scan',
            'mri', 'magnetic resonance imaging',
            'x-ray', 'radiography', 'chest x-ray',
            'biopsy', 'needle biopsy', 'core biopsy',
            'surgery', 'surgical procedure', 'operation'
        }
    
    def _load_condition_terms(self) -> Set[str]:
        """Load medical condition terms"""
        return {
            'diabetes', 'diabetes mellitus', 'diabetic',
            'hypertension', 'high blood pressure', 'htn',
            'hyperlipidemia', 'high cholesterol', 'dyslipidemia',
            'obesity', 'overweight', 'weight management',
            'osteoporosis', 'osteopenia', 'bone loss',
            'depression', 'major depressive disorder', 'mood disorder',
            'anxiety', 'anxiety disorder', 'panic disorder',
            'copd', 'chronic obstructive pulmonary disease',
            'asthma', 'bronchial asthma', 'allergic asthma',
            'cancer', 'malignancy', 'carcinoma', 'tumor'
        }
    
    def _load_medication_terms(self) -> Set[str]:
        """Load medication terms"""
        return {
            'insulin', 'metformin', 'glipizide', 'glyburide',
            'lisinopril', 'enalapril', 'losartan', 'valsartan',
            'atorvastatin', 'simvastatin', 'rosuvastatin',
            'aspirin', 'clopidogrel', 'warfarin', 'apixaban',
            'levothyroxine', 'synthroid', 'thyroid hormone',
            'omeprazole', 'pantoprazole', 'ranitidine',
            'albuterol', 'inhaler', 'bronchodilator'
        }
    
    def _load_anatomy_terms(self) -> Set[str]:
        """Load anatomical terms"""
        return {
            'heart', 'cardiac', 'cardiovascular', 'coronary',
            'lung', 'pulmonary', 'respiratory', 'bronchial',
            'liver', 'hepatic', 'hepato', 'bile',
            'kidney', 'renal', 'nephro', 'urinary',
            'brain', 'cerebral', 'neurological', 'cranial',
            'bone', 'skeletal', 'orthopedic', 'joint',
            'skin', 'dermatologic', 'cutaneous', 'epidermal',
            'eye', 'ocular', 'ophthalmic', 'visual',
            'breast', 'mammary', 'chest', 'thoracic'
        }
    
    def _load_lab_test_terms(self) -> Set[str]:
        """Load laboratory test terms"""
        return {
            'complete blood count', 'cbc', 'hemoglobin', 'hematocrit',
            'comprehensive metabolic panel', 'cmp', 'basic metabolic panel', 'bmp',
            'lipid panel', 'cholesterol', 'triglycerides', 'ldl', 'hdl',
            'thyroid function', 'tsh', 'free t4', 'thyroid',
            'hemoglobin a1c', 'a1c', 'hba1c', 'glucose',
            'liver function', 'alt', 'ast', 'bilirubin',
            'kidney function', 'creatinine', 'bun', 'egfr',
            'urinalysis', 'urine test', 'protein', 'microalbumin',
            'prostate specific antigen', 'psa', 'tumor marker',
            'vitamin d', 'vitamin b12', 'folate', 'iron'
        }
    
    def categorize_term(self, term: str) -> List[str]:
        """Categorize a medical term"""
        normalized_term = normalize_text(term)
        categories = []
        
        for category, terms in self.term_categories.items():
            for known_term in terms:
                if get_similarity_score(normalized_term, known_term) > 0.8:
                    categories.append(category)
                    break
        
        return categories
    
    def find_related_terms(self, term: str, category: str = None) -> List[str]:
        """Find related medical terms"""
        related_terms = []
        normalized_term = normalize_text(term)
        
        # Search specific category or all categories
        categories_to_search = [category] if category else self.term_categories.keys()
        
        for cat in categories_to_search:
            if cat in self.term_categories:
                for known_term in self.term_categories[cat]:
                    score = get_similarity_score(normalized_term, known_term)
                    if 0.6 <= score < 0.95:  # Related but not identical
                        related_terms.append(known_term)
        
        return related_terms[:10]  # Limit to top 10 related terms

# Global instance for reuse
medical_matcher = MedicalTermMatcher()
