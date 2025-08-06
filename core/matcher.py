"""
Advanced fuzzy keyword matching and document matching functionality with semantic detection
"""
from app import db
from models import Document, Screening, ScreeningType, ScreeningDocumentMatch
from .fuzzy_detection import FuzzyDetectionEngine
import logging

class DocumentMatcher:
    """Handles document matching against screening criteria using advanced fuzzy matching"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.fuzzy_engine = FuzzyDetectionEngine()
        
        # Legacy term mappings (maintained for backward compatibility)
        self.term_mappings = {
            'dxa': ['dexa', 'bone density', 'densitometry'],
            'mammogram': ['mammography', 'breast imaging'],
            'colonoscopy': ['colonography', 'colon screening'],
            'pap': ['pap smear', 'cervical screening', 'cytology'],
            'a1c': ['hemoglobin a1c', 'hba1c', 'glycohemoglobin'],
            'lipid': ['cholesterol', 'lipid panel', 'lipids'],
            'cbc': ['complete blood count', 'blood count'],
            'echo': ['echocardiogram', 'cardiac echo'],
            'ekg': ['ecg', 'electrocardiogram'],
            'stress test': ['cardiac stress', 'exercise test']
        }
    
    def find_document_matches(self, document):
        """Find all screenings that match this document"""
        matches = []
        
        if not document.ocr_text:
            return matches
        
        screening_types = ScreeningType.query.filter_by(is_active=True).all()
        
        for screening_type in screening_types:
            confidence = self._calculate_match_confidence(document, screening_type)
            
            if confidence > 0.3:  # Minimum confidence threshold
                # Find screenings of this type for the patient
                screenings = Screening.query.filter_by(
                    patient_id=document.patient_id,
                    screening_type_id=screening_type.id
                ).all()
                
                for screening in screenings:
                    matches.append((screening.id, confidence))
        
        return matches
    
    def find_screening_matches(self, screening):
        """Find all documents that match this screening"""
        matches = []
        
        documents = Document.query.filter_by(patient_id=screening.patient_id).all()
        
        for document in documents:
            if document.ocr_text:
                confidence = self._calculate_match_confidence(document, screening.screening_type)
                
                if confidence > 0.3:
                    matches.append({
                        'document': document,
                        'confidence': confidence,
                        'document_date': document.document_date
                    })
        
        return sorted(matches, key=lambda x: x['document_date'] or date.min, reverse=True)
    
    def _calculate_match_confidence(self, document, screening_type):
        """Calculate confidence score for document-screening match using advanced fuzzy detection"""
        confidence = 0.0
        
        # Get text to search (filename + OCR text)
        search_text = f"{document.filename or ''} {document.ocr_text or ''}".strip()
        
        if not search_text:
            return 0.0
        
        # Use advanced fuzzy matching for keywords
        keywords = screening_type.keywords_list
        if keywords:
            # Get fuzzy matches for all keywords
            fuzzy_matches = self.fuzzy_engine.fuzzy_match_keywords(
                search_text, keywords, threshold=0.6
            )
            
            if fuzzy_matches:
                # Calculate weighted confidence based on best matches
                best_match_confidence = fuzzy_matches[0][1]  # Highest confidence
                match_count = len(fuzzy_matches)
                
                # Base confidence from best match
                confidence += best_match_confidence * 0.5
                
                # Bonus for multiple keyword matches
                if match_count > 1:
                    multi_match_bonus = min(0.2, (match_count - 1) * 0.05)
                    confidence += multi_match_bonus
                
                self.logger.debug(f"Fuzzy matches for {screening_type.name}: {fuzzy_matches}")
        
        # Check document type alignment
        if document.document_type:
            type_confidence = self._get_document_type_confidence(
                document.document_type, screening_type.name.lower()
            )
            confidence += type_confidence * 0.15
        
        # Enhanced medical terminology check using fuzzy engine
        terminology_confidence = self._check_enhanced_medical_terminology(
            search_text, screening_type.name.lower()
        )
        confidence += terminology_confidence * 0.25
        
        # Semantic term extraction bonus
        semantic_terms = self.fuzzy_engine.extract_semantic_terms(search_text)
        if semantic_terms.get('medical_terms'):
            confidence += min(0.1, len(semantic_terms['medical_terms']) * 0.02)
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def _fuzzy_match_keyword(self, keyword, text):
        """Legacy fuzzy matching method - replaced by FuzzyDetectionEngine"""
        # Use the new fuzzy detection engine for better results
        matches = self.fuzzy_engine.fuzzy_match_keywords(text, [keyword], threshold=0.6)
        return matches[0][1] if matches else 0.0
    
    def _get_document_type_confidence(self, doc_type, screening_name):
        """Get confidence based on document type alignment with screening"""
        type_mappings = {
            'lab': ['a1c', 'cholesterol', 'lipid', 'glucose', 'cbc', 'blood'],
            'imaging': ['mammogram', 'dxa', 'dexa', 'ct', 'mri', 'ultrasound', 'xray'],
            'consult': ['cardiology', 'oncology', 'endocrinology', 'specialty'],
            'hospital': ['admission', 'discharge', 'emergency', 'hospital']
        }
        
        if doc_type in type_mappings:
            for term in type_mappings[doc_type]:
                if term in screening_name:
                    return 0.8
        
        return 0.0
    
    def _check_medical_terminology(self, text, screening_name):
        """Legacy medical terminology check - kept for compatibility"""
        confidence = 0.0
        
        for main_term, variants in self.term_mappings.items():
            if main_term in screening_name:
                # Check if any variant appears in the text
                for variant in variants + [main_term]:
                    if variant in text:
                        confidence = max(confidence, 0.8)
                        break
        
        return confidence
    
    def _check_enhanced_medical_terminology(self, text, screening_name):
        """Enhanced medical terminology check using fuzzy detection engine"""
        # Extract all possible screening name variations
        screening_variations = self.fuzzy_engine._get_keyword_variations(screening_name)
        
        # Use fuzzy matching to find terminology matches
        matches = self.fuzzy_engine.fuzzy_match_keywords(
            text, screening_variations, threshold=0.7
        )
        
        # Return confidence based on best match
        return matches[0][1] if matches else 0.0
    
    def update_all_matches(self):
        """Update all document-screening matches in the database"""
        self.logger.info("Starting to update all document-screening matches")
        
        # Clear existing matches
        ScreeningDocumentMatch.query.delete()
        
        # Process all documents
        documents = Document.query.filter(Document.ocr_text.isnot(None)).all()
        
        for document in documents:
            matches = self.find_document_matches(document)
            
            for screening_id, confidence in matches:
                match = ScreeningDocumentMatch(
                    screening_id=screening_id,
                    document_id=document.id,
                    match_confidence=confidence
                )
                db.session.add(match)
        
        db.session.commit()
        self.logger.info("Completed updating all document-screening matches")
    
    def suggest_keywords_for_screening(self, screening_type_id, sample_documents=None):
        """Suggest keywords for a screening type based on document analysis"""
        screening_type = ScreeningType.query.get(screening_type_id)
        if not screening_type:
            return []
        
        # Get sample documents if not provided
        if not sample_documents:
            sample_documents = Document.query.limit(50).all()
        
        # Extract text from documents
        document_texts = []
        for doc in sample_documents:
            text = f"{doc.filename or ''} {doc.ocr_text or ''}".strip()
            if text:
                document_texts.append(text)
        
        # Use fuzzy engine to suggest keywords
        existing_keywords = screening_type.keywords_list
        suggestions = []
        
        for text in document_texts[:10]:  # Analyze first 10 documents
            text_suggestions = self.fuzzy_engine.suggest_keywords(text, existing_keywords)
            suggestions.extend(text_suggestions)
        
        # Remove duplicates and validate relevance
        unique_suggestions = list(set(suggestions))
        validated_suggestions = []
        
        for suggestion in unique_suggestions:
            relevance = self.fuzzy_engine.validate_keyword_relevance(suggestion, document_texts)
            if relevance > 0.3:  # Only include relevant suggestions
                validated_suggestions.append((suggestion, relevance))
        
        # Sort by relevance and return top suggestions
        validated_suggestions.sort(key=lambda x: x[1], reverse=True)
        return [suggestion for suggestion, _ in validated_suggestions[:10]]
    
    def analyze_document_content(self, document):
        """Analyze document content using fuzzy detection for semantic understanding"""
        if not document:
            return {}
        
        text = f"{document.filename or ''} {document.ocr_text or ''}".strip()
        if not text:
            return {}
        
        # Extract semantic terms
        semantic_analysis = self.fuzzy_engine.extract_semantic_terms(text)
        
        # Add confidence scores for detected terms
        analysis = {
            'semantic_terms': semantic_analysis,
            'suggested_keywords': self.fuzzy_engine.suggest_keywords(text),
            'document_complexity': len(text.split()) if text else 0,
            'has_medical_content': bool(semantic_analysis.get('medical_terms'))
        }
        
        return analysis

from datetime import date
