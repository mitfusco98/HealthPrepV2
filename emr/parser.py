"""
Converts FHIR bundles to internal model representations
"""
from datetime import datetime, date
from app import db
from models import Patient, Document, PatientCondition
import logging

class FHIRParser:
    """Parses FHIR resources into internal data models"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_patient(self, patient_resource):
        """Parse FHIR Patient resource into internal Patient model"""
        try:
            # Extract name
            name = patient_resource.get('name', [{}])[0]
            given_names = name.get('given', [])
            family_name = name.get('family', '')
            
            first_name = given_names[0] if given_names else ''
            last_name = family_name
            
            # Extract gender
            gender_mapping = {'male': 'M', 'female': 'F'}
            gender = gender_mapping.get(patient_resource.get('gender', '').lower(), 'M')
            
            # Extract birth date
            birth_date_str = patient_resource.get('birthDate')
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
            
            # Extract identifiers (MRN)
            identifiers = patient_resource.get('identifier', [])
            mrn = None
            
            for identifier in identifiers:
                if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                    mrn = identifier.get('value')
                    break
            
            if not mrn and identifiers:
                mrn = identifiers[0].get('value')
            
            # Extract contact information
            telecoms = patient_resource.get('telecom', [])
            phone = None
            email = None
            
            for telecom in telecoms:
                if telecom.get('system') == 'phone':
                    phone = telecom.get('value')
                elif telecom.get('system') == 'email':
                    email = telecom.get('value')
            
            # Extract address
            addresses = patient_resource.get('address', [])
            address = None
            
            if addresses:
                addr = addresses[0]
                address_parts = []
                
                if addr.get('line'):
                    address_parts.extend(addr['line'])
                if addr.get('city'):
                    address_parts.append(addr['city'])
                if addr.get('state'):
                    address_parts.append(addr['state'])
                if addr.get('postalCode'):
                    address_parts.append(addr['postalCode'])
                
                address = ', '.join(address_parts)
            
            return {
                'mrn': mrn,
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': birth_date,
                'gender': gender,
                'phone': phone,
                'email': email,
                'address': address
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR Patient resource: {str(e)}")
            return None
    
    def parse_document_reference(self, doc_ref_resource, patient_id):
        """Parse FHIR DocumentReference into internal Document model"""
        try:
            # Extract document metadata
            doc_data = {
                'patient_id': patient_id,
                'filename': 'Unknown',
                'document_type': 'unknown'
            }
            
            # Extract content information
            content_list = doc_ref_resource.get('content', [])
            if content_list:
                content = content_list[0]
                attachment = content.get('attachment', {})
                
                doc_data['filename'] = attachment.get('title', 'Unknown Document')
                doc_data['original_filename'] = doc_data['filename']
                
                # Try to determine document type from content type or category
                content_type = attachment.get('contentType', '')
                if 'pdf' in content_type:
                    doc_data['filename'] += '.pdf'
            
            # Extract document date
            doc_date_str = doc_ref_resource.get('date')
            if doc_date_str:
                doc_data['document_date'] = datetime.fromisoformat(doc_date_str.replace('Z', '+00:00')).date()
            
            # Extract document type from category
            category_list = doc_ref_resource.get('category', [])
            if category_list:
                category = category_list[0]
                coding_list = category.get('coding', [])
                if coding_list:
                    code = coding_list[0].get('code', '').lower()
                    
                    # Map FHIR categories to internal types
                    type_mapping = {
                        'laboratory': 'lab',
                        'radiology': 'imaging',
                        'consultation': 'consult',
                        'discharge-summary': 'hospital',
                        'clinical-note': 'consult'
                    }
                    
                    doc_data['document_type'] = type_mapping.get(code, 'unknown')
            
            return doc_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR DocumentReference: {str(e)}")
            return None
    
    def parse_diagnostic_report(self, diag_report_resource, patient_id):
        """Parse FHIR DiagnosticReport into document-like structure"""
        try:
            # Extract report information
            doc_data = {
                'patient_id': patient_id,
                'document_type': 'lab'  # Default to lab
            }
            
            # Extract report text/conclusion
            text_content = []
            
            if diag_report_resource.get('text', {}).get('div'):
                text_content.append(diag_report_resource['text']['div'])
            
            if diag_report_resource.get('conclusion'):
                text_content.append(diag_report_resource['conclusion'])
            
            # Extract code/name for filename
            code = diag_report_resource.get('code', {})
            coding_list = code.get('coding', [])
            
            if coding_list:
                display_name = coding_list[0].get('display', 'Diagnostic Report')
                doc_data['filename'] = f"{display_name}.txt"
                doc_data['original_filename'] = doc_data['filename']
            
            # Extract effective date
            effective_date = diag_report_resource.get('effectiveDateTime')
            if effective_date:
                doc_data['document_date'] = datetime.fromisoformat(effective_date.replace('Z', '+00:00')).date()
            
            # Determine document type from category
            category_list = diag_report_resource.get('category', [])
            if category_list:
                category_code = category_list[0].get('coding', [{}])[0].get('code', '').lower()
                
                type_mapping = {
                    'lab': 'lab',
                    'rad': 'imaging',
                    'cardiology': 'consult',
                    'pathology': 'lab'
                }
                
                doc_data['document_type'] = type_mapping.get(category_code, 'lab')
            
            # Set OCR text from extracted content
            doc_data['ocr_text'] = '\n'.join(text_content)
            doc_data['ocr_confidence'] = 0.9  # High confidence for structured data
            
            return doc_data
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR DiagnosticReport: {str(e)}")
            return None
    
    def parse_condition(self, condition_resource, patient_id):
        """Parse FHIR Condition into internal PatientCondition model"""
        try:
            # Extract condition name
            code = condition_resource.get('code', {})
            coding_list = code.get('coding', [])
            
            condition_name = 'Unknown Condition'
            icd_code = None
            
            for coding in coding_list:
                if coding.get('display'):
                    condition_name = coding['display']
                
                if coding.get('system') and 'icd' in coding['system'].lower():
                    icd_code = coding.get('code')
            
            # Extract onset date
            onset_date = None
            onset_date_str = condition_resource.get('onsetDateTime')
            if onset_date_str:
                onset_date = datetime.fromisoformat(onset_date_str.replace('Z', '+00:00')).date()
            
            # Check if condition is active
            clinical_status = condition_resource.get('clinicalStatus', {})
            is_active = False
            
            for coding in clinical_status.get('coding', []):
                if coding.get('code') == 'active':
                    is_active = True
                    break
            
            return {
                'patient_id': patient_id,
                'condition_name': condition_name,
                'icd_code': icd_code,
                'diagnosis_date': onset_date,
                'is_active': is_active
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing FHIR Condition: {str(e)}")
            return None
    
    def sync_fhir_data(self, fhir_data, patient_mrn):
        """Sync parsed FHIR data to internal database"""
        try:
            # Parse patient data
            patient_data = self.parse_patient(fhir_data['patient'])
            if not patient_data:
                return False
            
            # Get or create patient
            patient = Patient.query.filter_by(mrn=patient_mrn).first()
            
            if not patient:
                patient = Patient(**patient_data)
                db.session.add(patient)
            else:
                # Update existing patient
                for key, value in patient_data.items():
                    if value is not None:
                        setattr(patient, key, value)
            
            db.session.flush()  # Get patient ID
            
            # Sync documents
            if fhir_data.get('documents', {}).get('entry'):
                for entry in fhir_data['documents']['entry']:
                    doc_data = self.parse_document_reference(entry['resource'], patient.id)
                    if doc_data:
                        # Check if document already exists
                        existing_doc = Document.query.filter_by(
                            patient_id=patient.id,
                            filename=doc_data['filename']
                        ).first()
                        
                        if not existing_doc:
                            document = Document(**doc_data)
                            db.session.add(document)
            
            # Sync diagnostic reports as documents
            if fhir_data.get('diagnostic_reports', {}).get('entry'):
                for entry in fhir_data['diagnostic_reports']['entry']:
                    doc_data = self.parse_diagnostic_report(entry['resource'], patient.id)
                    if doc_data:
                        # Check if document already exists
                        existing_doc = Document.query.filter_by(
                            patient_id=patient.id,
                            filename=doc_data['filename']
                        ).first()
                        
                        if not existing_doc:
                            document = Document(**doc_data)
                            db.session.add(document)
            
            # Sync conditions
            if fhir_data.get('conditions', {}).get('entry'):
                for entry in fhir_data['conditions']['entry']:
                    condition_data = self.parse_condition(entry['resource'], patient.id)
                    if condition_data:
                        # Check if condition already exists
                        existing_condition = PatientCondition.query.filter_by(
                            patient_id=patient.id,
                            condition_name=condition_data['condition_name']
                        ).first()
                        
                        if not existing_condition:
                            condition = PatientCondition(**condition_data)
                            db.session.add(condition)
            
            db.session.commit()
            self.logger.info(f"Successfully synced FHIR data for patient {patient_mrn}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error syncing FHIR data: {str(e)}")
            return False
