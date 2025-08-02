"""
Regex-based PHI redaction with medical term protection
"""
import re
import logging
from models import PHIFilterSettings

class PHIFilter:
    
    def __init__(self):
        # Initialize PHI patterns
        self.patterns = self._initialize_patterns()
        self.medical_terms = self._load_medical_terms()
        
    def _initialize_patterns(self):
        """Initialize regex patterns for different PHI types"""
        return {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{3}\s\d{2}\s\d{4}\b',
                r'\b\d{9}\b'
            ],
            'phone': [
                r'\b\(\d{3}\)\s?\d{3}-\d{4}\b',
                r'\b\d{3}-\d{3}-\d{4}\b',
                r'\b\d{3}\.\d{3}\.\d{4}\b',
                r'\b\d{10}\b'
            ],
            'mrn': [
                r'\bMRN:?\s*\d+\b',
                r'\bMedical\s+Record\s+Number:?\s*\d+\b',
                r'\bPatient\s+ID:?\s*\d+\b'
            ],
            'insurance': [
                r'\bPolicy\s+Number:?\s*\w+\b',
                r'\bMember\s+ID:?\s*\w+\b',
                r'\bGroup\s+Number:?\s*\w+\b'
            ],
            'addresses': [
                r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b',
                r'\b[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'
            ],
            'names': [
                r'\bDear\s+(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Za-z]+\b',
                r'\bPatient:?\s+[A-Za-z]+,?\s+[A-Za-z]+\b'
            ],
            'dates': [
                r'\b\d{1,2}/\d{1,2}/\d{4}\b',
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
            ]
        }
    
    def _load_medical_terms(self):
        """Load protected medical terms that should not be redacted"""
        return {
            'vital_signs': [
                r'\b\d+/\d+\s*mmHg\b',  # Blood pressure
                r'\b\d+\s*bpm\b',       # Heart rate
                r'\b\d+\.\d+\s*°[CF]\b', # Temperature
                r'\b\d+\s*kg\b',        # Weight
                r'\b\d+\s*cm\b',        # Height
            ],
            'lab_values': [
                r'\b\d+\.\d+\s*mg/dL\b',
                r'\b\d+\.\d+\s*mmol/L\b',
                r'\b\d+\.\d+\s*%\b',
                r'\b\d+\s*U/L\b',
                r'\bA1[Cc]\s*:?\s*\d+\.\d+%?\b',
                r'\bGlucose\s*:?\s*\d+\s*mg/dL\b',
                r'\bCholesterol\s*:?\s*\d+\s*mg/dL\b'
            ],
            'medical_procedures': [
                r'\bmammogram\b',
                r'\bcolonoscopy\b',
                r'\bpap\s*smear\b',
                r'\bdexa\s*scan\b',
                r'\b(?:CT|MRI|X-ray|ultrasound)\b'
            ]
        }
    
    def filter_text(self, text):
        """Apply PHI filtering to text based on current settings"""
        if not text:
            return text
        
        # Get current settings
        settings = PHIFilterSettings.query.first()
        if not settings or not settings.filter_enabled:
            return text
        
        filtered_text = text
        
        try:
            # Protect medical terms first
            protected_spans = self._identify_protected_spans(filtered_text)
            
            # Apply filters based on settings
            if settings.filter_ssn:
                filtered_text = self._apply_filter(filtered_text, 'ssn', '[SSN REDACTED]', protected_spans)
            
            if settings.filter_phone:
                filtered_text = self._apply_filter(filtered_text, 'phone', '[PHONE REDACTED]', protected_spans)
            
            if settings.filter_mrn:
                filtered_text = self._apply_filter(filtered_text, 'mrn', '[MRN REDACTED]', protected_spans)
            
            if settings.filter_insurance:
                filtered_text = self._apply_filter(filtered_text, 'insurance', '[INSURANCE REDACTED]', protected_spans)
            
            if settings.filter_addresses:
                filtered_text = self._apply_filter(filtered_text, 'addresses', '[ADDRESS REDACTED]', protected_spans)
            
            if settings.filter_names:
                filtered_text = self._apply_filter(filtered_text, 'names', '[NAME REDACTED]', protected_spans)
            
            if settings.filter_dates:
                # Be careful with dates - don't redact medical values
                filtered_text = self._apply_date_filter(filtered_text, protected_spans)
            
            return filtered_text
            
        except Exception as e:
            logging.error(f"Error filtering PHI: {e}")
            return text  # Return original text if filtering fails
    
    def _identify_protected_spans(self, text):
        """Identify spans of text that should be protected from PHI filtering"""
        protected_spans = []
        
        for category, patterns in self.medical_terms.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    protected_spans.append((match.start(), match.end()))
        
        # Merge overlapping spans
        protected_spans.sort()
        merged_spans = []
        for start, end in protected_spans:
            if merged_spans and start <= merged_spans[-1][1]:
                merged_spans[-1] = (merged_spans[-1][0], max(merged_spans[-1][1], end))
            else:
                merged_spans.append((start, end))
        
        return merged_spans
    
    def _apply_filter(self, text, phi_type, replacement, protected_spans):
        """Apply specific PHI filter while avoiding protected spans"""
        patterns = self.patterns.get(phi_type, [])
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            
            # Process matches in reverse order to maintain string positions
            for match in reversed(matches):
                start, end = match.span()
                
                # Check if this match overlaps with any protected span
                if not self._overlaps_protected_span(start, end, protected_spans):
                    text = text[:start] + replacement + text[end:]
        
        return text
    
    def _apply_date_filter(self, text, protected_spans):
        """Apply date filtering with extra caution for medical values"""
        date_patterns = self.patterns['dates']
        
        for pattern in date_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            
            for match in reversed(matches):
                start, end = match.span()
                
                # Skip if protected
                if self._overlaps_protected_span(start, end, protected_spans):
                    continue
                
                # Additional check: don't redact if it looks like a medical measurement
                match_text = match.group()
                if self._looks_like_medical_value(text, start, end):
                    continue
                
                text = text[:start] + '[DATE REDACTED]' + text[end:]
        
        return text
    
    def _overlaps_protected_span(self, start, end, protected_spans):
        """Check if a span overlaps with any protected span"""
        for p_start, p_end in protected_spans:
            if not (end <= p_start or start >= p_end):
                return True
        return False
    
    def _looks_like_medical_value(self, text, start, end):
        """Check if a date-like pattern is actually a medical value"""
        # Look at context around the match
        context_start = max(0, start - 20)
        context_end = min(len(text), end + 20)
        context = text[context_start:context_end].lower()
        
        # Medical context indicators
        medical_indicators = [
            'bp', 'blood pressure', 'glucose', 'a1c', 'cholesterol',
            'weight', 'height', 'temperature', 'pulse', 'rate'
        ]
        
        return any(indicator in context for indicator in medical_indicators)
    
    def test_filter(self, test_text):
        """Test PHI filtering on sample text"""
        original_text = test_text
        filtered_text = self.filter_text(test_text)
        
        return {
            'original': original_text,
            'filtered': filtered_text,
            'changes_made': original_text != filtered_text
        }
    
    def get_filter_statistics(self, text):
        """Get statistics about PHI detection in text"""
        stats = {}
        
        for phi_type, patterns in self.patterns.items():
            count = 0
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                count += len(list(matches))
            stats[phi_type] = count
        
        return stats
