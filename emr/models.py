"""
Internal EMR data models
Represents EMR data in our internal format after FHIR parsing
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict, Any

@dataclass
class EMRPatient:
    """Internal representation of patient data from EMR"""
    fhir_id: str
    mrn: str
    name: str
    date_of_birth: Optional[date]
    gender: Optional[str]
    conditions: List['EMRCondition'] = None
    documents: List['EMRDocument'] = None
    observations: List['EMRObservation'] = None
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
        if self.documents is None:
            self.documents = []
        if self.observations is None:
            self.observations = []
    
    @property
    def age(self) -> Optional[int]:
        """Calculate patient age"""
        if not self.date_of_birth:
            return None
        
        today = date.today()
        age = today.year - self.date_of_birth.year
        
        # Adjust if birthday hasn't occurred this year
        if today < date(today.year, self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        
        return age
    
    def has_condition(self, condition_code: str) -> bool:
        """Check if patient has a specific condition"""
        return any(
            cond.condition_code == condition_code or condition_code.lower() in cond.condition_name.lower()
            for cond in self.conditions
            if cond.condition_name and cond.status == 'active'
        )
    
    def get_active_conditions(self) -> List['EMRCondition']:
        """Get all active conditions"""
        return [cond for cond in self.conditions if cond.status == 'active']

@dataclass
class EMRCondition:
    """Internal representation of patient condition from EMR"""
    fhir_id: str
    condition_code: Optional[str]
    condition_name: Optional[str]
    status: str
    onset_date: Optional[date]
    
    def is_active(self) -> bool:
        """Check if condition is currently active"""
        return self.status.lower() == 'active'

@dataclass
class EMRDocument:
    """Internal representation of medical document from EMR"""
    fhir_id: str
    document_type: str
    filename: str
    date_created: Optional[date]
    content_url: Optional[str]
    content: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    
    def get_searchable_text(self) -> str:
        """Get all searchable text from document"""
        text_parts = []
        
        if self.filename:
            text_parts.append(self.filename)
        if self.content:
            text_parts.append(self.content)
        if self.ocr_text:
            text_parts.append(self.ocr_text)
        
        return ' '.join(text_parts).lower()
    
    def is_recent(self, months: int = 12) -> bool:
        """Check if document is from within specified months"""
        if not self.date_created:
            return False
        
        from dateutil.relativedelta import relativedelta
        cutoff_date = date.today() - relativedelta(months=months)
        return self.date_created >= cutoff_date

@dataclass
class EMRObservation:
    """Internal representation of observation/lab result from EMR"""
    fhir_id: str
    code: Optional[str]
    display: Optional[str]
    value: Optional[str]
    unit: Optional[str]
    date: Optional[date]
    category: str
    reference_range: Optional[str] = None
    status: Optional[str] = None
    
    def is_abnormal(self) -> bool:
        """Check if observation value is outside normal range"""
        # This would need more sophisticated logic based on reference ranges
        # For now, return False as we don't have reference range parsing
        return False
    
    def is_recent(self, months: int = 12) -> bool:
        """Check if observation is from within specified months"""
        if not self.date:
            return False
        
        from dateutil.relativedelta import relativedelta
        cutoff_date = date.today() - relativedelta(months=months)
        return self.date >= cutoff_date

@dataclass
class EMRBundle:
    """Bundle of EMR data for a patient"""
    patient: EMRPatient
    conditions: List[EMRCondition]
    documents: List[EMRDocument]
    observations: List[EMRObservation]
    
    def __post_init__(self):
        # Link related data to patient
        self.patient.conditions = self.conditions
        self.patient.documents = self.documents
        self.patient.observations = self.observations
    
    def get_documents_by_type(self, doc_type: str) -> List[EMRDocument]:
        """Get documents filtered by type"""
        return [doc for doc in self.documents if doc.document_type == doc_type]
    
    def get_recent_documents(self, months: int = 12) -> List[EMRDocument]:
        """Get documents from within specified months"""
        return [doc for doc in self.documents if doc.is_recent(months)]
    
    def get_observations_by_category(self, category: str) -> List[EMRObservation]:
        """Get observations filtered by category"""
        return [obs for obs in self.observations if obs.category == category]
    
    def get_recent_observations(self, months: int = 12) -> List[EMRObservation]:
        """Get observations from within specified months"""
        return [obs for obs in self.observations if obs.is_recent(months)]
