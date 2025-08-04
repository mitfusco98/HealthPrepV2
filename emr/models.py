"""
Internal EMR data models for representing FHIR resources.
These are lightweight models for data transformation before database storage.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class DocumentType(Enum):
    """Enumeration of document types."""
    LAB = "lab"
    IMAGING = "imaging"
    CONSULT = "consult"
    HOSPITAL = "hospital"
    OTHER = "other"

class Gender(Enum):
    """Enumeration of gender values."""
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"

class ConditionStatus(Enum):
    """Enumeration of condition status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESOLVED = "resolved"

@dataclass
class EMRPatient:
    """Internal representation of patient data from EMR."""
    
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Gender
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    emergency_contact: Optional[Dict[str, str]] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

@dataclass
class EMRDocument:
    """Internal representation of medical document from EMR."""
    
    document_id: str
    patient_mrn: str
    title: str
    document_type: DocumentType
    document_date: date
    content: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    author: Optional[str] = None
    department: Optional[str] = None
    url: Optional[str] = None
    
    def __post_init__(self):
        """Validate document data after initialization."""
        if not self.document_id:
            raise ValueError("Document ID is required")
        if not self.patient_mrn:
            raise ValueError("Patient MRN is required")
        if not self.title:
            raise ValueError("Document title is required")

@dataclass
class EMRCondition:
    """Internal representation of patient condition from EMR."""
    
    condition_id: str
    patient_mrn: str
    condition_name: str
    status: ConditionStatus
    diagnosis_date: Optional[date] = None
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        return self.status == ConditionStatus.ACTIVE

@dataclass
class EMRObservation:
    """Internal representation of observation/lab result from EMR."""
    
    observation_id: str
    patient_mrn: str
    test_name: str
    value: Optional[str] = None
    value_numeric: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = None
    observation_date: Optional[date] = None
    category: Optional[str] = None
    
    @property
    def is_abnormal(self) -> bool:
        """Check if observation value is abnormal based on status."""
        if self.status:
            return self.status.lower() in ['abnormal', 'high', 'low', 'critical']
        return False

@dataclass
class EMREncounter:
    """Internal representation of patient encounter from EMR."""
    
    encounter_id: str
    patient_mrn: str
    encounter_type: str
    start_date: datetime
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    location: Optional[str] = None
    provider: Optional[str] = None
    diagnosis_codes: Optional[List[str]] = None
    
    @property
    def duration_hours(self) -> Optional[float]:
        """Calculate encounter duration in hours."""
        if self.end_date:
            delta = self.end_date - self.start_date
            return delta.total_seconds() / 3600
        return None

@dataclass
class EMRBundle:
    """Bundle of EMR data for a patient or set of patients."""
    
    bundle_id: str
    timestamp: datetime
    patients: List[EMRPatient]
    documents: List[EMRDocument]
    conditions: List[EMRCondition]
    observations: List[EMRObservation]
    encounters: List[EMREncounter]
    
    def get_patient_by_mrn(self, mrn: str) -> Optional[EMRPatient]:
        """Get patient by MRN from bundle."""
        for patient in self.patients:
            if patient.mrn == mrn:
                return patient
        return None
    
    def get_documents_for_patient(self, mrn: str) -> List[EMRDocument]:
        """Get all documents for a specific patient."""
        return [doc for doc in self.documents if doc.patient_mrn == mrn]
    
    def get_conditions_for_patient(self, mrn: str) -> List[EMRCondition]:
        """Get all conditions for a specific patient."""
        return [cond for cond in self.conditions if cond.patient_mrn == mrn]
    
    def get_observations_for_patient(self, mrn: str) -> List[EMRObservation]:
        """Get all observations for a specific patient."""
        return [obs for obs in self.observations if obs.patient_mrn == mrn]
    
    def get_encounters_for_patient(self, mrn: str) -> List[EMREncounter]:
        """Get all encounters for a specific patient."""
        return [enc for enc in self.encounters if enc.patient_mrn == mrn]
    
    def filter_documents_by_type(self, document_type: DocumentType) -> List[EMRDocument]:
        """Filter documents by type across all patients."""
        return [doc for doc in self.documents if doc.document_type == document_type]
    
    def filter_documents_by_date_range(self, start_date: date, end_date: date) -> List[EMRDocument]:
        """Filter documents by date range."""
        return [doc for doc in self.documents 
                if start_date <= doc.document_date <= end_date]
    
    def get_active_conditions(self) -> List[EMRCondition]:
        """Get all active conditions across all patients."""
        return [cond for cond in self.conditions if cond.is_active]
    
    def get_abnormal_observations(self) -> List[EMRObservation]:
        """Get all abnormal observations across all patients."""
        return [obs for obs in self.observations if obs.is_abnormal]
    
    def summary(self) -> Dict[str, int]:
        """Get summary statistics for the bundle."""
        return {
            'total_patients': len(self.patients),
            'total_documents': len(self.documents),
            'total_conditions': len(self.conditions),
            'active_conditions': len(self.get_active_conditions()),
            'total_observations': len(self.observations),
            'abnormal_observations': len(self.get_abnormal_observations()),
            'total_encounters': len(self.encounters),
            'lab_documents': len(self.filter_documents_by_type(DocumentType.LAB)),
            'imaging_documents': len(self.filter_documents_by_type(DocumentType.IMAGING)),
            'consult_documents': len(self.filter_documents_by_type(DocumentType.CONSULT)),
            'hospital_documents': len(self.filter_documents_by_type(DocumentType.HOSPITAL))
        }

