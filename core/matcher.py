"""
Fuzzy keyword matching and document matching logic
"""
import re
from difflib import SequenceMatcher
import logging

class FuzzyMatcher:
    def __init__(self):
        # Common medical term variations for fuzzy matching
        self.medical_variants = {
            'dexa': ['dxa', 'dexa', 'bone density', 'bone scan'],
            'mammogram': ['mammo', 'mammography', 'breast imaging'],
            'colonoscopy': ['colon', 'colonoscopy', 'colon screening'],
            'pap': ['pap smear', 'cervical screening', 'pap test'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'lipid': ['cholesterol', 'lipid panel', 'lipid profile'],
            'ecg': ['ekg', 'electrocardiogram', 'electrocardiography']
        }
    
    def matches_keywords(self, text, keywords, threshold=0.8):
        """Check if text matches any of the keywords with fuzzy matching"""
        if not text or not keywords:
            return False
        
        text_lower = text.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            
            # Exact match
            if keyword_lower in text_lower:
                return True
            
            # Fuzzy match
            if self._fuzzy_match(text_lower, keyword_lower, threshold):
                return True
            
            # Medical variant matching
            if self._matches_medical_variants(text_lower, keyword_lower):
                return True
        
        return False
    
    def _fuzzy_match(self, text, keyword, threshold):
        """Perform fuzzy string matching"""
        # Split text into words for better matching
        words = re.findall(r'\b\w+\b', text)
        
        for word in words:
            similarity = SequenceMatcher(None, word, keyword).ratio()
            if similarity >= threshold:
                return True
        
        # Also check full phrases
        similarity = SequenceMatcher(None, text, keyword).ratio()
        return similarity >= threshold
    
    def _matches_medical_variants(self, text, keyword):
        """Check if keyword matches known medical term variants"""
        for base_term, variants in self.medical_variants.items():
            if keyword == base_term or keyword in variants:
                # Check if any variant appears in text
                for variant in variants + [base_term]:
                    if variant in text:
                        return True
        return False
    
    def get_match_confidence(self, text, keyword):
        """Get confidence score for a match"""
        if not text or not keyword:
            return 0.0
        
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        # Exact match gets highest confidence
        if keyword_lower in text_lower:
            return 1.0
        
        # Fuzzy match confidence
        words = re.findall(r'\b\w+\b', text_lower)
        max_similarity = 0
        
        for word in words:
            similarity = SequenceMatcher(None, word, keyword_lower).ratio()
            max_similarity = max(max_similarity, similarity)
        
        # Medical variant match gets high confidence
        if self._matches_medical_variants(text_lower, keyword_lower):
            max_similarity = max(max_similarity, 0.9)
        
        return max_similarity
    
    def extract_matching_phrases(self, text, keywords):
        """Extract phrases from text that match keywords"""
        if not text or not keywords:
            return []
        
        matches = []
        text_lower = text.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            
            # Find exact matches with context
            pattern = r'\b\w*' + re.escape(keyword_lower) + r'\w*\b'
            found_matches = re.finditer(pattern, text_lower)
            
            for match in found_matches:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()
                
                matches.append({
                    'keyword': keyword,
                    'match': match.group(),
                    'context': context,
                    'confidence': self.get_match_confidence(match.group(), keyword_lower)
                })
        
        return matches
