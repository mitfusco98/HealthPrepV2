"""
Internal representations of EMR data structures
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any

@dataclass
class PatientInfo:
    """Internal patient representation"""
    fhir_id: Optional[str] = None
    mrn: str = ""
    first_name: str = ""
    last_name: str = ""
    date_of_birth: Optional[date] = None
    gender: str = ""
    phone: str = ""
    email: str = ""
    created_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def age(self) -> Optional[int]:
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

@dataclass
class DocumentInfo:
    """Internal document representation"""
    fhir_id: Optional[str] = None
    filename: str = ""
    document_type: str = ""
    document_date: Optional[date] = None
    content_type: str = ""
    description: str = ""
    file_path: str = ""
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    phi_filtered: bool = False
    raw_fhir: str = ""

@dataclass
class ConditionInfo:
    """Internal condition representation"""
    fhir_id: Optional[str] = None
    condition_code: str = ""
    condition_name: str = ""
    diagnosis_date: Optional[date] = None
    is_active: bool = True

@dataclass
class ObservationInfo:
    """Internal observation representation"""
    fhir_id: Optional[str] = None
    code_text: str = ""
    value_text: str = ""
    observation_date: Optional[date] = None
    category: str = ""
    raw_fhir: str = ""

@dataclass
class DiagnosticReportInfo:
    """Internal diagnostic report representation"""
    fhir_id: Optional[str] = None
    category: str = ""
    code_text: str = ""
    report_date: Optional[date] = None
    conclusion: str = ""
    status: str = ""
    raw_fhir: str = ""

@dataclass
class ScreeningResult:
    """Internal screening result representation"""
    screening_id: Optional[int] = None
    patient_name: str = ""
    screening_type: str = ""
    status: str = "Due"  # Due, Due Soon, Complete, Overdue
    last_completed_date: Optional[date] = None
    next_due_date: Optional[date] = None
    frequency: str = ""
    matched_documents: List[DocumentInfo] = field(default_factory=list)
    eligibility_met: bool = True
    notes: str = ""
    confidence_score: float = 0.0

@dataclass
class PrepSheetData:
    """Internal prep sheet data representation"""
    patient: PatientInfo = field(default_factory=PatientInfo)
    prep_date: date = field(default_factory=date.today)
    last_visit_date: Optional[date] = None
    
    # Medical data sections
    recent_labs: List[ObservationInfo] = field(default_factory=list)
    recent_imaging: List[DiagnosticReportInfo] = field(default_factory=list)
    recent_consults: List[DocumentInfo] = field(default_factory=list)
    recent_hospital_stays: List[DocumentInfo] = field(default_factory=list)
    
    # Screening checklist
    screenings: List[ScreeningResult] = field(default_factory=list)
    
    # Active conditions
    active_conditions: List[ConditionInfo] = field(default_factory=list)
    
    # Document summaries
    lab_documents: List[DocumentInfo] = field(default_factory=list)
    imaging_documents: List[DocumentInfo] = field(default_factory=list)
    consult_documents: List[DocumentInfo] = field(default_factory=list)
    hospital_documents: List[DocumentInfo] = field(default_factory=list)

@dataclass
class EMRSyncStatus:
    """EMR synchronization status"""
    last_sync_time: Optional[datetime] = None
    patients_synced: int = 0
    documents_synced: int = 0
    errors_encountered: int = 0
    sync_duration_seconds: float = 0.0
    error_details: List[str] = field(default_factory=list)
    success: bool = False

@dataclass
class FHIRResource:
    """Generic FHIR resource wrapper"""
    resource_type: str = ""
    resource_id: str = ""
    resource_data: Dict[str, Any] = field(default_factory=dict)
    patient_id: str = ""
    last_updated: Optional[datetime] = None
    
    def get_display_name(self) -> str:
        """Get human-readable display name for the resource"""
        if self.resource_type == "Patient":
            names = self.resource_data.get('name', [])
            if names:
                name = names[0]
                given = ' '.join(name.get('given', []))
                family = name.get('family', '')
                return f"{given} {family}".strip()
        elif self.resource_type == "DocumentReference":
            return self.resource_data.get('description', 'Document')
        elif self.resource_type == "DiagnosticReport":
            code = self.resource_data.get('code', {})
            return code.get('text', 'Diagnostic Report')
        elif self.resource_type == "Condition":
            code = self.resource_data.get('code', {})
            return code.get('text', 'Condition')
        elif self.resource_type == "Observation":
            code = self.resource_data.get('code', {})
            return code.get('text', 'Observation')
        
        return f"{self.resource_type} {self.resource_id}"
