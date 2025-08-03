"""
Fuzzy keyword and document matching functionality
Handles keyword matching between documents and screening types
"""

import re
import logging
from typing import List, Dict, Set
from difflib import SequenceMatcher
from models import MedicalDocument, ScreeningType

logger = logging.getLogger(__name__)

class FuzzyMatcher:
    """Handles fuzzy keyword matching for screening types and documents"""
    
    # Common medical term variations and standardizations
    MEDICAL_TERM_VARIANTS = {
        'dxa': ['dexa', 'dxa', 'bone density', 'bone scan'],
        'mammogram': ['mammography', 'mammo', 'breast imaging'],
        'colonoscopy': ['colon', 'colonoscopy', 'lower endoscopy'],
        'pap': ['pap smear', 'cervical screening', 'pap test'],
        'a1c': ['hemoglobin a1c', 'hba1c', 'glycated hemoglobin'],
        'lipid': ['cholesterol', 'lipid panel', 'lipid profile'],
        'cbc': ['complete blood count', 'full blood count'],
        'bmp': ['basic metabolic panel', 'chem 7'],
        'cmp': ['comprehensive metabolic panel', 'chem 14'],
        'tsh': ['thyroid stimulating hormone', 'thyroid function'],
        'psa': ['prostate specific antigen', 'prostate screening'],
        'echo': ['echocardiogram', 'cardiac echo', 'heart ultrasound'],
        'ekg': ['electrocardiogram', 'ecg', 'heart rhythm'],
        'stress': ['stress test', 'cardiac stress', 'exercise test']
    }
    
    # Common condition variations for trigger matching
    CONDITION_VARIANTS = {
        'diabetes': ['diabetes mellitus', 'dm', 'diabetic', 'type 1 diabetes', 'type 2 diabetes'],
        'hypertension': ['high blood pressure', 'htn', 'elevated bp'],
        'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'elevated lipids'],
        'obesity': ['overweight', 'elevated bmi', 'weight management'],
        'heart disease': ['coronary artery disease', 'cad', 'cardiac disease', 'heart condition'],
        'copd': ['chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis'],
        'depression': ['major depression', 'depressive disorder', 'mood disorder'],
        'anxiety': ['anxiety disorder', 'generalized anxiety', 'panic disorder']
    }
    
    def __init__(self):
        self.similarity_threshold = 0.8
        self.partial_match_threshold = 0.6
    
    def matches_screening(self, document: MedicalDocument, screening_type: ScreeningType) -> bool:
        """
        Check if a document matches a screening type based on keywords
        """
        if not screening_type.keywords:
            return False
        
        # Combine document text sources
        text_sources = []
        if document.filename:
            text_sources.append(document.filename.lower())
        if document.ocr_text:
            text_sources.append(document.ocr_text.lower())
        if document.phi_filtered_text:
            text_sources.append(document.phi_filtered_text.lower())
        if document.content:
            text_sources.append(document.content.lower())
        
        combined_text = ' '.join(text_sources)
        
        # Check each keyword for matches
        for keyword in screening_type.keywords:
            if self._keyword_matches_text(keyword.lower(), combined_text):
                return True
        
        return False
    
    def _keyword_matches_text(self, keyword: str, text: str) -> bool:
        """Check if a keyword matches text using fuzzy matching"""
        
        # Direct substring match
        if keyword in text:
            return True
        
        # Check medical term variants
        standardized_variants = self._get_medical_variants(keyword)
        for variant in standardized_variants:
            if variant in text:
                return True
        
        # Fuzzy matching for individual words
        keyword_words = keyword.split()
        text_words = text.split()
        
        matched_words = 0
        for kw_word in keyword_words:
            if self._word_matches_in_text(kw_word, text_words):
                matched_words += 1
        
        # Consider it a match if most words match
        return matched_words >= len(keyword_words) * 0.7
    
    def _word_matches_in_text(self, word: str, text_words: List[str]) -> bool:
        """Check if a word matches any word in text using fuzzy similarity"""
        for text_word in text_words:
            if len(word) > 3 and len(text_word) > 3:
                similarity = SequenceMatcher(None, word, text_word).ratio()
                if similarity >= self.similarity_threshold:
                    return True
            elif word == text_word:
                return True
        return False
    
    def _get_medical_variants(self, term: str) -> List[str]:
        """Get medical term variants for a given term"""
        variants = []
        
        # Check if term is a key in our variants dictionary
        if term in self.MEDICAL_TERM_VARIANTS:
            variants.extend(self.MEDICAL_TERM_VARIANTS[term])
        
        # Check if term appears as a variant of any key
        for key, variant_list in self.MEDICAL_TERM_VARIANTS.items():
            if term in variant_list and key not in variants:
                variants.append(key)
                variants.extend([v for v in variant_list if v != term])
        
        return variants
    
    def standardize_screening_name(self, name: str) -> str:
        """Standardize screening name to avoid duplicates"""
        name_lower = name.lower().strip()
        
        # Check for standard medical terms
        for standard_term, variants in self.MEDICAL_TERM_VARIANTS.items():
            if name_lower in variants or name_lower == standard_term:
                return standard_term.title()
        
        return name.title()
    
    def find_condition_matches(self, patient_conditions: List[str], trigger_conditions: List[str]) -> bool:
        """Check if patient conditions match any trigger conditions"""
        if not trigger_conditions:
            return True  # No specific conditions required
        
        patient_conditions_lower = [cond.lower() for cond in patient_conditions]
        
        for trigger in trigger_conditions:
            trigger_lower = trigger.lower()
            
            # Direct match
            if trigger_lower in patient_conditions_lower:
                return True
            
            # Check condition variants
            condition_variants = self._get_condition_variants(trigger_lower)
            for variant in condition_variants:
                if any(variant in patient_cond for patient_cond in patient_conditions_lower):
                    return True
        
        return False
    
    def _get_condition_variants(self, condition: str) -> List[str]:
        """Get condition variants for matching"""
        variants = []
        
        # Check if condition is a key in our variants dictionary
        if condition in self.CONDITION_VARIANTS:
            variants.extend(self.CONDITION_VARIANTS[condition])
        
        # Check if condition appears as a variant of any key
        for key, variant_list in self.CONDITION_VARIANTS.items():
            if condition in variant_list and key not in variants:
                variants.append(key)
                variants.extend([v for v in variant_list if v != condition])
        
        return variants
    
    def suggest_keywords(self, partial_keyword: str, limit: int = 10) -> List[str]:
        """Suggest keywords based on partial input"""
        suggestions = []
        partial_lower = partial_keyword.lower()
        
        # Get suggestions from medical terms
        all_terms = set()
        for term, variants in self.MEDICAL_TERM_VARIANTS.items():
            all_terms.add(term)
            all_terms.update(variants)
        
        for term in all_terms:
            if partial_lower in term or term.startswith(partial_lower):
                suggestions.append(term.title())
        
        return sorted(suggestions)[:limit]
    
    def suggest_conditions(self, partial_condition: str, limit: int = 10) -> List[str]:
        """Suggest medical conditions based on partial input"""
        suggestions = []
        partial_lower = partial_condition.lower()
        
        # Get suggestions from condition variants
        all_conditions = set()
        for condition, variants in self.CONDITION_VARIANTS.items():
            all_conditions.add(condition)
            all_conditions.update(variants)
        
        for condition in all_conditions:
            if partial_lower in condition or condition.startswith(partial_lower):
                suggestions.append(condition.title())
        
        return sorted(suggestions)[:limit]
