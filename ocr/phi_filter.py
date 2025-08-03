"""
Regex-based PHI redaction
HIPAA-compliant filtering of Protected Health Information
"""

import re
import logging
from datetime import datetime
from app import db
from models import PHIFilterSettings

class PHIFilter:
    """Handles HIPAA-compliant PHI filtering from OCR text"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings = self._load_settings()
        
        # Medical terms to preserve (should not be filtered)
        self.medical_terms = [
            # Lab values
            'glucose', 'cholesterol', 'triglycerides', 'hdl', 'ldl', 'a1c', 'hba1c',
            'creatinine', 'bun', 'gfr', 'hemoglobin', 'hematocrit', 'wbc', 'rbc',
            'platelet', 'inr', 'pt', 'ptt', 'tsh', 'free t4', 'vitamin d',
            
            # Measurements
            'mg/dl', 'mmol/l', 'ng/ml', 'pg/ml', 'iu/ml', 'u/l', 'g/dl',
            'mmhg', 'bpm', 'kg', 'lbs', 'cm', 'inches', 'ft',
            
            # Medical procedures
            'mammogram', 'colonoscopy', 'endoscopy', 'biopsy', 'ultrasound',
            'ct scan', 'mri', 'xray', 'x-ray', 'ecg', 'ekg', 'echo',
            
            # Body parts and medical terms
            'heart', 'lung', 'liver', 'kidney', 'brain', 'spine', 'chest',
            'abdomen', 'pelvis', 'extremities', 'skin', 'eye', 'ear'
        ]
        
        # Blood pressure pattern (preserve medical values)
        self.bp_pattern = r'\b\d{2,3}/\d{2,3}\b'
        
        # Initialize regex patterns
        self._compile_patterns()
    
    def _load_settings(self):
        """Load PHI filter settings from database"""
        try:
            settings = PHIFilterSettings.query.first()
            if not settings:
                # Create default settings
                settings = PHIFilterSettings()
                db.session.add(settings)
                db.session.commit()
            return settings
        except Exception as e:
            self.logger.error(f"Error loading PHI filter settings: {str(e)}")
            # Return default settings
            return PHIFilterSettings()
    
    def _compile_patterns(self):
        """Compile regex patterns for PHI detection"""
        self.patterns = {}
        
        # Social Security Numbers
        if self.settings.filter_ssn:
            self.patterns['ssn'] = re.compile(
                r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
                re.IGNORECASE
            )
        
        # Phone Numbers
        if self.settings.filter_phone:
            self.patterns['phone'] = re.compile(
                r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
                re.IGNORECASE
            )
        
        # Medical Record Numbers (various formats)
        if self.settings.filter_mrn:
            self.patterns['mrn'] = re.compile(
                r'\b(?:MRN|Medical\s+Record|Patient\s+ID|ID)\s*[:#]?\s*([A-Z0-9]{6,12})\b',
                re.IGNORECASE
            )
        
        # Insurance Information
        if self.settings.filter_insurance:
            self.patterns['insurance'] = re.compile(
                r'\b(?:Policy|Member|Group|Plan)\s*(?:Number|ID|#)\s*[:#]?\s*([A-Z0-9]{6,20})\b',
                re.IGNORECASE
            )
        
        # Street Addresses
        if self.settings.filter_addresses:
            self.patterns['address'] = re.compile(
                r'\b\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl)\b',
                re.IGNORECASE
            )
        
        # Email Addresses
        if self.settings.filter_names:  # Using names setting for emails
            self.patterns['email'] = re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            )
        
        # Dates (but preserve medical values)
        if self.settings.filter_dates:
            self.patterns['date'] = re.compile(
                r'\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b',
                re.IGNORECASE
            )
    
    def filter_text(self, text):
        """Apply PHI filtering to text"""
        if not self.settings.is_enabled or not text:
            return text
        
        try:
            filtered_text = text
            phi_found = {}
            
            # Apply each filter pattern
            for filter_type, pattern in self.patterns.items():
                matches = pattern.findall(filtered_text)
                if matches:
                    phi_found[filter_type] = len(matches)
                    
                    # Apply filtering based on type
                    if filter_type == 'ssn':
                        filtered_text = pattern.sub('[REDACTED-SSN]', filtered_text)
                    elif filter_type == 'phone':
                        filtered_text = pattern.sub('[REDACTED-PHONE]', filtered_text)
                    elif filter_type == 'mrn':
                        filtered_text = pattern.sub(r'\1 [REDACTED-MRN]', filtered_text)
                    elif filter_type == 'insurance':
                        filtered_text = pattern.sub(r'\1 [REDACTED-INSURANCE]', filtered_text)
                    elif filter_type == 'address':
                        filtered_text = pattern.sub('[REDACTED-ADDRESS]', filtered_text)
                    elif filter_type == 'email':
                        filtered_text = pattern.sub('[REDACTED-EMAIL]', filtered_text)
                    elif filter_type == 'date':
                        # Only filter dates that don't look like medical values
                        filtered_text = self._filter_dates_preserve_medical(filtered_text)
            
            # Log PHI filtering activity
            if phi_found:
                self._log_phi_filtering(phi_found)
            
            return filtered_text
            
        except Exception as e:
            self.logger.error(f"Error filtering PHI from text: {str(e)}")
            return text  # Return original text if filtering fails
    
    def _filter_dates_preserve_medical(self, text):
        """Filter dates while preserving medical context"""
        if not self.settings.preserve_medical_terms:
            return self.patterns['date'].sub('[REDACTED-DATE]', text)
        
        # More sophisticated date filtering that preserves medical values
        words = text.split()
        filtered_words = []
        
        for i, word in enumerate(words):
            if self.patterns['date'].match(word):
                # Check context to see if this might be a medical value
                context_window = 3
                start_idx = max(0, i - context_window)
                end_idx = min(len(words), i + context_window + 1)
                context = ' '.join(words[start_idx:end_idx]).lower()
                
                # Check if surrounded by medical terms
                is_medical = any(term in context for term in self.medical_terms)
                
                # Check if it looks like a blood pressure reading
                if re.match(self.bp_pattern, word):
                    is_medical = True
                
                if is_medical:
                    filtered_words.append(word)  # Keep medical values
                else:
                    filtered_words.append('[REDACTED-DATE]')
            else:
                filtered_words.append(word)
        
        return ' '.join(filtered_words)
    
    def _log_phi_filtering(self, phi_found):
        """Log PHI filtering activity"""
        try:
            from models import AdminLog
            
            phi_summary = []
            for phi_type, count in phi_found.items():
                phi_summary.append(f"{phi_type}: {count}")
            
            log_entry = AdminLog(
                action='phi_filtering',
                description=f"PHI filtered - {', '.join(phi_summary)}"
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging PHI filtering: {str(e)}")
    
    def test_filter(self, test_text):
        """Test PHI filtering on sample text"""
        try:
            original_text = test_text
            filtered_text = self.filter_text(test_text)
            
            # Identify what was filtered
            changes = []
            if original_text != filtered_text:
                # Simple diff to show what changed
                orig_words = original_text.split()
                filt_words = filtered_text.split()
                
                for i, (orig, filt) in enumerate(zip(orig_words, filt_words)):
                    if orig != filt and '[REDACTED' in filt:
                        changes.append({
                            'position': i,
                            'original': orig,
                            'filtered': filt
                        })
            
            return {
                'original': original_text,
                'filtered': filtered_text,
                'changes': changes,
                'phi_detected': len(changes) > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error testing PHI filter: {str(e)}")
            return {
                'original': test_text,
                'filtered': test_text,
                'changes': [],
                'phi_detected': False,
                'error': str(e)
            }
    
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
            
            settings.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Reload settings and recompile patterns
            self.settings = settings
            self._compile_patterns()
            
            self.logger.info("PHI filter settings updated")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating PHI filter settings: {str(e)}")
            db.session.rollback()
            return False
    
    def get_filter_statistics(self):
        """Get statistics about PHI filtering"""
        try:
            # Count documents with PHI filtered text
            from models import MedicalDocument
            
            docs_with_phi = MedicalDocument.query.filter(
                MedicalDocument.phi_filtered_text.isnot(None)
            ).count()
            
            total_docs = MedicalDocument.query.count()
            
            # Count recent PHI filtering events
            from datetime import timedelta
            recent_logs = db.session.query(AdminLog).filter(
                AdminLog.action == 'phi_filtering',
                AdminLog.created_at > datetime.utcnow() - timedelta(days=30)
            ).count()
            
            return {
                'documents_with_phi_filtering': docs_with_phi,
                'total_documents': total_docs,
                'filtering_rate': (docs_with_phi / total_docs * 100) if total_docs > 0 else 0,
                'recent_filtering_events': recent_logs,
                'filter_enabled': self.settings.is_enabled
            }
            
        except Exception as e:
            self.logger.error(f"Error getting filter statistics: {str(e)}")
            return {}
    
    def export_configuration(self):
        """Export current PHI filter configuration"""
        try:
            config = {
                'is_enabled': self.settings.is_enabled,
                'filter_ssn': self.settings.filter_ssn,
                'filter_phone': self.settings.filter_phone,
                'filter_mrn': self.settings.filter_mrn,
                'filter_insurance': self.settings.filter_insurance,
                'filter_addresses': self.settings.filter_addresses,
                'filter_names': self.settings.filter_names,
                'filter_dates': self.settings.filter_dates,
                'preserve_medical_terms': self.settings.preserve_medical_terms,
                'confidence_threshold': self.settings.confidence_threshold,
                'exported_at': datetime.utcnow().isoformat()
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {str(e)}")
            return {}
