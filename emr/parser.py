"""
FHIR data parser that converts FHIR bundles to internal model representations.
Handles patient data, documents, conditions, and encounters.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import json

from app import db
from models import Patient, MedicalDocument, PatientCondition

class FHIRParser:
    """Parses FHIR resources into internal data models."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_patient(self, patient_resource: Dict) -> Optional[Patient]:
        """Parse FHIR Patient resource into internal Patient model."""
        
        try:
            # Extract basic demographics
            patient_data = {
                'mrn': self._extract_identifier(patient_resource),
                'first_name': self._extract_given_name(patient_resource),
                'last_name': self._extract_family_name(patient_resource),
                'date_of_birth': self._extract_birth_date(patient_resource),
                'gender': self._extract_gender(patient_resource)
            }
            
            # Validate required fields
            if not all([patient_data['mrn'], patient_data['first_name'], 
                       patient_data['last_name'], patient_data['date_of_birth'],
                       patient_data['gender']]):
                self.logger.warning(f"Missing required patient data: {patient_data}")
                return None
            
            # Check if patient already exists
            existing_patient = Patient.query.filter_by(mrn=patient_data['mrn']).first()
            
            if existing_patient:
                # Update existing patient
                existing_patient.first_name = patient_data['first_name']
                existing_patient.last_name = patient_data['last_name']
                existing_patient.date_of_birth = patient_data['date_of_birth']
                existing_patient.gender = patient_data['gender']
                return existing_patient
            else:
                # Create new patient
                patient = Patient(**patient_data)
                db.session.add(patient)
                return patient
                
        except Exception as e:
            self.logger.error(f"Error parsing patient resource: {e}")
            return None
    
    def parse_document_reference(self, document_ref: Dict, patient: Patient) -> Optional[MedicalDocument]:
        """Parse FHIR DocumentReference into internal MedicalDocument model."""
        
        try:
            # Extract document metadata
            document_data = {
                'patient_id': patient.id,
                'filename': self._extract_document_title(document_ref),
                'document_type': self._extract_document_type(document_ref),
                'document_date': self._extract_document_date(document_ref),
                'content': self._extract_document_text(document_ref)
            }
            
            # Validate required fields
            if not all([document_data['filename'], document_data['document_date']]):
                self.logger.warning(f"Missing required document data: {document_data}")
                return None
            
            # Create document record
            document = MedicalDocument(**document_data)
            db.session.add(document)
            return document
            
        except Exception as e:
            self.logger.error(f"Error parsing document reference: {e}")
            return None
    
    def parse_diagnostic_report(self, diagnostic_report: Dict, patient: Patient) -> Optional[MedicalDocument]:
        """Parse FHIR DiagnosticReport into internal MedicalDocument model."""
        
        try:
            # Extract report data
            document_data = {
                'patient_id': patient.id,
                'filename': self._extract_report_title(diagnostic_report),
                'document_type': self._extract_report_type(diagnostic_report),
                'document_date': self._extract_report_date(diagnostic_report),
                'content': self._extract_report_text(diagnostic_report)
            }
            
            # Validate required fields
            if not all([document_data['filename'], document_data['document_date']]):
                self.logger.warning(f"Missing required diagnostic report data: {document_data}")
                return None
            
            # Create document record
            document = MedicalDocument(**document_data)
            db.session.add(document)
            return document
            
        except Exception as e:
            self.logger.error(f"Error parsing diagnostic report: {e}")
            return None
    
    def parse_conditions(self, conditions_bundle: Dict, patient: Patient) -> List[PatientCondition]:
        """Parse FHIR Condition resources into internal PatientCondition models."""
        
        parsed_conditions = []
        
        try:
            # Handle both Bundle format and direct array
            conditions = []
            if 'entry' in conditions_bundle:
                conditions = [entry['resource'] for entry in conditions_bundle['entry'] 
                             if entry.get('resource', {}).get('resourceType') == 'Condition']
            elif isinstance(conditions_bundle, list):
                conditions = conditions_bundle
            elif conditions_bundle.get('resourceType') == 'Condition':
                conditions = [conditions_bundle]
            
            for condition_resource in conditions:
                try:
                    condition_data = {
                        'patient_id': patient.id,
                        'condition_name': self._extract_condition_name(condition_resource),
                        'diagnosis_date': self._extract_condition_date(condition_resource),
                        'is_active': self._extract_condition_status(condition_resource)
                    }
                    
                    if condition_data['condition_name']:
                        # Check if condition already exists
                        existing_condition = PatientCondition.query.filter_by(
                            patient_id=patient.id,
                            condition_name=condition_data['condition_name']
                        ).first()
                        
                        if existing_condition:
                            # Update existing condition
                            existing_condition.is_active = condition_data['is_active']
                            if condition_data['diagnosis_date']:
                                existing_condition.diagnosis_date = condition_data['diagnosis_date']
                            parsed_conditions.append(existing_condition)
                        else:
                            # Create new condition
                            condition = PatientCondition(**condition_data)
                            db.session.add(condition)
                            parsed_conditions.append(condition)
                            
                except Exception as e:
                    self.logger.error(f"Error parsing individual condition: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error parsing conditions bundle: {e}")
        
        return parsed_conditions
    
    def parse_bundle(self, bundle: Dict) -> Dict:
        """Parse a complete FHIR Bundle and extract all relevant resources."""
        
        results = {
            'patients': [],
            'documents': [],
            'conditions': [],
            'encounters': [],
            'observations': []
        }
        
        try:
            if 'entry' not in bundle:
                self.logger.warning("Bundle has no entries")
                return results
            
            # First pass: extract patients
            for entry in bundle['entry']:
                resource = entry.get('resource', {})
                resource_type = resource.get('resourceType')
                
                if resource_type == 'Patient':
                    patient = self.parse_patient(resource)
                    if patient:
                        results['patients'].append(patient)
            
            # Second pass: extract other resources linked to patients
            for patient in results['patients']:
                for entry in bundle['entry']:
                    resource = entry.get('resource', {})
                    resource_type = resource.get('resourceType')
                    
                    # Check if resource is for this patient
                    if self._resource_belongs_to_patient(resource, patient):
                        
                        if resource_type == 'DocumentReference':
                            document = self.parse_document_reference(resource, patient)
                            if document:
                                results['documents'].append(document)
                        
                        elif resource_type == 'DiagnosticReport':
                            document = self.parse_diagnostic_report(resource, patient)
                            if document:
                                results['documents'].append(document)
                        
                        elif resource_type == 'Condition':
                            conditions = self.parse_conditions(resource, patient)
                            results['conditions'].extend(conditions)
                        
                        # Additional resource types can be added here
                        
        except Exception as e:
            self.logger.error(f"Error parsing FHIR bundle: {e}")
        
        return results
    
    # Helper methods for extracting specific fields
    
    def _extract_identifier(self, patient_resource: Dict) -> Optional[str]:
        """Extract MRN or primary identifier from Patient resource."""
        identifiers = patient_resource.get('identifier', [])
        
        # Look for MRN type identifier first
        for identifier in identifiers:
            if identifier.get('type', {}).get('coding', []):
                for coding in identifier['type']['coding']:
                    if coding.get('code') in ['MR', 'MRN']:
                        return identifier.get('value')
        
        # Fall back to first identifier with value
        for identifier in identifiers:
            if identifier.get('value'):
                return identifier['value']
        
        return None
    
    def _extract_given_name(self, patient_resource: Dict) -> Optional[str]:
        """Extract given (first) name from Patient resource."""
        names = patient_resource.get('name', [])
        
        for name in names:
            if name.get('use', 'official') in ['official', 'usual']:
                given = name.get('given', [])
                if given:
                    return given[0]
        
        return None
    
    def _extract_family_name(self, patient_resource: Dict) -> Optional[str]:
        """Extract family (last) name from Patient resource."""
        names = patient_resource.get('name', [])
        
        for name in names:
            if name.get('use', 'official') in ['official', 'usual']:
                return name.get('family')
        
        return None
    
    def _extract_birth_date(self, patient_resource: Dict) -> Optional[date]:
        """Extract birth date from Patient resource."""
        birth_date_str = patient_resource.get('birthDate')
        
        if birth_date_str:
            try:
                return datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(birth_date_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        return None
    
    def _extract_gender(self, patient_resource: Dict) -> Optional[str]:
        """Extract gender from Patient resource."""
        gender = patient_resource.get('gender', '').lower()
        
        if gender in ['male', 'm']:
            return 'M'
        elif gender in ['female', 'f']:
            return 'F'
        
        return None
    
    def _extract_document_title(self, document_ref: Dict) -> str:
        """Extract document title from DocumentReference."""
        # Try description first
        if 'description' in document_ref:
            return document_ref['description']
        
        # Try type coding display
        doc_type = document_ref.get('type', {})
        if 'coding' in doc_type:
            for coding in doc_type['coding']:
                if 'display' in coding:
                    return coding['display']
        
        # Fall back to generic title
        return f"Document_{document_ref.get('id', 'unknown')}"
    
    def _extract_document_type(self, document_ref: Dict) -> str:
        """Extract document type category."""
        categories = document_ref.get('category', [])
        
        for category in categories:
            if 'coding' in category:
                for coding in category['coding']:
                    code = coding.get('code', '').lower()
                    if 'lab' in code:
                        return 'lab'
                    elif 'rad' in code or 'imaging' in code:
                        return 'imaging'
                    elif 'consult' in code:
                        return 'consult'
                    elif 'discharge' in code or 'admission' in code:
                        return 'hospital'
        
        return 'other'
    
    def _extract_document_date(self, document_ref: Dict) -> Optional[date]:
        """Extract document date."""
        date_str = document_ref.get('date')
        
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except ValueError:
                try:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        return date.today()  # Fall back to today
    
    def _extract_document_text(self, document_ref: Dict) -> Optional[str]:
        """Extract text content from DocumentReference."""
        # This would typically require downloading the actual document
        # For now, return any available text in the resource
        
        if 'content' in document_ref:
            for content in document_ref['content']:
                if 'attachment' in content:
                    attachment = content['attachment']
                    if 'data' in attachment:
                        # Base64 encoded content
                        import base64
                        try:
                            return base64.b64decode(attachment['data']).decode('utf-8')
                        except:
                            pass
        
        return None
    
    def _extract_condition_name(self, condition_resource: Dict) -> Optional[str]:
        """Extract condition name from Condition resource."""
        code = condition_resource.get('code', {})
        
        if 'text' in code:
            return code['text']
        
        if 'coding' in code:
            for coding in code['coding']:
                if 'display' in coding:
                    return coding['display']
        
        return None
    
    def _extract_condition_date(self, condition_resource: Dict) -> Optional[date]:
        """Extract condition diagnosis date."""
        date_str = condition_resource.get('onsetDateTime')
        
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except ValueError:
                try:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        return None
    
    def _extract_condition_status(self, condition_resource: Dict) -> bool:
        """Extract condition active status."""
        clinical_status = condition_resource.get('clinicalStatus', {})
        
        if 'coding' in clinical_status:
            for coding in clinical_status['coding']:
                if coding.get('code') == 'active':
                    return True
        
        return False
    
    def _resource_belongs_to_patient(self, resource: Dict, patient: Patient) -> bool:
        """Check if a resource belongs to a specific patient."""
        
        # Check subject reference
        subject = resource.get('subject', {})
        if 'reference' in subject:
            ref = subject['reference']
            if f"Patient/{patient.mrn}" in ref or patient.mrn in ref:
                return True
        
        # Check patient reference
        patient_ref = resource.get('patient', {})
        if 'reference' in patient_ref:
            ref = patient_ref['reference']
            if f"Patient/{patient.mrn}" in ref or patient.mrn in ref:
                return True
        
        return False
    
    # Additional helper methods for other resource types...
    
    def _extract_report_title(self, diagnostic_report: Dict) -> str:
        """Extract title from DiagnosticReport."""
        code = diagnostic_report.get('code', {})
        
        if 'text' in code:
            return code['text']
        
        if 'coding' in code:
            for coding in code['coding']:
                if 'display' in coding:
                    return coding['display']
        
        return f"Report_{diagnostic_report.get('id', 'unknown')}"
    
    def _extract_report_type(self, diagnostic_report: Dict) -> str:
        """Extract report type category."""
        category = diagnostic_report.get('category', [])
        
        for cat in category:
            if 'coding' in cat:
                for coding in cat['coding']:
                    code = coding.get('code', '').lower()
                    if 'lab' in code:
                        return 'lab'
                    elif 'rad' in code or 'imaging' in code:
                        return 'imaging'
        
        return 'lab'  # Default to lab
    
    def _extract_report_date(self, diagnostic_report: Dict) -> Optional[date]:
        """Extract report date."""
        date_str = diagnostic_report.get('effectiveDateTime')
        
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except ValueError:
                try:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        return date.today()
    
    def _extract_report_text(self, diagnostic_report: Dict) -> Optional[str]:
        """Extract text from DiagnosticReport."""
        # Try conclusion first
        if 'conclusion' in diagnostic_report:
            return diagnostic_report['conclusion']
        
        # Try presentedForm
        if 'presentedForm' in diagnostic_report:
            for form in diagnostic_report['presentedForm']:
                if 'data' in form:
                    import base64
                    try:
                        return base64.b64decode(form['data']).decode('utf-8')
                    except:
                        pass
        
        return None
