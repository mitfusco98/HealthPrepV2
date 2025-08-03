"""
PHI filtering and HIPAA compliance
Regex-based pattern removal with medical term protection
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any
from models import PHIFilterSettings
from app import db

logger = logging.getLogger(__name__)

class PHIFilter:
    """Handles PHI filtering and redaction for HIPAA compliance"""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.medical_terms = self._initialize_medical_terms()
        self.replacement_char = '[REDACTED]'
        
    def _initialize_patterns(self) -> Dict[str, str]:
        """Initialize regex patterns for different PHI types"""
        return {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
            'phone': r'\b\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'mrn': r'\b(?:MRN|Medical Record|Patient ID)[\s:]*([A-Z0-9]{6,12})\b',
            'insurance': r'\b(?:Policy|Member|Insurance)[\s:]*([\dA-Z]{8,15})\b',
            'address': r'\b\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'dates': r'\b(?:0?[1-9]|1[0-2])[\/\-](?:0?[1-9]|[12]\d|3[01])[\/\-](?:19|20)\d{2}\b',
            'names': r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        }
    
    def _initialize_medical_terms(self) -> List[str]:
        """Initialize protected medical terms that should not be filtered"""
        return [
            # Vital signs and measurements
            'blood pressure', 'bp', 'systolic', 'diastolic', 'mmhg',
            'heart rate', 'hr', 'bpm', 'temperature', 'temp', 'fahrenheit', 'celsius',
            'weight', 'height', 'bmi', 'body mass index',
            
            # Lab values and units
            'mg/dl', 'mmol/l', 'g/dl', 'mcg', 'ng/ml', 'iu/l', 'pg/ml',
            'glucose', 'cholesterol', 'triglycerides', 'hdl', 'ldl',
            'hemoglobin', 'hematocrit', 'wbc', 'rbc', 'platelets',
            'creatinine', 'bun', 'gfr', 'sodium', 'potassium', 'chloride',
            'a1c', 'hba1c', 'tsh', 't3', 't4', 'psa',
            
            # Medical procedures
            'mammogram', 'colonoscopy', 'endoscopy', 'biopsy', 'surgery',
            'ct scan', 'mri', 'ultrasound', 'x-ray', 'echocardiogram', 'ekg', 'ecg',
            'stress test', 'pap smear', 'bone density', 'dxa', 'dexa',
            
            # Medical conditions
            'diabetes', 'hypertension', 'hyperlipidemia', 'obesity',
            'coronary artery disease', 'heart disease', 'stroke', 'cancer',
            'pneumonia', 'bronchitis', 'asthma', 'copd',
            
            # Medications and dosages
            'mg', 'ml', 'mcg', 'units', 'tablets', 'capsules',
            'twice daily', 'once daily', 'as needed', 'prn',
            'metformin', 'lisinopril', 'atorvastatin', 'aspirin'
        ]
    
    def filter_text(self, text: str, settings: PHIFilterSettings = None) -> Tuple[str, Dict[str, int]]:
        """
        Filter PHI from text while preserving medical terminology
        Returns filtered text and statistics
        """
        if not text:
            return text, {}
        
        if not settings:
            settings = self._get_filter_settings()
        
        if not settings.is_enabled:
            return text, {'filtered': 0}
        
        filtered_text = text
        stats = {}
        
        # Apply filters based on settings
        if settings.filter_ssn:
            filtered_text, ssn_count = self._apply_filter(filtered_text, 'ssn')
            stats['ssn'] = ssn_count
        
        if settings.filter_phone:
            filtered_text, phone_count = self._apply_filter(filtered_text, 'phone')
            stats['phone'] = phone_count
        
        if settings.filter_mrn:
            filtered_text, mrn_count = self._apply_filter(filtered_text, 'mrn')
            stats['mrn'] = mrn_count
        
        if settings.filter_insurance:
            filtered_text, insurance_count = self._apply_filter(filtered_text, 'insurance')
            stats['insurance'] = insurance_count
        
        if settings.filter_addresses:
            filtered_text, address_count = self._apply_filter(filtered_text, 'address')
            stats['address'] = address_count
        
        if settings.filter_email:
            filtered_text, email_count = self._apply_filter(filtered_text, 'email')
            stats['email'] = email_count
        
        if settings.filter_dates:
            filtered_text, date_count = self._apply_date_filter(filtered_text)
            stats['dates'] = date_count
        
        if settings.filter_names:
            filtered_text, name_count = self._apply_name_filter(filtered_text)
            stats['names'] = name_count
        
        # Calculate total filtered items
        stats['total_filtered'] = sum(stats.values())
        
        return filtered_text, stats
    
    def _apply_filter(self, text: str, filter_type: str) -> Tuple[str, int]:
        """Apply a specific filter pattern to text"""
        pattern = self.patterns.get(filter_type)
        if not pattern:
            return text, 0
        
        matches = re.findall(pattern, text, re.IGNORECASE)
        count = len(matches)
        
        if count > 0:
            filtered_text = re.sub(pattern, self.replacement_char, text, flags=re.IGNORECASE)
            return filtered_text, count
        
        return text, 0
    
    def _apply_date_filter(self, text: str) -> Tuple[str, int]:
        """Filter dates while preserving medical values like blood pressure"""
        # Protect medical measurements that might look like dates
        protected_patterns = [
            r'\b\d{2,3}\/\d{2,3}\b',  # Blood pressure readings like 120/80
            r'\b\d{1,3}\/\d{1,3}\s*mmhg\b',  # BP with unit
        ]
        
        # Store protected segments
        protected_segments = {}
        placeholder_counter = 0
        
        for pattern in protected_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                placeholder = f"__PROTECTED_{placeholder_counter}__"
                protected_segments[placeholder] = match.group()
                text = text.replace(match.group(), placeholder)
                placeholder_counter += 1
        
        # Apply date filter
        date_pattern = self.patterns['dates']
        matches = re.findall(date_pattern, text)
        count = len(matches)
        
        if count > 0:
            text = re.sub(date_pattern, self.replacement_char, text)
        
        # Restore protected segments
        for placeholder, original in protected_segments.items():
            text = text.replace(placeholder, original)
        
        return text, count
    
    def _apply_name_filter(self, text: str) -> Tuple[str, int]:
        """Filter names while preserving medical terminology"""
        # Protect medical professional titles and terms
        medical_titles = ['Dr', 'Doctor', 'Nurse', 'Physician', 'Specialist']
        
        # Store protected medical contexts
        protected_segments = {}
        placeholder_counter = 0
        
        # Protect medical contexts
        for title in medical_titles:
            pattern = f'\\b{title}\\s+[A-Z][a-z]+'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Only protect if in medical context
                context = text[max(0, match.start()-50):match.end()+50].lower()
                if any(term in context for term in ['consultation', 'referral', 'specialist', 'department']):
                    placeholder = f"__PROTECTED_{placeholder_counter}__"
                    protected_segments[placeholder] = match.group()
                    text = text.replace(match.group(), placeholder)
                    placeholder_counter += 1
        
        # Apply name filter
        name_pattern = self.patterns['names']
        matches = re.findall(name_pattern, text)
        count = len(matches)
        
        if count > 0:
            text = re.sub(name_pattern, self.replacement_char, text)
        
        # Restore protected segments
        for placeholder, original in protected_segments.items():
            text = text.replace(placeholder, original)
        
        return text, count
    
    def _get_filter_settings(self) -> PHIFilterSettings:
        """Get current PHI filter settings"""
        settings = PHIFilterSettings.query.first()
        if not settings:
            # Create default settings
            settings = PHIFilterSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def test_filter(self, test_text: str) -> Dict[str, Any]:
        """Test PHI filter on sample text for configuration purposes"""
        settings = self._get_filter_settings()
        
        filtered_text, stats = self.filter_text(test_text, settings)
        
        return {
            'original_text': test_text,
            'filtered_text': filtered_text,
            'statistics': stats,
            'settings_applied': {
                'filter_ssn': settings.filter_ssn,
                'filter_phone': settings.filter_phone,
                'filter_mrn': settings.filter_mrn,
                'filter_insurance': settings.filter_insurance,
                'filter_addresses': settings.filter_addresses,
                'filter_names': settings.filter_names,
                'filter_dates': settings.filter_dates
            }
        }
    
    def update_settings(self, new_settings: Dict[str, bool]) -> bool:
        """Update PHI filter settings"""
        try:
            settings = self._get_filter_settings()
            
            for key, value in new_settings.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info("PHI filter settings updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating PHI filter settings: {str(e)}")
            db.session.rollback()
            return False
    
    def get_filter_statistics(self) -> Dict[str, Any]:
        """Get PHI filtering statistics"""
        from models import MedicalDocument
        
        # Count documents with PHI filtering applied
        total_docs = db.session.query(MedicalDocument).count()
        filtered_docs = db.session.query(MedicalDocument).filter(
            MedicalDocument.phi_filtered_text.isnot(None)
        ).count()
        
        # Calculate processing rate
        processing_rate = (filtered_docs / total_docs * 100) if total_docs > 0 else 0
        
        return {
            'total_documents': total_docs,
            'filtered_documents': filtered_docs,
            'processing_rate': round(processing_rate, 1),
            'filter_enabled': self._get_filter_settings().is_enabled
        }
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current PHI filter configuration"""
        settings = self._get_filter_settings()
        
        return {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'settings': {
                'is_enabled': settings.is_enabled,
                'filter_ssn': settings.filter_ssn,
                'filter_phone': settings.filter_phone,
                'filter_mrn': settings.filter_mrn,
                'filter_insurance': settings.filter_insurance,
                'filter_addresses': settings.filter_addresses,
                'filter_names': settings.filter_names,
                'filter_dates': settings.filter_dates
            },
            'patterns': self.patterns,
            'protected_terms_count': len(self.medical_terms)
        }
    
    def import_configuration(self, config: Dict[str, Any]) -> bool:
        """Import PHI filter configuration"""
        try:
            if 'settings' not in config:
                return False
            
            return self.update_settings(config['settings'])
            
        except Exception as e:
            logger.error(f"Error importing PHI filter configuration: {str(e)}")
            return False