class EMRDataValidator:
    """Validates EMR data integrity and completeness."""
    
    @staticmethod
    def validate_patient(patient: EMRPatient) -> List[str]:
        """Validate patient data and return list of issues."""
        issues = []
        
        if not patient.mrn or len(patient.mrn.strip()) == 0:
            issues.append("MRN is required")
        
        if not patient.first_name or len(patient.first_name.strip()) == 0:
            issues.append("First name is required")
        
        if not patient.last_name or len(patient.last_name.strip()) == 0:
            issues.append("Last name is required")
        
        if not patient.date_of_birth:
            issues.append("Date of birth is required")
        elif patient.date_of_birth > date.today():
            issues.append("Date of birth cannot be in the future")
        elif patient.age > 150:
            issues.append("Patient age seems unrealistic")
        
        if patient.gender not in Gender:
            issues.append("Invalid gender value")
        
        return issues
    
    @staticmethod
    def validate_document(document: EMRDocument) -> List[str]:
        """Validate document data and return list of issues."""
        issues = []
        
        if not document.document_id:
            issues.append("Document ID is required")
        
        if not document.patient_mrn:
            issues.append("Patient MRN is required")
        
        if not document.title:
            issues.append("Document title is required")
        
        if not document.document_date:
            issues.append("Document date is required")
        elif document.document_date > date.today():
            issues.append("Document date cannot be in the future")
        
        if document.document_type not in DocumentType:
            issues.append("Invalid document type")
        
        return issues
    
    @staticmethod
    def validate_bundle(bundle: EMRBundle) -> Dict[str, List[str]]:
        """Validate entire EMR bundle and return issues by category."""
        validation_results = {
            'patient_issues': [],
            'document_issues': [],
            'condition_issues': [],
            'observation_issues': [],
            'encounter_issues': [],
            'data_consistency_issues': []
        }
        
        # Validate individual records
        for patient in bundle.patients:
            patient_issues = EMRDataValidator.validate_patient(patient)
            if patient_issues:
                validation_results['patient_issues'].extend([f"Patient {patient.mrn}: {issue}" for issue in patient_issues])
        
        for document in bundle.documents:
            doc_issues = EMRDataValidator.validate_document(document)
            if doc_issues:
                validation_results['document_issues'].extend([f"Document {document.document_id}: {issue}" for issue in doc_issues])
        
        # Check data consistency
        patient_mrns = {p.mrn for p in bundle.patients}
        
        for document in bundle.documents:
            if document.patient_mrn not in patient_mrns:
                validation_results['data_consistency_issues'].append(f"Document {document.document_id} references unknown patient {document.patient_mrn}")
        
        for condition in bundle.conditions:
            if condition.patient_mrn not in patient_mrns:
                validation_results['data_consistency_issues'].append(f"Condition {condition.condition_id} references unknown patient {condition.patient_mrn}")
        
        return validation_results
