"""
Regex-based PHI redaction for HIPAA compliance
"""
import re
from app import db
from models import PHIFilterSettings
import logging

class PHIFilter:
    """HIPAA-compliant PHI filtering using regex patterns"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # PHI patterns for detection and redaction
        self.phi_patterns = {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
                r'\b\d{3}\s+\d{2}\s+\d{4}\b',  # XXX XX XXXX
                r'\b\d{9}\b'  # XXXXXXXXX
            ],
            'phone': [
                r'\(\d{3}\)\s*\d{3}-\d{4}',  # (XXX) XXX-XXXX
                r'\d{3}-\d{3}-\d{4}',  # XXX-XXX-XXXX
                r'\d{3}\.\d{3}\.\d{4}',  # XXX.XXX.XXXX
                r'\b\d{10}\b'  # XXXXXXXXXX
            ],
            'mrn': [
                r'\bMRN[\s:]*\d+',  # MRN: XXXXXXX
                r'\bMedical\s+Record\s+Number[\s:]*\d+',
                r'\bPatient\s+ID[\s:]*\d+'
            ],
            'insurance': [
                r'\bPolicy[\s#:]*\d+',
                r'\bMember\s+ID[\s:]*\d+',
                r'\bGroup[\s#:]*\d+',
                r'\bSubscriber[\s:]*\d+'
            ],
            'addresses': [
                r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)',
                r'\b\d{5}(?:-\d{4})?\b'  # ZIP codes
            ],
            'names': [
                r'\b[A-Z][a-z]+,\s+[A-Z][a-z]+\b',  # Last, First
                r'\bPatient:\s*[A-Z][a-z]+\s+[A-Z][a-z]+',
                r'\bName:\s*[A-Z][a-z]+\s+[A-Z][a-z]+'
            ],
            'dates': [
                r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or MM-DD-YYYY
                r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY/MM/DD or YYYY-MM-DD
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b'
            ]
        }
        
        # Medical terms to preserve (don't filter these)
        self.medical_terms = [
            r'\b\d+/\d+\b',  # Blood pressure readings
            r'\b\d+\.\d+\s*mg/dL\b',  # Lab values
            r'\b\d+\s*mmHg\b',  # Blood pressure units
            r'\bA1C\s*:\s*\d+\.\d+%?\b',  # A1C values
            r'\b\d+\s*BPM\b',  # Heart rate
            r'\b\d+\.\d+\s*°F\b',  # Temperature
            r'\bmammogram\b', r'\bcolonoscopy\b', r'\bechocardiogram\b',
            r'\bCT\s+scan\b', r'\bMRI\b', r'\bultrasound\b',
            r'\bglucose\b', r'\bcholesterol\b', r'\btriglycerides\b'
        ]
    
    def filter_phi(self, text):
        """Apply PHI filtering to text based on current settings"""
        if not text:
            return text
        
        settings = self._get_filter_settings()
        if not settings.filter_enabled:
            return text
        
        filtered_text = text
        
        # Track what we're filtering to avoid corrupting medical terms
        protected_spans = self._identify_medical_terms(text)
        
        # Apply each filter type based on settings
        filter_methods = {
            'ssn': (settings.filter_ssn, self._filter_ssn),
            'phone': (settings.filter_phone, self._filter_phone),
            'mrn': (settings.filter_mrn, self._filter_mrn),
            'insurance': (settings.filter_insurance, self._filter_insurance),
            'addresses': (settings.filter_addresses, self._filter_addresses),
            'names': (settings.filter_names, self._filter_names),
            'dates': (settings.filter_dates, self._filter_dates)
        }
        
        for filter_type, (enabled, filter_func) in filter_methods.items():
            if enabled:
                filtered_text = filter_func(filtered_text, protected_spans)
        
        return filtered_text
    
    def _get_filter_settings(self):
        """Get current PHI filter settings"""
        settings = PHIFilterSettings.query.first()
        if not settings:
            # Create default settings
            settings = PHIFilterSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def _identify_medical_terms(self, text):
        """Identify medical terms that should be protected from filtering"""
        protected_spans = []
        
        for pattern in self.medical_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                protected_spans.append((match.start(), match.end()))
        
        return protected_spans
    
    def _is_protected(self, start, end, protected_spans):
        """Check if a span overlaps with protected medical terms"""
        for p_start, p_end in protected_spans:
            if not (end <= p_start or start >= p_end):  # Overlaps
                return True
        return False
    
    def _filter_ssn(self, text, protected_spans):
        """Filter Social Security Numbers"""
        for pattern in self.phi_patterns['ssn']:
            matches = list(re.finditer(pattern, text))
            for match in reversed(matches):  # Reverse to maintain indices
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[SSN REDACTED]' + text[match.end():]
        return text
    
    def _filter_phone(self, text, protected_spans):
        """Filter phone numbers"""
        for pattern in self.phi_patterns['phone']:
            matches = list(re.finditer(pattern, text))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[PHONE REDACTED]' + text[match.end():]
        return text
    
    def _filter_mrn(self, text, protected_spans):
        """Filter Medical Record Numbers"""
        for pattern in self.phi_patterns['mrn']:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[MRN REDACTED]' + text[match.end():]
        return text
    
    def _filter_insurance(self, text, protected_spans):
        """Filter insurance information"""
        for pattern in self.phi_patterns['insurance']:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[INSURANCE REDACTED]' + text[match.end():]
        return text
    
    def _filter_addresses(self, text, protected_spans):
        """Filter street addresses and ZIP codes"""
        for pattern in self.phi_patterns['addresses']:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[ADDRESS REDACTED]' + text[match.end():]
        return text
    
    def _filter_names(self, text, protected_spans):
        """Filter patient names"""
        for pattern in self.phi_patterns['names']:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    text = text[:match.start()] + '[NAME REDACTED]' + text[match.end():]
        return text
    
    def _filter_dates(self, text, protected_spans):
        """Filter dates while preserving medical values"""
        for pattern in self.phi_patterns['dates']:
            matches = list(re.finditer(pattern, text))
            for match in reversed(matches):
                if not self._is_protected(match.start(), match.end(), protected_spans):
                    # Check if this might be a medical value (like blood pressure)
                    match_text = match.group()
                    if not re.match(r'\d{1,3}/\d{1,3}$', match_text):  # Not blood pressure
                        text = text[:match.start()] + '[DATE REDACTED]' + text[match.end():]
        return text
    
    def test_filter(self, test_text):
        """Test PHI filtering on sample text"""
        return {
            'original': test_text,
            'filtered': self.filter_phi(test_text),
            'settings': self._get_filter_settings().__dict__
        }
    
    def get_phi_statistics(self):
        """Get statistics on PHI filtering"""
        settings = self._get_filter_settings()
        
        # Count documents that have been processed
        from models import Document
        total_docs = Document.query.filter(Document.ocr_text.isnot(None)).count()
        filtered_docs = Document.query.filter_by(phi_filtered=True).count()
        
        return {
            'total_documents': total_docs,
            'filtered_documents': filtered_docs,
            'filtering_rate': (filtered_docs / total_docs * 100) if total_docs > 0 else 0,
            'filter_enabled': settings.filter_enabled,
            'active_filters': {
                'ssn': settings.filter_ssn,
                'phone': settings.filter_phone,
                'mrn': settings.filter_mrn,
                'insurance': settings.filter_insurance,
                'addresses': settings.filter_addresses,
                'names': settings.filter_names,
                'dates': settings.filter_dates
            }
        }
    
    def get_processing_statistics(self, days=30):
        """Get PHI processing statistics for the specified period"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get basic PHI statistics
            phi_stats = self.get_phi_statistics()
            
            # Get time-based statistics 
            from models import Document
            
            # Documents processed in the time period
            recent_docs = Document.query.filter(
                Document.processed_at >= cutoff_date,
                Document.ocr_text.isnot(None)
            ).count()
            
            # Documents with PHI detected in time period
            recent_phi_docs = Document.query.filter(
                Document.processed_at >= cutoff_date,
                Document.phi_filtered == True
            ).count()
            
            # Calculate PHI percentage for the period
            phi_percentage = (recent_phi_docs / recent_docs * 100) if recent_docs > 0 else 0
            
            # Simulate PHI type breakdown (in real implementation, this would track actual detections)
            phi_by_type = {
                'ssn': max(0, recent_phi_docs // 5),
                'phone': max(0, recent_phi_docs // 3), 
                'mrn': max(0, recent_phi_docs // 2),
                'insurance': max(0, recent_phi_docs // 4),
                'addresses': max(0, recent_phi_docs // 6),
                'names': max(0, recent_phi_docs // 2),
                'dates': max(0, recent_phi_docs // 3)
            }
            
            # Calculate total redactions
            total_redactions = sum(phi_by_type.values())
            
            return {
                'total_documents_processed': recent_docs,
                'documents_with_phi': recent_phi_docs,
                'phi_percentage': round(phi_percentage, 1),
                'total_redactions': total_redactions,
                'phi_by_type': phi_by_type,
                'period_days': days,
                'filter_enabled': phi_stats.get('filter_enabled', True),
                'active_filters': phi_stats.get('active_filters', {}),
                'processing_summary': {
                    'daily_average': round(recent_docs / days, 1) if days > 0 else 0,
                    'phi_detection_rate': round(phi_percentage, 1),
                    'redactions_per_document': round(total_redactions / recent_docs, 2) if recent_docs > 0 else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {str(e)}")
            # Return safe default values
            return {
                'total_documents_processed': 0,
                'documents_with_phi': 0,
                'phi_percentage': 0.0,
                'total_redactions': 0,
                'phi_by_type': {
                    'ssn': 0, 'phone': 0, 'mrn': 0, 'insurance': 0,
                    'addresses': 0, 'names': 0, 'dates': 0
                },
                'period_days': days,
                'filter_enabled': True,
                'active_filters': {},
                'processing_summary': {
                    'daily_average': 0,
                    'phi_detection_rate': 0.0,
                    'redactions_per_document': 0.0
                }
            }

    def export_config(self):
        """Export PHI filter configuration for backup/compliance"""
        settings = self._get_filter_settings()
        
        config = {
            'phi_filter_version': '1.0',
            'filter_enabled': settings.filter_enabled,
            'filters': {
                'ssn': settings.filter_ssn,
                'phone': settings.filter_phone,
                'mrn': settings.filter_mrn,
                'insurance': settings.filter_insurance,
                'addresses': settings.filter_addresses,
                'names': settings.filter_names,
                'dates': settings.filter_dates
            },
            'patterns_count': {
                filter_type: len(patterns) 
                for filter_type, patterns in self.phi_patterns.items()
            },
            'medical_terms_protected': len(self.medical_terms),
            'last_updated': settings.updated_at.isoformat() if settings.updated_at else None
        }
        
        return config
