"""
Regex-based PHI redaction for HIPAA compliance
Removes personally identifiable information while preserving medical values
"""
import re
import logging
from app import db
from models import PHISettings

logger = logging.getLogger(__name__)

class PHIFilter:
    """Handles PHI filtering and redaction in OCR text"""
    
    def __init__(self):
        self.settings = None
        self.load_settings()
        
        # Medical terms to preserve (not redact)
        self.medical_terms = {
            'measurements': [
                r'\d+/\d+\s*mmHg',  # Blood pressure
                r'\d+\.\d+\s*mg/dL',  # Lab values
                r'\d+\s*mg/dL',
                r'\d+\.\d+\s*%',  # Percentages (A1C, etc.)
                r'\d+\s*%',
                r'\d+\.\d+\s*mEq/L',  # Electrolytes
                r'\d+\s*bpm',  # Heart rate
                r'\d+\.\d+\s*°F',  # Temperature
                r'\d+\s*°F',
                r'\d+\.\d+\s*°C',
                r'\d+\s*°C'
            ],
            'procedures': [
                'mammogram', 'colonoscopy', 'endoscopy', 'ct scan', 'mri',
                'x-ray', 'ultrasound', 'ecg', 'ekg', 'echo', 'stress test',
                'biopsy', 'surgery', 'procedure'
            ],
            'conditions': [
                'diabetes', 'hypertension', 'hyperlipidemia', 'copd',
                'asthma', 'pneumonia', 'bronchitis', 'infection'
            ]
        }
        
        # PHI patterns to redact
        self.phi_patterns = {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
                r'\b\d{3}\s\d{2}\s\d{4}\b',  # XXX XX XXXX
                r'\b\d{9}\b'  # XXXXXXXXX (9 consecutive digits)
            ],
            'phone': [
                r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',  # (XXX) XXX-XXXX
                r'\b\d{3}-\d{3}-\d{4}\b',  # XXX-XXX-XXXX
                r'\b\d{3}\.\d{3}\.\d{4}\b',  # XXX.XXX.XXXX
                r'\b\d{10}\b'  # XXXXXXXXXX (10 consecutive digits)
            ],
            'mrn': [
                r'\bMRN[:\s]*\d+\b',  # MRN: 12345
                r'\bMedical\s+Record\s+Number[:\s]*\d+\b',
                r'\bChart\s+Number[:\s]*\d+\b'
            ],
            'insurance': [
                r'\bPolicy\s+Number[:\s]*\w+\b',
                r'\bMember\s+ID[:\s]*\w+\b',
                r'\bGroup\s+Number[:\s]*\w+\b',
                r'\bSubscriber\s+ID[:\s]*\w+\b'
            ],
            'address': [
                r'\b\d+\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Place|Pl)\b',
                r'\b\w+,\s*[A-Z]{2}\s+\d{5}(-\d{4})?\b'  # City, ST ZIP
            ],
            'dates': [
                r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # MM-DD-YYYY
                r'\b\d{4}-\d{1,2}-\d{1,2}\b',  # YYYY-MM-DD
                # Exclude medical values that look like dates
                r'(?<!\d+/\d+\s*mmHg)\b\d{1,2}/\d{1,2}/\d{4}\b'
            ]
        }
        
        # Replacement texts
        self.replacements = {
            'ssn': '[SSN REDACTED]',
            'phone': '[PHONE REDACTED]',
            'mrn': 'MRN: [REDACTED]',
            'insurance': '[INSURANCE ID REDACTED]',
            'address': '[ADDRESS REDACTED]',
            'dates': '[DATE REDACTED]',
            'names': '[NAME REDACTED]'
        }
    
    def load_settings(self):
        """Load PHI filtering settings from database"""
        self.settings = PHISettings.query.first()
        if not self.settings:
            # Create default settings
            self.settings = PHISettings()
            db.session.add(self.settings)
            db.session.commit()
    
    def is_enabled(self):
        """Check if PHI filtering is enabled"""
        return self.settings.phi_filtering_enabled if self.settings else True
    
    def filter_text(self, text):
        """Apply PHI filtering to text"""
        if not text or not self.is_enabled():
            return text
        
        filtered_text = text
        
        # Apply each filter based on settings
        if self.settings.filter_ssn:
            filtered_text = self.filter_ssn(filtered_text)
        
        if self.settings.filter_phone:
            filtered_text = self.filter_phone_numbers(filtered_text)
        
        if self.settings.filter_mrn:
            filtered_text = self.filter_mrn(filtered_text)
        
        if self.settings.filter_insurance:
            filtered_text = self.filter_insurance_ids(filtered_text)
        
        if self.settings.filter_addresses:
            filtered_text = self.filter_addresses(filtered_text)
        
        if self.settings.filter_dates:
            filtered_text = self.filter_dates(filtered_text)
        
        # Names require special handling and are done last
        if self.settings.filter_names:
            filtered_text = self.filter_names(filtered_text)
        
        return filtered_text
    
    def filter_ssn(self, text):
        """Filter Social Security Numbers"""
        for pattern in self.phi_patterns['ssn']:
            text = re.sub(pattern, self.replacements['ssn'], text, flags=re.IGNORECASE)
        return text
    
    def filter_phone_numbers(self, text):
        """Filter phone numbers"""
        for pattern in self.phi_patterns['phone']:
            text = re.sub(pattern, self.replacements['phone'], text, flags=re.IGNORECASE)
        return text
    
    def filter_mrn(self, text):
        """Filter Medical Record Numbers"""
        for pattern in self.phi_patterns['mrn']:
            text = re.sub(pattern, self.replacements['mrn'], text, flags=re.IGNORECASE)
        return text
    
    def filter_insurance_ids(self, text):
        """Filter insurance information"""
        for pattern in self.phi_patterns['insurance']:
            text = re.sub(pattern, self.replacements['insurance'], text, flags=re.IGNORECASE)
        return text
    
    def filter_addresses(self, text):
        """Filter street addresses"""
        for pattern in self.phi_patterns['address']:
            text = re.sub(pattern, self.replacements['address'], text, flags=re.IGNORECASE)
        return text
    
    def filter_dates(self, text):
        """Filter dates while preserving medical measurements"""
        # First, protect medical measurements that contain slashes
        protected_text = text
        medical_patterns = []
        
        # Identify and temporarily replace medical measurements
        for measurement_pattern in self.medical_terms['measurements']:
            matches = re.finditer(measurement_pattern, protected_text, re.IGNORECASE)
            for match in matches:
                placeholder = f"__MEDICAL_{len(medical_patterns)}__"
                medical_patterns.append(match.group())
                protected_text = protected_text.replace(match.group(), placeholder, 1)
        
        # Now filter dates
        for pattern in self.phi_patterns['dates']:
            protected_text = re.sub(pattern, self.replacements['dates'], protected_text, flags=re.IGNORECASE)
        
        # Restore medical measurements
        for i, medical_value in enumerate(medical_patterns):
            placeholder = f"__MEDICAL_{i}__"
            protected_text = protected_text.replace(placeholder, medical_value)
        
        return protected_text
    
    def filter_names(self, text):
        """Filter patient names (basic implementation)"""
        # This is a simplified implementation
        # In practice, you'd want to have a list of known patient names
        # or use more sophisticated NLP techniques
        
        # Common name patterns (this is very basic and may need improvement)
        name_patterns = [
            r'\bPatient\s+Name[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            r'\bName[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        ]
        
        for pattern in name_patterns:
            text = re.sub(pattern, f'Patient Name: {self.replacements["names"]}', text, flags=re.IGNORECASE)
        
        return text
    
    def is_medical_term(self, text):
        """Check if text contains medical terminology that should be preserved"""
        text_lower = text.lower()
        
        # Check procedures
        for procedure in self.medical_terms['procedures']:
            if procedure in text_lower:
                return True
        
        # Check conditions
        for condition in self.medical_terms['conditions']:
            if condition in text_lower:
                return True
        
        # Check measurements
        for measurement_pattern in self.medical_terms['measurements']:
            if re.search(measurement_pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def get_filter_statistics(self, text):
        """Get statistics about what was filtered from text"""
        if not text:
            return {}
        
        stats = {
            'ssn_found': 0,
            'phone_found': 0,
            'mrn_found': 0,
            'insurance_found': 0,
            'address_found': 0,
            'dates_found': 0,
            'total_redactions': 0
        }
        
        # Count each type of PHI found
        for phi_type, patterns in self.phi_patterns.items():
            count = 0
            for pattern in patterns:
                matches = re.findall(pattern, text, flags=re.IGNORECASE)
                count += len(matches)
            
            stats[f'{phi_type}_found'] = count
            stats['total_redactions'] += count
        
        return stats
    
    def test_filter(self, test_text):
        """Test PHI filtering on sample text (for admin interface)"""
        if not test_text:
            return {'original': '', 'filtered': '', 'statistics': {}}
        
        statistics = self.get_filter_statistics(test_text)
        filtered = self.filter_text(test_text)
        
        return {
            'original': test_text,
            'filtered': filtered,
            'statistics': statistics,
            'settings_used': {
                'phi_filtering_enabled': self.settings.phi_filtering_enabled,
                'filter_ssn': self.settings.filter_ssn,
                'filter_phone': self.settings.filter_phone,
                'filter_mrn': self.settings.filter_mrn,
                'filter_insurance': self.settings.filter_insurance,
                'filter_addresses': self.settings.filter_addresses,
                'filter_dates': self.settings.filter_dates,
                'filter_names': self.settings.filter_names
            }
        }
