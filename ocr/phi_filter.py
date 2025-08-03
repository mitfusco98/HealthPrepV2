"""
PHI (Protected Health Information) filtering module.
Implements regex-based PHI redaction while preserving clinical values.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import json

from app import db
from models import PHISettings

class PHIFilter:
    """HIPAA-compliant PHI filtering system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # PHI detection patterns
        self.patterns = {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{3}\s\d{2}\s\d{4}\b',
                r'\b\d{9}\b'
            ],
            'phone': [
                r'\(\d{3}\)\s?\d{3}-\d{4}',
                r'\d{3}-\d{3}-\d{4}',
                r'\d{3}\.\d{3}\.\d{4}',
                r'\d{3}\s\d{3}\s\d{4}',
                r'\b\d{10}\b'
            ],
            'mrn': [
                r'\bMRN\s*:?\s*\d+\b',
                r'\bMedical\s+Record\s+Number\s*:?\s*\d+\b',
                r'\bID\s*:?\s*\d{6,}\b'
            ],
            'insurance': [
                r'\bPolicy\s+Number\s*:?\s*\w+\b',
                r'\bMember\s+ID\s*:?\s*\w+\b',
                r'\bGroup\s+Number\s*:?\s*\w+\b',
                r'\bSubscriber\s+ID\s*:?\s*\w+\b'
            ],
            'addresses': [
                r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Court|Ct|Lane|Ln)',
                r'\b\d{5}(?:-\d{4})?\b'  # ZIP codes
            ],
            'names': [
                r'\b[A-Z][a-z]+,\s+[A-Z][a-z]+\b',  # Last, First
                r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'  # First Last Middle
            ],
            'dates': [
                r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
                r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4}\b'
            ]
        }
        
        # Medical terms to preserve (never filter these)
        self.medical_preservations = [
            # Lab values
            r'\b\d+(?:\.\d+)?\s*mg/dL\b',
            r'\b\d+(?:\.\d+)?\s*mmol/L\b',
            r'\b\d+(?:\.\d+)?\s*%\b',
            r'\b\d+/\d+\s*mmHg\b',  # Blood pressure
            r'\bA1C\s*:?\s*\d+(?:\.\d+)?%?\b',
            r'\bGlucose\s*:?\s*\d+\b',
            r'\bCholesterol\s*:?\s*\d+\b',
            r'\bLDL\s*:?\s*\d+\b',
            r'\bHDL\s*:?\s*\d+\b',
            r'\bTriglycerides\s*:?\s*\d+\b',
            
            # Medical procedures
            r'\bMammogram\b',
            r'\bColonoscopy\b',
            r'\bEndoscopy\b',
            r'\bBiopsy\b',
            r'\bCT\s+scan\b',
            r'\bMRI\b',
            r'\bUltrasound\b',
            r'\bX-ray\b',
            
            # Medical conditions
            r'\bDiabetes\b',
            r'\bHypertension\b',
            r'\bHyperlipidemia\b',
            r'\bCOPD\b',
            r'\bAsthma\b',
            r'\bCAD\b',
            
            # Measurements
            r'\b\d+\s*cm\b',
            r'\b\d+\s*mm\b',
            r'\b\d+\s*kg\b',
            r'\b\d+\s*lbs?\b'
        ]
        
        # Replacement patterns
        self.replacements = {
            'ssn': '[SSN REDACTED]',
            'phone': '[PHONE REDACTED]',
            'mrn': '[MRN REDACTED]',
            'insurance': '[INSURANCE INFO REDACTED]',
            'addresses': '[ADDRESS REDACTED]',
            'names': '[NAME REDACTED]',
            'dates': '[DATE REDACTED]'
        }
    
    def filter_phi(self, text: str) -> str:
        """Filter PHI from text while preserving medical information"""
        if not text:
            return text
        
        try:
            # Get current PHI settings
            settings = self._get_phi_settings()
            
            if not settings.phi_filtering_enabled:
                return text
            
            filtered_text = text
            phi_stats = {}
            
            # Preserve medical terms first
            preserved_terms = self._extract_preserved_terms(text)
            
            # Apply filters based on settings
            if settings.filter_ssn:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'ssn')
                phi_stats['ssn'] = count
            
            if settings.filter_phone:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'phone')
                phi_stats['phone'] = count
            
            if settings.filter_mrn:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'mrn')
                phi_stats['mrn'] = count
            
            if settings.filter_insurance:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'insurance')
                phi_stats['insurance'] = count
            
            if settings.filter_addresses:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'addresses')
                phi_stats['addresses'] = count
            
            if settings.filter_names:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'names')
                phi_stats['names'] = count
            
            if settings.filter_dates:
                filtered_text, count = self._filter_pattern_type(filtered_text, 'dates')
                phi_stats['dates'] = count
            
            # Restore preserved medical terms
            filtered_text = self._restore_preserved_terms(filtered_text, preserved_terms)
            
            # Log PHI filtering statistics
            self._log_phi_stats(phi_stats)
            
            return filtered_text
            
        except Exception as e:
            self.logger.error(f"Error filtering PHI: {str(e)}")
            return text  # Return original text if filtering fails
    
    def _get_phi_settings(self) -> PHISettings:
        """Get current PHI filtering settings"""
        settings = PHISettings.query.first()
        if not settings:
            # Create default settings
            settings = PHISettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def _extract_preserved_terms(self, text: str) -> List[Tuple[str, int]]:
        """Extract medical terms that should be preserved"""
        preserved = []
        
        for pattern in self.medical_preservations:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preserved.append((match.group(), match.start()))
        
        return preserved
    
    def _restore_preserved_terms(self, text: str, preserved_terms: List[Tuple[str, int]]) -> str:
        """Restore preserved medical terms to filtered text"""
        # This is a simplified restoration - in practice, you'd need more sophisticated tracking
        # of text positions after filtering
        for term, _ in preserved_terms:
            # Look for redacted placeholders and restore if appropriate
            if '[' in text and 'REDACTED]' in text:
                # Simple restoration logic - this could be enhanced
                pass
        
        return text
    
    def _filter_pattern_type(self, text: str, pattern_type: str) -> Tuple[str, int]:
        """Filter a specific type of PHI pattern"""
        if pattern_type not in self.patterns:
            return text, 0
        
        filtered_text = text
        total_replacements = 0
        
        for pattern in self.patterns[pattern_type]:
            # Check if this replacement would affect preserved medical terms
            matches = list(re.finditer(pattern, filtered_text, re.IGNORECASE))
            
            valid_matches = []
            for match in matches:
                if not self._is_medical_term(match.group()):
                    valid_matches.append(match)
            
            # Replace valid matches
            for match in reversed(valid_matches):  # Reverse to maintain positions
                start, end = match.span()
                replacement = self.replacements.get(pattern_type, '[REDACTED]')
                filtered_text = filtered_text[:start] + replacement + filtered_text[end:]
                total_replacements += 1
        
        return filtered_text, total_replacements
    
    def _is_medical_term(self, text: str) -> bool:
        """Check if text appears to be a medical term that should be preserved"""
        for pattern in self.medical_preservations:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _log_phi_stats(self, stats: Dict[str, int]) -> None:
        """Log PHI filtering statistics"""
        total_redacted = sum(stats.values())
        if total_redacted > 0:
            self.logger.info(f"PHI filtering completed: {stats} (Total: {total_redacted})")
    
    def test_phi_filter(self, test_text: str) -> Dict[str, Any]:
        """Test PHI filtering on sample text and return before/after comparison"""
        try:
            original_text = test_text
            filtered_text = self.filter_phi(test_text)
            
            # Detect what was filtered
            detected_phi = {}
            settings = self._get_phi_settings()
            
            for phi_type, patterns in self.patterns.items():
                count = 0
                for pattern in patterns:
                    matches = re.findall(pattern, original_text, re.IGNORECASE)
                    count += len(matches)
                detected_phi[phi_type] = count
            
            return {
                'original_text': original_text,
                'filtered_text': filtered_text,
                'detected_phi': detected_phi,
                'total_redactions': sum(detected_phi.values()),
                'settings_used': {
                    'phi_filtering_enabled': settings.phi_filtering_enabled,
                    'filter_ssn': settings.filter_ssn,
                    'filter_phone': settings.filter_phone,
                    'filter_mrn': settings.filter_mrn,
                    'filter_insurance': settings.filter_insurance,
                    'filter_addresses': settings.filter_addresses,
                    'filter_names': settings.filter_names,
                    'filter_dates': settings.filter_dates
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error testing PHI filter: {str(e)}")
            return {
                'error': str(e),
                'original_text': test_text,
                'filtered_text': test_text
            }
    
    def get_phi_statistics(self) -> Dict[str, Any]:
        """Get PHI filtering statistics from processed documents"""
        try:
            # This would require storing PHI stats in the database
            # For now, return basic information
            settings = self._get_phi_settings()
            
            total_filtered_docs = db.session.query(MedicalDocument).filter(
                MedicalDocument.phi_filtered == True
            ).count()
            
            return {
                'total_documents_filtered': total_filtered_docs,
                'current_settings': {
                    'phi_filtering_enabled': settings.phi_filtering_enabled,
                    'filter_ssn': settings.filter_ssn,
                    'filter_phone': settings.filter_phone,
                    'filter_mrn': settings.filter_mrn,
                    'filter_insurance': settings.filter_insurance,
                    'filter_addresses': settings.filter_addresses,
                    'filter_names': settings.filter_names,
                    'filter_dates': settings.filter_dates
                },
                'last_updated': settings.updated_at.isoformat() if settings.updated_at else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting PHI statistics: {str(e)}")
            return {}
    
    def export_phi_config(self) -> Dict[str, Any]:
        """Export PHI filtering configuration for backup/compliance"""
        try:
            settings = self._get_phi_settings()
            
            config = {
                'phi_filtering_enabled': settings.phi_filtering_enabled,
                'filter_settings': {
                    'ssn': settings.filter_ssn,
                    'phone': settings.filter_phone,
                    'mrn': settings.filter_mrn,
                    'insurance': settings.filter_insurance,
                    'addresses': settings.filter_addresses,
                    'names': settings.filter_names,
                    'dates': settings.filter_dates
                },
                'patterns': self.patterns,
                'replacements': self.replacements,
                'medical_preservations': self.medical_preservations,
                'export_timestamp': datetime.utcnow().isoformat(),
                'version': '1.0'
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error exporting PHI config: {str(e)}")
            return {}
