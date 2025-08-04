"""
Document matching engine with fuzzy keyword detection and confidence scoring.
Handles matching medical documents to screening criteria.
"""

import re
import logging
from typing import List, Dict, Optional, Set
from difflib import SequenceMatcher
from dataclasses import dataclass

from models import MedicalDocument

@dataclass
class MatchResult:
    """Result of document matching operation."""
    confidence: float
    matched_keywords: List[str]
    match_positions: List[int]

class DocumentMatcher:
    """Handles fuzzy keyword matching for medical documents."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common medical term equivalents for fuzzy matching
        self.equivalents = {
            'dxa': ['dexa', 'bone density', 'bone scan'],
            'dexa': ['dxa', 'bone density', 'bone scan'],
            'mammogram': ['mammography', 'breast imaging', 'breast xray'],
            'colonoscopy': ['colon', 'colonoscopic', 'lower endoscopy'],
            'pap': ['pap smear', 'cervical', 'papanicolaou'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'lipid': ['cholesterol', 'lipid panel', 'lipid profile'],
            'echo': ['echocardiogram', 'cardiac echo', 'heart ultrasound'],
            'ekg': ['ecg', 'electrocardiogram', 'cardiac rhythm'],
            'cbc': ['complete blood count', 'blood count', 'full blood count'],
            'bmp': ['basic metabolic panel', 'chem 7', 'basic chemistry'],
            'cmp': ['comprehensive metabolic panel', 'chem 14', 'complete chemistry']
        }
        
        # Medical stopwords to ignore during matching
        self.stopwords = {
            'report', 'result', 'test', 'lab', 'laboratory', 'study', 'exam',
            'examination', 'imaging', 'radiology', 'pathology', 'blood', 'urine',
            'specimen', 'sample', 'analysis', 'findings', 'impression', 'conclusion'
        }
    
    def calculate_match_score(self, document: MedicalDocument, keywords: List[str]) -> float:
        """Calculate overall match confidence score for a document."""
        if not keywords or not document.content:
            return 0.0
        
        content_lower = document.content.lower()
        filename_lower = document.filename.lower()
        
        total_score = 0.0
        keyword_count = 0
        
        for keyword in keywords:
            if not keyword.strip():
                continue
                
            keyword_lower = keyword.strip().lower()
            keyword_count += 1
            
            # Direct match scoring
            content_score = self._calculate_direct_match_score(content_lower, keyword_lower)
            filename_score = self._calculate_direct_match_score(filename_lower, keyword_lower) * 1.5  # Filename matches weighted higher
            
            # Fuzzy match scoring
            fuzzy_score = self._calculate_fuzzy_match_score(content_lower + " " + filename_lower, keyword_lower)
            
            # Take the best score for this keyword
            best_score = max(content_score, filename_score, fuzzy_score)
            total_score += best_score
        
        if keyword_count == 0:
            return 0.0
        
        # Average score with confidence adjustment based on document OCR quality
        avg_score = total_score / keyword_count
        ocr_confidence_factor = document.confidence_score if document.confidence_score else 0.8
        
        return min(avg_score * ocr_confidence_factor, 1.0)
    
    def _calculate_direct_match_score(self, text: str, keyword: str) -> float:
        """Calculate score for direct keyword matches."""
        # Exact match
        if keyword in text:
            return 1.0
        
        # Word boundary match
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text):
            return 0.9
        
        # Partial match
        if any(part in text for part in keyword.split() if len(part) > 2):
            return 0.6
        
        return 0.0
    
    def _calculate_fuzzy_match_score(self, text: str, keyword: str) -> float:
        """Calculate score for fuzzy keyword matches using equivalents."""
        keyword_lower = keyword.lower()
        
        # Check for equivalent terms
        equivalents = self.equivalents.get(keyword_lower, [])
        all_terms = [keyword_lower] + equivalents
        
        best_score = 0.0
        
        for term in all_terms:
            # Direct match with equivalent
            if term in text:
                best_score = max(best_score, 0.85)
            
            # Fuzzy string matching
            words = text.split()
            for word in words:
                # Skip stopwords
                if word in self.stopwords:
                    continue
                
                similarity = SequenceMatcher(None, term, word).ratio()
                if similarity > 0.8:
                    best_score = max(best_score, similarity * 0.8)
        
        return best_score
    
    def get_matched_keywords(self, document: MedicalDocument, keywords: List[str]) -> List[str]:
        """Get list of keywords that matched in the document."""
        if not keywords or not document.content:
            return []
        
        content_lower = document.content.lower()
        filename_lower = document.filename.lower()
        text = content_lower + " " + filename_lower
        
        matched = []
        
        for keyword in keywords:
            if not keyword.strip():
                continue
                
            keyword_lower = keyword.strip().lower()
            
            # Check direct matches
            if self._calculate_direct_match_score(text, keyword_lower) > 0.5:
                matched.append(keyword.strip())
                continue
            
            # Check fuzzy matches
            if self._calculate_fuzzy_match_score(text, keyword_lower) > 0.7:
                matched.append(keyword.strip())
        
        return matched
    
    def find_match_positions(self, document: MedicalDocument, keywords: List[str]) -> Dict[str, List[int]]:
        """Find positions of keyword matches in document content."""
        if not keywords or not document.content:
            return {}
        
        content_lower = document.content.lower()
        positions = {}
        
        for keyword in keywords:
            if not keyword.strip():
                continue
                
            keyword_lower = keyword.strip().lower()
            keyword_positions = []
            
            # Find all occurrences
            start = 0
            while True:
                pos = content_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                keyword_positions.append(pos)
                start = pos + 1
            
            if keyword_positions:
                positions[keyword.strip()] = keyword_positions
        
        return positions
    
    def validate_match_quality(self, document: MedicalDocument, keywords: List[str]) -> Dict[str, any]:
        """Validate and provide detailed match quality information."""
        match_score = self.calculate_match_score(document, keywords)
        matched_keywords = self.get_matched_keywords(document, keywords)
        positions = self.find_match_positions(document, keywords)
        
        # Calculate quality metrics
        keyword_coverage = len(matched_keywords) / len(keywords) if keywords else 0
        ocr_quality = document.confidence_score if document.confidence_score else 0.8
        
        quality_assessment = "High"
        if match_score < 0.6 or keyword_coverage < 0.5:
            quality_assessment = "Medium"
        if match_score < 0.4 or keyword_coverage < 0.3:
            quality_assessment = "Low"
        
        return {
            'match_score': match_score,
            'matched_keywords': matched_keywords,
            'keyword_coverage': keyword_coverage,
            'ocr_quality': ocr_quality,
            'quality_assessment': quality_assessment,
            'match_positions': positions,
            'total_keywords': len(keywords),
            'matched_count': len(matched_keywords)
        }
