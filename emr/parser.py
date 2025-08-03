"""
FHIR data parser - converts FHIR bundles to internal model representations
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

class FHIRParser:
    """Parser for FHIR resources to internal data models"""
    
    def parse_patient(self, fhir_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Patient resource to internal patient data"""
        try:
            patient_data = {
                'fhir_id': fhir_patient.get('id'),
                'name': self._extract_patient_name(fhir_patient),
                'date_of_birth': self._extract_birth_date(fhir_patient),
                'gender': self._extract_gender(fhir_patient),
                'mrn': self._extract_mrn(fhir_patient)
            }
            return patient_data
        except Exception as e:
            logger.error(f"Error parsing patient: {str(e)}")
            return {}
    
    def _extract_patient_name(self, fhir_patient: Dict[str, Any]) -> str:
        """Extract patient name from FHIR Patient resource"""
        names = fhir_patient.get('name', [])
        if not names:
            return "Unknown Patient"
        
        # Get the first name with use='official' or just the first name
        official_name = None
        for name in names:
            if name.get('use') == 'official':
                official_name = name
                break
        
        name_to_use = official_name or names[0]
        
        # Build full name
        given_names = name_to_use.get('given', [])
        family_name = name_to_use.get('family', '')
        
        full_name = ' '.join(given_names)
        if family_name:
            full_name += f' {family_name}'
        
        return full_name.strip() or "Unknown Patient"
    
    def _extract_birth_date(self, fhir_patient: Dict[str, Any]) -> Optional[date]:
        """Extract birth date from FHIR Patient resource"""
        birth_date_str = fhir_patient.get('birthDate')
        if not birth_date_str:
            return None
        
        try:
            return datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(f"Invalid birth date format: {birth_date_str}")
            return None
    
    def _extract_gender(self, fhir_patient: Dict[str, Any]) -> Optional[str]:
        """Extract gender from FHIR Patient resource"""
        gender = fhir_patient.get('gender')
        if gender:
            # Convert FHIR gender to our format
            gender_map = {
                'male': 'M',
                'female': 'F',
                'other': 'O',
                'unknown': None
            }
            return gender_map.get(gender.lower())
        return None
    
    def _extract_mrn(self, fhir_patient: Dict[str, Any]) -> Optional[str]:
        """Extract MRN from FHIR Patient identifiers"""
        identifiers = fhir_patient.get('identifier', [])
        
        # Look for MRN identifier
        for identifier in identifiers:
            id_type = identifier.get('type', {})
            coding = id_type.get('coding', [])
            
            for code in coding:
                if code.get('code') in ['MR', 'mrn', 'medical-record']:
                    return identifier.get('value')
        
        # If no MRN found, use the first identifier
        if identifiers:
            return identifiers[0].get('value')
        
        return None
    
    def parse_condition(self, fhir_condition: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Condition resource to internal condition data"""
        try:
            condition_data = {
                'fhir_id': fhir_condition.get('id'),
                'condition_code': self._extract_condition_code(fhir_condition),
                'condition_name': self._extract_condition_name(fhir_condition),
                'status': self._extract_condition_status(fhir_condition),
                'onset_date': self._extract_condition_onset(fhir_condition)
            }
            return condition_data
        except Exception as e:
            logger.error(f"Error parsing condition: {str(e)}")
            return {}
    
    def _extract_condition_code(self, fhir_condition: Dict[str, Any]) -> Optional[str]:
        """Extract condition code from FHIR Condition resource"""
        code_data = fhir_condition.get('code', {})
        coding = code_data.get('coding', [])
        
        # Prioritize ICD-10, then SNOMED, then any code
        for code in coding:
            system = code.get('system', '')
            if 'icd-10' in system.lower():
                return code.get('code')
        
        for code in coding:
            system = code.get('system', '')
            if 'snomed' in system.lower():
                return code.get('code')
        
        # Return first available code
        if coding:
            return coding[0].get('code')
        
        return None
    
    def _extract_condition_name(self, fhir_condition: Dict[str, Any]) -> Optional[str]:
        """Extract condition display name from FHIR Condition resource"""
        code_data = fhir_condition.get('code', {})
        
        # Try text first
        if code_data.get('text'):
            return code_data['text']
        
        # Try coding display
        coding = code_data.get('coding', [])
        for code in coding:
            if code.get('display'):
                return code['display']
        
        return None
    
    def _extract_condition_status(self, fhir_condition: Dict[str, Any]) -> str:
        """Extract condition status from FHIR Condition resource"""
        clinical_status = fhir_condition.get('clinicalStatus', {})
        coding = clinical_status.get('coding', [])
        
        if coding:
            status_code = coding[0].get('code', 'unknown')
            # Map FHIR status to our internal status
            status_map = {
                'active': 'active',
                'recurrence': 'active',
                'relapse': 'active',
                'inactive': 'inactive',
                'remission': 'inactive',
                'resolved': 'resolved'
            }
            return status_map.get(status_code, 'unknown')
        
        return 'unknown'
    
    def _extract_condition_onset(self, fhir_condition: Dict[str, Any]) -> Optional[date]:
        """Extract condition onset date from FHIR Condition resource"""
        onset = fhir_condition.get('onsetDateTime') or fhir_condition.get('onsetDate')
        
        if onset:
            try:
                # Handle both datetime and date formats
                if 'T' in onset:
                    return datetime.fromisoformat(onset.replace('Z', '+00:00')).date()
                else:
                    return datetime.strptime(onset, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid onset date format: {onset}")
        
        return None
    
    def parse_document_reference(self, fhir_doc_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR DocumentReference resource to internal document data"""
        try:
            doc_data = {
                'fhir_id': fhir_doc_ref.get('id'),
                'document_type': self._extract_document_type(fhir_doc_ref),
                'filename': self._extract_document_title(fhir_doc_ref),
                'date_created': self._extract_document_date(fhir_doc_ref),
                'content_url': self._extract_content_url(fhir_doc_ref)
            }
            return doc_data
        except Exception as e:
            logger.error(f"Error parsing document reference: {str(e)}")
            return {}
    
    def _extract_document_type(self, fhir_doc_ref: Dict[str, Any]) -> str:
        """Extract document type from FHIR DocumentReference"""
        type_data = fhir_doc_ref.get('type', {})
        coding = type_data.get('coding', [])
        
        if coding:
            code = coding[0].get('code', '').lower()
            display = coding[0].get('display', '').lower()
            
            # Map FHIR document types to our internal types
            if any(term in code or term in display for term in ['lab', 'laboratory']):
                return 'lab'
            elif any(term in code or term in display for term in ['imaging', 'radiology', 'xray', 'ct', 'mri']):
                return 'imaging'
            elif any(term in code or term in display for term in ['consult', 'consultation', 'specialist']):
                return 'consult'
            elif any(term in code or term in display for term in ['hospital', 'discharge', 'admission']):
                return 'hospital'
        
        return 'other'
    
    def _extract_document_title(self, fhir_doc_ref: Dict[str, Any]) -> str:
        """Extract document title/filename from FHIR DocumentReference"""
        # Try description first
        if fhir_doc_ref.get('description'):
            return fhir_doc_ref['description']
        
        # Try type display name
        type_data = fhir_doc_ref.get('type', {})
        if type_data.get('text'):
            return type_data['text']
        
        coding = type_data.get('coding', [])
        if coding and coding[0].get('display'):
            return coding[0]['display']
        
        return f"Document {fhir_doc_ref.get('id', 'Unknown')}"
    
    def _extract_document_date(self, fhir_doc_ref: Dict[str, Any]) -> Optional[date]:
        """Extract document creation date from FHIR DocumentReference"""
        date_str = fhir_doc_ref.get('date') or fhir_doc_ref.get('created')
        
        if date_str:
            try:
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                else:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid document date format: {date_str}")
        
        return None
    
    def _extract_content_url(self, fhir_doc_ref: Dict[str, Any]) -> Optional[str]:
        """Extract content URL from FHIR DocumentReference"""
        content = fhir_doc_ref.get('content', [])
        if content:
            attachment = content[0].get('attachment', {})
            return attachment.get('url')
        return None
    
    def parse_observation(self, fhir_observation: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Observation resource to internal observation data"""
        try:
            obs_data = {
                'fhir_id': fhir_observation.get('id'),
                'code': self._extract_observation_code(fhir_observation),
                'display': self._extract_observation_display(fhir_observation),
                'value': self._extract_observation_value(fhir_observation),
                'unit': self._extract_observation_unit(fhir_observation),
                'date': self._extract_observation_date(fhir_observation),
                'category': self._extract_observation_category(fhir_observation)
            }
            return obs_data
        except Exception as e:
            logger.error(f"Error parsing observation: {str(e)}")
            return {}
    
    def _extract_observation_code(self, fhir_observation: Dict[str, Any]) -> Optional[str]:
        """Extract observation code from FHIR Observation resource"""
        code_data = fhir_observation.get('code', {})
        coding = code_data.get('coding', [])
        
        if coding:
            return coding[0].get('code')
        return None
    
    def _extract_observation_display(self, fhir_observation: Dict[str, Any]) -> Optional[str]:
        """Extract observation display name from FHIR Observation resource"""
        code_data = fhir_observation.get('code', {})
        
        if code_data.get('text'):
            return code_data['text']
        
        coding = code_data.get('coding', [])
        if coding and coding[0].get('display'):
            return coding[0]['display']
        
        return None
    
    def _extract_observation_value(self, fhir_observation: Dict[str, Any]) -> Optional[str]:
        """Extract observation value from FHIR Observation resource"""
        # Handle different value types
        for value_key in ['valueQuantity', 'valueString', 'valueCodeableConcept', 'valueBoolean']:
            if value_key in fhir_observation:
                value_data = fhir_observation[value_key]
                
                if value_key == 'valueQuantity':
                    return str(value_data.get('value', ''))
                elif value_key == 'valueString':
                    return value_data
                elif value_key == 'valueCodeableConcept':
                    return value_data.get('text') or (value_data.get('coding', [{}])[0].get('display'))
                elif value_key == 'valueBoolean':
                    return 'Yes' if value_data else 'No'
        
        return None
    
    def _extract_observation_unit(self, fhir_observation: Dict[str, Any]) -> Optional[str]:
        """Extract observation unit from FHIR Observation resource"""
        value_quantity = fhir_observation.get('valueQuantity', {})
        return value_quantity.get('unit') or value_quantity.get('code')
    
    def _extract_observation_date(self, fhir_observation: Dict[str, Any]) -> Optional[date]:
        """Extract observation date from FHIR Observation resource"""
        date_str = fhir_observation.get('effectiveDateTime') or fhir_observation.get('effectiveDate')
        
        if date_str:
            try:
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                else:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid observation date format: {date_str}")
        
        return None
    
    def _extract_observation_category(self, fhir_observation: Dict[str, Any]) -> str:
        """Extract observation category from FHIR Observation resource"""
        categories = fhir_observation.get('category', [])
        
        for category in categories:
            coding = category.get('coding', [])
            for code in coding:
                code_value = code.get('code', '').lower()
                if 'laboratory' in code_value or 'lab' in code_value:
                    return 'lab'
                elif 'vital' in code_value:
                    return 'vital'
                elif 'imaging' in code_value:
                    return 'imaging'
        
        return 'other'
