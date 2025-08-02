"""
Internal representations of EMR data
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional, Dict, Any

@dataclass
class EMRPatient:
    """Internal representation of patient data"""
    fhir_id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

@dataclass
class EMRCondition:
    """Internal representation of medical condition"""
    condition_name: str
    icd10_code: Optional[str] = None
    onset_date: Optional[date] = None
    status: str = 'active'
    fhir_id: Optional[str] = None

@dataclass
class EMRDocument:
    """Internal representation of medical document"""
    document_id: str
    filename: str
    document_type: str
    document_date: Optional[date] = None
    content_url: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None
    
    def is_recent(self, days: int = 365) -> bool:
        """Check if document is recent"""
        if not self.document_date:
            return False
        return (date.today() - self.document_date).days <= days

@dataclass
class EMRObservation:
    """Internal representation of observation/lab result"""
    observation_id: str
    code: str
    display_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: str = 'final'
    effective_date: Optional[date] = None
    category: Optional[str] = None

@dataclass
class EMRAppointment:
    """Internal representation of appointment"""
    appointment_id: str
    appointment_date: datetime
    appointment_type: str
    provider: str
    status: str = 'scheduled'
    notes: Optional[str] = None

@dataclass
class EMRBundle:
    """Bundle of all EMR data for a patient"""
    patient: EMRPatient
    conditions: List[EMRCondition]
    documents: List[EMRDocument]
    observations: List[EMRObservation]
    appointments: List[EMRAppointment]
    
    def get_active_conditions(self) -> List[EMRCondition]:
        """Get only active conditions"""
        return [c for c in self.conditions if c.status == 'active']
    
    def get_recent_documents(self, days: int = 365) -> List[EMRDocument]:
        """Get documents from the last N days"""
        return [d for d in self.documents if d.is_recent(days)]
    
    def get_documents_by_type(self, doc_type: str) -> List[EMRDocument]:
        """Get documents of specific type"""
        return [d for d in self.documents if d.document_type == doc_type]
    
    def get_upcoming_appointments(self) -> List[EMRAppointment]:
        """Get future appointments"""
        now = datetime.now()
        return [a for a in self.appointments if a.appointment_date > now and a.status == 'scheduled']

class EMRDataValidator:
    """Validates EMR data quality and completeness"""
    
    @staticmethod
    def validate_patient(patient: EMRPatient) -> Dict[str, Any]:
        """Validate patient data completeness"""
        issues = []
        warnings = []
        
        # Required fields
        if not patient.mrn:
            issues.append("Missing MRN")
        if not patient.first_name:
            issues.append("Missing first name")
        if not patient.last_name:
            issues.append("Missing last name")
        if not patient.date_of_birth:
            issues.append("Missing date of birth")
        if not patient.gender:
            issues.append("Missing gender")
        
        # Optional but recommended fields
        if not patient.phone:
            warnings.append("Missing phone number")
        if not patient.email:
            warnings.append("Missing email address")
        
        # Data quality checks
        if patient.age < 0 or patient.age > 150:
            issues.append("Invalid age calculated from birth date")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    @staticmethod
    def validate_bundle(bundle: EMRBundle) -> Dict[str, Any]:
        """Validate complete EMR bundle"""
        patient_validation = EMRDataValidator.validate_patient(bundle.patient)
        
        issues = patient_validation['issues']
        warnings = patient_validation['warnings']
        
        # Check for minimum expected data
        if not bundle.conditions:
            warnings.append("No medical conditions found")
        if not bundle.documents:
            warnings.append("No medical documents found")
        
        # Check data consistency
        active_conditions = bundle.get_active_conditions()
        if len(active_conditions) != len(bundle.conditions):
            warnings.append(f"{len(bundle.conditions) - len(active_conditions)} inactive conditions found")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'summary': {
                'conditions_count': len(bundle.conditions),
                'documents_count': len(bundle.documents),
                'observations_count': len(bundle.observations),
                'appointments_count': len(bundle.appointments)
            }
        }

class EMRDataTransformer:
    """Transforms EMR data between formats"""
    
    @staticmethod
    def fhir_to_emr_patient(fhir_patient: Dict[str, Any]) -> EMRPatient:
        """Convert FHIR Patient resource to EMRPatient"""
        # Extract basic demographics
        fhir_id = fhir_patient.get('id', '')
        
        # Extract identifiers for MRN
        mrn = ''
        for identifier in fhir_patient.get('identifier', []):
            if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                mrn = identifier.get('value', '')
                break
        
        # Extract name
        names = fhir_patient.get('name', [])
        first_name = ''
        last_name = ''
        for name in names:
            if name.get('use') in ['official', 'usual']:
                first_name = ' '.join(name.get('given', []))
                last_name = name.get('family', '')
                break
        
        # Extract other demographics
        birth_date_str = fhir_patient.get('birthDate', '')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
        gender = fhir_patient.get('gender', '').upper()
        if gender == 'MALE':
            gender = 'M'
        elif gender == 'FEMALE':
            gender = 'F'
        
        # Extract contact info
        phone = ''
        email = ''
        for telecom in fhir_patient.get('telecom', []):
            if telecom.get('system') == 'phone':
                phone = telecom.get('value', '')
            elif telecom.get('system') == 'email':
                email = telecom.get('value', '')
        
        return EMRPatient(
            fhir_id=fhir_id,
            mrn=mrn,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=birth_date,
            gender=gender,
            phone=phone or None,
            email=email or None
        )
    
    @staticmethod
    def fhir_to_emr_condition(fhir_condition: Dict[str, Any]) -> EMRCondition:
        """Convert FHIR Condition resource to EMRCondition"""
        # Extract condition name and code
        coding = fhir_condition.get('code', {}).get('coding', [{}])[0]
        condition_name = coding.get('display', 'Unknown Condition')
        icd10_code = coding.get('code') if coding.get('system') == 'http://hl7.org/fhir/sid/icd-10' else None
        
        # Extract onset date
        onset_date = None
        onset_str = fhir_condition.get('onsetDateTime', '')
        if onset_str:
            onset_date = datetime.strptime(onset_str[:10], '%Y-%m-%d').date()
        
        # Extract status
        clinical_status = fhir_condition.get('clinicalStatus', {}).get('coding', [{}])[0]
        status = clinical_status.get('code', 'active')
        
        return EMRCondition(
            condition_name=condition_name,
            icd10_code=icd10_code,
            onset_date=onset_date,
            status=status,
            fhir_id=fhir_condition.get('id')
        )
