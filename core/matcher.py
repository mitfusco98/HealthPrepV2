"""
Fuzzy keyword matching and document matching functionality
"""
from app import db
from models import Document, Screening, ScreeningType, ScreeningDocumentMatch
from difflib import SequenceMatcher
import re
import logging

class DocumentMatcher:
    """Handles document matching against screening criteria using fuzzy matching"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Common medical terminology mappings for fuzzy detection
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
        """Calculate confidence score for document-screening match"""
        confidence = 0.0
        
        # Get text to search (filename + OCR text)
        search_text = f"{document.filename} {document.ocr_text or ''}".lower()
        
        # Check direct keyword matches
        keywords = screening_type.keywords_list
        if keywords:
            for keyword in keywords:
                keyword = keyword.lower().strip()
                if keyword in search_text:
                    confidence += 0.4
                else:
                    # Check fuzzy matches
                    fuzzy_confidence = self._fuzzy_match_keyword(keyword, search_text)
                    confidence += fuzzy_confidence * 0.3
        
        # Check document type alignment
        if document.document_type:
            type_confidence = self._get_document_type_confidence(
                document.document_type, screening_type.name.lower()
            )
            confidence += type_confidence * 0.2
        
        # Check medical terminology mappings
        terminology_confidence = self._check_medical_terminology(
            search_text, screening_type.name.lower()
        )
        confidence += terminology_confidence * 0.3
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def _fuzzy_match_keyword(self, keyword, text):
        """Perform fuzzy matching for a keyword in text"""
        best_ratio = 0.0
        
        # Split text into words for better matching
        words = re.findall(r'\b\w+\b', text.lower())
        
        for word in words:
            ratio = SequenceMatcher(None, keyword, word).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        
        # Also check for partial matches in phrases
        for i in range(len(words) - len(keyword.split()) + 1):
            phrase = ' '.join(words[i:i + len(keyword.split())])
            ratio = SequenceMatcher(None, keyword, phrase).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        
        # Return confidence only if similarity is high enough
        return best_ratio if best_ratio > 0.6 else 0.0
    
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
        """Check for medical terminology matches using predefined mappings"""
        confidence = 0.0
        
        for main_term, variants in self.term_mappings.items():
            if main_term in screening_name:
                # Check if any variant appears in the text
                for variant in variants + [main_term]:
                    if variant in text:
                        confidence = max(confidence, 0.8)
                        break
        
        return confidence
    
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

from datetime import date
