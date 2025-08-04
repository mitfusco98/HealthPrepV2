import re
from difflib import SequenceMatcher
from models import ScreeningType, MedicalDocument

class DocumentMatcher:
    """Handles fuzzy keyword matching and document-to-screening association"""
    
    def __init__(self):
        self.fuzzy_threshold = 0.8
        
        # Common medical term equivalents for fuzzy matching
        self.medical_synonyms = {
            'dxa': ['dexa', 'bone density', 'bone scan'],
            'mammogram': ['mammography', 'breast imaging'],
            'colonoscopy': ['colon screening', 'colo screening'],
            'pap': ['pap smear', 'cervical screening'],
            'a1c': ['hemoglobin a1c', 'hba1c', 'glycohemoglobin'],
            'cholesterol': ['lipid panel', 'lipids', 'lipid profile'],
            'echo': ['echocardiogram', 'cardiac echo'],
            'ekg': ['ecg', 'electrocardiogram'],
            'cbc': ['complete blood count', 'blood count'],
            'bmp': ['basic metabolic panel', 'chemistry panel']
        }
    
    def matches_screening(self, document, screening_type):
        """Check if document matches screening type based on keywords"""
        if not screening_type.keywords:
            return False
        
        # Get searchable text (filename + OCR content)
        search_text = self._get_searchable_text(document)
        
        # Check each keyword with fuzzy matching
        for keyword in screening_type.keywords:
            if self._fuzzy_match_keyword(keyword.lower(), search_text.lower()):
                return True
        
        return False
    
    def match_document_to_screenings(self, document):
        """Match a document to all applicable screening types"""
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        matches = []
        
        for screening_type in screening_types:
            if self.matches_screening(document, screening_type):
                matches.append(screening_type.id)
        
        return matches
    
    def _get_searchable_text(self, document):
        """Get all searchable text from document"""
        text_parts = [document.filename]
        
        if document.ocr_text:
            text_parts.append(document.ocr_text)
        
        return ' '.join(text_parts)
    
    def _fuzzy_match_keyword(self, keyword, text):
        """Perform fuzzy matching with synonyms"""
        # Direct substring match
        if keyword in text:
            return True
        
        # Check synonyms
        if keyword in self.medical_synonyms:
            for synonym in self.medical_synonyms[keyword]:
                if synonym.lower() in text:
                    return True
        
        # Fuzzy string matching for partial matches
        words = text.split()
        for word in words:
            if self._similarity(keyword, word) >= self.fuzzy_threshold:
                return True
        
        return False
    
    def _similarity(self, a, b):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a, b).ratio()
    
    def get_keyword_suggestions(self, partial_keyword):
        """Get keyword suggestions for autocomplete"""
        suggestions = []
        
        # Add exact matches from synonyms
        for key, synonyms in self.medical_synonyms.items():
            if partial_keyword.lower() in key:
                suggestions.append(key)
            for synonym in synonyms:
                if partial_keyword.lower() in synonym.lower():
                    suggestions.append(synonym)
        
        return list(set(suggestions))[:10]  # Return top 10 unique suggestions
