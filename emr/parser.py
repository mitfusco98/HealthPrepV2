"""
Converts FHIR bundles to internal model representations
Handles mapping between FHIR resources and application models
"""
import logging
from datetime import datetime
from app import db
from models import Patient, Document, Condition, Appointment
from .models import FHIRPatient, FHIRDocument, FHIRCondition

logger = logging.getLogger(__name__)

class FHIRParser:
    """Parser for converting FHIR resources to internal models"""
    
    def __init__(self):
        pass
    
    def parse_patient_bundle(self, fhir_bundle):
        """Parse a complete FHIR bundle for a patient"""
        if not fhir_bundle or 'entry' not in fhir_bundle:
            logger.error("Invalid FHIR bundle received")
            return None
        
        patient_data = {}
        
        for entry in fhir_bundle['entry']:
            resource = entry.get('resource', {})
            resource_type = resource.get('resourceType')
            
            if resource_type == 'Patient':
                patient_data['patient'] = self.parse_patient_resource(resource)
            elif resource_type == 'DocumentReference':
                if 'documents' not in patient_data:
                    patient_data['documents'] = []
                doc = self.parse_document_reference(resource)
                if doc:
                    patient_data['documents'].append(doc)
            elif resource_type == 'Condition':
                if 'conditions' not in patient_data:
                    patient_data['conditions'] = []
                condition = self.parse_condition_resource(resource)
                if condition:
                    patient_data['conditions'].append(condition)
            elif resource_type == 'Encounter':
                if 'encounters' not in patient_data:
                    patient_data['encounters'] = []
                encounter = self.parse_encounter_resource(resource)
                if encounter:
                    patient_data['encounters'].append(encounter)
        
        return patient_data
    
    def parse_patient_resource(self, fhir_patient):
        """Parse a FHIR Patient resource"""
        try:
            # Extract name
            name = fhir_patient.get('name', [{}])[0]
            first_name = name.get('given', [''])[0]
            last_name = name.get('family', '')
            
            # Extract identifiers (MRN)
            mrn = None
            for identifier in fhir_patient.get('identifier', []):
                if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                    mrn = identifier.get('value')
                    break
            
            # Extract birth date
            birth_date_str = fhir_patient.get('birthDate')
            birth_date = None
            if birth_date_str:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            
            # Extract gender
            gender = fhir_patient.get('gender', '').upper()
            if gender == 'MALE':
                gender = 'M'
            elif gender == 'FEMALE':
                gender = 'F'
            else:
                gender = 'O'
            
            # Extract contact information
            phone = None
            email = None
            for telecom in fhir_patient.get('telecom', []):
                if telecom.get('system') == 'phone':
                    phone = telecom.get('value')
                elif telecom.get('system') == 'email':
                    email = telecom.get('value')
            
            # Extract address
            address = None
            if fhir_patient.get('address'):
                addr = fhir_patient['address'][0]
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
            
            return FHIRPatient(
                fhir_id=fhir_patient.get('id'),
                mrn=mrn,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=birth_date,
                gender=gender,
                phone=phone,
                email=email,
                address=address
            )
            
        except Exception as e:
            logger.error(f"Error parsing FHIR patient: {e}")
            return None
    
    def parse_document_reference(self, fhir_doc):
        """Parse a FHIR DocumentReference resource"""
        try:
            # Extract patient reference
            patient_ref = fhir_doc.get('subject', {}).get('reference', '')
            patient_id = patient_ref.split('/')[-1] if '/' in patient_ref else patient_ref
            
            # Extract document metadata
            content = fhir_doc.get('content', [{}])[0]
            attachment = content.get('attachment', {})
            
            title = attachment.get('title', 'Unknown Document')
            content_type = attachment.get('contentType', 'application/pdf')
            creation_date_str = attachment.get('creation')
            
            creation_date = None
            if creation_date_str:
                try:
                    creation_date = datetime.fromisoformat(creation_date_str.replace('Z', '+00:00'))
                except:
                    creation_date = datetime.utcnow()
            
            # Extract document type/category
            doc_type = None
            if fhir_doc.get('type', {}).get('coding'):
                doc_type = fhir_doc['type']['coding'][0].get('display', 'Unknown')
            
            # Extract document URL
            doc_url = attachment.get('url')
            
            return FHIRDocument(
                fhir_id=fhir_doc.get('id'),
                patient_fhir_id=patient_id,
                title=title,
                content_type=content_type,
                document_type=doc_type,
                creation_date=creation_date,
                document_url=doc_url
            )
            
        except Exception as e:
            logger.error(f"Error parsing FHIR document reference: {e}")
            return None
    
    def parse_condition_resource(self, fhir_condition):
        """Parse a FHIR Condition resource"""
        try:
            # Extract patient reference
            patient_ref = fhir_condition.get('subject', {}).get('reference', '')
            patient_id = patient_ref.split('/')[-1] if '/' in patient_ref else patient_ref
            
            # Extract condition code and display
            coding = fhir_condition.get('code', {}).get('coding', [{}])[0]
            condition_name = coding.get('display', 'Unknown Condition')
            icd10_code = coding.get('code')
            
            # Extract onset date
            onset_date = None
            onset_datetime = fhir_condition.get('onsetDateTime')
            if onset_datetime:
                try:
                    onset_date = datetime.fromisoformat(onset_datetime.replace('Z', '+00:00'))
                except:
                    pass
            
            # Extract clinical status
            clinical_status = 'active'
            if fhir_condition.get('clinicalStatus', {}).get('coding'):
                status_code = fhir_condition['clinicalStatus']['coding'][0].get('code', 'active')
                clinical_status = status_code
            
            return FHIRCondition(
                fhir_id=fhir_condition.get('id'),
                patient_fhir_id=patient_id,
                condition_name=condition_name,
                icd10_code=icd10_code,
                onset_date=onset_date,
                clinical_status=clinical_status
            )
            
        except Exception as e:
            logger.error(f"Error parsing FHIR condition: {e}")
            return None
    
    def parse_encounter_resource(self, fhir_encounter):
        """Parse a FHIR Encounter resource"""
        try:
            # Extract patient reference
            patient_ref = fhir_encounter.get('subject', {}).get('reference', '')
            patient_id = patient_ref.split('/')[-1] if '/' in patient_ref else patient_ref
            
            # Extract encounter type
            encounter_type = 'Unknown'
            if fhir_encounter.get('type'):
                type_coding = fhir_encounter['type'][0].get('coding', [{}])[0]
                encounter_type = type_coding.get('display', 'Unknown')
            
            # Extract period
            period = fhir_encounter.get('period', {})
            start_date = None
            end_date = None
            
            if period.get('start'):
                try:
                    start_date = datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                except:
                    pass
            
            if period.get('end'):
                try:
                    end_date = datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                except:
                    pass
            
            # Extract status
            status = fhir_encounter.get('status', 'unknown')
            
            return {
                'fhir_id': fhir_encounter.get('id'),
                'patient_fhir_id': patient_id,
                'encounter_type': encounter_type,
                'start_date': start_date,
                'end_date': end_date,
                'status': status
            }
            
        except Exception as e:
            logger.error(f"Error parsing FHIR encounter: {e}")
            return None
    
    def create_or_update_patient(self, fhir_patient):
        """Create or update a patient in the local database"""
        if not fhir_patient or not fhir_patient.mrn:
            logger.error("Cannot create patient without MRN")
            return None
        
        # Check if patient already exists
        patient = Patient.query.filter_by(mrn=fhir_patient.mrn).first()
        
        if patient:
            # Update existing patient
            patient.first_name = fhir_patient.first_name
            patient.last_name = fhir_patient.last_name
            patient.date_of_birth = fhir_patient.date_of_birth
            patient.gender = fhir_patient.gender
            patient.phone = fhir_patient.phone
            patient.email = fhir_patient.email
            patient.address = fhir_patient.address
            patient.updated_at = datetime.utcnow()
        else:
            # Create new patient
            patient = Patient(
                mrn=fhir_patient.mrn,
                first_name=fhir_patient.first_name,
                last_name=fhir_patient.last_name,
                date_of_birth=fhir_patient.date_of_birth,
                gender=fhir_patient.gender,
                phone=fhir_patient.phone,
                email=fhir_patient.email,
                address=fhir_patient.address
            )
            db.session.add(patient)
        
        db.session.commit()
        return patient
