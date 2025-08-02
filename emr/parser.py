"""
Converts FHIR bundles to internal model representations
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from models import Patient, Condition, MedicalDocument, Appointment, db

logger = logging.getLogger(__name__)

class FHIRParser:
    """Parses FHIR resources into internal data models"""
    
    def parse_patient_bundle(self, bundle: Dict[str, Any]) -> Optional[Patient]:
        """
        Parse FHIR bundle and create/update internal patient record
        """
        if not bundle or bundle.get('resourceType') != 'Bundle':
            logger.error("Invalid FHIR bundle provided")
            return None
        
        patient_resource = None
        conditions = []
        documents = []
        appointments = []
        
        # Extract resources from bundle
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            resource_type = resource.get('resourceType')
            
            if resource_type == 'Patient':
                patient_resource = resource
            elif resource_type == 'Condition':
                conditions.append(resource)
            elif resource_type == 'DocumentReference':
                documents.append(resource)
            elif resource_type == 'Appointment':
                appointments.append(resource)
        
        if not patient_resource:
            logger.error("No Patient resource found in bundle")
            return None
        
        # Parse and create patient
        patient = self._parse_patient_resource(patient_resource)
        if not patient:
            return None
        
        # Parse related resources
        self._parse_conditions(patient, conditions)
        self._parse_documents(patient, documents)
        self._parse_appointments(patient, appointments)
        
        return patient
    
    def _parse_patient_resource(self, resource: Dict[str, Any]) -> Optional[Patient]:
        """Parse FHIR Patient resource"""
        try:
            # Extract patient identifiers
            fhir_id = resource.get('id')
            if not fhir_id:
                logger.error("Patient resource missing ID")
                return None
            
            # Extract MRN from identifiers
            mrn = self._extract_mrn(resource.get('identifier', []))
            if not mrn:
                mrn = f"FHIR-{fhir_id}"  # Fallback to FHIR ID
            
            # Extract name
            names = resource.get('name', [])
            first_name, last_name = self._extract_name(names)
            
            if not first_name or not last_name:
                logger.error(f"Patient {fhir_id} missing required name fields")
                return None
            
            # Extract birth date
            birth_date_str = resource.get('birthDate')
            if not birth_date_str:
                logger.error(f"Patient {fhir_id} missing birth date")
                return None
            
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            
            # Extract gender
            gender = resource.get('gender', '').upper()
            if gender not in ['M', 'F', 'MALE', 'FEMALE']:
                gender = 'U'  # Unknown
            elif gender == 'MALE':
                gender = 'M'
            elif gender == 'FEMALE':
                gender = 'F'
            
            # Extract contact information
            telecom = resource.get('telecom', [])
            phone = self._extract_phone(telecom)
            email = self._extract_email(telecom)
            
            # Extract address
            addresses = resource.get('address', [])
            address = self._extract_address(addresses)
            
            # Check if patient already exists
            existing_patient = Patient.query.filter_by(mrn=mrn).first()
            
            if existing_patient:
                # Update existing patient
                existing_patient.first_name = first_name
                existing_patient.last_name = last_name
                existing_patient.date_of_birth = birth_date
                existing_patient.gender = gender
                existing_patient.phone = phone
                existing_patient.email = email
                existing_patient.address = address
                existing_patient.updated_at = datetime.utcnow()
                
                logger.info(f"Updated existing patient {mrn}")
                return existing_patient
            else:
                # Create new patient
                patient = Patient(
                    mrn=mrn,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=birth_date,
                    gender=gender,
                    phone=phone,
                    email=email,
                    address=address
                )
                
                db.session.add(patient)
                logger.info(f"Created new patient {mrn}")
                return patient
                
        except Exception as e:
            logger.error(f"Error parsing patient resource: {str(e)}")
            return None
    
    def _extract_mrn(self, identifiers: List[Dict[str, Any]]) -> Optional[str]:
        """Extract MRN from patient identifiers"""
        for identifier in identifiers:
            # Look for MRN type
            type_coding = identifier.get('type', {}).get('coding', [])
            for coding in type_coding:
                if coding.get('code') == 'MR' or 'MRN' in coding.get('display', '').upper():
                    return identifier.get('value')
            
            # Fallback - look for identifiers with MRN in system
            system = identifier.get('system', '')
            if 'mrn' in system.lower():
                return identifier.get('value')
        
        return None
    
    def _extract_name(self, names: List[Dict[str, Any]]) -> tuple:
        """Extract first and last name from FHIR name array"""
        for name in names:
            if name.get('use') in ['official', 'usual'] or not name.get('use'):
                first_name = ' '.join(name.get('given', []))
                last_name = name.get('family', '')
                
                if first_name and last_name:
                    return first_name, last_name
        
        return None, None
    
    def _extract_phone(self, telecom: List[Dict[str, Any]]) -> Optional[str]:
        """Extract phone number from telecom array"""
        for contact in telecom:
            if contact.get('system') == 'phone':
                return contact.get('value')
        return None
    
    def _extract_email(self, telecom: List[Dict[str, Any]]) -> Optional[str]:
        """Extract email from telecom array"""
        for contact in telecom:
            if contact.get('system') == 'email':
                return contact.get('value')
        return None
    
    def _extract_address(self, addresses: List[Dict[str, Any]]) -> Optional[str]:
        """Extract address from address array"""
        for address in addresses:
            if address.get('use') in ['home', 'work'] or not address.get('use'):
                parts = []
                
                if address.get('line'):
                    parts.extend(address['line'])
                if address.get('city'):
                    parts.append(address['city'])
                if address.get('state'):
                    parts.append(address['state'])
                if address.get('postalCode'):
                    parts.append(address['postalCode'])
                
                if parts:
                    return ', '.join(parts)
        
        return None
    
    def _parse_conditions(self, patient: Patient, conditions: List[Dict[str, Any]]):
        """Parse FHIR Condition resources"""
        for condition_resource in conditions:
            try:
                # Extract condition name
                coding = condition_resource.get('code', {}).get('coding', [])
                condition_name = None
                icd10_code = None
                
                for code in coding:
                    if code.get('system') == 'http://hl7.org/fhir/sid/icd-10':
                        icd10_code = code.get('code')
                        condition_name = code.get('display')
                        break
                    elif code.get('display'):
                        condition_name = code.get('display')
                
                if not condition_name:
                    continue
                
                # Extract onset date
                onset_date = None
                onset_datetime = condition_resource.get('onsetDateTime')
                if onset_datetime:
                    onset_date = datetime.strptime(onset_datetime[:10], '%Y-%m-%d').date()
                
                # Extract status
                clinical_status = condition_resource.get('clinicalStatus', {}).get('coding', [])
                status = 'active'
                for status_code in clinical_status:
                    if status_code.get('code') in ['resolved', 'inactive']:
                        status = status_code['code']
                        break
                
                # Check if condition already exists
                existing_condition = Condition.query.filter_by(
                    patient_id=patient.id,
                    condition_name=condition_name
                ).first()
                
                if not existing_condition:
                    condition = Condition(
                        patient_id=patient.id,
                        condition_name=condition_name,
                        icd10_code=icd10_code,
                        onset_date=onset_date,
                        status=status
                    )
                    db.session.add(condition)
                    logger.debug(f"Added condition {condition_name} for patient {patient.mrn}")
                
            except Exception as e:
                logger.error(f"Error parsing condition: {str(e)}")
                continue
    
    def _parse_documents(self, patient: Patient, documents: List[Dict[str, Any]]):
        """Parse FHIR DocumentReference resources"""
        for doc_resource in documents:
            try:
                # Extract document metadata
                doc_id = doc_resource.get('id')
                if not doc_id:
                    continue
                
                # Extract document type
                type_coding = doc_resource.get('type', {}).get('coding', [])
                document_type = 'unknown'
                for coding in type_coding:
                    display = coding.get('display', '').lower()
                    if 'lab' in display:
                        document_type = 'lab'
                    elif 'imaging' in display or 'radiology' in display:
                        document_type = 'imaging'
                    elif 'consult' in display or 'referral' in display:
                        document_type = 'consult'
                    elif 'discharge' in display or 'hospital' in display:
                        document_type = 'hospital'
                    break
                
                # Extract document date
                document_date = None
                date_str = doc_resource.get('date')
                if date_str:
                    document_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                
                # Extract filename from content
                filename = f"FHIR-{doc_id}"
                content = doc_resource.get('content', [])
                if content and content[0].get('attachment', {}).get('title'):
                    filename = content[0]['attachment']['title']
                
                # Check if document already exists
                existing_doc = MedicalDocument.query.filter_by(
                    patient_id=patient.id,
                    filename=filename
                ).first()
                
                if not existing_doc:
                    document = MedicalDocument(
                        patient_id=patient.id,
                        filename=filename,
                        document_type=document_type,
                        document_date=document_date,
                        file_path=f"fhir/{doc_id}"
                    )
                    db.session.add(document)
                    logger.debug(f"Added document {filename} for patient {patient.mrn}")
                
            except Exception as e:
                logger.error(f"Error parsing document: {str(e)}")
                continue
    
    def _parse_appointments(self, patient: Patient, appointments: List[Dict[str, Any]]):
        """Parse FHIR Appointment resources"""
        for appt_resource in appointments:
            try:
                # Extract appointment date
                start_str = appt_resource.get('start')
                if not start_str:
                    continue
                
                appointment_date = datetime.strptime(start_str[:19], '%Y-%m-%dT%H:%M:%S')
                
                # Extract appointment type
                service_type = appt_resource.get('serviceType', [])
                appointment_type = 'General'
                if service_type and service_type[0].get('coding'):
                    appointment_type = service_type[0]['coding'][0].get('display', 'General')
                
                # Extract status
                status = appt_resource.get('status', 'scheduled')
                
                # Extract provider
                provider = 'Unknown'
                participants = appt_resource.get('participant', [])
                for participant in participants:
                    actor = participant.get('actor', {})
                    if actor.get('display'):
                        provider = actor['display']
                        break
                
                # Check if appointment already exists
                existing_appt = Appointment.query.filter_by(
                    patient_id=patient.id,
                    appointment_date=appointment_date
                ).first()
                
                if not existing_appt:
                    appointment = Appointment(
                        patient_id=patient.id,
                        appointment_date=appointment_date,
                        appointment_type=appointment_type,
                        provider=provider,
                        status=status
                    )
                    db.session.add(appointment)
                    logger.debug(f"Added appointment for patient {patient.mrn}")
                
            except Exception as e:
                logger.error(f"Error parsing appointment: {str(e)}")
                continue
