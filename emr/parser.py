from datetime import datetime
from models import Patient, PatientCondition, MedicalDocument
from app import db
import logging

class FHIRParser:
    """Converts FHIR resources to internal data models"""
    
    def __init__(self):
        pass
    
    def parse_patient(self, fhir_patient):
        """Convert FHIR Patient resource to internal Patient model"""
        try:
            # Extract basic information
            identifier = self._get_identifier(fhir_patient)
            name = self._get_human_name(fhir_patient)
            
            patient_data = {
                'mrn': identifier,
                'first_name': name.get('given', 'Unknown'),
                'last_name': name.get('family', 'Unknown'),
                'date_of_birth': self._parse_date(fhir_patient.get('birthDate')),
                'gender': fhir_patient.get('gender', 'unknown'),
                'phone': self._get_telecom(fhir_patient, 'phone'),
                'email': self._get_telecom(fhir_patient, 'email'),
                'address': self._get_address(fhir_patient)
            }
            
            return patient_data
            
        except Exception as e:
            logging.error(f"Error parsing FHIR patient: {str(e)}")
            return None
    
    def parse_condition(self, fhir_condition, patient_id):
        """Convert FHIR Condition resource to internal PatientCondition model"""
        try:
            condition_data = {
                'patient_id': patient_id,
                'condition_name': self._get_coding_display(fhir_condition.get('code')),
                'icd10_code': self._get_coding_code(fhir_condition.get('code'), 'ICD-10'),
                'diagnosis_date': self._parse_date(fhir_condition.get('onsetDateTime')),
                'status': self._map_condition_status(fhir_condition.get('clinicalStatus'))
            }
            
            return condition_data
            
        except Exception as e:
            logging.error(f"Error parsing FHIR condition: {str(e)}")
            return None
    
    def parse_document_reference(self, fhir_doc_ref, patient_id):
        """Convert FHIR DocumentReference to internal MedicalDocument model"""
        try:
            doc_data = {
                'patient_id': patient_id,
                'filename': fhir_doc_ref.get('description', 'FHIR Document'),
                'document_type': self._get_document_type(fhir_doc_ref),
                'document_date': self._parse_date(fhir_doc_ref.get('date')),
                'file_path': self._get_document_url(fhir_doc_ref)
            }
            
            return doc_data
            
        except Exception as e:
            logging.error(f"Error parsing FHIR document reference: {str(e)}")
            return None
    
    def parse_observation(self, fhir_observation, patient_id):
        """Parse FHIR Observation resource"""
        try:
            obs_data = {
                'patient_id': patient_id,
                'code': self._get_coding_display(fhir_observation.get('code')),
                'value': self._get_observation_value(fhir_observation),
                'unit': self._get_observation_unit(fhir_observation),
                'date': self._parse_date(fhir_observation.get('effectiveDateTime')),
                'status': fhir_observation.get('status')
            }
            
            return obs_data
            
        except Exception as e:
            logging.error(f"Error parsing FHIR observation: {str(e)}")
            return None
    
    def _get_identifier(self, fhir_resource):
        """Extract identifier from FHIR resource"""
        identifiers = fhir_resource.get('identifier', [])
        if identifiers:
            # Prefer MRN type identifier
            for identifier in identifiers:
                if identifier.get('type', {}).get('text') == 'MRN':
                    return identifier.get('value')
            # Fallback to first identifier
            return identifiers[0].get('value')
        return f"FHIR_{fhir_resource.get('id', 'unknown')}"
    
    def _get_human_name(self, fhir_patient):
        """Extract human name from FHIR Patient"""
        names = fhir_patient.get('name', [])
        if names:
            name = names[0]  # Use first name
            return {
                'given': ' '.join(name.get('given', [])),
                'family': name.get('family', '')
            }
        return {'given': 'Unknown', 'family': 'Unknown'}
    
    def _get_telecom(self, fhir_resource, system):
        """Extract telecom information"""
        telecoms = fhir_resource.get('telecom', [])
        for telecom in telecoms:
            if telecom.get('system') == system:
                return telecom.get('value')
        return None
    
    def _get_address(self, fhir_patient):
        """Extract address from FHIR Patient"""
        addresses = fhir_patient.get('address', [])
        if addresses:
            address = addresses[0]
            parts = []
            if address.get('line'):
                parts.extend(address['line'])
            if address.get('city'):
                parts.append(address['city'])
            if address.get('state'):
                parts.append(address['state'])
            if address.get('postalCode'):
                parts.append(address['postalCode'])
            return ', '.join(parts)
        return None
    
    def _get_coding_display(self, code_concept):
        """Get display text from CodeableConcept"""
        if not code_concept:
            return None
        
        if code_concept.get('text'):
            return code_concept['text']
        
        codings = code_concept.get('coding', [])
        if codings:
            return codings[0].get('display', codings[0].get('code'))
        
        return None
    
    def _get_coding_code(self, code_concept, system_filter=None):
        """Get code from CodeableConcept"""
        if not code_concept:
            return None
        
        codings = code_concept.get('coding', [])
        for coding in codings:
            if not system_filter or system_filter.lower() in coding.get('system', '').lower():
                return coding.get('code')
        
        return None
    
    def _parse_date(self, date_string):
        """Parse FHIR date string to Python date"""
        if not date_string:
            return None
        
        try:
            # Handle different FHIR date formats
            if 'T' in date_string:
                return datetime.fromisoformat(date_string.replace('Z', '+00:00')).date()
            else:
                return datetime.strptime(date_string, '%Y-%m-%d').date()
        except ValueError:
            return None
    
    def _map_condition_status(self, clinical_status):
        """Map FHIR condition status to internal status"""
        if not clinical_status:
            return 'active'
        
        status_mapping = {
            'active': 'active',
            'recurrence': 'active',
            'relapse': 'active',
            'inactive': 'resolved',
            'remission': 'resolved',
            'resolved': 'resolved'
        }
        
        status_code = clinical_status.get('coding', [{}])[0].get('code', 'active')
        return status_mapping.get(status_code, 'active')
    
    def _get_document_type(self, fhir_doc_ref):
        """Determine document type from FHIR DocumentReference"""
        type_concept = fhir_doc_ref.get('type', {})
        type_display = self._get_coding_display(type_concept)
        
        if not type_display:
            return 'other'
        
        type_lower = type_display.lower()
        
        # Map to internal document types
        if any(term in type_lower for term in ['lab', 'laboratory', 'blood', 'urine']):
            return 'lab'
        elif any(term in type_lower for term in ['imaging', 'radiology', 'x-ray', 'ct', 'mri']):
            return 'imaging'
        elif any(term in type_lower for term in ['consult', 'specialist', 'referral']):
            return 'consult'
        elif any(term in type_lower for term in ['hospital', 'admission', 'discharge']):
            return 'hospital'
        else:
            return 'other'
    
    def _get_document_url(self, fhir_doc_ref):
        """Get document URL from FHIR DocumentReference"""
        content = fhir_doc_ref.get('content', [])
        if content:
            attachment = content[0].get('attachment', {})
            return attachment.get('url')
        return None
    
    def _get_observation_value(self, fhir_observation):
        """Extract observation value"""
        if 'valueQuantity' in fhir_observation:
            return str(fhir_observation['valueQuantity'].get('value'))
        elif 'valueString' in fhir_observation:
            return fhir_observation['valueString']
        elif 'valueCodeableConcept' in fhir_observation:
            return self._get_coding_display(fhir_observation['valueCodeableConcept'])
        return None
    
    def _get_observation_unit(self, fhir_observation):
        """Extract observation unit"""
        if 'valueQuantity' in fhir_observation:
            return fhir_observation['valueQuantity'].get('unit')
        return None
