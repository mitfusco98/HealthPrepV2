"""
Fuzzy keyword and document matching for screening types
"""
import json
import re
import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher
from models import MedicalDocument

logger = logging.getLogger(__name__)

class FuzzyMatcher:
    """Handles fuzzy matching of keywords against document content and filenames"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.medical_term_mappings = self._load_medical_term_mappings()
    
    def _load_medical_term_mappings(self) -> Dict[str, List[str]]:
        """Load common medical term variations and synonyms"""
        return {
            'mammogram': ['mammography', 'mammo', 'breast imaging', 'breast xray'],
            'colonoscopy': ['colonoscope', 'colon screening', 'colo', 'bowel scope'],
            'pap smear': ['pap test', 'cervical screening', 'papanicolaou'],
            'dexa': ['dxa', 'bone density', 'bone scan', 'osteoporosis screening'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin', 'diabetic control'],
            'lipid panel': ['cholesterol', 'lipids', 'lipid profile', 'lipid screen'],
            'blood pressure': ['bp', 'hypertension check', 'pressure check'],
            'eye exam': ['ophthalmology', 'vision check', 'eye check', 'retinal exam'],
            'skin check': ['dermatology', 'mole check', 'skin screening', 'melanoma screening']
        }
    
    def document_matches_keywords(self, document: MedicalDocument, keywords: List[str]) -> bool:
        """
        Check if a document matches any of the provided keywords
        Uses fuzzy matching on filename and OCR content
        """
        if not keywords:
            return False
        
        # Prepare search text (filename + OCR content)
        search_text = ""
        if document.filename:
            search_text += document.filename.lower()
        if document.ocr_text:
            search_text += " " + document.ocr_text.lower()
        
        if not search_text.strip():
            return False
        
        # Check each keyword
        for keyword in keywords:
            if self._keyword_matches_text(keyword.lower(), search_text):
                logger.debug(f"Document {document.id} matches keyword '{keyword}'")
                return True
        
        return False
    
    def _keyword_matches_text(self, keyword: str, text: str) -> bool:
        """Check if a keyword matches text using fuzzy logic"""
        
        # Direct substring match
        if keyword in text:
            return True
        
        # Check medical term variations
        if keyword in self.medical_term_mappings:
            for variant in self.medical_term_mappings[keyword]:
                if variant.lower() in text:
                    return True
        
        # Fuzzy matching for individual words
        keyword_words = keyword.split()
        text_words = text.split()
        
        for kword in keyword_words:
            if len(kword) < 3:  # Skip very short words
                continue
                
            for tword in text_words:
                if len(tword) < 3:
                    continue
                    
                similarity = SequenceMatcher(None, kword, tword).ratio()
                if similarity >= self.similarity_threshold:
                    return True
        
        # Regular expression patterns for medical codes
        medical_patterns = [
            r'\b' + re.escape(keyword) + r'\b',  # Exact word boundary match
            r'\b' + re.escape(keyword.replace(' ', '')) + r'\b',  # No spaces
        ]
        
        for pattern in medical_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def find_similar_screening_types(self, name: str, existing_names: List[str]) -> List[str]:
        """Find similar screening type names to help with fuzzy detection"""
        similar = []
        
        for existing_name in existing_names:
            similarity = SequenceMatcher(None, name.lower(), existing_name.lower()).ratio()
            if similarity >= 0.6:  # Lower threshold for suggestions
                similar.append(existing_name)
        
        return similar
    
    def normalize_medical_term(self, term: str) -> str:
        """Normalize medical terms to standard forms"""
        term_lower = term.lower().strip()
        
        # Check if term has a standard mapping
        for standard, variants in self.medical_term_mappings.items():
            if term_lower == standard:
                return standard
            if term_lower in variants:
                return standard
        
        # Basic normalization
        normalized = re.sub(r'[^\w\s]', '', term_lower)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        
        return normalized.strip()
    
    def extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract potential medical keywords from text"""
        if not text:
            return []
        
        # Common medical terms pattern
        medical_patterns = [
            r'\b(?:mammogram|mammography|mammo)\b',
            r'\b(?:colonoscopy|colonoscope|colon screening)\b',
            r'\b(?:pap smear|pap test|cervical screening)\b',
            r'\b(?:dexa|dxa|bone density)\b',
            r'\b(?:a1c|hba1c|hemoglobin a1c)\b',
            r'\b(?:lipid panel|cholesterol|lipids)\b',
            r'\b(?:blood pressure|bp|hypertension)\b',
            r'\b(?:eye exam|ophthalmology|vision)\b',
            r'\b(?:skin check|dermatology|mole check)\b'
        ]
        
        keywords = []
        text_lower = text.lower()
        
        for pattern in medical_patterns:
            matches = re.findall(pattern, text_lower)
            keywords.extend(matches)
        
        # Remove duplicates and normalize
        unique_keywords = []
        for keyword in keywords:
            normalized = self.normalize_medical_term(keyword)
            if normalized and normalized not in unique_keywords:
                unique_keywords.append(normalized)
        
        return unique_keywords
    
    def calculate_match_confidence(self, document: MedicalDocument, keywords: List[str]) -> float:
        """Calculate confidence score for document-keyword matching"""
        if not keywords:
            return 0.0
        
        search_text = ""
        if document.filename:
            search_text += document.filename.lower()
        if document.ocr_text:
            search_text += " " + document.ocr_text.lower()
        
        if not search_text.strip():
            return 0.0
        
        total_score = 0.0
        matched_keywords = 0
        
        for keyword in keywords:
            if self._keyword_matches_text(keyword.lower(), search_text):
                matched_keywords += 1
                # Higher score for exact matches
                if keyword.lower() in search_text:
                    total_score += 1.0
                else:
                    total_score += 0.7  # Fuzzy match gets lower score
        
        if matched_keywords == 0:
            return 0.0
        
        # Confidence is average score weighted by OCR confidence
        base_confidence = total_score / len(keywords)
        ocr_weight = document.ocr_confidence or 0.8
        
        return min(base_confidence * ocr_weight, 1.0)
