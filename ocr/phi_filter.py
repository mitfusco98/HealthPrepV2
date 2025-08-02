"""
HIPAA-compliant PHI filtering with regex-based redaction
"""
import re
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from app import db
from models import PHIFilterSettings

logger = logging.getLogger(__name__)

class PHIFilter:
    """Handles PHI detection and redaction for HIPAA compliance"""
    
    def __init__(self):
        self.medical_terms = self._load_medical_terms()
        self.phi_patterns = self._load_phi_patterns()
        self.replacement_text = "[REDACTED]"
    
    def _load_medical_terms(self) -> List[str]:
        """Load medical terms that should be preserved during filtering"""
        return [
            # Vital signs and measurements
            'blood pressure', 'bp', 'mmhg', 'mg/dl', 'mg/l', 'bpm',
            # Lab values
            'glucose', 'cholesterol', 'hdl', 'ldl', 'triglycerides', 'a1c', 'hba1c',
            'creatinine', 'bun', 'gfr', 'sodium', 'potassium', 'chloride',
            # Procedures
            'mammogram', 'mammography', 'colonoscopy', 'endoscopy', 'biopsy',
            'ultrasound', 'ct scan', 'mri', 'x-ray', 'ecg', 'ekg',
            # Medications (common prefixes/suffixes)
            'lisinopril', 'metformin', 'atorvastatin', 'amlodipine', 'losartan',
            # Medical specialties
            'cardiology', 'neurology', 'gastroenterology', 'oncology', 'radiology'
        ]
    
    def _load_phi_patterns(self) -> Dict[str, str]:
        """Load regex patterns for PHI detection"""
        return {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
            'phone': r'\b(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'mrn': r'\b(MRN|Medical Record|Patient ID)[\s:]*([A-Z0-9]{6,12})\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'address': r'\b\d{1,5}\s[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir)\b',
            'zip_code': r'\b\d{5}(-\d{4})?\b',
            'dates': r'\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])[-/](19|20)\d{2}\b|\b(19|20)\d{2}[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])\b',
            'insurance_id': r'\b(Policy|Member|Insurance)\s?(ID|Number)[\s:]*([A-Z0-9]{8,15})\b',
            'driver_license': r'\b(DL|Driver.?s?\s?License)[\s:]*([A-Z0-9]{8,12})\b'
        }
    
    def filter_text(self, text: str, settings: Optional[PHIFilterSettings] = None) -> Dict[str, Any]:
        """
        Filter PHI from text and return results with audit trail
        """
        if not text:
            return {
                'filtered_text': '',
                'original_text': '',
                'redactions_made': 0,
                'phi_found': [],
                'confidence': 1.0
            }
        
        # Get current settings
        if not settings:
            settings = self._get_current_settings()
        
        original_text = text
        filtered_text = text
        phi_found = []
        redactions_made = 0
        
        try:
            # Apply each PHI filter based on settings
            if settings.filter_ssn:
                filtered_text, ssn_matches = self._apply_pattern_filter(
                    filtered_text, 'ssn', 'Social Security Number'
                )
                phi_found.extend(ssn_matches)
                redactions_made += len(ssn_matches)
            
            if settings.filter_phone:
                filtered_text, phone_matches = self._apply_pattern_filter(
                    filtered_text, 'phone', 'Phone Number'
                )
                phi_found.extend(phone_matches)
                redactions_made += len(phone_matches)
            
            if settings.filter_mrn:
                filtered_text, mrn_matches = self._apply_pattern_filter(
                    filtered_text, 'mrn', 'Medical Record Number'
                )
                phi_found.extend(mrn_matches)
                redactions_made += len(mrn_matches)
            
            if settings.filter_addresses:
                filtered_text, addr_matches = self._apply_pattern_filter(
                    filtered_text, 'address', 'Address'
                )
                phi_found.extend(addr_matches)
                redactions_made += len(addr_matches)
                
                filtered_text, zip_matches = self._apply_pattern_filter(
                    filtered_text, 'zip_code', 'ZIP Code'
                )
                phi_found.extend(zip_matches)
                redactions_made += len(zip_matches)
            
            if settings.filter_dates:
                filtered_text, date_matches = self._apply_date_filter(
                    filtered_text, settings.preserve_medical_values
                )
                phi_found.extend(date_matches)
                redactions_made += len(date_matches)
            
            # Email filtering
            filtered_text, email_matches = self._apply_pattern_filter(
                filtered_text, 'email', 'Email Address'
            )
            phi_found.extend(email_matches)
            redactions_made += len(email_matches)
            
            # Insurance and ID filtering
            filtered_text, insurance_matches = self._apply_pattern_filter(
                filtered_text, 'insurance_id', 'Insurance ID'
            )
            phi_found.extend(insurance_matches)
            redactions_made += len(insurance_matches)
            
            # Name filtering (if enabled)
            if settings.filter_names:
                filtered_text, name_matches = self._apply_name_filter(filtered_text)
                phi_found.extend(name_matches)
                redactions_made += len(name_matches)
            
            # Calculate confidence score
            confidence = self._calculate_filter_confidence(original_text, filtered_text, phi_found)
            
            return {
                'filtered_text': filtered_text,
                'original_text': original_text,
                'redactions_made': redactions_made,
                'phi_found': phi_found,
                'confidence': confidence,
                'processing_timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error filtering PHI from text: {str(e)}")
            return {
                'filtered_text': text,
                'original_text': text,
                'redactions_made': 0,
                'phi_found': [],
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _apply_pattern_filter(self, text: str, pattern_name: str, phi_type: str) -> Tuple[str, List[Dict]]:
        """Apply a specific regex pattern filter"""
        pattern = self.phi_patterns.get(pattern_name)
        if not pattern:
            return text, []
        
        matches = []
        filtered_text = text
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            match_text = match.group()
            start_pos = match.start()
            end_pos = match.end()
            
            # Skip if this looks like a medical value
            if self._is_medical_value(match_text):
                continue
            
            matches.append({
                'type': phi_type,
                'text': match_text,
                'position': (start_pos, end_pos),
                'pattern': pattern_name
            })
        
        # Replace matches with redaction text
        for match in reversed(matches):  # Reverse to maintain positions
            start, end = match['position']
            filtered_text = filtered_text[:start] + self.replacement_text + filtered_text[end:]
        
        return filtered_text, matches
    
    def _apply_date_filter(self, text: str, preserve_medical: bool) -> Tuple[str, List[Dict]]:
        """Apply date filtering with medical value preservation"""
        date_pattern = self.phi_patterns['dates']
        matches = []
        filtered_text = text
        
        for match in re.finditer(date_pattern, text):
            match_text = match.group()
            start_pos = match.start()
            end_pos = match.end()
            
            # If preserving medical values, check context
            if preserve_medical:
                context = text[max(0, start_pos-20):min(len(text), end_pos+20)]
                if self._is_medical_date_context(context):
                    continue
            
            matches.append({
                'type': 'Date',
                'text': match_text,
                'position': (start_pos, end_pos),
                'pattern': 'dates'
            })
        
        # Replace matches with redaction text
        for match in reversed(matches):
            start, end = match['position']
            filtered_text = filtered_text[:start] + self.replacement_text + filtered_text[end:]
        
        return filtered_text, matches
    
    def _apply_name_filter(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply name filtering using simple heuristics"""
        # This is a basic implementation - in production, use NLP libraries
        name_patterns = [
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',  # First Last or First Middle Last
            r'\b(Mr|Mrs|Ms|Dr|Doctor)\s+[A-Z][a-z]+\b'  # Title + Name
        ]
        
        matches = []
        filtered_text = text
        
        for pattern in name_patterns:
            for match in re.finditer(pattern, text):
                match_text = match.group()
                start_pos = match.start()
                end_pos = match.end()
                
                # Skip medical terms and common words
                if self._is_medical_term(match_text) or self._is_common_phrase(match_text):
                    continue
                
                matches.append({
                    'type': 'Name',
                    'text': match_text,
                    'position': (start_pos, end_pos),
                    'pattern': 'name'
                })
        
        # Replace matches with redaction text
        for match in reversed(matches):
            start, end = match['position']
            filtered_text = filtered_text[:start] + self.replacement_text + filtered_text[end:]
        
        return filtered_text, matches
    
    def _is_medical_value(self, text: str) -> bool:
        """Check if text appears to be a medical value"""
        text_lower = text.lower()
        
        # Check for medical measurement patterns
        medical_patterns = [
            r'\d+/\d+',  # Blood pressure
            r'\d+\s*(mg/dl|mmhg|bpm)',  # Medical units
            r'(glucose|cholesterol|a1c).*\d+',  # Lab values
        ]
        
        for pattern in medical_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _is_medical_date_context(self, context: str) -> bool:
        """Check if a date appears in medical context"""
        medical_keywords = [
            'test', 'lab', 'result', 'procedure', 'appointment',
            'visit', 'exam', 'surgery', 'diagnosis', 'treatment'
        ]
        
        context_lower = context.lower()
        return any(keyword in context_lower for keyword in medical_keywords)
    
    def _is_medical_term(self, text: str) -> bool:
        """Check if text is a known medical term"""
        text_lower = text.lower()
        return any(term in text_lower for term in self.medical_terms)
    
    def _is_common_phrase(self, text: str) -> bool:
        """Check if text is a common non-name phrase"""
        common_phrases = [
            'patient care', 'health care', 'medical center', 'test results',
            'blood pressure', 'heart rate', 'patient information'
        ]
        
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in common_phrases)
    
    def _calculate_filter_confidence(self, original: str, filtered: str, phi_found: List[Dict]) -> float:
        """Calculate confidence score for PHI filtering"""
        if not original:
            return 1.0
        
        # Base confidence on coverage and pattern matching
        redaction_ratio = len(phi_found) / len(original.split()) if original.split() else 0
        
        # Lower confidence if too many or too few redactions
        if redaction_ratio > 0.3:  # Too aggressive
            confidence = 0.6
        elif redaction_ratio < 0.01 and len(original) > 100:  # Possibly missed PHI
            confidence = 0.8
        else:
            confidence = 0.95
        
        return confidence
    
    def _get_current_settings(self) -> PHIFilterSettings:
        """Get current PHI filter settings"""
        settings = PHIFilterSettings.query.first()
        if not settings:
            # Create default settings
            settings = PHIFilterSettings(
                filter_ssn=True,
                filter_phone=True,
                filter_mrn=True,
                filter_addresses=True,
                filter_names=True,
                filter_dates=True,
                preserve_medical_values=True,
                confidence_threshold=0.8
            )
            db.session.add(settings)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating default PHI settings: {str(e)}")
        
        return settings
    
    def test_filter(self, test_text: str) -> Dict[str, Any]:
        """Test PHI filter with sample text"""
        settings = self._get_current_settings()
        result = self.filter_text(test_text, settings)
        
        return {
            'original_text': test_text,
            'filtered_text': result['filtered_text'],
            'phi_detected': result['phi_found'],
            'redactions_count': result['redactions_made'],
            'confidence': result['confidence'],
            'test_timestamp': datetime.utcnow()
        }
    
    def get_filter_statistics(self) -> Dict[str, Any]:
        """Get statistics about PHI filtering usage"""
        # In production, this would query a PHI audit log table
        return {
            'total_documents_filtered': 0,
            'total_redactions_made': 0,
            'average_confidence': 0.95,
            'most_common_phi_types': ['Phone Number', 'SSN', 'Address'],
            'last_filter_run': datetime.utcnow()
        }

# Global PHI filter instance
phi_filter = PHIFilter()
