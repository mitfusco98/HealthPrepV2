"""
Internal representations of EMR data
Data classes for FHIR resources before database conversion
"""
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List

@dataclass
class FHIRPatient:
    """Internal representation of a FHIR Patient resource"""
    fhir_id: str
    mrn: Optional[str]
    first_name: str
    last_name: str
    date_of_birth: Optional[date]
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

@dataclass
class FHIRDocument:
    """Internal representation of a FHIR DocumentReference resource"""
    fhir_id: str
    patient_fhir_id: str
    title: str
    content_type: str
    document_type: Optional[str]
    creation_date: Optional[datetime]
    document_url: Optional[str]
    
    def get_file_extension(self):
        """Get file extension based on content type"""
        content_type_map = {
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'text/plain': '.txt',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
        }
        return content_type_map.get(self.content_type, '.pdf')

@dataclass
class FHIRCondition:
    """Internal representation of a FHIR Condition resource"""
    fhir_id: str
    patient_fhir_id: str
    condition_name: str
    icd10_code: Optional[str]
    onset_date: Optional[datetime]
    clinical_status: str = 'active'
    
    def is_active(self):
        return self.clinical_status.lower() in ['active', 'recurrence']

@dataclass
class FHIRObservation:
    """Internal representation of a FHIR Observation resource"""
    fhir_id: str
    patient_fhir_id: str
    code: str
    display_name: str
    value: Optional[str]
    unit: Optional[str]
    effective_date: Optional[datetime]
    category: Optional[str] = None
    status: str = 'final'
    
    def get_numeric_value(self):
        """Extract numeric value if possible"""
        if not self.value:
            return None
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return None

@dataclass
class FHIREncounter:
    """Internal representation of a FHIR Encounter resource"""
    fhir_id: str
    patient_fhir_id: str
    encounter_type: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: str
    provider: Optional[str] = None
    location: Optional[str] = None
    
    @property
    def duration_minutes(self):
        """Calculate encounter duration in minutes"""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            return int(delta.total_seconds() / 60)
        return None

@dataclass
class FHIRBundle:
    """Internal representation of a FHIR Bundle"""
    bundle_id: str
    bundle_type: str
    total: int
    entries: List[dict]
    
    def get_resources_by_type(self, resource_type: str):
        """Get all resources of a specific type from the bundle"""
        resources = []
        for entry in self.entries:
            resource = entry.get('resource', {})
            if resource.get('resourceType') == resource_type:
                resources.append(resource)
        return resources
    
    def get_patient_resources(self):
        """Get all Patient resources from the bundle"""
        return self.get_resources_by_type('Patient')
    
    def get_document_references(self):
        """Get all DocumentReference resources from the bundle"""
        return self.get_resources_by_type('DocumentReference')
    
    def get_conditions(self):
        """Get all Condition resources from the bundle"""
        return self.get_resources_by_type('Condition')
    
    def get_observations(self):
        """Get all Observation resources from the bundle"""
        return self.get_resources_by_type('Observation')
    
    def get_encounters(self):
        """Get all Encounter resources from the bundle"""
        return self.get_resources_by_type('Encounter')
