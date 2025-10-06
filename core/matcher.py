"""
Advanced fuzzy keyword matching and document matching functionality with semantic detection
"""
from app import db
from models import Document, Screening, ScreeningType, ScreeningDocumentMatch
from .fuzzy_detection import FuzzyDetectionEngine
from datetime import date
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
            self.logger.debug(f"Document {document.id} has no OCR text")
            return matches
        
        # Get patient's existing screenings directly (respects org scoping via Screening records)
        screenings = Screening.query.filter_by(patient_id=document.patient_id).all()
        self.logger.debug(f"Found {len(screenings)} screenings for patient {document.patient_id}")
        
        for screening in screenings:
            confidence = self._calculate_match_confidence(document, screening.screening_type)
            self.logger.debug(f"Document {document.id} vs Screening {screening.id} ({screening.screening_type.name}): confidence={confidence:.3f}")
            
            if confidence > 0.75:  # Raised threshold to reduce false positives
                matches.append((screening.id, confidence))
                self.logger.info(f"MATCH FOUND: Document {document.id} matches Screening {screening.id} with confidence {confidence:.3f}")
        
        self.logger.info(f"Document {document.id} matching complete: {len(matches)} matches found")
        return matches
    
    def find_screening_matches(self, screening, exclude_dismissed=True):
        """
        Find all documents that match this screening
        
        Args:
            screening: Screening object to find matches for
            exclude_dismissed: If True, filters out dismissed matches (default True)
        
        Returns:
            List of match dicts sorted by document_date (newest first)
        """
        from models import DismissedDocumentMatch, db
        matches = []
        candidate_matches = []
        
        documents = Document.query.filter_by(patient_id=screening.patient_id).all()
        
        # First pass: find all potential matches
        for document in documents:
            if document.ocr_text:
                confidence = self._calculate_match_confidence(document, screening.screening_type)
                
                if confidence > 0.75:
                    document_date = getattr(document, 'document_date', None) or document.created_at
                    candidate_matches.append({
                        'document': document,
                        'confidence': confidence,
                        'document_date': document_date
                    })
        
        # If dismissal filtering enabled, batch query for all dismissed document IDs
        if exclude_dismissed and candidate_matches:
            doc_ids = [m['document'].id for m in candidate_matches]
            dismissed_ids = set(
                row[0] for row in db.session.query(DismissedDocumentMatch.document_id).filter(
                    DismissedDocumentMatch.document_id.in_(doc_ids),
                    DismissedDocumentMatch.screening_id == screening.id,
                    DismissedDocumentMatch.is_active == True
                ).all()
            )
            
            # Filter out dismissed matches using batched set
            matches = [m for m in candidate_matches if m['document'].id not in dismissed_ids]
        else:
            matches = candidate_matches
        
        return sorted(matches, key=lambda x: x['document_date'] or date.min, reverse=True)
    
    def get_document_match_details(self, document, include_dismissed=False):
        """
        Get detailed match information for a document including matched keywords.
        
        Args:
            document: Document or FHIRDocument to analyze
            include_dismissed: If True, returns dict with 'active' and 'dismissed' lists.
                             If False, returns only active matches (default).
        
        Returns:
            If include_dismissed=False: List of active match dicts
            If include_dismissed=True: Dict with 'active' and 'dismissed' lists
        """
        from models import DismissedDocumentMatch, Document, FHIRDocument
        
        active_matches = []
        dismissed_matches = []
        
        if not document.ocr_text:
            return {'active': [], 'dismissed': []} if include_dismissed else []
        
        # Determine if this is a local Document or FHIRDocument
        is_fhir = isinstance(document, FHIRDocument)
        
        # Get patient's screenings
        screenings = Screening.query.filter_by(patient_id=document.patient_id).all()
        
        for screening in screenings:
            confidence, matched_keywords = self._calculate_match_with_keywords(document, screening.screening_type)
            
            if confidence > 0.75:
                # Check if this match has been dismissed
                dismissal_query = DismissedDocumentMatch.query.filter_by(
                    screening_id=screening.id,
                    is_active=True
                )
                
                if is_fhir:
                    dismissal_query = dismissal_query.filter_by(fhir_document_id=document.id)
                else:
                    dismissal_query = dismissal_query.filter_by(document_id=document.id)
                
                dismissal = dismissal_query.first()
                
                match_data = {
                    'screening_id': screening.id,
                    'screening_name': screening.screening_type.display_name,
                    'screening_type_name': screening.screening_type.name,
                    'confidence': confidence,
                    'matched_keywords': matched_keywords
                }
                
                if dismissal:
                    match_data['dismissal_id'] = dismissal.id
                    match_data['dismissal_reason'] = dismissal.dismissal_reason
                    dismissed_matches.append(match_data)
                else:
                    active_matches.append(match_data)
        
        if include_dismissed:
            return {'active': active_matches, 'dismissed': dismissed_matches}
        else:
            return active_matches
    
    def _calculate_match_with_keywords(self, document, screening_type):
        """
        Calculate confidence AND return matched keywords for highlighting.
        Returns (confidence, matched_keywords_list)
        """
        import re
        from models import FHIRDocument
        
        # Hybrid approach: use both filename/title AND OCR text for comprehensive matching
        # Handle both Document (has 'filename') and FHIRDocument (has 'title')
        if isinstance(document, FHIRDocument):
            filename = document.title or document.document_type_display or ''
        else:
            filename = getattr(document, 'filename', '') or ''
        
        ocr_text = document.ocr_text or ''
        
        if not filename and not ocr_text:
            return 0.0, []
        
        # Only use explicit keywords - NO fallback to screening type name
        keywords = screening_type.keywords_list
        if not keywords:
            return 0.0, []
        
        # Remove generic stopwords that cause false positives
        stopwords = {'review', 'note', 'report', 'imaging', 'result', 'clinic', 'screening', 'test', 'exam'}
        valid_keywords = [k for k in keywords if k.lower() not in stopwords]
        
        if not valid_keywords:
            return 0.0, []
        
        # Check for matches in both filename and OCR text
        filename_matches = []
        ocr_matches = []
        
        for keyword in valid_keywords:
            # Handle multi-word keywords: require sequential word matching
            if ' ' in keyword:
                # Multi-word: escape each word and require sequential matching with whitespace
                escaped_words = [re.escape(word) for word in keyword.split()]
                pattern = r'\b' + r'\s+'.join(escaped_words) + r'\b'
            else:
                # Single word: exact word boundary matching
                pattern = r'\b' + re.escape(keyword) + r'\b'
            
            # Check filename matches
            if filename and re.search(pattern, filename, re.IGNORECASE):
                filename_matches.append(keyword)
            
            # Check OCR text matches
            if ocr_text and re.search(pattern, ocr_text, re.IGNORECASE):
                ocr_matches.append(keyword)
        
        # Calculate confidence based on matches found
        if filename_matches or ocr_matches:
            # Start with base confidence
            confidence = 0.0
            
            # Filename matches are very reliable (high confidence)
            if filename_matches:
                confidence += 0.9  # High confidence for filename matches
                if len(filename_matches) > 1:
                    confidence += min(0.1, (len(filename_matches) - 1) * 0.02)  # Small bonus for multiple
            
            # OCR matches are also reliable but slightly lower than filename
            if ocr_matches:
                ocr_confidence = 0.8  # Base confidence for OCR matches
                if len(ocr_matches) > 1:
                    ocr_confidence += min(0.15, (len(ocr_matches) - 1) * 0.03)  # Bonus for multiple OCR matches
                
                # If we already have filename matches, OCR adds additional confidence
                if filename_matches:
                    confidence += ocr_confidence * 0.3  # 30% additional confidence from OCR when filename already matches
                else:
                    confidence += ocr_confidence  # Full OCR confidence if no filename match
            
            # Return confidence and all matched keywords (deduplicated)
            all_matched = list(set(filename_matches + ocr_matches))
            final_confidence = min(confidence, 1.0)
            return final_confidence, all_matched
        
        # No exact matches = zero confidence
        return 0.0, []
    
    def _calculate_match_confidence(self, document, screening_type):
        """Calculate confidence score using intelligent hybrid filename + OCR keyword matching"""
        confidence, _ = self._calculate_match_with_keywords(document, screening_type)
        return confidence
    
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
