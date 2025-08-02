"""
FHIR data parser - Converts FHIR bundles to internal data models
"""
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)

class FHIRParser:
    """Parses FHIR resources into internal data structures"""
    
    def __init__(self):
        self.gender_mapping = {
            'male': 'Male',
            'female': 'Female',
            'other': 'Other',
            'unknown': 'Unknown'
        }
    
    def parse_patient(self, fhir_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Patient resource to internal format"""
        try:
            # Extract name
            names = fhir_patient.get('name', [])
            first_name = ''
            last_name = ''
            
            if names:
                name = names[0]  # Use first name entry
                given = name.get('given', [])
                family = name.get('family', '')
                
                first_name = ' '.join(given) if given else ''
                last_name = family
            
            # Extract birth date
            birth_date_str = fhir_patient.get('birthDate')
            birth_date = None
            if birth_date_str:
                try:
                    birth_date = parse_date(birth_date_str).date()
                except:
                    logger.warning(f"Could not parse birth date: {birth_date_str}")
            
            # Extract gender
            fhir_gender = fhir_patient.get('gender', 'unknown')
            gender = self.gender_mapping.get(fhir_gender.lower(), 'Unknown')
            
            # Extract contact information
            telecoms = fhir_patient.get('telecom', [])
            phone = ''
            email = ''
            
            for telecom in telecoms:
                system = telecom.get('system', '')
                value = telecom.get('value', '')
                
                if system == 'phone' and not phone:
                    phone = value
                elif system == 'email' and not email:
                    email = value
            
            # Extract identifiers (MRN)
            identifiers = fhir_patient.get('identifier', [])
            mrn = ''
            
            for identifier in identifiers:
                system = identifier.get('system', '')
                if 'mrn' in system.lower() or 'medical-record' in system.lower():
                    mrn = identifier.get('value', '')
                    break
            
            if not mrn and identifiers:
                # Fallback to first identifier
                mrn = identifiers[0].get('value', '')
            
            return {
                'fhir_id': fhir_patient.get('id'),
                'mrn': mrn,
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': birth_date,
                'gender': gender,
                'phone': phone,
                'email': email
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR patient: {str(e)}")
            return {}
    
    def parse_document_reference(self, fhir_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR DocumentReference to internal format"""
        try:
            # Extract basic info
            doc_id = fhir_doc.get('id')
            
            # Extract document type
            type_coding = fhir_doc.get('type', {}).get('coding', [])
            document_type = ''
            if type_coding:
                document_type = type_coding[0].get('display', type_coding[0].get('code', ''))
            
            # Extract date
            doc_date = None
            date_str = fhir_doc.get('date')
            if date_str:
                try:
                    doc_date = parse_date(date_str).date()
                except:
                    logger.warning(f"Could not parse document date: {date_str}")
            
            # Extract content info
            content = fhir_doc.get('content', [])
            filename = ''
            content_type = ''
            
            if content:
                attachment = content[0].get('attachment', {})
                filename = attachment.get('title', attachment.get('url', ''))
                content_type = attachment.get('contentType', '')
            
            # Extract description
            description = fhir_doc.get('description', '')
            
            # Determine document category
            category = self._categorize_document(document_type, filename, description)
            
            return {
                'fhir_id': doc_id,
                'filename': filename or f"Document_{doc_id}",
                'document_type': category,
                'document_date': doc_date,
                'content_type': content_type,
                'description': description,
                'raw_fhir': json.dumps(fhir_doc)
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR document reference: {str(e)}")
            return {}
    
    def parse_diagnostic_report(self, fhir_report: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR DiagnosticReport to internal format"""
        try:
            report_id = fhir_report.get('id')
            
            # Extract category
            categories = fhir_report.get('category', [])
            category = ''
            if categories:
                coding = categories[0].get('coding', [])
                if coding:
                    category = coding[0].get('display', coding[0].get('code', ''))
            
            # Extract code/type
            code_info = fhir_report.get('code', {})
            code_text = ''
            if code_info:
                coding = code_info.get('coding', [])
                if coding:
                    code_text = coding[0].get('display', coding[0].get('code', ''))
                else:
                    code_text = code_info.get('text', '')
            
            # Extract date
            report_date = None
            date_str = fhir_report.get('effectiveDateTime') or fhir_report.get('effectivePeriod', {}).get('start')
            if date_str:
                try:
                    report_date = parse_date(date_str).date()
                except:
                    logger.warning(f"Could not parse report date: {date_str}")
            
            # Extract conclusion
            conclusion = fhir_report.get('conclusion', '')
            
            # Extract status
            status = fhir_report.get('status', '')
            
            return {
                'fhir_id': report_id,
                'category': category,
                'code_text': code_text,
                'report_date': report_date,
                'conclusion': conclusion,
                'status': status,
                'raw_fhir': json.dumps(fhir_report)
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR diagnostic report: {str(e)}")
            return {}
    
    def parse_condition(self, fhir_condition: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Condition to internal format"""
        try:
            condition_id = fhir_condition.get('id')
            
            # Extract condition code and display
            code_info = fhir_condition.get('code', {})
            condition_code = ''
            condition_name = ''
            
            if code_info:
                coding = code_info.get('coding', [])
                if coding:
                    condition_code = coding[0].get('code', '')
                    condition_name = coding[0].get('display', '')
                
                if not condition_name:
                    condition_name = code_info.get('text', '')
            
            # Extract onset date
            onset_date = None
            onset_datetime = fhir_condition.get('onsetDateTime')
            if onset_datetime:
                try:
                    onset_date = parse_date(onset_datetime).date()
                except:
                    logger.warning(f"Could not parse onset date: {onset_datetime}")
            
            # Extract clinical status
            clinical_status = fhir_condition.get('clinicalStatus', {})
            is_active = True
            if clinical_status:
                coding = clinical_status.get('coding', [])
                if coding:
                    status_code = coding[0].get('code', '').lower()
                    is_active = status_code in ['active', 'relapse', 'remission']
            
            return {
                'fhir_id': condition_id,
                'condition_code': condition_code,
                'condition_name': condition_name,
                'diagnosis_date': onset_date,
                'is_active': is_active
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR condition: {str(e)}")
            return {}
    
    def parse_observation(self, fhir_observation: Dict[str, Any]) -> Dict[str, Any]:
        """Parse FHIR Observation to internal format"""
        try:
            obs_id = fhir_observation.get('id')
            
            # Extract code
            code_info = fhir_observation.get('code', {})
            code_text = ''
            if code_info:
                coding = code_info.get('coding', [])
                if coding:
                    code_text = coding[0].get('display', coding[0].get('code', ''))
                else:
                    code_text = code_info.get('text', '')
            
            # Extract value
            value_text = ''
            value_quantity = fhir_observation.get('valueQuantity')
            value_string = fhir_observation.get('valueString')
            
            if value_quantity:
                value_text = f"{value_quantity.get('value', '')} {value_quantity.get('unit', '')}"
            elif value_string:
                value_text = value_string
            
            # Extract date
            obs_date = None
            date_str = fhir_observation.get('effectiveDateTime')
            if date_str:
                try:
                    obs_date = parse_date(date_str).date()
                except:
                    logger.warning(f"Could not parse observation date: {date_str}")
            
            # Extract category
            categories = fhir_observation.get('category', [])
            category = ''
            if categories:
                coding = categories[0].get('coding', [])
                if coding:
                    category = coding[0].get('display', coding[0].get('code', ''))
            
            return {
                'fhir_id': obs_id,
                'code_text': code_text,
                'value_text': value_text,
                'observation_date': obs_date,
                'category': category,
                'raw_fhir': json.dumps(fhir_observation)
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR observation: {str(e)}")
            return {}
    
    def _categorize_document(self, doc_type: str, filename: str, description: str) -> str:
        """Categorize document based on type, filename, and description"""
        combined_text = f"{doc_type} {filename} {description}".lower()
        
        # Lab-related keywords
        lab_keywords = ['lab', 'laboratory', 'blood', 'urine', 'chemistry', 'cbc', 'lipid', 'glucose']
        if any(keyword in combined_text for keyword in lab_keywords):
            return 'lab'
        
        # Imaging-related keywords
        imaging_keywords = ['imaging', 'radiology', 'xray', 'x-ray', 'ct', 'mri', 'ultrasound', 'mammogram']
        if any(keyword in combined_text for keyword in imaging_keywords):
            return 'imaging'
        
        # Consult-related keywords
        consult_keywords = ['consult', 'consultation', 'referral', 'specialist', 'cardiology', 'neurology']
        if any(keyword in combined_text for keyword in consult_keywords):
            return 'consult'
        
        # Hospital-related keywords
        hospital_keywords = ['admission', 'discharge', 'hospital', 'inpatient', 'emergency']
        if any(keyword in combined_text for keyword in hospital_keywords):
            return 'hospital'
        
        return 'other'

# Global parser instance
fhir_parser = FHIRParser()
