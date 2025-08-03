"""
Internal representations of EMR data.
Data models for storing and processing EMR information internally.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date, datetime

@dataclass
class EMRPatient:
    """Internal representation of patient data from EMR"""
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str  # 'M', 'F', 'O'
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    fhir_id: Optional[str] = None
    last_sync: Optional[datetime] = None

@dataclass
class EMRObservation:
    """Internal representation of lab/observation data"""
    code: str
    display: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    date: Optional[date] = None
    category: str = 'laboratory'
    reference_range: Optional[Dict[str, Any]] = None
    status: str = 'final'
    fhir_id: Optional[str] = None

@dataclass
class EMRDiagnosticReport:
    """Internal representation of diagnostic report"""
    code: str
    display: str
    date: Optional[date] = None
    category: str = 'diagnostic'
    conclusion: str = ''
    status: str = 'final'
    observations: List[EMRObservation] = field(default_factory=list)
    fhir_id: Optional[str] = None

@dataclass
class EMRDocument:
    """Internal representation of document reference"""
    title: str
    document_date: Optional[date] = None
    type_code: Optional[str] = None
    type_display: Optional[str] = None
    category: str = 'clinical'
    description: str = ''
    mime_type: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    status: str = 'final'
    content: Optional[bytes] = None
    fhir_id: Optional[str] = None

@dataclass
class EMRCondition:
    """Internal representation of medical condition"""
    code: str
    display: str
    system: Optional[str] = None
    clinical_status: str = 'active'
    verification_status: str = 'confirmed'
    onset_date: Optional[date] = None
    recorded_date: Optional[date] = None
    fhir_id: Optional[str] = None

@dataclass
class EMRProcedure:
    """Internal representation of medical procedure"""
    code: str
    display: str
    system: Optional[str] = None
    performed_date: Optional[date] = None
    status: str = 'completed'
    category: Optional[str] = None
    fhir_id: Optional[str] = None

@dataclass
class EMRBundle:
    """Bundle of EMR data for a patient"""
    patient: EMRPatient
    observations: List[EMRObservation] = field(default_factory=list)
    diagnostic_reports: List[EMRDiagnosticReport] = field(default_factory=list)
    documents: List[EMRDocument] = field(default_factory=list)
    conditions: List[EMRCondition] = field(default_factory=list)
    procedures: List[EMRProcedure] = field(default_factory=list)
    sync_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def get_lab_results(self, date_range: Optional[tuple] = None) -> List[EMRObservation]:
        """Get lab results, optionally filtered by date range"""
        labs = [obs for obs in self.observations if obs.category == 'laboratory']
        
        if date_range:
            start_date, end_date = date_range
            labs = [lab for lab in labs 
                   if lab.date and start_date <= lab.date <= end_date]
        
        return sorted(labs, key=lambda x: x.date or date.min, reverse=True)
    
    def get_imaging_studies(self, date_range: Optional[tuple] = None) -> List[EMRDiagnosticReport]:
        """Get imaging studies, optionally filtered by date range"""
        imaging = [report for report in self.diagnostic_reports 
                  if 'imaging' in report.category.lower() or 'radiology' in report.category.lower()]
        
        if date_range:
            start_date, end_date = date_range
            imaging = [study for study in imaging 
                      if study.date and start_date <= study.date <= end_date]
        
        return sorted(imaging, key=lambda x: x.date or date.min, reverse=True)
    
    def get_procedures_by_category(self, category: str, date_range: Optional[tuple] = None) -> List[EMRProcedure]:
        """Get procedures by category, optionally filtered by date range"""
        procedures = [proc for proc in self.procedures 
                     if proc.category and category.lower() in proc.category.lower()]
        
        if date_range:
            start_date, end_date = date_range
            procedures = [proc for proc in procedures 
                         if proc.performed_date and start_date <= proc.performed_date <= end_date]
        
        return sorted(procedures, key=lambda x: x.performed_date or date.min, reverse=True)
    
    def get_active_conditions(self) -> List[EMRCondition]:
        """Get active medical conditions"""
        return [cond for cond in self.conditions 
                if cond.clinical_status == 'active']
    
    def get_documents_by_type(self, document_type: str, date_range: Optional[tuple] = None) -> List[EMRDocument]:
        """Get documents by type, optionally filtered by date range"""
        docs = [doc for doc in self.documents 
                if document_type.lower() in doc.category.lower() or 
                   (doc.type_display and document_type.lower() in doc.type_display.lower())]
        
        if date_range:
            start_date, end_date = date_range
            docs = [doc for doc in docs 
                   if doc.document_date and start_date <= doc.document_date <= end_date]
        
        return sorted(docs, key=lambda x: x.document_date or date.min, reverse=True)
    
    def find_screening_evidence(self, screening_keywords: List[str]) -> Dict[str, List[Any]]:
        """Find evidence for screening completion based on keywords"""
        evidence = {
            'observations': [],
            'reports': [],
            'procedures': [],
            'documents': []
        }
        
        keywords_lower = [kw.lower() for kw in screening_keywords]
        
        # Search observations
        for obs in self.observations:
            if any(kw in obs.display.lower() for kw in keywords_lower):
                evidence['observations'].append(obs)
        
        # Search diagnostic reports
        for report in self.diagnostic_reports:
            if any(kw in report.display.lower() for kw in keywords_lower):
                evidence['reports'].append(report)
        
        # Search procedures
        for proc in self.procedures:
            if any(kw in proc.display.lower() for kw in keywords_lower):
                evidence['procedures'].append(proc)
        
        # Search documents
        for doc in self.documents:
            doc_text = f"{doc.title} {doc.description} {doc.type_display or ''}".lower()
            if any(kw in doc_text for kw in keywords_lower):
                evidence['documents'].append(doc)
        
        return evidence
    
    def get_most_recent_date(self, screening_keywords: List[str]) -> Optional[date]:
        """Get the most recent date for screening evidence"""
        evidence = self.find_screening_evidence(screening_keywords)
        dates = []
        
        # Collect dates from all evidence
        for obs in evidence['observations']:
            if obs.date:
                dates.append(obs.date)
        
        for report in evidence['reports']:
            if report.date:
                dates.append(report.date)
        
        for proc in evidence['procedures']:
            if proc.performed_date:
                dates.append(proc.performed_date)
        
        for doc in evidence['documents']:
            if doc.document_date:
                dates.append(doc.document_date)
        
        return max(dates) if dates else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bundle to dictionary format"""
        return {
            'patient': {
                'mrn': self.patient.mrn,
                'name': f"{self.patient.first_name} {self.patient.last_name}",
                'date_of_birth': self.patient.date_of_birth.isoformat() if self.patient.date_of_birth else None,
                'gender': self.patient.gender,
                'contact': {
                    'phone': self.patient.phone,
                    'email': self.patient.email,
                    'address': self.patient.address
                }
            },
            'data_summary': {
                'observations_count': len(self.observations),
                'reports_count': len(self.diagnostic_reports),
                'documents_count': len(self.documents),
                'conditions_count': len(self.conditions),
                'procedures_count': len(self.procedures),
                'sync_timestamp': self.sync_timestamp.isoformat()
            },
            'recent_activity': {
                'last_lab_date': max([obs.date for obs in self.observations if obs.date], default=None),
                'last_imaging_date': max([rep.date for rep in self.diagnostic_reports if rep.date], default=None),
                'last_procedure_date': max([proc.performed_date for proc in self.procedures if proc.performed_date], default=None)
            }
        }
