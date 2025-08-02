"""
Regex-based PHI redaction for HIPAA compliance
Filters personally identifiable information from OCR text
"""
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from models import PHISettings, db

class PHIFilter:
    """Handles PHI filtering and redaction for HIPAA compliance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._load_settings()
        
        # Default PHI patterns - these preserve medical values
        self.phi_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'phone': r'\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',
            'mrn': r'\bMRN:?\s*[A-Z0-9]{6,12}\b',
            'addresses': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Court|Ct|Place|Pl)\b',
            'names': r'\b[A-Z][a-z]+,?\s+[A-Z][a-z]+\b(?=\s|$|,)',
            'dates': r'\b(?:0?[1-9]|1[0-2])[\/\-](?:0?[1-9]|[12][0-9]|3[01])[\/\-](?:19|20)\d{2}\b'
        }
        
        # Medical terms to preserve (never filter these)
        self.medical_terms = {
            'blood_pressure': r'\b\d{2,3}\/\d{2,3}\s*(?:mmHg)?\b',
            'glucose': r'\b\d{2,4}\s*(?:mg\/dL|mmol\/L)\b',
            'cholesterol': r'\b\d{2,4}\s*(?:mg\/dL|mmol\/L)?\b',
            'hemoglobin': r'\b\d{1,2}\.\d\s*(?:g\/dL)?\b',
            'weight': r'\b\d{2,4}\s*(?:lbs?|kg|pounds?)\b',
            'height': r'\b\d\'\s*\d{1,2}\"|\b\d{2,3}\s*(?:cm|inches?)\b',
            'temperature': r'\b\d{2,3}\.\d\s*(?:°F|°C|F|C)?\b',
            'procedures': r'\b(?:mammogram|colonoscopy|pap\s*smear|dexa|dxa|ct\s*scan|mri|x-ray|ultrasound)\b'
        }
        
    def _load_settings(self):
        """Load PHI filtering settings from database"""
        try:
            self.settings = PHISettings.query.first()
            if not self.settings:
                # Create default settings
                self.settings = PHISettings(
                    filter_enabled=True,
                    filter_ssn=True,
                    filter_phone=True,
                    filter_mrn=True,
                    filter_addresses=True,
                    filter_names=True,
                    filter_dates=False  # Be careful with medical dates
                )
                db.session.add(self.settings)
                db.session.commit()
        except Exception as e:
            self.logger.error(f"Error loading PHI settings: {str(e)}")
            # Create minimal default settings
            self.settings = PHISettings()
    
    def filter_phi(self, text: str) -> Dict[str, any]:
        """
        Filter PHI from text while preserving medical terminology
        Returns filtered text and redaction statistics
        """
        try:
            if not self.settings.filter_enabled or not text:
                return {
                    "filtered_text": text,
                    "redactions": {},
                    "total_redactions": 0,
                    "original_length": len(text) if text else 0,
                    "filtered_length": len(text) if text else 0
                }
            
            filtered_text = text
            redaction_stats = {}
            
            # Apply each filter based on settings
            if self.settings.filter_ssn:
                filtered_text, count = self._apply_filter(filtered_text, 'ssn', '[SSN-REDACTED]')
                redaction_stats['ssn'] = count
            
            if self.settings.filter_phone:
                filtered_text, count = self._apply_filter(filtered_text, 'phone', '[PHONE-REDACTED]')
                redaction_stats['phone'] = count
            
            if self.settings.filter_mrn:
                filtered_text, count = self._apply_filter(filtered_text, 'mrn', '[MRN-REDACTED]')
                redaction_stats['mrn'] = count
            
            if self.settings.filter_addresses:
                filtered_text, count = self._apply_filter(filtered_text, 'addresses', '[ADDRESS-REDACTED]')
                redaction_stats['addresses'] = count
            
            if self.settings.filter_names:
                filtered_text, count = self._apply_names_filter(filtered_text)
                redaction_stats['names'] = count
            
            if self.settings.filter_dates:
                filtered_text, count = self._apply_dates_filter(filtered_text)
                redaction_stats['dates'] = count
            
            # Apply custom patterns if any
            if self.settings.custom_patterns:
                try:
                    custom_patterns = json.loads(self.settings.custom_patterns)
                    for pattern in custom_patterns:
                        filtered_text, count = self._apply_custom_filter(filtered_text, pattern)
                        redaction_stats[f'custom_{pattern[:20]}'] = count
                except json.JSONDecodeError:
                    self.logger.warning("Invalid custom patterns JSON")
            
            total_redactions = sum(redaction_stats.values())
            
            return {
                "filtered_text": filtered_text,
                "redactions": redaction_stats,
                "total_redactions": total_redactions,
                "original_length": len(text),
                "filtered_length": len(filtered_text)
            }
            
        except Exception as e:
            self.logger.error(f"Error filtering PHI: {str(e)}")
            return {
                "filtered_text": text,
                "redactions": {},
                "total_redactions": 0,
                "error": str(e)
            }
    
    def _apply_filter(self, text: str, pattern_type: str, replacement: str) -> Tuple[str, int]:
        """Apply a specific PHI filter pattern"""
        try:
            pattern = self.phi_patterns.get(pattern_type)
            if not pattern:
                return text, 0
            
            # Find all matches before replacement to count them
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            # Apply replacement
            filtered_text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
            return filtered_text, len(matches)
            
        except Exception as e:
            self.logger.error(f"Error applying {pattern_type} filter: {str(e)}")
            return text, 0
    
    def _apply_names_filter(self, text: str) -> Tuple[str, int]:
        """Apply names filter with medical term protection"""
        try:
            # First, protect medical terms by temporarily replacing them
            protected_terms = {}
            temp_text = text
            
            for term_type, pattern in self.medical_terms.items():
                matches = re.findall(pattern, temp_text, re.IGNORECASE)
                for i, match in enumerate(matches):
                    placeholder = f"__MEDICAL_{term_type.upper()}_{i}__"
                    protected_terms[placeholder] = match
                    temp_text = temp_text.replace(match, placeholder, 1)
            
            # Now apply names filter
            names_pattern = self.phi_patterns['names']
            matches = re.findall(names_pattern, temp_text, re.IGNORECASE)
            
            # Filter out common medical terms that might match name pattern
            medical_false_positives = [
                'Patient Chart', 'Medical Record', 'Lab Results', 'Test Results',
                'Doctor Note', 'Nurse Note', 'Vital Signs', 'Blood Pressure'
            ]
            
            actual_names = []
            for match in matches:
                if not any(fp.lower() in match.lower() for fp in medical_false_positives):
                    actual_names.append(match)
            
            filtered_text = re.sub(names_pattern, '[NAME-REDACTED]', temp_text, flags=re.IGNORECASE)
            
            # Restore protected medical terms
            for placeholder, original in protected_terms.items():
                filtered_text = filtered_text.replace(placeholder, original)
            
            return filtered_text, len(actual_names)
            
        except Exception as e:
            self.logger.error(f"Error applying names filter: {str(e)}")
            return text, 0
    
    def _apply_dates_filter(self, text: str) -> Tuple[str, int]:
        """Apply dates filter while preserving medical date contexts"""
        try:
            # Protect medical date contexts
            medical_date_contexts = [
                r'(?:born|birth|dob):\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
                r'(?:test|lab|procedure)\s+(?:date|on):\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
                r'(?:visit|appointment)\s+(?:date|on):\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}'
            ]
            
            protected_dates = {}
            temp_text = text
            
            for i, context_pattern in enumerate(medical_date_contexts):
                matches = re.findall(context_pattern, temp_text, re.IGNORECASE)
                for j, match in enumerate(matches):
                    placeholder = f"__MEDICAL_DATE_{i}_{j}__"
                    protected_dates[placeholder] = match
                    temp_text = temp_text.replace(match, placeholder, 1)
            
            # Apply date filter to remaining dates
            dates_pattern = self.phi_patterns['dates']
            matches = re.findall(dates_pattern, temp_text)
            
            filtered_text = re.sub(dates_pattern, '[DATE-REDACTED]', temp_text)
            
            # Restore protected medical dates
            for placeholder, original in protected_dates.items():
                filtered_text = filtered_text.replace(placeholder, original)
            
            return filtered_text, len(matches)
            
        except Exception as e:
            self.logger.error(f"Error applying dates filter: {str(e)}")
            return text, 0
    
    def _apply_custom_filter(self, text: str, pattern: str) -> Tuple[str, int]:
        """Apply custom regex pattern filter"""
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            filtered_text = re.sub(pattern, '[CUSTOM-REDACTED]', text, flags=re.IGNORECASE)
            return filtered_text, len(matches)
            
        except re.error as e:
            self.logger.error(f"Invalid regex pattern '{pattern}': {str(e)}")
            return text, 0
        except Exception as e:
            self.logger.error(f"Error applying custom filter: {str(e)}")
            return text, 0
    
    def test_filter(self, test_text: str) -> Dict[str, any]:
        """Test PHI filter with sample text and return before/after comparison"""
        try:
            result = self.filter_phi(test_text)
            
            return {
                "original_text": test_text,
                "filtered_text": result["filtered_text"],
                "redactions": result["redactions"],
                "total_redactions": result["total_redactions"],
                "reduction_percentage": (
                    (result["original_length"] - result["filtered_length"]) / 
                    result["original_length"] * 100
                ) if result["original_length"] > 0 else 0,
                "settings_used": {
                    "filter_enabled": self.settings.filter_enabled,
                    "filter_ssn": self.settings.filter_ssn,
                    "filter_phone": self.settings.filter_phone,
                    "filter_mrn": self.settings.filter_mrn,
                    "filter_addresses": self.settings.filter_addresses,
                    "filter_names": self.settings.filter_names,
                    "filter_dates": self.settings.filter_dates
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error testing filter: {str(e)}")
            return {"error": str(e)}
    
    def get_filter_statistics(self) -> Dict[str, any]:
        """Get overall PHI filtering statistics"""
        try:
            from models import Document
            
            total_documents = Document.query.count()
            phi_filtered_docs = Document.query.filter_by(phi_filtered=True).count()
            
            # Get documents processed in last 30 days
            thirty_days_ago = datetime.utcnow() - datetime.timedelta(days=30)
            recent_filtered = Document.query.filter(
                Document.created_at >= thirty_days_ago,
                Document.phi_filtered == True
            ).count()
            
            return {
                "total_documents": total_documents,
                "phi_filtered_documents": phi_filtered_docs,
                "filtering_rate": (phi_filtered_docs / total_documents * 100) if total_documents > 0 else 0,
                "recent_30_days": recent_filtered,
                "current_settings": {
                    "filter_enabled": self.settings.filter_enabled,
                    "filter_ssn": self.settings.filter_ssn,
                    "filter_phone": self.settings.filter_phone,
                    "filter_mrn": self.settings.filter_mrn,
                    "filter_addresses": self.settings.filter_addresses,
                    "filter_names": self.settings.filter_names,
                    "filter_dates": self.settings.filter_dates
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting filter statistics: {str(e)}")
            return {"error": str(e)}
    
    def export_settings(self) -> Dict[str, any]:
        """Export current PHI filter settings for backup/compliance"""
        try:
            return {
                "filter_enabled": self.settings.filter_enabled,
                "filter_ssn": self.settings.filter_ssn,
                "filter_phone": self.settings.filter_phone,
                "filter_mrn": self.settings.filter_mrn,
                "filter_addresses": self.settings.filter_addresses,
                "filter_names": self.settings.filter_names,
                "filter_dates": self.settings.filter_dates,
                "custom_patterns": self.settings.custom_patterns,
                "exported_at": datetime.utcnow().isoformat(),
                "patterns_used": self.phi_patterns
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting settings: {str(e)}")
            return {"error": str(e)}
