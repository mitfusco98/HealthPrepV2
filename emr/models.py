"""
Internal representations of EMR data
"""
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional, Dict, Any

@dataclass
class EMRPatient:
    """Internal representation of patient data from EMR"""
    fhir_id: str
    local_id: Optional[int]
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    mrn: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

@dataclass
class EMRObservation:
    """Internal representation of laboratory/vital observations"""
    id: str
    patient_id: str
    code: str
    display: str
    value: str
    unit: Optional[str]
    reference_range: Optional[str]
    status: str
    effective_date: datetime
    category: str
    
    def to_document_text(self):
        """Convert observation to searchable document text"""
        text = f"Lab Test: {self.display}\n"
        text += f"Value: {self.value}"
        if self.unit:
            text += f" {self.unit}"
        text += "\n"
        if self.reference_range:
            text += f"Reference Range: {self.reference_range}\n"
        text += f"Date: {self.effective_date.strftime('%Y-%m-%d')}\n"
        text += f"Status: {self.status}"
        return text

@dataclass 
class EMRDiagnosticReport:
    """Internal representation of diagnostic reports"""
    id: str
    patient_id: str
    code: str
    display: str
    category: str
    status: str
    effective_date: datetime
    conclusion: Optional[str]
    presentation_text: Optional[str]
    
    def to_document_text(self):
        """Convert diagnostic report to searchable document text"""
        text = f"Diagnostic Report: {self.display}\n"
        text += f"Category: {self.category}\n"
        text += f"Date: {self.effective_date.strftime('%Y-%m-%d')}\n"
        text += f"Status: {self.status}\n"
        if self.conclusion:
            text += f"Conclusion: {self.conclusion}\n"
        if self.presentation_text:
            text += f"Details: {self.presentation_text}"
        return text

@dataclass
class EMRCondition:
    """Internal representation of patient conditions"""
    id: str
    patient_id: str
    code: str
    display: str
    clinical_status: str
    verification_status: str
    onset_date: Optional[date]
    recorded_date: datetime
    
    def to_document_text(self):
        """Convert condition to searchable document text"""
        text = f"Medical Condition: {self.display}\n"
        text += f"Clinical Status: {self.clinical_status}\n"
        text += f"Verification Status: {self.verification_status}\n"
        if self.onset_date:
            text += f"Onset Date: {self.onset_date.strftime('%Y-%m-%d')}\n"
        text += f"Recorded Date: {self.recorded_date.strftime('%Y-%m-%d')}"
        return text

@dataclass
class EMRMedication:
    """Internal representation of patient medications"""
    id: str
    patient_id: str
    code: str
    display: str
    status: str
    intent: str
    dosage_text: Optional[str]
    authored_date: datetime
    
    def to_document_text(self):
        """Convert medication to searchable document text"""
        text = f"Medication: {self.display}\n"
        text += f"Status: {self.status}\n"
        text += f"Intent: {self.intent}\n"
        if self.dosage_text:
            text += f"Dosage: {self.dosage_text}\n"
        text += f"Prescribed Date: {self.authored_date.strftime('%Y-%m-%d')}"
        return text

class EMRDataBundle:
    """Container for all EMR data for a patient"""
    
    def __init__(self, patient: EMRPatient):
        self.patient = patient
        self.observations: List[EMRObservation] = []
        self.diagnostic_reports: List[EMRDiagnosticReport] = []
        self.conditions: List[EMRCondition] = []
        self.medications: List[EMRMedication] = []
    
    def add_observation(self, observation: EMRObservation):
        self.observations.append(observation)
    
    def add_diagnostic_report(self, report: EMRDiagnosticReport):
        self.diagnostic_reports.append(report)
    
    def add_condition(self, condition: EMRCondition):
        self.conditions.append(condition)
    
    def add_medication(self, medication: EMRMedication):
        self.medications.append(medication)
    
    def get_all_searchable_content(self):
        """Get all content as searchable text for screening matching"""
        content = []
        
        for obs in self.observations:
            content.append(obs.to_document_text())
        
        for report in self.diagnostic_reports:
            content.append(report.to_document_text())
        
        for condition in self.conditions:
            content.append(condition.to_document_text())
        
        for medication in self.medications:
            content.append(medication.to_document_text())
        
        return content
    
    def get_conditions_list(self):
        """Get list of active condition codes for screening eligibility"""
        return [condition.code for condition in self.conditions 
                if condition.clinical_status.lower() == 'active']
