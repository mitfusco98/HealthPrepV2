"""
Fuzzy keyword and document matching module.
Handles keyword matching against document names and content with fuzzy logic.
"""

import re
import logging
from typing import List, Dict, Set
from difflib import SequenceMatcher
import json

from models import ScreeningType, MedicalDocument

class FuzzyMatcher:
    """Handles fuzzy matching of keywords against documents"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common medical term equivalents for fuzzy matching
        self.medical_equivalents = {
            'dxa': ['dexa', 'bone density', 'bone densitometry'],
            'dexa': ['dxa', 'bone density', 'bone densitometry'],
            'mammogram': ['mammography', 'breast screening', 'breast imaging'],
            'colonoscopy': ['colon screening', 'colorectal screening'],
            'pap': ['pap smear', 'cervical screening', 'cytology'],
            'a1c': ['hemoglobin a1c', 'hba1c', 'glycated hemoglobin'],
            'lipid': ['cholesterol', 'lipid panel', 'lipid profile'],
            'cbc': ['complete blood count', 'full blood count'],
            'bmp': ['basic metabolic panel', 'chem 7'],
            'cmp': ['comprehensive metabolic panel', 'chem 14'],
            'tsh': ['thyroid stimulating hormone', 'thyroid function'],
            'psa': ['prostate specific antigen', 'prostate screening'],
            'ekg': ['ecg', 'electrocardiogram', 'cardiac screening'],
            'echo': ['echocardiogram', 'cardiac echo', 'heart ultrasound'],
            'ct': ['computed tomography', 'cat scan'],
            'mri': ['magnetic resonance imaging'],
            'ultrasound': ['us', 'sonogram', 'ultrasonography']
        }
        
        # Common condition aliases
        self.condition_equivalents = {
            'diabetes': ['diabetic', 'dm', 'diabetes mellitus', 't2dm', 't1dm'],
            'hypertension': ['htn', 'high blood pressure', 'elevated bp'],
            'hyperlipidemia': ['high cholesterol', 'dyslipidemia', 'elevated cholesterol'],
            'copd': ['chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis'],
            'cad': ['coronary artery disease', 'heart disease', 'cardiac disease'],
            'ckd': ['chronic kidney disease', 'renal disease', 'kidney disease'],
            'osteoporosis': ['bone loss', 'osteopenia'],
            'depression': ['major depression', 'depressive disorder'],
            'anxiety': ['anxiety disorder', 'generalized anxiety']
        }
    
    def find_matching_documents(self, screening_type: ScreeningType, documents: List[MedicalDocument]) -> List[MedicalDocument]:
        """Find documents that match the screening type keywords"""
        if not screening_type or not documents:
            return []
        
        keywords = screening_type.get_keywords_list()
        if not keywords:
            return []
        
        matched_documents = []
        
        for document in documents:
            if self._document_matches_keywords(document, keywords):
                matched_documents.append(document)
        
        self.logger.debug(f"Found {len(matched_documents)} matching documents for screening '{screening_type.name}'")
        return matched_documents
    
    def _document_matches_keywords(self, document: MedicalDocument, keywords: List[str]) -> bool:
        """Check if a document matches any of the keywords using fuzzy logic"""
        # Combine filename and OCR text for searching
        search_text = ""
        
        if document.filename:
            search_text += document.filename.lower() + " "
        
        if document.ocr_text:
            search_text += document.ocr_text.lower()
        
        if not search_text.strip():
            return False
        
        # Check each keyword
        for keyword in keywords:
            if self._keyword_matches_text(keyword.lower().strip(), search_text):
                return True
        
        return False
    
    def _keyword_matches_text(self, keyword: str, text: str) -> bool:
        """Check if a keyword matches text using fuzzy logic"""
        if not keyword or not text:
            return False
        
        # Direct substring match
        if keyword in text:
            return True
        
        # Check equivalents
        equivalents = self._get_keyword_equivalents(keyword)
        for equivalent in equivalents:
            if equivalent.lower() in text:
                return True
        
        # Fuzzy matching for typos (minimum 80% similarity)
        words = text.split()
        for word in words:
            if len(word) >= 3 and self._fuzzy_match(keyword, word, 0.8):
                return True
        
        # Word boundary matching for compound terms
        if self._word_boundary_match(keyword, text):
            return True
        
        return False
    
    def _get_keyword_equivalents(self, keyword: str) -> List[str]:
        """Get equivalent terms for a keyword"""
        equivalents = [keyword]
        
        # Check medical equivalents
        if keyword in self.medical_equivalents:
            equivalents.extend(self.medical_equivalents[keyword])
        
        # Check condition equivalents
        if keyword in self.condition_equivalents:
            equivalents.extend(self.condition_equivalents[keyword])
        
        # Check reverse mapping
        for key, values in self.medical_equivalents.items():
            if keyword in values and key not in equivalents:
                equivalents.append(key)
        
        for key, values in self.condition_equivalents.items():
            if keyword in values and key not in equivalents:
                equivalents.append(key)
        
        return equivalents
    
    def _fuzzy_match(self, keyword: str, word: str, threshold: float = 0.8) -> bool:
        """Check if two strings match with fuzzy logic"""
        if not keyword or not word:
            return False
        
        # Skip very short words to avoid false positives
        if len(keyword) < 3 or len(word) < 3:
            return keyword == word
        
        similarity = SequenceMatcher(None, keyword, word).ratio()
        return similarity >= threshold
    
    def _word_boundary_match(self, keyword: str, text: str) -> bool:
        """Match keywords with word boundaries to avoid partial matches"""
        # Create regex pattern with word boundaries
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def get_match_confidence(self, screening_type: ScreeningType, document: MedicalDocument) -> float:
        """Calculate confidence score for document matching"""
        if not screening_type or not document:
            return 0.0
        
        keywords = screening_type.get_keywords_list()
        if not keywords:
            return 0.0
        
        # Combine filename and OCR text
        search_text = ""
        if document.filename:
            search_text += document.filename.lower() + " "
        if document.ocr_text:
            search_text += document.ocr_text.lower()
        
        if not search_text.strip():
            return 0.0
        
        matched_keywords = 0
        total_keywords = len(keywords)
        
        for keyword in keywords:
            if self._keyword_matches_text(keyword.lower().strip(), search_text):
                matched_keywords += 1
        
        # Base confidence on keyword match ratio
        base_confidence = matched_keywords / total_keywords
        
        # Boost confidence if document type aligns with screening type
        type_boost = self._get_document_type_boost(screening_type, document)
        
        # Consider OCR confidence if available
        ocr_factor = document.ocr_confidence if document.ocr_confidence else 0.8
        
        final_confidence = min(1.0, base_confidence * type_boost * ocr_factor)
        return round(final_confidence, 3)
    
    def _get_document_type_boost(self, screening_type: ScreeningType, document: MedicalDocument) -> float:
        """Get confidence boost based on document type alignment"""
        if not document.document_type:
            return 1.0
        
        # Map screening types to expected document types
        type_mapping = {
            'lab': ['laboratory', 'blood', 'urine', 'test', 'panel', 'a1c', 'lipid', 'cbc', 'bmp', 'cmp'],
            'imaging': ['imaging', 'xray', 'ct', 'mri', 'ultrasound', 'mammogram', 'dexa', 'dxa'],
            'consult': ['consult', 'specialist', 'cardiology', 'endocrine', 'gastro'],
            'hospital': ['hospital', 'admission', 'discharge', 'inpatient']
        }
        
        screening_name = screening_type.name.lower()
        doc_type = document.document_type.lower()
        
        if doc_type in type_mapping:
            expected_terms = type_mapping[doc_type]
            for term in expected_terms:
                if term in screening_name:
                    return 1.2  # 20% boost for matching document type
        
        return 1.0
    
    def suggest_keywords(self, text: str) -> List[str]:
        """Suggest keywords based on document text analysis"""
        if not text:
            return []
        
        text_lower = text.lower()
        suggestions = set()
        
        # Look for common medical terms
        all_medical_terms = set()
        for terms in self.medical_equivalents.values():
            all_medical_terms.update(terms)
        all_medical_terms.update(self.medical_equivalents.keys())
        
        for term in all_medical_terms:
            if term in text_lower:
                suggestions.add(term)
        
        # Look for condition terms
        all_conditions = set()
        for conditions in self.condition_equivalents.values():
            all_conditions.update(conditions)
        all_conditions.update(self.condition_equivalents.keys())
        
        for condition in all_conditions:
            if condition in text_lower:
                suggestions.add(condition)
        
        return sorted(list(suggestions))
