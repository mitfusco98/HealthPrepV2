"""
FHIR data parser module.
Converts FHIR bundles and resources to internal data models.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import json
from dateutil import parser as date_parser

from models import Patient, MedicalDocument

class FHIRParser:
    """Parser for FHIR resources to internal models"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_patient(self, fhir_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Patient resource to internal patient data"""
        try:
            patient_data = {}
            
            # Extract MRN from identifiers
            identifiers = fhir_patient.get('identifier', [])
            for identifier in identifiers:
                if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                    patient_data['mrn'] = identifier.get('value')
                    break
            
            # Extract name
            names = fhir_patient.get('name', [])
            if names:
                name = names[0]  # Use first name entry
                patient_data['first_name'] = ' '.join(name.get('given', []))
                patient_data['last_name'] = name.get('family', '')
            
            # Extract birth date
            birth_date = fhir_patient.get('birthDate')
            if birth_date:
                patient_data['date_of_birth'] = datetime.strptime(birth_date, '%Y-%m-%d').date()
            
            # Extract gender
            gender = fhir_patient.get('gender')
            if gender:
                gender_map = {'male': 'M', 'female': 'F', 'other': 'O', 'unknown': 'O'}
                patient_data['gender'] = gender_map.get(gender.lower(), 'O')
            
            # Extract contact information
            contacts = fhir_patient.get('telecom', [])
            for contact in contacts:
                if contact.get('system') == 'phone':
                    patient_data['phone'] = contact.get('value')
                elif contact.get('system') == 'email':
                    patient_data['email'] = contact.get('value')
            
            # Extract address
            addresses = fhir_patient.get('address', [])
            if addresses:
                address = addresses[0]
                address_parts = []
                
                if address.get('line'):
                    address_parts.extend(address['line'])
                if address.get('city'):
                    address_parts.append(address['city'])
                if address.get('state'):
                    address_parts.append(address['state'])
                if address.get('postalCode'):
                    address_parts.append(address['postalCode'])
                
                patient_data['address'] = ', '.join(address_parts)
            
            return patient_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR patient: {str(e)}")
            return {}
    
    def parse_observation(self, fhir_observation: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Observation resource to internal format"""
        try:
            observation_data = {}
            
            # Extract effective date
            effective = fhir_observation.get('effectiveDateTime') or fhir_observation.get('effectivePeriod', {}).get('start')
            if effective:
                observation_data['date'] = self._parse_fhir_date(effective)
            
            # Extract code/display
            code = fhir_observation.get('code', {})
            if code.get('coding'):
                coding = code['coding'][0]
                observation_data['code'] = coding.get('code')
                observation_data['display'] = coding.get('display')
            
            # Extract value
            if 'valueQuantity' in fhir_observation:
                value_qty = fhir_observation['valueQuantity']
                observation_data['value'] = value_qty.get('value')
                observation_data['unit'] = value_qty.get('unit')
            elif 'valueString' in fhir_observation:
                observation_data['value'] = fhir_observation['valueString']
            elif 'valueCodeableConcept' in fhir_observation:
                concept = fhir_observation['valueCodeableConcept']
                if concept.get('coding'):
                    observation_data['value'] = concept['coding'][0].get('display')
            
            # Extract reference range
            reference_ranges = fhir_observation.get('referenceRange', [])
            if reference_ranges:
                ref_range = reference_ranges[0]
                observation_data['reference_range'] = {
                    'low': ref_range.get('low', {}).get('value'),
                    'high': ref_range.get('high', {}).get('value'),
                    'unit': ref_range.get('low', {}).get('unit') or ref_range.get('high', {}).get('unit')
                }
            
            # Extract category
            categories = fhir_observation.get('category', [])
            if categories and categories[0].get('coding'):
                observation_data['category'] = categories[0]['coding'][0].get('display', 'laboratory')
            
            return observation_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR observation: {str(e)}")
            return {}
    
    def parse_diagnostic_report(self, fhir_report: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR DiagnosticReport resource to internal format"""
        try:
            report_data = {}
            
            # Extract effective date
            effective = fhir_report.get('effectiveDateTime') or fhir_report.get('effectivePeriod', {}).get('start')
            if effective:
                report_data['date'] = self._parse_fhir_date(effective)
            
            # Extract code/category
            code = fhir_report.get('code', {})
            if code.get('coding'):
                coding = code['coding'][0]
                report_data['code'] = coding.get('code')
                report_data['display'] = coding.get('display')
            
            category = fhir_report.get('category', [])
            if category and category[0].get('coding'):
                report_data['category'] = category[0]['coding'][0].get('display', 'diagnostic')
            
            # Extract conclusion
            report_data['conclusion'] = fhir_report.get('conclusion', '')
            
            # Extract status
            report_data['status'] = fhir_report.get('status', 'unknown')
            
            return report_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR diagnostic report: {str(e)}")
            return {}
    
    def parse_document_reference(self, fhir_doc_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR DocumentReference resource to internal format"""
        try:
            doc_data = {}
            
            # Extract creation date
            date_val = fhir_doc_ref.get('date')
            if date_val:
                doc_data['document_date'] = self._parse_fhir_date(date_val)
            
            # Extract type/category
            type_concept = fhir_doc_ref.get('type', {})
            if type_concept.get('coding'):
                coding = type_concept['coding'][0]
                doc_data['type_code'] = coding.get('code')
                doc_data['type_display'] = coding.get('display')
            
            category = fhir_doc_ref.get('category', [])
            if category and category[0].get('coding'):
                doc_data['category'] = category[0]['coding'][0].get('display', 'clinical')
            
            # Extract description
            doc_data['description'] = fhir_doc_ref.get('description', '')
            
            # Extract content information
            content = fhir_doc_ref.get('content', [])
            if content:
                attachment = content[0].get('attachment', {})
                doc_data['mime_type'] = attachment.get('contentType')
                doc_data['size'] = attachment.get('size')
                doc_data['url'] = attachment.get('url')
                doc_data['title'] = attachment.get('title', '')
            
            # Extract status
            doc_data['status'] = fhir_doc_ref.get('docStatus', 'final')
            
            return doc_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR document reference: {str(e)}")
            return {}
    
    def parse_condition(self, fhir_condition: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Condition resource to internal format"""
        try:
            condition_data = {}
            
            # Extract code
            code = fhir_condition.get('code', {})
            if code.get('coding'):
                coding = code['coding'][0]
                condition_data['code'] = coding.get('code')
                condition_data['display'] = coding.get('display')
                condition_data['system'] = coding.get('system')
            
            # Extract clinical status
            clinical_status = fhir_condition.get('clinicalStatus', {})
            if clinical_status.get('coding'):
                condition_data['clinical_status'] = clinical_status['coding'][0].get('code')
            
            # Extract verification status
            verification_status = fhir_condition.get('verificationStatus', {})
            if verification_status.get('coding'):
                condition_data['verification_status'] = verification_status['coding'][0].get('code')
            
            # Extract onset date
            onset = fhir_condition.get('onsetDateTime')
            if onset:
                condition_data['onset_date'] = self._parse_fhir_date(onset)
            
            # Extract recorded date
            recorded = fhir_condition.get('recordedDate')
            if recorded:
                condition_data['recorded_date'] = self._parse_fhir_date(recorded)
            
            return condition_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR condition: {str(e)}")
            return {}
    
    def parse_procedure(self, fhir_procedure: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Procedure resource to internal format"""
        try:
            procedure_data = {}
            
            # Extract code
            code = fhir_procedure.get('code', {})
            if code.get('coding'):
                coding = code['coding'][0]
                procedure_data['code'] = coding.get('code')
                procedure_data['display'] = coding.get('display')
                procedure_data['system'] = coding.get('system')
            
            # Extract performed date
            performed = fhir_procedure.get('performedDateTime') or fhir_procedure.get('performedPeriod', {}).get('start')
            if performed:
                procedure_data['performed_date'] = self._parse_fhir_date(performed)
            
            # Extract status
            procedure_data['status'] = fhir_procedure.get('status', 'unknown')
            
            # Extract category
            category = fhir_procedure.get('category', {})
            if category.get('coding'):
                procedure_data['category'] = category['coding'][0].get('display')
            
            return procedure_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR procedure: {str(e)}")
            return {}
    
    def _parse_fhir_date(self, date_string: str) -> Optional[date]:
        """Parse FHIR date string to Python date object"""
        try:
            if not date_string:
                return None
            
            # Handle different FHIR date formats
            parsed_date = date_parser.parse(date_string)
            return parsed_date.date()
            
        except Exception as e:
            self.logger.warning(f"Failed to parse date '{date_string}': {str(e)}")
            return None
    
    def categorize_document_type(self, fhir_type: str, fhir_category: str) -> str:
        """Categorize FHIR document into internal document types"""
        type_lower = fhir_type.lower() if fhir_type else ''
        category_lower = fhir_category.lower() if fhir_category else ''
        
        # Laboratory documents
        lab_keywords = ['laboratory', 'lab', 'pathology', 'blood', 'urine', 'specimen']
        if any(keyword in type_lower or keyword in category_lower for keyword in lab_keywords):
            return 'lab'
        
        # Imaging documents
        imaging_keywords = ['radiology', 'imaging', 'xray', 'ct', 'mri', 'ultrasound', 'mammography']
        if any(keyword in type_lower or keyword in category_lower for keyword in imaging_keywords):
            return 'imaging'
        
        # Consultation documents
        consult_keywords = ['consultation', 'consult', 'specialist', 'referral']
        if any(keyword in type_lower or keyword in category_lower for keyword in consult_keywords):
            return 'consult'
        
        # Hospital documents
        hospital_keywords = ['discharge', 'admission', 'hospital', 'inpatient', 'emergency']
        if any(keyword in type_lower or keyword in category_lower for keyword in hospital_keywords):
            return 'hospital'
        
        return 'other'
    
    def extract_screening_relevant_data(self, fhir_resources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Extract data relevant for screening from FHIR resources"""
        screening_data = {
            'lab_results': [],
            'imaging_studies': [],
            'procedures': [],
            'conditions': [],
            'documents': []
        }
        
        for resource in fhir_resources:
            resource_type = resource.get('resourceType', '')
            
            if resource_type == 'Observation':
                screening_data['lab_results'].append(self.parse_observation(resource))
            elif resource_type == 'DiagnosticReport':
                screening_data['imaging_studies'].append(self.parse_diagnostic_report(resource))
            elif resource_type == 'Procedure':
                screening_data['procedures'].append(self.parse_procedure(resource))
            elif resource_type == 'Condition':
                screening_data['conditions'].append(self.parse_condition(resource))
            elif resource_type == 'DocumentReference':
                screening_data['documents'].append(self.parse_document_reference(resource))
        
        return screening_data
