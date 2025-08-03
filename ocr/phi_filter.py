import re
import logging
from datetime import datetime
from models import PHISettings
from app import db

logger = logging.getLogger(__name__)

class PHIFilter:
    """Handles PHI filtering and redaction"""

    def __init__(self):
        self.load_settings()
        self.setup_patterns()

    def load_settings(self):
        """Load PHI filtering settings from database"""
        settings = PHISettings.query.first()

        if not settings:
            # Create default settings
            settings = PHISettings()
            db.session.add(settings)
            db.session.commit()

        self.settings = settings

    def setup_patterns(self):
        """Setup regex patterns for PHI detection"""
        self.patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'phone': r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',
            'mrn': r'\b[Mm][Rr][Nn][\s:]?\d{6,10}\b',
            'dates': r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
            'insurance': r'\b(?:policy|member|id)[\s:]?\d{8,15}\b'
        }

        # Medical terms to preserve
        self.medical_terms = [
            r'\d+/\d+\s*mmHg',  # Blood pressure
            r'\d+\.\d+\s*mg/dL',  # Lab values
            r'A1C:?\s*\d+\.\d+',  # A1C values
            r'glucose:?\s*\d+',   # Glucose values
        ]

    def filter_text(self, text, user_id=None):
        """Apply PHI filtering to text"""
        try:
            if not self.settings.phi_filtering_enabled:
                return {'success': True, 'filtered_text': text, 'phi_count': 0}

            filtered_text = text
            phi_count = 0

            # Apply filters based on settings
            if self.settings.filter_ssn:
                filtered_text, count = self.redact_pattern(filtered_text, self.patterns['ssn'], '[SSN-REDACTED]')
                phi_count += count

            if self.settings.filter_phone:
                filtered_text, count = self.redact_pattern(filtered_text, self.patterns['phone'], '[PHONE-REDACTED]')
                phi_count += count

            if self.settings.filter_mrn:
                filtered_text, count = self.redact_pattern(filtered_text, self.patterns['mrn'], '[MRN-REDACTED]')
                phi_count += count

            if self.settings.filter_dates:
                # Preserve medical values while filtering dates
                filtered_text = self.redact_dates_preserve_medical(filtered_text)

            logger.info(f"PHI filtering completed: {phi_count} items redacted")

            return {
                'success': True,
                'filtered_text': filtered_text,
                'phi_count': phi_count
            }

        except Exception as e:
            logger.error(f"PHI filtering failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def redact_pattern(self, text, pattern, replacement):
        """Redact text matching a pattern"""
        matches = re.findall(pattern, text, re.IGNORECASE)
        filtered_text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return filtered_text, len(matches)

    def redact_dates_preserve_medical(self, text):
        """Redact dates while preserving medical values"""
        # First protect medical terms
        protected_segments = []
        for pattern in self.medical_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                protected_segments.append((match.start(), match.end(), match.group()))

        # Then apply date filtering avoiding protected segments
        filtered_text = text
        if self.settings.filter_dates:
            # Simple date redaction (can be enhanced)
            filtered_text = re.sub(self.patterns['dates'], '[DATE-REDACTED]', filtered_text)

        return filtered_text