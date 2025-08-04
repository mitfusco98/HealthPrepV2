"""
Internal representations of EMR data for processing
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

@dataclass
class EMRPatient:
    """Internal representation of patient data from EMR"""
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

@dataclass
class EMRDocument:
    """Internal representation of medical documents from EMR"""
    id: str
    patient_mrn: str
    title: str
    document_type: str  # 'lab', 'imaging', 'consult', 'hospital'
    document_date: date
    content_url: Optional[str] = None
    content_type: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None

@dataclass
class EMRCondition:
    """Internal representation of patient conditions from EMR"""
    id: str
    patient_mrn: str
    condition_name: str
    icd_code: Optional[str] = None
    onset_date: Optional[date] = None
    clinical_status: str = 'active'
    verification_status: str = 'confirmed'

@dataclass
class EMRObservation:
    """Internal representation of lab results/observations from EMR"""
    id: str
    patient_mrn: str
    code: str
    display_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: str = 'final'
    effective_date: Optional[date] = None
    category: str = 'laboratory'

@dataclass
class EMREncounter:
    """Internal representation of patient encounters/visits from EMR"""
    id: str
    patient_mrn: str
    encounter_type: str
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    provider: Optional[str] = None
    location: Optional[str] = None

class EMRDataBundle:
    """Container for all EMR data for a patient"""
    
    def __init__(self):
        self.patient: Optional[EMRPatient] = None
        self.documents: List[EMRDocument] = []
        self.conditions: List[EMRCondition] = []
        self.observations: List[EMRObservation] = []
        self.encounters: List[EMREncounter] = []
    
    def add_patient(self, patient: EMRPatient):
        """Add patient data to bundle"""
        self.patient = patient
    
    def add_document(self, document: EMRDocument):
        """Add document to bundle"""
        self.documents.append(document)
    
    def add_condition(self, condition: EMRCondition):
        """Add condition to bundle"""
        self.conditions.append(condition)
    
    def add_observation(self, observation: EMRObservation):
        """Add observation to bundle"""
        self.observations.append(observation)
    
    def add_encounter(self, encounter: EMREncounter):
        """Add encounter to bundle"""
        self.encounters.append(encounter)
    
    def get_documents_by_type(self, doc_type: str) -> List[EMRDocument]:
        """Get documents filtered by type"""
        return [doc for doc in self.documents if doc.document_type == doc_type]
    
    def get_active_conditions(self) -> List[EMRCondition]:
        """Get only active conditions"""
        return [cond for cond in self.conditions if cond.clinical_status == 'active']
    
    def get_recent_observations(self, days: int = 365) -> List[EMRObservation]:
        """Get observations from the last N days"""
        cutoff_date = date.today() - timedelta(days=days)
        return [obs for obs in self.observations 
                if obs.effective_date and obs.effective_date >= cutoff_date]
    
    def to_dict(self):
        """Convert bundle to dictionary for JSON serialization"""
        return {
            'patient': self.patient.__dict__ if self.patient else None,
            'documents': [doc.__dict__ for doc in self.documents],
            'conditions': [cond.__dict__ for cond in self.conditions],
            'observations': [obs.__dict__ for obs in self.observations],
            'encounters': [enc.__dict__ for enc in self.encounters]
        }

from datetime import timedelta
