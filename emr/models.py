"""
Internal representations of EMR data
Provides internal models for FHIR data handling
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict, Any
import json

@dataclass
class FHIRPatient:
    """Internal representation of FHIR Patient data"""
    id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: Optional[date]
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    identifiers: Optional[List[Dict]] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self) -> Optional[int]:
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'mrn': self.mrn,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'age': self.age,
            'gender': self.gender,
            'phone': self.phone,
            'email': self.email,
            'address': self.address
        }

@dataclass
class FHIRDocument:
    """Internal representation of FHIR DocumentReference"""
    id: str
    patient_id: str
    title: str
    description: Optional[str]
    document_type: str
    creation_date: Optional[datetime]
    author: Optional[str] = None
    content_url: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'title': self.title,
            'description': self.description,
            'document_type': self.document_type,
            'creation_date': self.creation_date.isoformat() if self.creation_date else None,
            'author': self.author,
            'content_url': self.content_url,
            'mime_type': self.mime_type,
            'size': self.size
        }

@dataclass
class FHIRCondition:
    """Internal representation of FHIR Condition"""
    id: str
    patient_id: str
    condition_name: str
    clinical_status: str
    verification_status: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    onset_date: Optional[date] = None
    recorded_date: Optional[date] = None
    icd10_code: Optional[str] = None
    snomed_code: Optional[str] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'condition_name': self.condition_name,
            'clinical_status': self.clinical_status,
            'verification_status': self.verification_status,
            'category': self.category,
            'severity': self.severity,
            'onset_date': self.onset_date.isoformat() if self.onset_date else None,
            'recorded_date': self.recorded_date.isoformat() if self.recorded_date else None,
            'icd10_code': self.icd10_code,
            'snomed_code': self.snomed_code,
            'notes': self.notes
        }

@dataclass
class FHIRObservation:
    """Internal representation of FHIR Observation"""
    id: str
    patient_id: str
    code: str
    display_name: str
    category: Optional[str] = None
    value_quantity: Optional[Dict] = None
    value_string: Optional[str] = None
    value_boolean: Optional[bool] = None
    effective_date: Optional[datetime] = None
    issued_date: Optional[datetime] = None
    status: str = 'final'
    interpretation: Optional[str] = None
    reference_range: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'code': self.code,
            'display_name': self.display_name,
            'category': self.category,
            'value_quantity': self.value_quantity,
            'value_string': self.value_string,
            'value_boolean': self.value_boolean,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'status': self.status,
            'interpretation': self.interpretation,
            'reference_range': self.reference_range
        }

@dataclass
class FHIREncounter:
    """Internal representation of FHIR Encounter"""
    id: str
    patient_id: str
    status: str
    encounter_class: str
    type_display: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    provider: Optional[str] = None
    reason_display: Optional[str] = None
    diagnosis: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'status': self.status,
            'encounter_class': self.encounter_class,
            'type_display': self.type_display,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'location': self.location,
            'provider': self.provider,
            'reason_display': self.reason_display,
            'diagnosis': self.diagnosis
        }

class FHIRBundle:
    """Container for FHIR Bundle resources"""
    
    def __init__(self, bundle_type: str = 'searchset'):
        self.type = bundle_type
        self.total = 0
        self.entries = []
    
    def add_resource(self, resource: Any):
        """Add a resource to the bundle"""
        self.entries.append(resource)
        self.total += 1
    
    def get_patients(self) -> List[FHIRPatient]:
        """Get all patients from the bundle"""
        return [entry for entry in self.entries if isinstance(entry, FHIRPatient)]
    
    def get_documents(self) -> List[FHIRDocument]:
        """Get all documents from the bundle"""
        return [entry for entry in self.entries if isinstance(entry, FHIRDocument)]
    
    def get_conditions(self) -> List[FHIRCondition]:
        """Get all conditions from the bundle"""
        return [entry for entry in self.entries if isinstance(entry, FHIRCondition)]
    
    def get_observations(self) -> List[FHIRObservation]:
        """Get all observations from the bundle"""
        return [entry for entry in self.entries if isinstance(entry, FHIRObservation)]
    
    def get_encounters(self) -> List[FHIREncounter]:
        """Get all encounters from the bundle"""
        return [entry for entry in self.entries if isinstance(entry, FHIREncounter)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bundle to dictionary"""
        return {
            'resourceType': 'Bundle',
            'type': self.type,
            'total': self.total,
            'entry': [
                {'resource': entry.to_dict() if hasattr(entry, 'to_dict') else entry}
                for entry in self.entries
            ]
        }
    
    def to_json(self) -> str:
        """Convert bundle to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)

class FHIRResourceFactory:
    """Factory for creating FHIR resources from raw FHIR JSON"""
    
    @staticmethod
    def create_patient(fhir_json: Dict) -> FHIRPatient:
        """Create FHIRPatient from FHIR JSON"""
        # Extract identifiers
        identifiers = fhir_json.get('identifier', [])
        mrn = 'UNKNOWN'
        
        for identifier in identifiers:
            type_coding = identifier.get('type', {}).get('coding', [])
            for coding in type_coding:
                if coding.get('code') == 'MR':
                    mrn = identifier.get('value', 'UNKNOWN')
                    break
        
        # Extract name
        names = fhir_json.get('name', [])
        first_name = 'Unknown'
        last_name = 'Unknown'
        
        for name in names:
            if name.get('use') in ['official', 'usual'] or not name.get('use'):
                given_names = name.get('given', [])
                if given_names:
                    first_name = given_names[0]
                last_name = name.get('family', 'Unknown')
                break
        
        # Extract birth date
        birth_date = None
        birth_date_str = fhir_json.get('birthDate')
        if birth_date_str:
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Extract gender
        gender = fhir_json.get('gender', 'unknown').lower()
        gender_mapping = {
            'male': 'M',
            'female': 'F',
            'other': 'Other',
            'unknown': 'Other'
        }
        gender = gender_mapping.get(gender, 'Other')
        
        # Extract contact info
        phone = None
        email = None
        telecoms = fhir_json.get('telecom', [])
        for telecom in telecoms:
            if telecom.get('system') == 'phone':
                phone = telecom.get('value')
            elif telecom.get('system') == 'email':
                email = telecom.get('value')
        
        # Extract address
        address = None
        addresses = fhir_json.get('address', [])
        if addresses:
            addr = addresses[0]
            parts = []
            lines = addr.get('line', [])
            if lines:
                parts.extend(lines)
            if addr.get('city'):
                parts.append(addr['city'])
            if addr.get('state'):
                parts.append(addr['state'])
            if addr.get('postalCode'):
                parts.append(addr['postalCode'])
            address = ', '.join(parts) if parts else None
        
        return FHIRPatient(
            id=fhir_json.get('id', ''),
            mrn=mrn,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=birth_date,
            gender=gender,
            phone=phone,
            email=email,
            address=address,
            identifiers=identifiers
        )
    
    @staticmethod
    def create_document(fhir_json: Dict) -> FHIRDocument:
        """Create FHIRDocument from FHIR JSON"""
        # Extract patient reference
        subject = fhir_json.get('subject', {})
        patient_id = subject.get('reference', '').replace('Patient/', '')
        
        # Extract type
        type_info = fhir_json.get('type', {})
        coding = type_info.get('coding', [])
        document_type = 'other'
        
        if coding:
            code = coding[0].get('code', '')
            display = coding[0].get('display', '').lower()
            
            type_mapping = {
                '11502-2': 'lab',
                '18748-4': 'imaging',
                '11488-4': 'consult',
                '18842-5': 'hospital'
            }
            
            if code in type_mapping:
                document_type = type_mapping[code]
            elif any(term in display for term in ['lab', 'laboratory']):
                document_type = 'lab'
            elif any(term in display for term in ['imaging', 'xray', 'ct', 'mri']):
                document_type = 'imaging'
        
        # Extract creation date
        creation_date = None
        date_str = fhir_json.get('date')
        if date_str:
            try:
                creation_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except ValueError:
                try:
                    creation_date = datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    pass
        
        return FHIRDocument(
            id=fhir_json.get('id', ''),
            patient_id=patient_id,
            title=fhir_json.get('description', f"Document {fhir_json.get('id', '')}"),
            description=fhir_json.get('description'),
            document_type=document_type,
            creation_date=creation_date
        )
    
    @staticmethod
    def create_condition(fhir_json: Dict) -> FHIRCondition:
        """Create FHIRCondition from FHIR JSON"""
        # Extract patient reference
        subject = fhir_json.get('subject', {})
        patient_id = subject.get('reference', '').replace('Patient/', '')
        
        # Extract condition name and codes
        code_info = fhir_json.get('code', {})
        coding = code_info.get('coding', [])
        condition_name = 'Unknown Condition'
        icd10_code = None
        snomed_code = None
        
        for code in coding:
            if code.get('display'):
                condition_name = code['display']
            
            system = code.get('system', '').lower()
            if 'icd' in system:
                icd10_code = code.get('code')
            elif 'snomed' in system:
                snomed_code = code.get('code')
        
        if not condition_name and code_info.get('text'):
            condition_name = code_info['text']
        
        # Extract status
        clinical_status = fhir_json.get('clinicalStatus', {})
        status_coding = clinical_status.get('coding', [])
        status = 'active'
        
        if status_coding:
            status_code = status_coding[0].get('code', '').lower()
            status_mapping = {
                'active': 'active',
                'inactive': 'inactive',
                'resolved': 'resolved'
            }
            status = status_mapping.get(status_code, 'active')
        
        # Extract onset date
        onset_date = None
        onset_date_str = fhir_json.get('onsetDateTime')
        if onset_date_str:
            try:
                onset_date = datetime.strptime(onset_date_str[:10], '%Y-%m-%d').date()
            except ValueError:
                pass
        
        return FHIRCondition(
            id=fhir_json.get('id', ''),
            patient_id=patient_id,
            condition_name=condition_name,
            clinical_status=status,
            onset_date=onset_date,
            icd10_code=icd10_code,
            snomed_code=snomed_code
        )
