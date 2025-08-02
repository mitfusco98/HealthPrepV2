"""
Fuzzy keyword matching and document matching logic
"""

import re
import logging
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher
from models import MedicalDocument, ScreeningType

logger = logging.getLogger(__name__)

class FuzzyMatcher:
    """Handles fuzzy keyword matching and document classification"""
    
    def __init__(self):
        # Common medical terminology mappings for fuzzy matching
        self.fuzzy_mappings = {
            'mammogram': ['mammo', 'mammography', 'breast imaging'],
            'colonoscopy': ['colon', 'colonoscopic', 'endoscopy'],
            'dexa': ['dxa', 'bone density', 'densitometry'],
            'pap': ['pap smear', 'cervical', 'cytology'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'cholesterol': ['lipid', 'lipid panel', 'cholesterol panel'],
            'bp': ['blood pressure', 'hypertension check'],
            'eye': ['ophthalmology', 'optometry', 'vision'],
            'ekg': ['ecg', 'electrocardiogram', 'cardiac'],
            'chest xray': ['cxr', 'chest x-ray', 'chest radiograph']
        }
        
        # Medical conditions for trigger matching
        self.condition_mappings = {
            'diabetes': ['diabetes mellitus', 'dm', 'diabetic', 'type 1 diabetes', 'type 2 diabetes'],
            'hypertension': ['high blood pressure', 'htn', 'elevated bp'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'elevated cholesterol'],
            'osteoporosis': ['bone loss', 'low bone density'],
            'copd': ['chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis']
        }
    
    def find_matching_documents(self, documents: List[MedicalDocument], 
                              screening_type: ScreeningType, 
                              variant: Dict[str, Any]) -> List[MedicalDocument]:
        """
        Find documents that match the screening type keywords
        """
        if not documents or not screening_type.keywords_list:
            return []
        
        matched_docs = []
        keywords = screening_type.keywords_list
        
        # Add variant-specific keywords if any
        if variant.get('additional_keywords'):
            keywords.extend(variant['additional_keywords'])
        
        for document in documents:
            if self._document_matches_keywords(document, keywords):
                matched_docs.append(document)
        
        logger.debug(f"Found {len(matched_docs)} matching documents for {screening_type.name}")
        return matched_docs
    
    def _document_matches_keywords(self, document: MedicalDocument, keywords: List[str]) -> bool:
        """
        Check if document matches any of the keywords using fuzzy matching
        """
        # Search in filename
        filename_text = document.filename.lower()
        
        # Search in OCR text if available
        ocr_text = ""
        if document.ocr_text:
            ocr_text = document.ocr_text.lower()
        
        # Combine text sources
        search_text = f"{filename_text} {ocr_text}"
        
        for keyword in keywords:
            if self._fuzzy_keyword_match(search_text, keyword.lower()):
                return True
        
        return False
    
    def _fuzzy_keyword_match(self, text: str, keyword: str) -> bool:
        """
        Perform fuzzy matching for a keyword in text
        """
        # Direct match
        if keyword in text:
            return True
        
        # Check fuzzy mappings
        for main_term, variants in self.fuzzy_mappings.items():
            if keyword == main_term or keyword in variants:
                # Check if any variant appears in text
                for variant in [main_term] + variants:
                    if variant in text:
                        return True
        
        # Word boundary matching with partial matches
        keyword_words = keyword.split()
        if len(keyword_words) > 1:
            # Multi-word keywords - check if all words appear
            all_words_found = True
            for word in keyword_words:
                if not self._word_appears_fuzzy(text, word):
                    all_words_found = False
                    break
            if all_words_found:
                return True
        else:
            # Single word - use fuzzy string matching
            return self._word_appears_fuzzy(text, keyword)
        
        return False
    
    def _word_appears_fuzzy(self, text: str, word: str) -> bool:
        """
        Check if a word appears in text with fuzzy matching
        """
        # Direct word boundary match
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
        
        # Fuzzy matching for typos and variations
        words_in_text = re.findall(r'\b\w+\b', text)
        for text_word in words_in_text:
            # Skip very short words for fuzzy matching
            if len(word) < 3 or len(text_word) < 3:
                continue
            
            # Calculate similarity
            similarity = SequenceMatcher(None, word, text_word).ratio()
            if similarity >= 0.8:  # 80% similarity threshold
                return True
        
        return False
    
    def match_condition_to_standard(self, condition_name: str) -> List[str]:
        """
        Match a condition name to standardized condition terms
        """
        condition_lower = condition_name.lower()
        matched_conditions = []
        
        for standard_condition, variants in self.condition_mappings.items():
            if condition_lower == standard_condition:
                matched_conditions.append(standard_condition)
            else:
                for variant in variants:
                    if variant in condition_lower or condition_lower in variant:
                        matched_conditions.append(standard_condition)
                        break
        
        return matched_conditions
    
    def suggest_keywords(self, partial_keyword: str) -> List[str]:
        """
        Suggest keywords based on partial input for UI assistance
        """
        suggestions = []
        partial_lower = partial_keyword.lower()
        
        # Check main terms
        for main_term in self.fuzzy_mappings.keys():
            if partial_lower in main_term:
                suggestions.append(main_term)
        
        # Check variants
        for main_term, variants in self.fuzzy_mappings.items():
            for variant in variants:
                if partial_lower in variant and variant not in suggestions:
                    suggestions.append(variant)
        
        return sorted(suggestions)[:10]  # Return top 10 suggestions
    
    def validate_keywords(self, keywords: List[str]) -> Dict[str, Any]:
        """
        Validate and suggest improvements for keywords
        """
        results = {
            'valid_keywords': [],
            'suggestions': {},
            'warnings': []
        }
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Check if keyword is recognized
            recognized = False
            for main_term, variants in self.fuzzy_mappings.items():
                if keyword_lower == main_term or keyword_lower in variants:
                    recognized = True
                    results['valid_keywords'].append(keyword)
                    break
            
            if not recognized:
                # Suggest similar keywords
                suggestions = self.suggest_keywords(keyword)
                if suggestions:
                    results['suggestions'][keyword] = suggestions
                else:
                    results['warnings'].append(f"Keyword '{keyword}' not recognized in medical terminology")
        
        return results
