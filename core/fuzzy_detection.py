"""
Advanced Fuzzy Detection System for Healthcare Screening Engine
Handles semantic equivalence and separator normalization for accurate keyword matching
"""
import re
import logging
from typing import List, Dict, Tuple, Set, Optional
from difflib import SequenceMatcher
from collections import defaultdict

class FuzzyDetectionEngine:
    """
    Advanced fuzzy detection engine for healthcare document and keyword matching
    Handles multiple separators, semantic equivalence, and medical terminology variations
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common separators and their normalization patterns
        self.separator_patterns = {
            'underscore': r'_+',
            'dash': r'-+', 
            'period': r'\.+',
            'space': r'\s+',
            'camel_case': r'(?<=[a-z])(?=[A-Z])',
            'mixed': r'[_\-\.\s]+'
        }
        
        # Medical terminology equivalence mapping
        self.medical_equivalents = {
            'mammography': ['mammogram', 'mammo', 'breast_imaging', 'breast-screening', 'breast.scan'],
            'colonoscopy': ['colon_screening', 'colon-scope', 'colonography', 'colon.exam'],
            'pap_smear': ['pap_test', 'pap-smear', 'cervical_screening', 'cervical.cytology'],
            'a1c': ['hba1c', 'hemoglobin_a1c', 'glycated-hemoglobin', 'a1c.test'],
            'dexa': ['dxa', 'bone_density', 'bone-scan', 'densitometry', 'bone.density'],
            'ecg': ['ekg', 'electrocardiogram', 'cardiac_rhythm', 'heart-rhythm'],
            'lipid_panel': ['cholesterol', 'lipids', 'lipid_profile', 'cholesterol-test'],
            'cbc': ['complete_blood_count', 'blood-count', 'full.blood.count'],
            'ultrasound': ['sonogram', 'sono', 'ultrasonography', 'us_scan'],
            'mri': ['magnetic_resonance', 'mr_imaging', 'mri_scan', 'mr-scan'],
            'ct_scan': ['computed_tomography', 'cat_scan', 'ct-scan', 'computerized.tomography'],
            'xray': ['x_ray', 'x-ray', 'radiograph', 'plain.film'],
            'stress_test': ['cardiac_stress', 'exercise-test', 'treadmill_test'],
            'echo': ['echocardiogram', 'cardiac_echo', 'heart-ultrasound', 'echo.study']
        }
        
        # Medical abbreviation expansions
        self.abbreviation_expansions = {
            'bp': 'blood pressure',
            'hr': 'heart rate',
            'rr': 'respiratory rate',
            'temp': 'temperature',
            'wbc': 'white blood cell',
            'rbc': 'red blood cell',
            'plt': 'platelet',
            'hgb': 'hemoglobin',
            'hct': 'hematocrit',
            'bun': 'blood urea nitrogen',
            'cr': 'creatinine',
            'gfr': 'glomerular filtration rate',
            'alt': 'alanine aminotransferase',
            'ast': 'aspartate aminotransferase',
            'ldh': 'lactate dehydrogenase',
            'tsh': 'thyroid stimulating hormone',
            'psa': 'prostate specific antigen',
            'cea': 'carcinoembryonic antigen',
            'afp': 'alpha fetoprotein'
        }
        
        # Common filename patterns in healthcare
        self.filename_patterns = {
            'date_patterns': [
                r'\d{4}[-_\.]\d{1,2}[-_\.]\d{1,2}',  # YYYY-MM-DD variants
                r'\d{1,2}[-_\.]\d{1,2}[-_\.]\d{4}',  # MM-DD-YYYY variants
                r'\d{8}',  # YYYYMMDD
                r'\d{6}'   # MMDDYY or YYMMDD
            ],
            'mrn_patterns': [
                r'mrn[-_\.]?\d+',
                r'patient[-_\.]?\d+',
                r'pt[-_\.]?\d+',
                r'\d{6,10}'  # Common MRN length
            ],
            'document_type_patterns': [
                r'(lab|labs|laboratory)',
                r'(imaging|radiology|rad)',
                r'(consult|consultation)',
                r'(hospital|admission|discharge)',
                r'(report|summary|results)'
            ]
        }
    
    def fuzzy_match_keywords(self, text: str, keywords: List[str], 
                           threshold: float = 0.7) -> List[Tuple[str, float, str]]:
        """
        Perform advanced fuzzy matching of keywords against text
        
        Args:
            text: Text to search in (filename + content)
            keywords: List of keywords to match
            threshold: Minimum confidence threshold
            
        Returns:
            List of tuples: (matched_keyword, confidence, matched_text)
        """
        matches = []
        normalized_text = self._normalize_text(text)
        
        for keyword in keywords:
            # Get all possible variations of the keyword
            keyword_variations = self._get_keyword_variations(keyword)
            
            best_match = None
            best_confidence = 0.0
            
            for variation in keyword_variations:
                normalized_variation = self._normalize_text(variation)
                
                # Direct match check
                if normalized_variation in normalized_text:
                    confidence = 1.0
                    matched_text = variation
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = matched_text
                    continue
                
                # Fuzzy matching with different strategies
                confidence, matched_text = self._calculate_fuzzy_confidence(
                    normalized_variation, normalized_text, text
                )
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = matched_text
            
            if best_confidence >= threshold:
                matches.append((keyword, best_confidence, best_match))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text by handling various separators and formatting
        """
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Handle camelCase by inserting spaces
        normalized = re.sub(self.separator_patterns['camel_case'], ' ', normalized)
        
        # Replace all separators with spaces
        normalized = re.sub(self.separator_patterns['mixed'], ' ', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Expand common abbreviations
        words = normalized.split()
        expanded_words = []
        for word in words:
            if word in self.abbreviation_expansions:
                expanded_words.append(self.abbreviation_expansions[word])
            else:
                expanded_words.append(word)
        
        return ' '.join(expanded_words)
    
    def _get_keyword_variations(self, keyword: str) -> List[str]:
        """
        Generate all possible variations of a keyword including medical equivalents
        """
        variations = [keyword]
        keyword_lower = keyword.lower()
        
        # Add medical equivalents
        for main_term, equivalents in self.medical_equivalents.items():
            if keyword_lower == main_term or keyword_lower in equivalents:
                variations.extend(equivalents)
                variations.append(main_term)
        
        # Generate separator variations
        base_variations = list(set(variations))
        separator_variations = []
        
        for variation in base_variations:
            # Original variation
            separator_variations.append(variation)
            
            # Replace spaces with different separators
            if ' ' in variation:
                separator_variations.append(variation.replace(' ', '_'))
                separator_variations.append(variation.replace(' ', '-'))
                separator_variations.append(variation.replace(' ', '.'))
                separator_variations.append(variation.replace(' ', ''))
            
            # If variation has separators, try with spaces
            normalized_variation = re.sub(self.separator_patterns['mixed'], ' ', variation)
            if normalized_variation != variation:
                separator_variations.append(normalized_variation)
        
        return list(set(separator_variations))
    
    def _calculate_fuzzy_confidence(self, keyword: str, normalized_text: str, 
                                  original_text: str) -> Tuple[float, str]:
        """
        Calculate fuzzy matching confidence using multiple strategies
        """
        best_confidence = 0.0
        best_match = ""
        
        # Strategy 1: Word-level fuzzy matching
        keyword_words = keyword.split()
        text_words = normalized_text.split()
        
        if len(keyword_words) == 1:
            # Single word matching
            for word in text_words:
                ratio = SequenceMatcher(None, keyword, word).ratio()
                if ratio > best_confidence and ratio > 0.6:
                    best_confidence = ratio
                    best_match = word
        else:
            # Multi-word phrase matching
            for i in range(len(text_words) - len(keyword_words) + 1):
                phrase = ' '.join(text_words[i:i + len(keyword_words)])
                ratio = SequenceMatcher(None, keyword, phrase).ratio()
                if ratio > best_confidence and ratio > 0.6:
                    best_confidence = ratio
                    best_match = phrase
        
        # Strategy 2: Substring matching with edit distance
        if best_confidence < 0.8:
            substring_confidence, substring_match = self._substring_fuzzy_match(
                keyword, normalized_text, original_text
            )
            if substring_confidence > best_confidence:
                best_confidence = substring_confidence
                best_match = substring_match
        
        # Strategy 3: Character n-gram matching for very similar terms
        if best_confidence < 0.9:
            ngram_confidence = self._ngram_similarity(keyword, normalized_text)
            if ngram_confidence > best_confidence:
                best_confidence = ngram_confidence
                best_match = keyword  # Use original keyword as match indicator
        
        return best_confidence, best_match
    
    def _substring_fuzzy_match(self, keyword: str, normalized_text: str, 
                             original_text: str) -> Tuple[float, str]:
        """
        Find best substring match using sliding window
        """
        best_ratio = 0.0
        best_match = ""
        keyword_len = len(keyword)
        
        # Try different window sizes around the keyword length
        for window_size in [keyword_len, keyword_len + 2, keyword_len - 2]:
            if window_size <= 0:
                continue
                
            for i in range(len(normalized_text) - window_size + 1):
                substring = normalized_text[i:i + window_size]
                ratio = SequenceMatcher(None, keyword, substring).ratio()
                
                if ratio > best_ratio and ratio > 0.6:
                    best_ratio = ratio
                    best_match = substring
        
        return best_ratio, best_match
    
    def _ngram_similarity(self, keyword: str, text: str, n: int = 3) -> float:
        """
        Calculate similarity based on character n-grams
        """
        def get_ngrams(string: str, n: int) -> Set[str]:
            return set(string[i:i+n] for i in range(len(string) - n + 1))
        
        keyword_ngrams = get_ngrams(keyword, n)
        text_ngrams = get_ngrams(text, n)
        
        if not keyword_ngrams:
            return 0.0
        
        intersection = keyword_ngrams.intersection(text_ngrams)
        union = keyword_ngrams.union(text_ngrams)
        
        return len(intersection) / len(union) if union else 0.0
    
    def extract_semantic_terms(self, text: str) -> Dict[str, List[str]]:
        """
        Extract semantically meaningful terms from text
        Useful for building keyword suggestions and improving matching
        """
        normalized_text = self._normalize_text(text)
        extracted_terms = defaultdict(list)
        
        # Extract medical terms by category
        for category, terms in self.medical_equivalents.items():
            for term in terms + [category]:
                if term in normalized_text:
                    extracted_terms['medical_terms'].append(term)
        
        # Extract potential dates
        for pattern in self.filename_patterns['date_patterns']:
            matches = re.findall(pattern, text)
            extracted_terms['dates'].extend(matches)
        
        # Extract potential MRNs
        for pattern in self.filename_patterns['mrn_patterns']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            extracted_terms['mrns'].extend(matches)
        
        # Extract document types
        for pattern in self.filename_patterns['document_type_patterns']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            extracted_terms['document_types'].extend(matches)
        
        return dict(extracted_terms)
    
    def suggest_keywords(self, text: str, existing_keywords: List[str] = None) -> List[str]:
        """
        Suggest keywords based on text content analysis
        """
        existing_keywords = existing_keywords or []
        suggestions = []
        
        # Extract semantic terms
        semantic_terms = self.extract_semantic_terms(text)
        
        # Add medical terms as suggestions
        for term in semantic_terms.get('medical_terms', []):
            if term not in existing_keywords:
                suggestions.append(term)
        
        # Add normalized versions of existing keywords
        normalized_text = self._normalize_text(text)
        words = normalized_text.split()
        
        # Look for multi-word medical phrases
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if any(bigram in equiv_list for equiv_list in self.medical_equivalents.values()):
                if bigram not in existing_keywords:
                    suggestions.append(bigram)
        
        return list(set(suggestions))
    
    def validate_keyword_relevance(self, keyword: str, document_texts: List[str]) -> float:
        """
        Validate how relevant a keyword is across a set of documents
        Returns relevance score (0.0 to 1.0)
        """
        if not document_texts:
            return 0.0
        
        match_count = 0
        total_confidence = 0.0
        
        for text in document_texts:
            matches = self.fuzzy_match_keywords(text, [keyword], threshold=0.5)
            if matches:
                match_count += 1
                total_confidence += matches[0][1]  # First match confidence
        
        # Calculate relevance based on match frequency and average confidence
        match_frequency = match_count / len(document_texts)
        avg_confidence = total_confidence / match_count if match_count > 0 else 0.0
        
        # Weighted combination of frequency and confidence
        relevance = (match_frequency * 0.6) + (avg_confidence * 0.4)
        
        return relevance