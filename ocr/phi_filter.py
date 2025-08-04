import re
import logging
from models import PHIFilterSettings
from app import db

class PHIFilter:
    """HIPAA-compliant PHI filtering for OCR text"""
    
    def __init__(self):
        self.settings = self._load_settings()
        
        # PHI regex patterns
        self.patterns = {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
                r'\b\d{3}\s\d{2}\s\d{4}\b',  # XXX XX XXXX
                r'\b\d{9}\b'  # XXXXXXXXX (9 consecutive digits)
            ],
            'phone': [
                r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',  # Various phone formats
                r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ],
            'mrn': [
                r'\bMRN:?\s*([A-Z0-9]{6,12})\b',  # MRN: XXXXXXXX
                r'\bMedical\s+Record\s+Number:?\s*([A-Z0-9]{6,12})\b'
            ],
            'insurance': [
                r'\bPolicy\s*#?:?\s*([A-Z0-9]{8,15})\b',
                r'\bMember\s*ID:?\s*([A-Z0-9]{8,15})\b',
                r'\bGroup\s*#?:?\s*([A-Z0-9]{6,12})\b'
            ],
            'addresses': [
                r'\b\d{1,5}\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl)\b',
                r'\b\d{5}(?:[-\s]\d{4})?\b'  # ZIP codes
            ],
            'names': [
                r'\bDear\s+(?:Mr|Mrs|Ms|Dr)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
                r'\bPatient:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
            ],
            'dates': [
                r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',  # MM/DD/YYYY, MM-DD-YYYY
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b'
            ]
        }
        
        # Medical terms to preserve (never filter these)
        self.medical_preserve_patterns = [
            r'\b\d+\s*mg/dl\b',  # Lab values
            r'\b\d+\s*mmHg\b',   # Blood pressure
            r'\b\d+/\d+\b',      # Blood pressure readings
            r'\b\d+\.\d+\s*%\b', # Percentages (like A1C)
            r'\b(?:mammogram|colonoscopy|pap smear|x-ray|mri|ct scan)\b',  # Procedures
            r'\b(?:cholesterol|glucose|hemoglobin|creatinine)\b'  # Lab tests
        ]
    
    def filter_text(self, text):
        """Apply PHI filtering to text based on current settings"""
        if not self.settings.filter_enabled or not text:
            return text
        
        # Preserve medical terms first
        preserved_terms = {}
        temp_text = text
        
        for i, pattern in enumerate(self.medical_preserve_patterns):
            matches = re.finditer(pattern, temp_text, re.IGNORECASE)
            for match in matches:
                placeholder = f"__PRESERVE_{i}_{len(preserved_terms)}__"
                preserved_terms[placeholder] = match.group()
                temp_text = temp_text.replace(match.group(), placeholder)
        
        # Apply PHI filters
        filtered_text = temp_text
        
        if self.settings.filter_ssn:
            filtered_text = self._filter_pattern_group(filtered_text, 'ssn', '[SSN REDACTED]')
        
        if self.settings.filter_phone:
            filtered_text = self._filter_pattern_group(filtered_text, 'phone', '[PHONE REDACTED]')
        
        if self.settings.filter_mrn:
            filtered_text = self._filter_pattern_group(filtered_text, 'mrn', '[MRN REDACTED]')
        
        if self.settings.filter_insurance:
            filtered_text = self._filter_pattern_group(filtered_text, 'insurance', '[INSURANCE REDACTED]')
        
        if self.settings.filter_addresses:
            filtered_text = self._filter_pattern_group(filtered_text, 'addresses', '[ADDRESS REDACTED]')
        
        if self.settings.filter_names:
            filtered_text = self._filter_pattern_group(filtered_text, 'names', '[NAME REDACTED]')
        
        if self.settings.filter_dates:
            filtered_text = self._filter_dates_preserve_medical(filtered_text)
        
        # Restore preserved medical terms
        for placeholder, original_term in preserved_terms.items():
            filtered_text = filtered_text.replace(placeholder, original_term)
        
        return filtered_text
    
    def _filter_pattern_group(self, text, pattern_group, replacement):
        """Filter a group of patterns with the same replacement"""
        patterns = self.patterns.get(pattern_group, [])
        
        for pattern in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def _filter_dates_preserve_medical(self, text):
        """Filter dates while preserving medical values like blood pressure"""
        # First preserve blood pressure readings and similar medical values
        medical_values = []
        temp_text = text
        
        # Preserve readings like "120/80", "15/10", etc. that might look like dates
        bp_pattern = r'\b\d{2,3}/\d{2,3}(?:\s*mmHg)?\b'
        for match in re.finditer(bp_pattern, temp_text):
            placeholder = f"__BP_{len(medical_values)}__"
            medical_values.append((placeholder, match.group()))
            temp_text = temp_text.replace(match.group(), placeholder)
        
        # Now filter actual dates
        for pattern in self.patterns['dates']:
            temp_text = re.sub(pattern, '[DATE REDACTED]', temp_text, flags=re.IGNORECASE)
        
        # Restore medical values
        for placeholder, original_value in medical_values:
            temp_text = temp_text.replace(placeholder, original_value)
        
        return temp_text
    
    def _load_settings(self):
        """Load PHI filter settings from database"""
        settings = PHIFilterSettings.query.first()
        if not settings:
            # Create default settings
            settings = PHIFilterSettings()
            db.session.add(settings)
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        return settings
    
    def update_settings(self, new_settings):
        """Update PHI filter settings"""
        try:
            settings = PHIFilterSettings.query.first()
            if not settings:
                settings = PHIFilterSettings()
                db.session.add(settings)
            
            # Update settings
            for key, value in new_settings.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            db.session.commit()
            self.settings = settings
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to update PHI settings: {str(e)}")
            return False
    
    def test_filter(self, test_text):
        """Test PHI filtering on sample text"""
        return {
            'original': test_text,
            'filtered': self.filter_text(test_text),
            'settings': {
                'filter_enabled': self.settings.filter_enabled,
                'filter_ssn': self.settings.filter_ssn,
                'filter_phone': self.settings.filter_phone,
                'filter_mrn': self.settings.filter_mrn,
                'filter_insurance': self.settings.filter_insurance,
                'filter_addresses': self.settings.filter_addresses,
                'filter_names': self.settings.filter_names,
                'filter_dates': self.settings.filter_dates
            }
        }
    
    def get_statistics(self):
        """Get PHI filtering statistics"""
        from models import MedicalDocument
        
        total_docs = MedicalDocument.query.count()
        filtered_docs = MedicalDocument.query.filter(MedicalDocument.phi_filtered == True).count()
        
        return {
            'total_documents': total_docs,
            'filtered_documents': filtered_docs,
            'filter_rate': (filtered_docs / total_docs * 100) if total_docs > 0 else 0,
            'settings_active': self.settings.filter_enabled
        }
