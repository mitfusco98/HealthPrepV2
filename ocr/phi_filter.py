"""
Regex-based PHI redaction for HIPAA compliance
"""
import re
from app import db
from models import PHIFilterSettings
import logging

class PHIFilter:
    """HIPAA-compliant PHI filtering using regex patterns
    
    IDEMPOTENCY: This filter detects already-redacted patterns and skips them
    to prevent double-redaction (e.g., "[SSN REDACTED]" becoming "[[SSN REDACTED] REDACTED]").
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_settings = None  # Thread-safe cached settings
        
        # Patterns for already-redacted content (idempotency protection)
        self.redacted_patterns = [
            r'\[SSN REDACTED\]',
            r'\[PHONE REDACTED\]',
            r'\[MRN REDACTED\]',
            r'\[INSURANCE REDACTED\]',
            r'\[ADDRESS REDACTED\]',
            r'\[NAME REDACTED\]',
            r'\[DATE REDACTED\]',
            r'\[[A-Z\s]+ REDACTED\]'  # Catch-all for any redaction marker
        ]
        
        # PHI patterns for detection and redaction
        # SSN patterns are more precise to avoid false positives on account numbers
        self.phi_patterns = {
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX (standard SSN format)
                r'\b\d{3}\s+\d{2}\s+\d{4}\b',  # XXX XX XXXX (space-separated)
                r'(?i)(?:SSN|Social\s*Security(?:\s*Number)?|SS#)[\s:]*\d{9}\b',  # 9 digits with SSN context
            ],
            'phone': [
                r'\(\d{3}\)\s*\d{3}-\d{4}',  # (XXX) XXX-XXXX
                r'\d{3}-\d{3}-\d{4}',  # XXX-XXX-XXXX
                r'\d{3}\.\d{3}\.\d{4}',  # XXX.XXX.XXXX
                r'\b\d{10}\b'  # XXXXXXXXXX (bare 10 digits with word boundaries)
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
    
    def filter_phi(self, text, preloaded_settings=None):
        """Apply PHI filtering to text - always enabled for HIPAA compliance
        
        IDEMPOTENCY: Detects already-redacted patterns and protects them from
        double-redaction. Safe to call multiple times on the same text.
        
        THREAD SAFETY: Pass preloaded_settings dict when calling from worker threads
        to avoid cross-thread session issues during batch processing.
        
        Args:
            text: Text to filter
            preloaded_settings: Optional dict with setting flags (filter_ssn, filter_phone, etc.)
                              If None, queries database for fresh settings.
        """
        if not text:
            return text
        
        settings = preloaded_settings if preloaded_settings else self._get_filter_settings()
        
        filtered_text = text
        
        # Track what we're filtering to avoid corrupting medical terms
        # AND already-redacted content (idempotency protection)
        protected_spans = self._identify_protected_spans(text)
        
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
        """Get current PHI filter settings
        
        Always queries the database for fresh settings to ensure admin
        configuration changes take effect immediately. Database queries
        are lightweight (single row) and essential for correct behavior.
        """
        settings = PHIFilterSettings.query.first()
        if not settings:
            # Create default settings
            settings = PHIFilterSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def get_settings_snapshot(self):
        """Get a thread-safe snapshot of PHI filter settings
        
        Returns a simple object with the same attributes as PHIFilterSettings
        but safe for use across threads. Call this before batch processing
        and pass the result to filter_phi() as preloaded_settings.
        
        Returns:
            Object with filter_* boolean attributes
        """
        settings = self._get_filter_settings()
        
        class SettingsSnapshot:
            def __init__(self, src):
                self.filter_ssn = getattr(src, 'filter_ssn', True)
                self.filter_phone = getattr(src, 'filter_phone', True)
                self.filter_mrn = getattr(src, 'filter_mrn', True)
                self.filter_insurance = getattr(src, 'filter_insurance', True)
                self.filter_addresses = getattr(src, 'filter_addresses', True)
                self.filter_names = getattr(src, 'filter_names', True)
                self.filter_dates = getattr(src, 'filter_dates', False)
        
        return SettingsSnapshot(settings)
    
    def _identify_protected_spans(self, text):
        """Identify spans that should be protected from filtering
        
        This includes:
        1. Medical terms (blood pressure, lab values, etc.)
        2. Already-redacted content (idempotency protection)
        """
        protected_spans = []
        
        # Protect medical terms
        for pattern in self.medical_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                protected_spans.append((match.start(), match.end()))
        
        # Protect already-redacted content (idempotency)
        for pattern in self.redacted_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                protected_spans.append((match.start(), match.end()))
        
        return protected_spans
    
    def _identify_medical_terms(self, text):
        """Identify medical terms that should be protected from filtering
        
        DEPRECATED: Use _identify_protected_spans instead for idempotency support.
        Kept for backward compatibility.
        """
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
    
    def filter_phi_with_counts(self, text, preloaded_settings=None):
        """
        Apply PHI filtering and return both filtered text and counts of redactions
        
        Used for audit logging to track what PHI types were found and redacted.
        
        Args:
            text: Text to filter
            preloaded_settings: Optional settings snapshot for thread safety
            
        Returns:
            Tuple of (filtered_text, phi_counts_dict)
            where phi_counts_dict maps PHI type to count, e.g. {'ssn': 2, 'phone': 1}
        """
        if not text:
            return text, {}
        
        settings = preloaded_settings if preloaded_settings else self._get_filter_settings()
        
        filtered_text = text
        phi_counts = {}
        
        protected_spans = self._identify_protected_spans(text)
        
        filter_methods = {
            'ssn': (settings.filter_ssn, self._filter_ssn, '[SSN REDACTED]'),
            'phone': (settings.filter_phone, self._filter_phone, '[PHONE REDACTED]'),
            'mrn': (settings.filter_mrn, self._filter_mrn, '[MRN REDACTED]'),
            'insurance': (settings.filter_insurance, self._filter_insurance, '[INSURANCE REDACTED]'),
            'addresses': (settings.filter_addresses, self._filter_addresses, '[ADDRESS REDACTED]'),
            'names': (settings.filter_names, self._filter_names, '[NAME REDACTED]'),
            'dates': (settings.filter_dates, self._filter_dates, '[DATE REDACTED]')
        }
        
        for filter_type, (enabled, filter_func, marker) in filter_methods.items():
            if enabled:
                before_count = filtered_text.count(marker)
                filtered_text = filter_func(filtered_text, protected_spans)
                after_count = filtered_text.count(marker)
                new_redactions = after_count - before_count
                if new_redactions > 0:
                    phi_counts[filter_type] = new_redactions
        
        return filtered_text, phi_counts
    
    # Class-level medical keywords whitelist for title filtering
    MEDICAL_KEYWORDS = {
        # Document types and sections
        'lab', 'labs', 'results', 'report', 'note', 'notes', 'progress', 'assessment',
        'plan', 'summary', 'discharge', 'admission', 'consultation', 'referral',
        'order', 'orders', 'prescription', 'imaging', 'xray', 'x-ray', 'ct', 'mri',
        'record', 'documentation', 'narrative', 'addendum', 'amendment', 'correction',
        # Imaging procedures
        'ultrasound', 'ecg', 'ekg', 'mammogram', 'mammography', 'colonoscopy',
        'echocardiogram', 'echo', 'dexa', 'dxa', 'densitometry', 'density', 'angiogram',
        'fluoroscopy', 'tomography', 'arteriogram', 'venogram',
        # Lab tests and panels
        'blood', 'panel', 'cbc', 'cmp', 'bmp', 'lipid', 'a1c', 'glucose', 'cholesterol',
        'hemoglobin', 'hematocrit', 'platelet', 'count', 'differential', 'smear',
        'triglyceride', 'hdl', 'ldl', 'creatinine', 'bun', 'electrolyte', 'potassium',
        'sodium', 'calcium', 'magnesium', 'phosphorus', 'albumin', 'bilirubin',
        'enzyme', 'troponin', 'bnp', 'procalcitonin', 'ferritin', 'iron', 'vitamin',
        'thyroid', 'tsh', 't3', 't4', 'psa', 'cea', 'afp', 'hcg', 'ige', 'culture',
        'urinalysis', 'urine', 'stool', 'fecal', 'occult', 'coagulation', 'pt', 'inr',
        # Pathology and cytology
        'pathology', 'biopsy', 'cytology', 'radiology', 'nuclear', 'pet', 'scan',
        'histology', 'specimen', 'tissue', 'cell', 'cells', 'cellular',
        # Physical exams and visits
        'physical', 'exam', 'examination', 'history', 'visit', 'encounter', 'follow-up', 'followup',
        'evaluation', 'eval', 'consult', 'review', 'assessment', 'checkup',
        # Preventive care
        'vaccine', 'vaccination', 'immunization', 'screening', 'preventive', 'annual',
        'wellness', 'prophylaxis', 'prophylactic', 'flu', 'influenza', 'covid', 'tdap',
        'pneumococcal', 'shingles', 'hepatitis', 'mmr', 'polio', 'varicella', 'hpv',
        # Surgical and procedural
        'operative', 'surgical', 'procedure', 'anesthesia', 'recovery', 'surgery',
        'endoscopy', 'arthroscopy', 'laparoscopy', 'thoracoscopy', 'bronchoscopy',
        'cystoscopy', 'sigmoidoscopy', 'esophagogastroduodenoscopy', 'egd',
        # Care settings
        'emergency', 'urgent', 'inpatient', 'outpatient', 'clinic', 'clinical',
        'ambulatory', 'acute', 'chronic', 'critical', 'intensive', 'icu', 'nicu',
        # Medical specialties
        'cardiology', 'oncology', 'neurology', 'dermatology', 'ophthalmology',
        'gastroenterology', 'pulmonology', 'endocrinology', 'rheumatology',
        'urology', 'nephrology', 'hematology', 'infectious', 'disease', 'internal',
        'medicine', 'pediatric', 'obstetric', 'gynecology', 'ob', 'gyn', 'obgyn',
        'orthopedic', 'ortho', 'podiatry', 'radiology', 'pathology', 'anesthesiology',
        'psychiatry', 'psychology', 'geriatric', 'neonatal', 'palliative', 'hospice',
        # Healthcare roles and settings
        'primary', 'care', 'specialist', 'specialty', 'department', 'unit',
        # Test descriptors
        'test', 'testing', 'analysis', 'complete', 'comprehensive', 'basic',
        'metabolic', 'diagnostic', 'therapeutic', 'final', 'preliminary', 'draft',
        'random', 'fasting', 'timed', 'serial', 'stat', 'routine', 'urgent',
        # Body parts and systems
        'chest', 'abdominal', 'pelvic', 'bone', 'joint', 'spine', 'brain', 'head',
        'neck', 'cardiac', 'vascular', 'hepatic', 'renal', 'pulmonary', 'dental',
        'vision', 'hearing', 'mental', 'health', 'behavioral', 'psychiatric',
        'skeletal', 'muscular', 'nervous', 'digestive', 'respiratory', 'circulatory',
        'lymphatic', 'endocrine', 'reproductive', 'urinary', 'integumentary', 'ocular',
        # Therapy and rehabilitation
        'therapy', 'rehabilitation', 'occupational', 'speech', 'dietary', 'nutrition',
        'physical', 'respiratory', 'cardiac', 'pulmonary', 'aquatic', 'vestibular',
        # Common conditions/diagnoses
        'allergy', 'asthma', 'diabetes', 'hypertension', 'cancer', 'tumor',
        'infection', 'viral', 'bacterial', 'fungal', 'antibiotic', 'medication',
        'anemia', 'leukemia', 'lymphoma', 'melanoma', 'carcinoma', 'sarcoma',
        # Administrative/billing
        'prescription', 'refill', 'renewal', 'authorization', 'prior', 'auth',
        'insurance', 'billing', 'payment', 'invoice', 'statement', 'receipt',
        'consent', 'release', 'authorization', 'hipaa', 'privacy', 'notice',
        'demographic', 'registration', 'intake', 'form', 'questionnaire', 'survey',
        # Time-related
        'after', 'before', 'during', 'pre', 'post', 'day', 'week', 'month', 'year',
        'first', 'second', 'third', 'initial', 'follow', 'up', 'routine', 'regular',
        # Visit types
        'new', 'established', 'patient', 'office', 'telehealth', 'telemedicine',
        'video', 'phone', 'call', 'message', 'portal', 'mychart', 'epic', 'chart',
        # Modifiers
        'with', 'without', 'and', 'or', 'for', 'of', 'the', 'to', 'in', 'on', 'at'
    }
    
    def sanitize_title_for_keywords(self, title):
        """Apply PHI filtering to document titles while preserving keyword-rich medical content.
        
        DUAL-TITLE ARCHITECTURE: This method is used for the search_title field, which
        enables keyword matching while maintaining HIPAA compliance. The result preserves
        medical terms and document type descriptors but removes patient identifying information.
        
        Use this for FHIRDocument.search_title (enables keyword matching).
        Use get_safe_document_type() for FHIRDocument.title (deterministic LOINC-based).
        
        Args:
            title: Original document title/description from Epic
            
        Returns:
            Sanitized title with PHI removed but medical keywords preserved
        """
        return self.filter_title(title)
    
    def filter_title(self, title):
        """Apply aggressive PHI filtering to document titles using whitelist approach
        
        HIPAA COMPLIANCE: Uses a whitelist strategy - only whitelisted medical/document
        keywords are preserved. All other words are assumed to potentially be PHI
        (patient names) and are redacted.
        
        Args:
            title: Document title string
            
        Returns:
            Filtered title with only whitelisted medical terms preserved
        """
        if not title:
            return title
        
        # Step 1: First apply existing PHI patterns (SSN, phone, MRN)
        filtered = title
        
        # Filter SSN
        filtered = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '', filtered)
        
        # Filter MRN patterns
        filtered = re.sub(r'\bMRN[\s:]*\d+', '', filtered, flags=re.IGNORECASE)
        
        # Filter phone numbers
        filtered = re.sub(r'\(\d{3}\)\s*\d{3}-\d{4}', '', filtered)
        filtered = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '', filtered)
        
        # Step 2: Split into tokens and filter using whitelist
        # Preserve separators for reconstruction
        tokens = re.split(r'(\s+|[-–—:,/\\|]+)', filtered)
        
        result_tokens = []
        for token in tokens:
            # Preserve separators and punctuation
            if not token or re.match(r'^[\s\-–—:,/\\|]+$', token):
                result_tokens.append(token)
                continue
            
            # Preserve numbers and dates (may be medically relevant)
            if re.match(r'^[\d./]+$', token):
                result_tokens.append(token)
                continue
            
            # Check if token (or its base form) is a whitelisted keyword
            token_lower = token.lower().strip()
            
            # Direct match
            if token_lower in self.MEDICAL_KEYWORDS:
                result_tokens.append(token)
                continue
            
            # Check for plural/possessive forms
            if token_lower.endswith('s') and token_lower[:-1] in self.MEDICAL_KEYWORDS:
                result_tokens.append(token)
                continue
            
            # Check for common suffixes (-ology, -ography, -oscopy, etc.)
            if any(token_lower.endswith(suffix) for suffix in 
                   ['ology', 'ography', 'oscopy', 'ectomy', 'otomy', 'plasty', 'itis', 'osis']):
                result_tokens.append(token)
                continue
            
            # Token not whitelisted - likely a name, skip it
            # (don't add anything to preserve just the medical context)
        
        # Step 3: Reconstruct and clean up
        result = ''.join(result_tokens)
        
        # Clean up extra separators and whitespace
        result = re.sub(r'[-–—:,/\\|]{2,}', ' - ', result)
        result = re.sub(r'\s{2,}', ' ', result)
        result = re.sub(r'^[\s\-–—:,/\\|]+', '', result)
        result = re.sub(r'[\s\-–—:,/\\|]+$', '', result)
        
        # If nothing remains, return generic title
        if not result.strip():
            return 'Document'
        
        return result.strip()
    
    def sanitize_fhir_resource(self, fhir_json_str):
        """Sanitize FHIR resource JSON to remove PHI before storage
        
        HIPAA COMPLIANCE: FHIR resources from Epic contain patient names, addresses,
        identifiers, and other PHI. This method recursively removes or redacts 
        sensitive fields while preserving clinically-relevant metadata.
        
        Args:
            fhir_json_str: JSON string of FHIR resource
            
        Returns:
            Sanitized JSON string with PHI removed
        """
        import json
        
        if not fhir_json_str:
            return fhir_json_str
        
        try:
            resource = json.loads(fhir_json_str)
        except json.JSONDecodeError:
            return fhir_json_str
        
        # Recursively sanitize the resource
        sanitized = self._sanitize_fhir_object(resource)
        
        return json.dumps(sanitized)
    
    def _sanitize_fhir_object(self, obj):
        """Recursively sanitize a FHIR object, removing PHI fields
        
        Args:
            obj: Dict, list, or primitive value
            
        Returns:
            Sanitized object
        """
        if obj is None:
            return None
        
        # Handle lists - recursively sanitize each item
        if isinstance(obj, list):
            return [self._sanitize_fhir_object(item) for item in obj]
        
        # Handle primitives
        if not isinstance(obj, dict):
            return obj
        
        # Fields to completely remove (contain direct PHI)
        phi_fields_remove = {
            'name', 'telecom', 'address', 'photo', 'contact',
            'communication', 'generalPractitioner', 'managingOrganization',
            'link', 'text', 'contained', 'extension', 'modifierExtension',
            'birthDate', 'deceasedBoolean', 'deceasedDateTime',
            'multipleBirthBoolean', 'multipleBirthInteger',
            'maritalStatus', 'language'
        }
        
        # Fields that always contain PHI strings and should be redacted
        phi_string_fields = {
            'display', 'description', 'comment', 'note', 'notes',
            'valueString', 'valueMarkdown', 'patientInstruction',
            'div', 'narrative', 'label', 'title', 'summary', 'subtitle',
            'conclusion', 'clinicalNotes', 'presentedForm'
        }
        
        # Fields where 'value' should be redacted
        identifier_fields = {'identifier', 'masterIdentifier'}
        
        result = {}
        
        for key, value in obj.items():
            # Skip PHI fields entirely
            if key in phi_fields_remove:
                continue
            
            # Redact all PHI string fields to [REDACTED]
            # HIPAA COMPLIANCE: Free-text fields like 'title', 'summary', 'description' 
            # may contain patient names. We redact them entirely in stored FHIR JSON.
            # The application uses structured type codes for display instead.
            if key in phi_string_fields:
                if isinstance(value, str):
                    result[key] = '[REDACTED]'
                else:
                    result[key] = self._sanitize_fhir_object(value)
                continue
            
            # Redact identifier values but keep type info
            if key in identifier_fields:
                if isinstance(value, list):
                    result[key] = [self._sanitize_identifier(id_obj) for id_obj in value]
                elif isinstance(value, dict):
                    result[key] = self._sanitize_identifier(value)
                else:
                    result[key] = value
                continue
            
            # Handle 'content' array (contains attachments with titles)
            if key == 'content' and isinstance(value, list):
                result[key] = [self._sanitize_content_item(item) for item in value]
                continue
            
            # Handle 'attachment' objects
            if key == 'attachment' and isinstance(value, dict):
                result[key] = self._sanitize_attachment(value)
                continue
            
            # Recursively process nested objects
            result[key] = self._sanitize_fhir_object(value)
        
        return result
    
    def _sanitize_identifier(self, identifier):
        """Sanitize an identifier object - keep type, redact value"""
        if not isinstance(identifier, dict):
            return identifier
        
        result = {}
        for key, value in identifier.items():
            if key == 'value':
                result[key] = '[REDACTED]'
            elif key in ('assigner',):
                # Recursively sanitize assigner reference
                result[key] = self._sanitize_reference(value) if isinstance(value, dict) else value
            else:
                result[key] = self._sanitize_fhir_object(value)
        return result
    
    def _sanitize_reference(self, ref):
        """Sanitize a reference object - redact display name"""
        if not isinstance(ref, dict):
            return ref
        
        result = {}
        for key, value in ref.items():
            if key == 'display':
                result[key] = '[REDACTED]'
            elif key == 'identifier':
                result[key] = self._sanitize_identifier(value) if isinstance(value, dict) else value
            else:
                result[key] = self._sanitize_fhir_object(value)
        return result
    
    def _sanitize_content_item(self, content):
        """Sanitize a content array item (DocumentReference.content)"""
        if not isinstance(content, dict):
            return content
        
        result = {}
        for key, value in content.items():
            if key == 'attachment':
                result[key] = self._sanitize_attachment(value) if isinstance(value, dict) else value
            else:
                result[key] = self._sanitize_fhir_object(value)
        return result
    
    def _sanitize_attachment(self, attachment):
        """Sanitize an attachment object - redact title and data
        
        HIPAA COMPLIANCE: Attachment titles may contain patient names.
        We redact them entirely since the application uses structured type codes
        for document identification instead.
        """
        if not isinstance(attachment, dict):
            return attachment
        
        result = {}
        for key, value in attachment.items():
            if key == 'title':
                # HIPAA: Redact title entirely - may contain patient names
                result[key] = '[REDACTED]'
            elif key == 'data':
                # Remove inline base64 data (may contain PHI)
                result[key] = '[REMOVED]'
            elif key == 'url':
                # Keep URL for reference but content must be fetched fresh
                result[key] = value
            else:
                result[key] = self._sanitize_fhir_object(value)
        return result
    
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
