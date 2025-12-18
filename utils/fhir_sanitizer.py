"""
FHIR Metadata Sanitizer for HIPAA Compliance

This module sanitizes FHIR resources (DocumentReference, etc.) before storage
to remove PHI while preserving essential metadata for system operation.

PHI fields that are sanitized/removed:
- Patient names, identifiers, SSN
- Address information
- Phone numbers, email addresses
- Practitioner/Author names (replaced with IDs only)
- Free-text descriptions containing PHI
- Binary content (base64 encoded documents)

Preserved fields:
- Resource IDs (Epic document IDs, patient IDs for linking)
- Document type codes (LOINC codes)
- Dates and timestamps
- Content URLs (for re-fetching if needed)
- Content type (MIME type)
- Status and category codes
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class FHIRSanitizer:
    """Sanitize FHIR resources to remove PHI for HIPAA compliance."""
    
    PHI_FIELDS_TO_REMOVE = {
        'name', 'address', 'telecom', 'birthDate', 'deceasedDateTime',
        'deceasedBoolean', 'maritalStatus', 'photo', 'contact',
        'communication', 'generalPractitioner', 'managingOrganization',
        'link', 'multipleBirthBoolean', 'multipleBirthInteger'
    }
    
    PHI_PATTERNS = [
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
        (r'\b\d{9}\b(?=\s|$)', '[SSN_REDACTED]'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        (r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE_REDACTED]'),
        (r'\b\d{1,5}\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\.?\b', '[ADDRESS_REDACTED]'),
        (r'(?i)\bDr\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b', '[PRACTITIONER_REDACTED]'),
    ]
    
    SAFE_CODING_SYSTEMS = {
        'http://loinc.org',
        'http://snomed.info/sct',
        'http://hl7.org/fhir/document-classcodes',
        'http://terminology.hl7.org/CodeSystem/v3-ActCode',
        'http://terminology.hl7.org/CodeSystem/document-classcodes'
    }
    
    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.PHI_PATTERNS
        ]
    
    def sanitize_document_reference(self, doc_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a FHIR DocumentReference resource for storage.
        
        Preserves:
        - id, resourceType
        - type (document type coding)
        - status
        - date (creation date)
        - content.attachment.url (for re-fetching)
        - content.attachment.contentType
        - content.attachment.size
        - content.attachment.hash
        
        Removes/Sanitizes:
        - subject (patient reference - keeps ID only)
        - author (practitioner references - removes names)
        - authenticator
        - custodian
        - content.attachment.data (binary content)
        - description (free text that may contain PHI)
        - context (may contain encounter details)
        """
        if not doc_ref or not isinstance(doc_ref, dict):
            return doc_ref
        
        sanitized = {}
        
        safe_fields = {'id', 'resourceType', 'status', 'date', 'docStatus', 'category'}
        for field in safe_fields:
            if field in doc_ref:
                sanitized[field] = doc_ref[field]
        
        if 'type' in doc_ref:
            sanitized['type'] = self._sanitize_codeable_concept(doc_ref['type'])
        
        if 'subject' in doc_ref:
            sanitized['subject'] = self._sanitize_reference(doc_ref['subject'])
        
        if 'author' in doc_ref:
            sanitized['author'] = [
                self._sanitize_reference(ref) for ref in doc_ref['author']
            ]
        
        if 'content' in doc_ref:
            sanitized['content'] = []
            for content in doc_ref['content']:
                sanitized_content = {}
                if 'attachment' in content:
                    attachment = content['attachment']
                    sanitized_attachment = {}
                    
                    safe_attachment_fields = {'url', 'contentType', 'size', 'hash', 'creation'}
                    for field in safe_attachment_fields:
                        if field in attachment:
                            sanitized_attachment[field] = attachment[field]
                    
                    if 'title' in attachment:
                        sanitized_attachment['title'] = self._sanitize_text(attachment['title'])
                    
                    sanitized_content['attachment'] = sanitized_attachment
                
                if 'format' in content:
                    sanitized_content['format'] = content['format']
                
                sanitized['content'].append(sanitized_content)
        
        if 'meta' in doc_ref:
            meta = doc_ref['meta']
            sanitized['meta'] = {}
            safe_meta_fields = {'versionId', 'lastUpdated', 'source', 'profile', 'tag'}
            for field in safe_meta_fields:
                if field in meta:
                    sanitized[field] = meta[field]
        
        sanitized['_sanitized'] = True
        sanitized['_sanitized_at'] = datetime.utcnow().isoformat()
        
        return sanitized
    
    def _sanitize_codeable_concept(self, concept: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a CodeableConcept, keeping only safe coding systems."""
        if not concept:
            return concept
        
        sanitized = {}
        
        if 'coding' in concept:
            sanitized['coding'] = []
            for coding in concept['coding']:
                system = coding.get('system', '')
                if system in self.SAFE_CODING_SYSTEMS or system.startswith('http://loinc.org'):
                    sanitized['coding'].append({
                        'system': coding.get('system'),
                        'code': coding.get('code'),
                        'display': coding.get('display')
                    })
                else:
                    sanitized['coding'].append({
                        'system': coding.get('system'),
                        'code': coding.get('code'),
                        'display': '[REDACTED]'
                    })
        
        if 'text' in concept:
            sanitized['text'] = self._sanitize_text(concept['text'])
        
        return sanitized
    
    def _sanitize_reference(self, ref: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a FHIR Reference, hashing identifiers for PHI safety.
        
        Patient and Practitioner references may contain MRNs or identifiable codes,
        so we hash them with a secret salt to an opaque identifier while preserving
        referential integrity. The salt prevents rainbow table attacks.
        
        Display names are always redacted (never stored) as they contain PHI.
        """
        import hashlib
        import os
        
        if not ref:
            return ref
        
        sanitized = {}
        
        # Get salt to prevent rainbow table attacks
        # Use SESSION_SECRET or generate random runtime salt (not predictable fallback)
        salt = os.environ.get('SESSION_SECRET', '')
        if not salt:
            import secrets as sec_module
            if not hasattr(FHIRSanitizer, '_runtime_salt'):
                FHIRSanitizer._runtime_salt = sec_module.token_hex(32)
                logger.warning("SESSION_SECRET not set - using random runtime salt for FHIR reference hashing")
            salt = FHIRSanitizer._runtime_salt
        
        if 'reference' in ref:
            reference = ref['reference']
            # Hash the identifier portion with salt to prevent PHI leakage
            # Format: "ResourceType/ID" -> "ResourceType/hash"
            if '/' in reference:
                resource_type, resource_id = reference.rsplit('/', 1)
                salted_id = f"{salt}:{resource_id}"
                hashed_id = hashlib.sha256(salted_id.encode()).hexdigest()[:12]
                sanitized['reference'] = f"{resource_type}/{hashed_id}"
            else:
                salted_ref = f"{salt}:{reference}"
                sanitized['reference'] = f"[ref_{hashlib.sha256(salted_ref.encode()).hexdigest()[:12]}]"
        else:
            # No reference ID available - use generic placeholder
            sanitized['reference'] = "[ref_unknown]"
        
        if 'type' in ref:
            sanitized['type'] = ref['type']
        
        # CRITICAL: Never copy 'display' field - it contains names (PHI)
        # Even if no reference ID, we don't store the display name
        
        return sanitized
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize free text to remove PHI patterns."""
        if not text:
            return text
        
        sanitized = text
        for pattern, replacement in self.compiled_patterns:
            sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized
    
    def sanitize_json_string(self, json_string: str) -> str:
        """Sanitize a JSON string containing FHIR resource."""
        if not json_string:
            return json_string
        
        try:
            resource = json.loads(json_string)
            
            resource_type = resource.get('resourceType', '')
            
            if resource_type == 'DocumentReference':
                sanitized = self.sanitize_document_reference(resource)
            else:
                sanitized = self._generic_sanitize(resource)
            
            return json.dumps(sanitized)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse FHIR JSON for sanitization: {e}")
            return self._sanitize_text(json_string)
    
    def _generic_sanitize(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Generic sanitization for unknown FHIR resource types."""
        if not isinstance(resource, dict):
            return resource
        
        sanitized = {}
        
        for key, value in resource.items():
            if key in self.PHI_FIELDS_TO_REMOVE:
                continue
            
            if key == 'data' and isinstance(value, str) and len(value) > 1000:
                continue
            
            if isinstance(value, dict):
                sanitized[key] = self._generic_sanitize(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._generic_sanitize(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str):
                sanitized[key] = self._sanitize_text(value)
            else:
                sanitized[key] = value
        
        return sanitized


fhir_sanitizer = FHIRSanitizer()
