"""
Fuzzy keyword + document matching
Handles document content analysis and keyword matching for screening types
"""

import re
from difflib import SequenceMatcher
from sqlalchemy import and_, or_
from models import MedicalDocument
import logging

class DocumentMatcher:
    """Handles fuzzy matching of documents to screening types based on keywords"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common medical term mappings for fuzzy matching
        self.term_mappings = {
            'mammogram': ['mammography', 'breast imaging', 'mammo'],
            'colonoscopy': ['colonoscopy', 'colon scope', 'colonoscopic'],
            'pap': ['pap smear', 'papanicolaou', 'cervical cytology'],
            'dxa': ['dexa', 'bone density', 'dual energy'],
            'a1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'lipid': ['cholesterol', 'lipid panel', 'lipids'],
            'eye': ['ophthalmology', 'retinal', 'vision'],
            'dermatology': ['skin', 'mole', 'dermatologic'],
            'cardiac': ['heart', 'cardiology', 'ecg', 'ekg'],
            'pulmonary': ['lung', 'chest', 'respiratory'],
        }
        
        # Confidence thresholds
        self.filename_match_threshold = 0.7
        self.content_match_threshold = 0.6
        self.fuzzy_match_threshold = 0.8
    
    def find_matching_documents(self, patient, screening_type, variant=None):
        """Find documents that match the screening type keywords"""
        try:
            # Get all keywords (from screening type and variant)
            keywords = self._get_all_keywords(screening_type, variant)
            
            if not keywords:
                return []
            
            # Get patient documents
            documents = MedicalDocument.query.filter_by(
                patient_id=patient.id,
                is_processed=True
            ).all()
            
            matched_documents = []
            
            for document in documents:
                match_score = self._calculate_document_match_score(document, keywords)
                
                if match_score > 0:
                    matched_documents.append({
                        'document': document,
                        'match_score': match_score
                    })
            
            # Sort by match score (highest first)
            matched_documents.sort(key=lambda x: x['match_score'], reverse=True)
            
            # Return document objects
            return [match['document'] for match in matched_documents]
            
        except Exception as e:
            self.logger.error(f"Error finding matching documents for {screening_type.name}: {str(e)}")
            return []
    
    def _get_all_keywords(self, screening_type, variant=None):
        """Get all keywords from screening type and variant"""
        keywords = []
        
        # Add screening type keywords
        if screening_type.keywords:
            keywords.extend(screening_type.keywords)
        
        # Add variant keywords
        if variant and variant.keywords:
            keywords.extend(variant.keywords)
        
        # Normalize keywords (lowercase, strip whitespace)
        keywords = [keyword.lower().strip() for keyword in keywords if keyword.strip()]
        
        return list(set(keywords))  # Remove duplicates
    
    def _calculate_document_match_score(self, document, keywords):
        """Calculate how well a document matches the given keywords"""
        filename_score = self._match_filename(document.filename, keywords)
        content_score = self._match_content(document.ocr_text or '', keywords)
        phi_content_score = self._match_content(document.phi_filtered_text or '', keywords)
        
        # Use the best content score
        best_content_score = max(content_score, phi_content_score)
        
        # Weight filename matches higher than content matches
        total_score = (filename_score * 0.7) + (best_content_score * 0.3)
        
        return total_score
    
    def _match_filename(self, filename, keywords):
        """Match keywords against document filename"""
        if not filename:
            return 0
        
        filename_lower = filename.lower()
        max_score = 0
        
        for keyword in keywords:
            # Direct substring match
            if keyword in filename_lower:
                max_score = max(max_score, 1.0)
                continue
            
            # Fuzzy match
            fuzzy_score = self._fuzzy_match_keyword(filename_lower, keyword)
            if fuzzy_score >= self.filename_match_threshold:
                max_score = max(max_score, fuzzy_score)
        
        return max_score
    
    def _match_content(self, content, keywords):
        """Match keywords against document content"""
        if not content:
            return 0
        
        content_lower = content.lower()
        max_score = 0
        
        for keyword in keywords:
            # Direct substring match
            if keyword in content_lower:
                max_score = max(max_score, 0.9)  # Slightly lower than filename match
                continue
            
            # Fuzzy match
            fuzzy_score = self._fuzzy_match_keyword(content_lower, keyword)
            if fuzzy_score >= self.content_match_threshold:
                max_score = max(max_score, fuzzy_score * 0.8)  # Reduce for content matches
        
        return max_score
    
    def _fuzzy_match_keyword(self, text, keyword):
        """Perform fuzzy matching of keyword against text"""
        # Check for expanded terms first
        expanded_terms = self._get_expanded_terms(keyword)
        
        for term in expanded_terms:
            if term in text:
                return 0.95  # High score for expanded term matches
        
        # Check for partial matches using sequence matching
        words = text.split()
        max_similarity = 0
        
        for word in words:
            similarity = SequenceMatcher(None, keyword, word).ratio()
            max_similarity = max(max_similarity, similarity)
            
            # Also check if keyword is contained in word or vice versa
            if keyword in word or word in keyword:
                if len(keyword) >= 3 and len(word) >= 3:  # Avoid short word false positives
                    max_similarity = max(max_similarity, 0.85)
        
        return max_similarity
    
    def _get_expanded_terms(self, keyword):
        """Get expanded terms for a keyword using medical terminology mappings"""
        expanded_terms = [keyword]  # Include original keyword
        
        # Check if keyword matches any mapped terms
        for base_term, variations in self.term_mappings.items():
            if keyword == base_term or keyword in variations:
                expanded_terms.extend(variations)
                if keyword != base_term:
                    expanded_terms.append(base_term)
        
        return list(set(expanded_terms))
    
    def analyze_document_relevance(self, document, screening_types):
        """Analyze which screening types a document might be relevant for"""
        relevance_scores = {}
        
        for screening_type in screening_types:
            keywords = self._get_all_keywords(screening_type)
            if keywords:
                score = self._calculate_document_match_score(document, keywords)
                if score > 0:
                    relevance_scores[screening_type.id] = {
                        'screening_type': screening_type,
                        'score': score,
                        'confidence': self._score_to_confidence_level(score)
                    }
        
        return relevance_scores
    
    def _score_to_confidence_level(self, score):
        """Convert numeric score to confidence level"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        elif score >= 0.3:
            return 'low'
        else:
            return 'very_low'
    
    def update_document_keywords(self, document_id):
        """Update the keywords_matched field for a document"""
        try:
            document = MedicalDocument.query.get(document_id)
            if not document:
                return
            
            # Get all active screening types
            from models import ScreeningType
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            
            # Analyze relevance
            relevance_scores = self.analyze_document_relevance(document, screening_types)
            
            # Update keywords_matched field
            matched_keywords = []
            for screening_id, data in relevance_scores.items():
                if data['score'] > 0.3:  # Only include meaningful matches
                    matched_keywords.append({
                        'screening_type_id': screening_id,
                        'screening_name': data['screening_type'].name,
                        'score': data['score'],
                        'confidence': data['confidence']
                    })
            
            document.keywords_matched = matched_keywords
            
            from app import db
            db.session.commit()
            
            self.logger.info(f"Updated keywords for document {document.filename}: {len(matched_keywords)} matches")
            
        except Exception as e:
            self.logger.error(f"Error updating document keywords for {document_id}: {str(e)}")
