from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict, Any

@dataclass
class FHIRPatient:
    """Internal representation of FHIR Patient data"""
    id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    active: bool = True

@dataclass
class FHIRCondition:
    """Internal representation of FHIR Condition data"""
    id: str
    patient_id: str
    condition_name: str
    icd10_code: Optional[str] = None
    onset_date: Optional[date] = None
    status: str = 'active'
    severity: Optional[str] = None

@dataclass
class FHIRObservation:
    """Internal representation of FHIR Observation data"""
    id: str
    patient_id: str
    code: str
    display: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    effective_date: Optional[date] = None
    status: str = 'final'
    category: Optional[str] = None

@dataclass
class FHIRDocumentReference:
    """Internal representation of FHIR DocumentReference data"""
    id: str
    patient_id: str
    title: str
    type: str
    category: Optional[str] = None
    creation_date: Optional[date] = None
    content_url: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None

@dataclass
class FHIRBundle:
    """Internal representation of FHIR Bundle"""
    id: str
    type: str
    total: int
    entries: List[Dict[str, Any]]
    
    def get_resources_by_type(self, resource_type: str) -> List[Dict[str, Any]]:
        """Get all resources of a specific type from bundle"""
        resources = []
        for entry in self.entries:
            resource = entry.get('resource', {})
            if resource.get('resourceType') == resource_type:
                resources.append(resource)
        return resources

class FHIRResourceMapper:
    """Maps FHIR resources to internal models"""
    
    @staticmethod
    def map_patient_bundle(bundle_data: Dict[str, Any]) -> List[FHIRPatient]:
        """Map FHIR Patient Bundle to list of FHIRPatient objects"""
        patients = []
        entries = bundle_data.get('entry', [])
        
        for entry in entries:
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Patient':
                patient = FHIRResourceMapper._map_patient_resource(resource)
                if patient:
                    patients.append(patient)
        
        return patients
    
    @staticmethod
    def _map_patient_resource(resource: Dict[str, Any]) -> Optional[FHIRPatient]:
        """Map single FHIR Patient resource"""
        try:
            # Extract identifier (MRN)
            mrn = 'Unknown'
            identifiers = resource.get('identifier', [])
            for identifier in identifiers:
                if identifier.get('type', {}).get('text') == 'MRN':
                    mrn = identifier.get('value', mrn)
                    break
            
            # Extract name
            names = resource.get('name', [])
            first_name = 'Unknown'
            last_name = 'Unknown'
            if names:
                name = names[0]
                first_name = ' '.join(name.get('given', []))
                last_name = name.get('family', 'Unknown')
            
            # Extract birth date
            birth_date_str = resource.get('birthDate')
            birth_date = None
            if birth_date_str:
                try:
                    birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            return FHIRPatient(
                id=resource.get('id', ''),
                mrn=mrn,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=birth_date,
                gender=resource.get('gender', 'unknown'),
                active=resource.get('active', True)
            )
            
        except Exception as e:
            print(f"Error mapping FHIR patient resource: {e}")
            return None
