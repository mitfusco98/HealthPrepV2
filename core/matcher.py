"""
Fuzzy keyword and document matching logic
Handles document matching against screening criteria
"""
import re
from difflib import SequenceMatcher
from models import Document, ScreeningType
import logging

logger = logging.getLogger(__name__)

class FuzzyMatcher:
    """Handles fuzzy matching for keywords and medical terms"""
    
    def __init__(self):
        # Common medical term variations
        self.medical_terms = {
            'mammogram': ['mammography', 'breast imaging', 'breast screen'],
            'colonoscopy': ['colono', 'colon screening', 'colorectal'],
            'pap smear': ['pap', 'cervical screening', 'papanicolaou'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'dxa': ['dexa', 'bone density', 'bone scan'],
            'ekg': ['ecg', 'electrocardiogram'],
            'echo': ['echocardiogram', 'cardiac echo']
        }
    
    def suggest_keywords(self, partial, limit=10):
        """Suggest keywords based on partial input"""
        suggestions = []
        partial_lower = partial.lower()
        
        # Search through medical terms
        for term, aliases in self.medical_terms.items():
            if partial_lower in term:
                suggestions.append(term)
            for alias in aliases:
                if partial_lower in alias and alias not in suggestions:
                    suggestions.append(alias)
        
        return suggestions[:limit]
    
    def suggest_conditions(self, partial, limit=10):
        """Suggest medical conditions based on partial input"""
        common_conditions = [
            'diabetes', 'hypertension', 'obesity', 'heart disease',
            'cancer', 'osteoporosis', 'kidney disease', 'liver disease',
            'thyroid disorder', 'depression', 'anxiety', 'copd'
        ]
        
        suggestions = []
        partial_lower = partial.lower()
        
        for condition in common_conditions:
            if partial_lower in condition.lower():
                suggestions.append(condition)
        
        return suggestions[:limit]

class DocumentMatcher:
    """Handles fuzzy matching of documents to screening types"""
    
    def __init__(self):
        # Common medical term variations for fuzzy matching
        self.medical_aliases = {
            'dxa': ['dexa', 'bone density', 'bone scan'],
            'mammogram': ['mammography', 'breast imaging'],
            'colonoscopy': ['colono', 'colon screening'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'pap': ['pap smear', 'cervical screening', 'papanicolaou'],
            'ekg': ['ecg', 'electrocardiogram'],
            'echo': ['echocardiogram', 'cardiac echo'],
            'stress test': ['cardiac stress', 'exercise stress']
        }
    
    def find_matching_documents(self, patient, screening_type):
        """Find all documents for a patient that match a screening type"""
        matching_docs = []
        
        # Get all patient documents
        documents = Document.query.filter_by(patient_id=patient.id).all()
        
        for doc in documents:
            if self.document_matches_screening(doc, screening_type):
                matching_docs.append(doc)
        
        return matching_docs
    
    def document_matches_screening(self, document, screening_type):
        """Check if a document matches a screening type"""
        if not screening_type.keywords:
            return False
        
        # Get searchable text from document
        searchable_text = self.get_searchable_text(document)
        
        # Check for keyword matches
        for keyword in screening_type.keywords:
            if self.fuzzy_keyword_match(keyword, searchable_text):
                return True
        
        return False
    
    def get_searchable_text(self, document):
        """Get all searchable text from a document"""
        text_parts = []
        
        # Add filename
        if document.original_filename:
            text_parts.append(document.original_filename.lower())
        
        # Add OCR text if available
        if document.ocr_text:
            text_parts.append(document.ocr_text.lower())
        
        # Add document type
        if document.document_type:
            text_parts.append(document.document_type.lower())
        
        return ' '.join(text_parts)
    
    def fuzzy_keyword_match(self, keyword, text):
        """Perform fuzzy matching of keyword against text"""
        keyword = keyword.lower().strip()
        text = text.lower()
        
        # Direct match
        if keyword in text:
            return True
        
        # Check aliases
        if keyword in self.medical_aliases:
            for alias in self.medical_aliases[keyword]:
                if alias in text:
                    return True
        
        # Fuzzy matching with similarity threshold
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            if self.similarity_match(keyword, word, threshold=0.8):
                return True
        
        return False
    
    def similarity_match(self, keyword, word, threshold=0.8):
        """Check if two words are similar enough to match"""
        if len(keyword) < 3 or len(word) < 3:
            return keyword == word
        
        similarity = SequenceMatcher(None, keyword, word).ratio()
        return similarity >= threshold
    
    def get_match_details(self, document, screening_type):
        """Get detailed information about how a document matches a screening"""
        searchable_text = self.get_searchable_text(document)
        matched_keywords = []
        total_matches = 0
        
        for keyword in screening_type.keywords or []:
            if self.fuzzy_keyword_match(keyword, searchable_text):
                matched_keywords.append(keyword)
                total_matches += 1
        
        # Calculate confidence based on number of matched keywords
        confidence = min(total_matches / max(len(screening_type.keywords or []), 1), 1.0)
        
        return {
            'confidence': confidence,
            'keywords': matched_keywords,
            'total_matches': total_matches
        }
    
    def expand_medical_term(self, term):
        """Expand a medical term to include common aliases"""
        term = term.lower().strip()
        expanded_terms = [term]
        
        # Add direct aliases
        if term in self.medical_aliases:
            expanded_terms.extend(self.medical_aliases[term])
        
        # Check if term is an alias of something else
        for main_term, aliases in self.medical_aliases.items():
            if term in aliases:
                expanded_terms.append(main_term)
                expanded_terms.extend(aliases)
        
        return list(set(expanded_terms))  # Remove duplicates
