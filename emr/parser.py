"""
Converts FHIR bundles to internal model
Handles parsing FHIR resources into application models
"""

from datetime import datetime, date
import json
import logging
from models import Patient, MedicalDocument, Condition, Visit
from app import db

class FHIRParser:
    """Parser for converting FHIR resources to internal models"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_patient(self, fhir_patient):
        """Parse FHIR Patient resource to internal Patient model"""
        try:
            # Extract basic patient information
            patient_data = {
                'mrn': self._extract_mrn(fhir_patient),
                'first_name': self._extract_first_name(fhir_patient),
                'last_name': self._extract_last_name(fhir_patient),
                'date_of_birth': self._extract_birth_date(fhir_patient),
                'gender': self._extract_gender(fhir_patient),
                'phone': self._extract_phone(fhir_patient),
                'email': self._extract_email(fhir_patient),
                'address': self._extract_address(fhir_patient)
            }
            
            # Check if patient already exists
            existing_patient = Patient.query.filter_by(mrn=patient_data['mrn']).first()
            
            if existing_patient:
                # Update existing patient
                for key, value in patient_data.items():
                    if value is not None:
                        setattr(existing_patient, key, value)
                patient = existing_patient
            else:
                # Create new patient
                patient = Patient(**patient_data)
                db.session.add(patient)
            
            db.session.commit()
            self.logger.info(f"Parsed patient: {patient.mrn}")
            return patient
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR patient: {str(e)}")
            db.session.rollback()
            return None
    
    def parse_documents_bundle(self, fhir_bundle, patient_id):
        """Parse FHIR DocumentReference bundle"""
        try:
            documents = []
            
            if not fhir_bundle.get('entry'):
                return documents
            
            for entry in fhir_bundle['entry']:
                resource = entry.get('resource')
                if resource and resource.get('resourceType') == 'DocumentReference':
                    document = self._parse_document_reference(resource, patient_id)
                    if document:
                        documents.append(document)
            
            db.session.commit()
            self.logger.info(f"Parsed {len(documents)} documents for patient {patient_id}")
            return documents
            
        except Exception as e:
            self.logger.error(f"Error parsing documents bundle: {str(e)}")
            db.session.rollback()
            return []
    
    def parse_conditions_bundle(self, fhir_bundle, patient_id):
        """Parse FHIR Condition bundle"""
        try:
            conditions = []
            
            if not fhir_bundle.get('entry'):
                return conditions
            
            for entry in fhir_bundle['entry']:
                resource = entry.get('resource')
                if resource and resource.get('resourceType') == 'Condition':
                    condition = self._parse_condition(resource, patient_id)
                    if condition:
                        conditions.append(condition)
            
            db.session.commit()
            self.logger.info(f"Parsed {len(conditions)} conditions for patient {patient_id}")
            return conditions
            
        except Exception as e:
            self.logger.error(f"Error parsing conditions bundle: {str(e)}")
            db.session.rollback()
            return []
    
    def _extract_mrn(self, fhir_patient):
        """Extract MRN from FHIR Patient"""
        identifiers = fhir_patient.get('identifier', [])
        for identifier in identifiers:
            type_coding = identifier.get('type', {}).get('coding', [])
            for coding in type_coding:
                if coding.get('code') == 'MR':  # Medical Record Number
                    return identifier.get('value')
        
        # Fallback to first identifier
        if identifiers:
            return identifiers[0].get('value')
        
        # Fallback to patient ID
        return fhir_patient.get('id', 'UNKNOWN')
    
    def _extract_first_name(self, fhir_patient):
        """Extract first name from FHIR Patient"""
        names = fhir_patient.get('name', [])
        for name in names:
            if name.get('use') in ['official', 'usual'] or not name.get('use'):
                given_names = name.get('given', [])
                if given_names:
                    return given_names[0]
        return 'Unknown'
    
    def _extract_last_name(self, fhir_patient):
        """Extract last name from FHIR Patient"""
        names = fhir_patient.get('name', [])
        for name in names:
            if name.get('use') in ['official', 'usual'] or not name.get('use'):
                return name.get('family', 'Unknown')
        return 'Unknown'
    
    def _extract_birth_date(self, fhir_patient):
        """Extract birth date from FHIR Patient"""
        birth_date_str = fhir_patient.get('birthDate')
        if birth_date_str:
            try:
                return datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.logger.warning(f"Invalid birth date format: {birth_date_str}")
        return None
    
    def _extract_gender(self, fhir_patient):
        """Extract gender from FHIR Patient"""
        gender = fhir_patient.get('gender', '').lower()
        gender_mapping = {
            'male': 'M',
            'female': 'F',
            'other': 'Other',
            'unknown': 'Other'
        }
        return gender_mapping.get(gender, 'Other')
    
    def _extract_phone(self, fhir_patient):
        """Extract phone number from FHIR Patient"""
        telecoms = fhir_patient.get('telecom', [])
        for telecom in telecoms:
            if telecom.get('system') == 'phone':
                return telecom.get('value')
        return None
    
    def _extract_email(self, fhir_patient):
        """Extract email from FHIR Patient"""
        telecoms = fhir_patient.get('telecom', [])
        for telecom in telecoms:
            if telecom.get('system') == 'email':
                return telecom.get('value')
        return None
    
    def _extract_address(self, fhir_patient):
        """Extract address from FHIR Patient"""
        addresses = fhir_patient.get('address', [])
        if addresses:
            address = addresses[0]
            parts = []
            
            lines = address.get('line', [])
            if lines:
                parts.extend(lines)
            
            if address.get('city'):
                parts.append(address['city'])
            
            if address.get('state'):
                parts.append(address['state'])
            
            if address.get('postalCode'):
                parts.append(address['postalCode'])
            
            return ', '.join(parts) if parts else None
        
        return None
    
    def _parse_document_reference(self, fhir_document, patient_id):
        """Parse FHIR DocumentReference to MedicalDocument"""
        try:
            # Extract document type
            document_type = self._extract_document_type(fhir_document)
            
            # Extract document date
            document_date = self._extract_document_date(fhir_document)
            
            # Extract filename/description
            filename = fhir_document.get('description', f"Document_{fhir_document.get('id', 'unknown')}")
            
            # Check if document already exists
            existing_doc = MedicalDocument.query.filter_by(
                patient_id=patient_id,
                filename=filename
            ).first()
            
            if existing_doc:
                # Update existing document
                existing_doc.document_type = document_type
                existing_doc.document_date = document_date
                return existing_doc
            else:
                # Create new document
                document = MedicalDocument(
                    patient_id=patient_id,
                    filename=filename,
                    document_type=document_type,
                    document_date=document_date,
                    processing_status='pending'
                )
                db.session.add(document)
                return document
            
        except Exception as e:
            self.logger.error(f"Error parsing document reference: {str(e)}")
            return None
    
    def _extract_document_type(self, fhir_document):
        """Extract document type from FHIR DocumentReference"""
        type_info = fhir_document.get('type', {})
        coding = type_info.get('coding', [])
        
        if coding:
            code = coding[0].get('code', '')
            display = coding[0].get('display', '').lower()
            
            # Map LOINC codes to document types
            type_mapping = {
                '11502-2': 'lab',
                '18748-4': 'imaging',
                '11488-4': 'consult',
                '18842-5': 'hospital'
            }
            
            if code in type_mapping:
                return type_mapping[code]
            
            # Try to infer from display text
            if any(term in display for term in ['lab', 'laboratory', 'blood', 'urine']):
                return 'lab'
            elif any(term in display for term in ['imaging', 'xray', 'ct', 'mri', 'ultrasound']):
                return 'imaging'
            elif any(term in display for term in ['consult', 'referral', 'specialist']):
                return 'consult'
            elif any(term in display for term in ['hospital', 'admission', 'discharge']):
                return 'hospital'
            elif any(term in display for term in ['screening', 'mammogram', 'colonoscopy']):
                return 'screening'
        
        return 'other'
    
    def _extract_document_date(self, fhir_document):
        """Extract document date from FHIR DocumentReference"""
        date_str = fhir_document.get('date')
        if date_str:
            try:
                # Handle different date formats
                for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
            except Exception:
                pass
        
        return date.today()  # Default to today if no valid date found
    
    def _parse_condition(self, fhir_condition, patient_id):
        """Parse FHIR Condition to internal Condition model"""
        try:
            # Extract condition name
            condition_name = self._extract_condition_name(fhir_condition)
            
            # Extract codes
            icd10_code = self._extract_icd10_code(fhir_condition)
            snomed_code = self._extract_snomed_code(fhir_condition)
            
            # Extract dates
            diagnosis_date = self._extract_condition_date(fhir_condition)
            
            # Extract status
            status = self._extract_condition_status(fhir_condition)
            
            # Check if condition already exists
            existing_condition = Condition.query.filter_by(
                patient_id=patient_id,
                condition_name=condition_name
            ).first()
            
            if existing_condition:
                # Update existing condition
                existing_condition.icd10_code = icd10_code
                existing_condition.snomed_code = snomed_code
                existing_condition.diagnosis_date = diagnosis_date
                existing_condition.status = status
                return existing_condition
            else:
                # Create new condition
                condition = Condition(
                    patient_id=patient_id,
                    condition_name=condition_name,
                    icd10_code=icd10_code,
                    snomed_code=snomed_code,
                    diagnosis_date=diagnosis_date,
                    status=status
                )
                db.session.add(condition)
                return condition
            
        except Exception as e:
            self.logger.error(f"Error parsing condition: {str(e)}")
            return None
    
    def _extract_condition_name(self, fhir_condition):
        """Extract condition name from FHIR Condition"""
        code_info = fhir_condition.get('code', {})
        coding = code_info.get('coding', [])
        
        if coding:
            # Prefer display text
            for code in coding:
                if code.get('display'):
                    return code['display']
        
        # Fallback to text
        if code_info.get('text'):
            return code_info['text']
        
        return 'Unknown Condition'
    
    def _extract_icd10_code(self, fhir_condition):
        """Extract ICD-10 code from FHIR Condition"""
        coding = fhir_condition.get('code', {}).get('coding', [])
        for code in coding:
            system = code.get('system', '')
            if 'icd' in system.lower():
                return code.get('code')
        return None
    
    def _extract_snomed_code(self, fhir_condition):
        """Extract SNOMED code from FHIR Condition"""
        coding = fhir_condition.get('code', {}).get('coding', [])
        for code in coding:
            system = code.get('system', '')
            if 'snomed' in system.lower():
                return code.get('code')
        return None
    
    def _extract_condition_date(self, fhir_condition):
        """Extract diagnosis date from FHIR Condition"""
        onset_date = fhir_condition.get('onsetDateTime')
        if onset_date:
            try:
                return datetime.strptime(onset_date[:10], '%Y-%m-%d').date()
            except ValueError:
                pass
        return None
    
    def _extract_condition_status(self, fhir_condition):
        """Extract condition status from FHIR Condition"""
        clinical_status = fhir_condition.get('clinicalStatus', {})
        coding = clinical_status.get('coding', [])
        
        if coding:
            code = coding[0].get('code', '').lower()
            status_mapping = {
                'active': 'active',
                'inactive': 'inactive',
                'resolved': 'resolved',
                'remission': 'inactive'
            }
            return status_mapping.get(code, 'active')
        
        return 'active'
