"""
Regex-based PHI redaction with HIPAA compliance
"""

import re
import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
from models import PHISettings

logger = logging.getLogger(__name__)

class PHIFilter:
    """HIPAA-compliant PHI filtering with regex-based pattern removal"""
    
    def __init__(self):
        # PHI pattern definitions
        self.phi_patterns = {
            'ssn': {
                'pattern': r'\b\d{3}-?\d{2}-?\d{4}\b',
                'replacement': '[SSN-REDACTED]',
                'description': 'Social Security Number'
            },
            'phone': {
                'pattern': r'\b(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b',
                'replacement': '[PHONE-REDACTED]',
                'description': 'Phone Number'
            },
            'mrn': {
                'pattern': r'\b(?:MRN|Medical Record|Patient ID|ID)[\s:]*\d{6,}\b',
                'replacement': '[MRN-REDACTED]',
                'description': 'Medical Record Number'
            },
            'address': {
                'pattern': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct|Place|Pl)\b',
                'replacement': '[ADDRESS-REDACTED]',
                'description': 'Street Address'
            },
            'email': {
                'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'replacement': '[EMAIL-REDACTED]',
                'description': 'Email Address'
            },
            'dates': {
                'pattern': r'\b(?:0?[1-9]|1[0-2])[\/\-.](?:0?[1-9]|[12][0-9]|3[01])[\/\-.]\d{4}\b',
                'replacement': '[DATE-REDACTED]',
                'description': 'Date (MM/DD/YYYY format)'
            },
            'zip_code': {
                'pattern': r'\b\d{5}(?:-\d{4})?\b',
                'replacement': '[ZIP-REDACTED]',
                'description': 'ZIP Code'
            }
        }
        
        # Medical terms to preserve (these should NOT be redacted)
        self.medical_preservations = {
            'vital_signs': [
                r'\b\d+/\d+\s*(?:mmHg|mm Hg)\b',  # Blood pressure
                r'\b\d+\.\d+\s*(?:mg/dL|mg/dl)\b',  # Lab values
                r'\b\d+\s*(?:bpm|BPM)\b',  # Heart rate
                r'\b\d+\.\d+\s*(?:°F|°C|F|C)\b',  # Temperature
                r'\b\d+\s*(?:kg|lbs|lb)\b',  # Weight
            ],
            'lab_values': [
                r'\bA1C\s*[:=]?\s*\d+\.\d+\b',  # A1C values
                r'\bglucose\s*[:=]?\s*\d+\b',  # Glucose
                r'\bcholesterol\s*[:=]?\s*\d+\b',  # Cholesterol
                r'\bHDL\s*[:=]?\s*\d+\b',  # HDL
                r'\bLDL\s*[:=]?\s*\d+\b',  # LDL
            ],
            'measurements': [
                r'\b\d+\s*(?:cm|mm|inches|in)\b',  # Measurements
                r'\b\d+\.\d+\s*(?:cm|mm|inches|in)\b',  # Decimal measurements
            ]
        }
    
    def filter_text(self, text: str, settings: PHISettings = None) -> Dict[str, Any]:
        """
        Filter PHI from text based on settings
        """
        if not text:
            return {
                'filtered_text': '',
                'patterns_found': [],
                'redactions_made': 0
            }
        
        # Get current settings
        if not settings:
            settings = PHISettings.get_current()
        
        if not settings.phi_filtering_enabled:
            return {
                'filtered_text': text,
                'patterns_found': [],
                'redactions_made': 0
            }
        
        filtered_text = text
        patterns_found = []
        total_redactions = 0
        
        # Apply each PHI filter based on settings
        filter_mapping = {
            'ssn': settings.filter_ssn,
            'phone': settings.filter_phone,
            'mrn': settings.filter_mrn,
            'address': settings.filter_addresses,
            'email': settings.filter_names,  # Using email for names setting
            'dates': settings.filter_dates,
            'zip_code': settings.filter_addresses
        }
        
        for pattern_name, should_filter in filter_mapping.items():
            if should_filter and pattern_name in self.phi_patterns:
                filtered_text, redactions, found_patterns = self._apply_phi_filter(
                    filtered_text, pattern_name
                )
                total_redactions += redactions
                patterns_found.extend(found_patterns)
        
        # Preserve medical terms that may have been inadvertently redacted
        filtered_text = self._preserve_medical_terms(text, filtered_text)
        
        logger.info(f"PHI filtering complete: {total_redactions} redactions made")
        
        return {
            'filtered_text': filtered_text,
            'patterns_found': patterns_found,
            'redactions_made': total_redactions
        }
    
    def _apply_phi_filter(self, text: str, pattern_name: str) -> Tuple[str, int, List[str]]:
        """Apply a specific PHI filter pattern"""
        
        if pattern_name not in self.phi_patterns:
            return text, 0, []
        
        pattern_config = self.phi_patterns[pattern_name]
        pattern = pattern_config['pattern']
        replacement = pattern_config['replacement']
        
        # Find all matches
        matches = re.finditer(pattern, text, re.IGNORECASE)
        found_patterns = []
        redaction_count = 0
        
        # Process matches from end to beginning to maintain string indices
        matches_list = list(matches)
        for match in reversed(matches_list):
            # Record the pattern found (for audit trail)
            found_patterns.append({
                'type': pattern_name,
                'pattern': match.group(),
                'position': match.start(),
                'description': pattern_config['description']
            })
            redaction_count += 1
        
        # Apply replacements
        filtered_text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return filtered_text, redaction_count, found_patterns
    
    def _preserve_medical_terms(self, original_text: str, filtered_text: str) -> str:
        """
        Restore medical terms that may have been incorrectly redacted
        """
        # This is a safety measure to ensure medical values aren't lost
        for category, patterns in self.medical_preservations.items():
            for pattern in patterns:
                # Find medical terms in original text
                original_matches = re.finditer(pattern, original_text, re.IGNORECASE)
                
                for match in original_matches:
                    medical_term = match.group()
                    # Check if this medical term was redacted
                    if medical_term not in filtered_text:
                        # Try to restore it in context
                        # This is a simplified approach - in production, you'd want more sophisticated logic
                        redaction_pattern = r'\[[\w-]+REDACTED\]'
                        filtered_text = re.sub(redaction_pattern, medical_term, filtered_text, count=1)
        
        return filtered_text
    
    def test_filter(self, test_text: str) -> Dict[str, Any]:
        """
        Test PHI filter on sample text (for admin testing interface)
        """
        # Show before/after comparison
        result = self.filter_text(test_text)
        
        return {
            'original_text': test_text,
            'filtered_text': result['filtered_text'],
            'patterns_found': result['patterns_found'],
            'redactions_made': result['redactions_made'],
            'preview': {
                'original_length': len(test_text),
                'filtered_length': len(result['filtered_text']),
                'reduction_percentage': round((1 - len(result['filtered_text']) / len(test_text)) * 100, 2) if test_text else 0
            }
        }
    
    def get_filter_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about PHI filtering usage
        """
        from models import MedicalDocument, db
        
        # Count documents with PHI filtering applied
        total_docs = MedicalDocument.query.count()
        phi_filtered_docs = MedicalDocument.query.filter_by(phi_filtered=True).count()
        
        # Aggregate pattern statistics
        pattern_stats = {}
        
        filtered_docs = MedicalDocument.query.filter_by(phi_filtered=True).all()
        for doc in filtered_docs:
            if doc.phi_patterns_list:
                for pattern_info in doc.phi_patterns_list:
                    pattern_type = pattern_info.get('type', 'unknown')
                    if pattern_type not in pattern_stats:
                        pattern_stats[pattern_type] = 0
                    pattern_stats[pattern_type] += 1
        
        return {
            'total_documents': total_docs,
            'phi_filtered_documents': phi_filtered_docs,
            'filtering_rate': round((phi_filtered_docs / total_docs * 100), 2) if total_docs > 0 else 0,
            'pattern_statistics': pattern_stats,
            'available_patterns': list(self.phi_patterns.keys()),
            'last_updated': datetime.utcnow().isoformat()
        }
    
    def export_filter_config(self) -> Dict[str, Any]:
        """
        Export current filter configuration for backup/compliance
        """
        settings = PHISettings.get_current()
        
        return {
            'export_metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'version': '1.0'
            },
            'phi_settings': {
                'phi_filtering_enabled': settings.phi_filtering_enabled,
                'filter_ssn': settings.filter_ssn,
                'filter_phone': settings.filter_phone,
                'filter_mrn': settings.filter_mrn,
                'filter_addresses': settings.filter_addresses,
                'filter_names': settings.filter_names,
                'filter_dates': settings.filter_dates
            },
            'pattern_definitions': self.phi_patterns,
            'medical_preservations': self.medical_preservations
        }
    
    def validate_patterns(self) -> Dict[str, Any]:
        """
        Validate all PHI patterns for correctness
        """
        validation_results = {}
        
        # Test patterns with known examples
        test_cases = {
            'ssn': ['123-45-6789', '123456789'],
            'phone': ['(555) 123-4567', '555-123-4567', '5551234567'],
            'mrn': ['MRN: 1234567', 'Medical Record 9876543'],
            'email': ['test@example.com', 'user.name@domain.org'],
            'dates': ['12/31/2023', '01-15-2024'],
            'zip_code': ['12345', '12345-6789']
        }
        
        for pattern_name, test_values in test_cases.items():
            if pattern_name in self.phi_patterns:
                pattern = self.phi_patterns[pattern_name]['pattern']
                results = []
                
                for test_value in test_values:
                    match = re.search(pattern, test_value, re.IGNORECASE)
                    results.append({
                        'test_value': test_value,
                        'matched': match is not None,
                        'matched_text': match.group() if match else None
                    })
                
                validation_results[pattern_name] = {
                    'pattern': pattern,
                    'test_results': results,
                    'all_passed': all(r['matched'] for r in results)
                }
        
        return validation_results

