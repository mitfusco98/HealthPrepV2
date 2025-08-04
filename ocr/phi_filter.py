"""
HIPAA-compliant PHI filtering system with regex-based pattern removal.
Protects patient identifiable information while preserving clinical values.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
import json

from app import db
from models import PHISettings

class PHIFilter:
    """Filters PHI from medical document text while preserving clinical information."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load PHI filtering patterns
        self.patterns = self._initialize_phi_patterns()
        
        # Medical terms to preserve (these should not be filtered even if they match patterns)
        self.medical_preservations = {
            # Common medical measurements that might look like dates
            'blood_pressure_patterns': [
                r'\b\d{2,3}/\d{2,3}\b',  # Blood pressure readings
                r'\b\d{1,3}/\d{1,3}\s*mmHg\b'
            ],
            # Lab values that might contain numbers
            'lab_value_patterns': [
                r'\b\d+\.?\d*\s*(mg/dL|g/dL|mEq/L|mg|g|mL|L|%)\b',
                r'\bA1C?\s*[:=]?\s*\d+\.?\d*\s*%?\b',
                r'\bglucose\s*[:=]?\s*\d+\b',
                r'\bcholesterol\s*[:=]?\s*\d+\b',
                r'\bBP\s*[:=]?\s*\d{2,3}/\d{2,3}\b'
            ],
            # Medical procedure codes
            'procedure_patterns': [
                r'\bCPT\s*:?\s*\d{5}\b',
                r'\bICD-?10?\s*:?\s*[A-Z]\d{2}\.?\d*\b'
            ]
        }
        
        # Replacement tokens
        self.replacement_tokens = {
            'ssn': '[SSN-REDACTED]',
            'phone': '[PHONE-REDACTED]',
            'mrn': '[MRN-REDACTED]',
            'address': '[ADDRESS-REDACTED]',
            'name': '[NAME-REDACTED]',
            'date': '[DATE-REDACTED]',
            'email': '[EMAIL-REDACTED]',
            'insurance': '[INSURANCE-REDACTED]'
        }
        
        # Processing statistics
        self.filtering_stats = {
            'total_documents_processed': 0,
            'phi_instances_found': 0,
            'phi_instances_redacted': 0,
            'last_processed': None,
            'phi_types_detected': {}
        }
    
    def _initialize_phi_patterns(self) -> Dict[str, List[str]]:
        """Initialize regex patterns for PHI detection."""
        
        return {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
                r'\b\d{3}\s\d{2}\s\d{4}\b',  # XXX XX XXXX
                r'\b\d{9}\b'  # XXXXXXXXX (9 consecutive digits)
            ],
            'phone': [
                r'\b\(\d{3}\)\s?\d{3}-?\d{4}\b',  # (XXX) XXX-XXXX
                r'\b\d{3}-\d{3}-\d{4}\b',  # XXX-XXX-XXXX
                r'\b\d{3}\.\d{3}\.\d{4}\b',  # XXX.XXX.XXXX
                r'\b\d{10}\b'  # XXXXXXXXXX (10 consecutive digits)
            ],
            'mrn': [
                r'\bMRN\s*:?\s*\d+\b',
                r'\bMedical\s+Record\s+Number\s*:?\s*\d+\b',
                r'\bPatient\s+ID\s*:?\s*\d+\b'
            ],
            'address': [
                r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct|Place|Pl)\b',
                r'\b\d{5}(?:-\d{4})?\b'  # ZIP codes
            ],
            'names': [
                r'\b[A-Z][a-z]+,?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'  # Names (simplified pattern)
            ],
            'dates': [
                r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or M/D/YY
                r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY/MM/DD
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b'  # Month DD, YYYY
            ],
            'email': [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ],
            'insurance': [
                r'\bPolicy\s+Number\s*:?\s*[A-Za-z0-9]+\b',
                r'\bMember\s+ID\s*:?\s*[A-Za-z0-9]+\b',
                r'\bGroup\s+Number\s*:?\s*[A-Za-z0-9]+\b'
            ]
        }
    
    def filter_text(self, text: str) -> str:
        """Filter PHI from text while preserving medical information."""
        
        if not text or not self.is_filtering_enabled():
            return text
        
        try:
            self.logger.debug("Starting PHI filtering process")
            
            # Get current PHI settings
            settings = self._get_phi_settings()
            
            # Preserve medical terms first
            text_with_preservations = self._preserve_medical_terms(text)
            
            # Track PHI instances found
            phi_found = {}
            
            # Apply filters based on settings
            filtered_text = text_with_preservations
            
            if settings.filter_ssn:
                filtered_text, ssn_count = self._apply_filter(filtered_text, 'ssn')
                phi_found['ssn'] = ssn_count
            
            if settings.filter_phone:
                filtered_text, phone_count = self._apply_filter(filtered_text, 'phone')
                phi_found['phone'] = phone_count
            
            if settings.filter_mrn:
                filtered_text, mrn_count = self._apply_filter(filtered_text, 'mrn')
                phi_found['mrn'] = mrn_count
            
            if settings.filter_addresses:
                filtered_text, address_count = self._apply_filter(filtered_text, 'address')
                phi_found['address'] = address_count
            
            if settings.filter_names:
                filtered_text, name_count = self._apply_filter(filtered_text, 'names')
                phi_found['names'] = name_count
            
            if settings.filter_dates:
                filtered_text, date_count = self._apply_filter_with_medical_preservation(filtered_text, 'dates')
                phi_found['dates'] = date_count
            
            # Restore preserved medical terms
            filtered_text = self._restore_medical_terms(filtered_text)
            
            # Update statistics
            self._update_filtering_stats(phi_found)
            
            self.logger.debug(f"PHI filtering completed. Found: {sum(phi_found.values())} instances")
            
            return filtered_text
            
        except Exception as e:
            self.logger.error(f"Error during PHI filtering: {e}")
            return text  # Return original text if filtering fails
    
    def _preserve_medical_terms(self, text: str) -> str:
        """Preserve medical terms by temporarily replacing them with tokens."""
        
        preserved_text = text
        self.preservation_map = {}
        token_counter = 0
        
        # Preserve medical measurements and values
        for category, patterns in self.medical_preservations.items():
            for pattern in patterns:
                matches = re.finditer(pattern, preserved_text, re.IGNORECASE)
                for match in matches:
                    token = f"__PRESERVE_{token_counter}__"
                    self.preservation_map[token] = match.group()
                    preserved_text = preserved_text.replace(match.group(), token, 1)
                    token_counter += 1
        
        return preserved_text
    
    def _restore_medical_terms(self, text: str) -> str:
        """Restore preserved medical terms."""
        
        restored_text = text
        
        for token, original_text in getattr(self, 'preservation_map', {}).items():
            restored_text = restored_text.replace(token, original_text)
        
        return restored_text
    
    def _apply_filter(self, text: str, phi_type: str) -> Tuple[str, int]:
        """Apply PHI filter for a specific type and return filtered text and count."""
        
        patterns = self.patterns.get(phi_type, [])
        replacement = self.replacement_tokens.get(phi_type, '[REDACTED]')
        
        filtered_text = text
        total_replacements = 0
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, filtered_text, re.IGNORECASE))
            total_replacements += len(matches)
            filtered_text = re.sub(pattern, replacement, filtered_text, flags=re.IGNORECASE)
        
        return filtered_text, total_replacements
    
    def _apply_filter_with_medical_preservation(self, text: str, phi_type: str) -> Tuple[str, int]:
        """Apply PHI filter while preserving medical values that might match patterns."""
        
        patterns = self.patterns.get(phi_type, [])
        replacement = self.replacement_tokens.get(phi_type, '[REDACTED]')
        
        filtered_text = text
        total_replacements = 0
        
        for pattern in patterns:
            # Find matches
            matches = list(re.finditer(pattern, filtered_text, re.IGNORECASE))
            
            for match in reversed(matches):  # Process in reverse to maintain positions
                match_text = match.group()
                match_start, match_end = match.span()
                
                # Check if this match is likely medical data
                if self._is_likely_medical_data(match_text, text, match_start):
                    continue  # Skip this match - it's medical data
                
                # Replace the match
                filtered_text = filtered_text[:match_start] + replacement + filtered_text[match_end:]
                total_replacements += 1
        
        return filtered_text, total_replacements
    
    def _is_likely_medical_data(self, match_text: str, full_text: str, position: int) -> bool:
        """Determine if a matched pattern is likely medical data that should be preserved."""
        
        # Get context around the match
        context_start = max(0, position - 50)
        context_end = min(len(full_text), position + len(match_text) + 50)
        context = full_text[context_start:context_end].lower()
        
        # Medical context indicators
        medical_indicators = [
            'blood pressure', 'bp', 'systolic', 'diastolic',
            'glucose', 'a1c', 'hba1c', 'cholesterol', 'hdl', 'ldl',
            'lab', 'result', 'value', 'level', 'test', 'measurement',
            'mg/dl', 'mmhg', 'bpm', 'temperature', 'weight', 'height',
            'dose', 'dosage', 'medication', 'prescription'
        ]
        
        # Check if any medical indicators are in the context
        for indicator in medical_indicators:
            if indicator in context:
                return True
        
        # Check if the match looks like a measurement
        if re.search(r'\d+[./]\d+\s*(mg|mmhg|bpm)', match_text.lower()):
            return True
        
        return False
    
    def _get_phi_settings(self) -> PHISettings:
        """Get current PHI filtering settings."""
        
        settings = PHISettings.query.first()
        
        if not settings:
            # Create default settings
            settings = PHISettings(
                filter_enabled=True,
                filter_ssn=True,
                filter_phone=True,
                filter_mrn=True,
                filter_addresses=True,
                filter_names=True,
                filter_dates=True
            )
            db.session.add(settings)
            db.session.commit()
        
        return settings
    
    def _update_filtering_stats(self, phi_found: Dict[str, int]):
        """Update PHI filtering statistics."""
        
        self.filtering_stats['total_documents_processed'] += 1
        self.filtering_stats['last_processed'] = datetime.utcnow()
        
        total_found = sum(phi_found.values())
        self.filtering_stats['phi_instances_found'] += total_found
        self.filtering_stats['phi_instances_redacted'] += total_found
        
        # Update type-specific stats
        for phi_type, count in phi_found.items():
            if phi_type not in self.filtering_stats['phi_types_detected']:
                self.filtering_stats['phi_types_detected'][phi_type] = 0
            self.filtering_stats['phi_types_detected'][phi_type] += count
    
    def is_filtering_enabled(self) -> bool:
        """Check if PHI filtering is globally enabled."""
        
        try:
            settings = PHISettings.query.first()
            return settings.filter_enabled if settings else True
        except:
            return True  # Default to enabled for safety
    
    def test_phi_filter(self, test_text: str) -> Dict[str, any]:
        """Test PHI filtering on sample text and return before/after comparison."""
        
        try:
            original_text = test_text
            filtered_text = self.filter_text(test_text)
            
            # Find differences
            differences = []
            original_lines = original_text.split('\n')
            filtered_lines = filtered_text.split('\n')
            
            for i, (orig_line, filt_line) in enumerate(zip(original_lines, filtered_lines)):
                if orig_line != filt_line:
                    differences.append({
                        'line_number': i + 1,
                        'original': orig_line,
                        'filtered': filt_line
                    })
            
            # Count redactions by type
            redaction_counts = {}
            for phi_type, token in self.replacement_tokens.items():
                count = filtered_text.count(token)
                if count > 0:
                    redaction_counts[phi_type] = count
            
            return {
                'success': True,
                'original_text': original_text,
                'filtered_text': filtered_text,
                'differences': differences,
                'redaction_counts': redaction_counts,
                'total_redactions': sum(redaction_counts.values()),
                'filtering_enabled': self.is_filtering_enabled()
            }
            
        except Exception as e:
            self.logger.error(f"Error testing PHI filter: {e}")
            return {
                'success': False,
                'error': str(e),
                'original_text': test_text,
                'filtered_text': test_text
            }
    
    def get_filtering_statistics(self) -> Dict[str, any]:
        """Get current PHI filtering statistics."""
        
        return {
            **self.filtering_stats,
            'average_phi_per_document': (
                self.filtering_stats['phi_instances_found'] / 
                max(self.filtering_stats['total_documents_processed'], 1)
            ),
            'current_settings': self._get_phi_settings_summary()
        }
    
    def _get_phi_settings_summary(self) -> Dict[str, bool]:
        """Get summary of current PHI settings."""
        
        try:
            settings = self._get_phi_settings()
            return {
                'filter_enabled': settings.filter_enabled,
                'filter_ssn': settings.filter_ssn,
                'filter_phone': settings.filter_phone,
                'filter_mrn': settings.filter_mrn,
                'filter_addresses': settings.filter_addresses,
                'filter_names': settings.filter_names,
                'filter_dates': settings.filter_dates
            }
        except:
            return {
                'filter_enabled': True,
                'filter_ssn': True,
                'filter_phone': True,
                'filter_mrn': True,
                'filter_addresses': True,
                'filter_names': True,
                'filter_dates': True
            }
    
    def export_configuration(self) -> Dict[str, any]:
        """Export current PHI filtering configuration."""
        
        return {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'settings': self._get_phi_settings_summary(),
            'patterns': self.patterns,
            'replacement_tokens': self.replacement_tokens,
            'medical_preservations': self.medical_preservations,
            'statistics': self.get_filtering_statistics()
        }
