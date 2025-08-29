"""
Epic FHIR Integration for HealthPrep Screening Engine
Provides specialized Epic interoperability for screening criteria
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .fhir_client import FHIRClient
from utils.fhir_mapping import FHIRResourceMapper, ScreeningTypeFHIREnhancer


class EpicScreeningIntegration:
    """Specialized Epic integration for HealthPrep screening requirements"""
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.mapper = FHIRResourceMapper()
        self.logger = logging.getLogger(__name__)
        
        # Load organization's Epic configuration
        epic_config = self._load_epic_config()
        
        # Initialize FHIR client with organization-specific config
        self.fhir_client = FHIRClient(epic_config)
        
        # Load and set organization-level tokens
        self._load_organization_tokens()
    
    def _load_epic_config(self):
        """Load Epic FHIR configuration for the organization"""
        from models import Organization
        
        org = Organization.query.get(self.organization_id)
        if org and org.epic_client_id:
            self.epic_environment = org.epic_environment
            return {
                'epic_client_id': org.epic_client_id,
                'epic_client_secret': org.epic_client_secret,
                'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
            }
        else:
            self.logger.warning(f"No Epic configuration found for organization {self.organization_id}")
            return None
    
    def _load_organization_tokens(self):
        """Load Epic tokens from organization's credentials"""
        try:
            from models import EpicCredentials
            
            epic_creds = EpicCredentials.query.filter_by(org_id=self.organization_id).first()
            
            if epic_creds and epic_creds.access_token:
                # Check if token is not expired
                if not (epic_creds.token_expires_at and datetime.now() >= epic_creds.token_expires_at):
                    # Set tokens in FHIR client
                    expires_in = int((epic_creds.token_expires_at - datetime.now()).total_seconds()) if epic_creds.token_expires_at else 3600
                    
                    self.fhir_client.set_tokens(
                        access_token=epic_creds.access_token,
                        refresh_token=epic_creds.refresh_token,
                        expires_in=expires_in,
                        scopes=epic_creds.token_scope.split() if epic_creds.token_scope else []
                    )
                    
                    self.logger.info(f"Loaded Epic tokens for organization {self.organization_id}")
                    return True
                else:
                    self.logger.warning(f"Epic tokens expired for organization {self.organization_id}")
            else:
                self.logger.info(f"No Epic tokens found for organization {self.organization_id}")
        except Exception as e:
            self.logger.error(f"Error loading Epic tokens for organization {self.organization_id}: {str(e)}")
        
        return False
    
    def get_screening_relevant_data(self, patient_mrn: str, screening_types: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Retrieve Epic data relevant for specific screening types for a patient
        
        Args:
            patient_mrn: Patient's medical record number
            screening_types: List of screening type data with FHIR mappings
            
        Returns:
            Dict containing organized Epic data for screening evaluation
        """
        try:
            # Ensure tokens are loaded from organization credentials
            if not self.fhir_client.access_token:
                if not self._load_organization_tokens():
                    raise Exception("No Epic FHIR access token available. Please complete organization authentication first.")
            
            # Use Epic's recommended data retrieval sequence
            # This implements the blueprint pattern: Patient → Condition → Observation → DocumentReference → Encounter
            epic_data = self.fhir_client.sync_patient_data_epic_sequence(patient_mrn)
            
            if not epic_data:
                raise Exception(f"No data retrieved for patient: {patient_mrn}")
            
            # Add screening context analysis
            epic_data['screening_context'] = self._build_screening_context(screening_types, epic_data.get('patient', {}))
            
            return epic_data
            
        except Exception as e:
            self.logger.error(f"Error retrieving Epic data for screening: {str(e)}")
            return {}
    
    def _get_patient_by_mrn(self, mrn: str) -> Optional[Dict[str, Any]]:
        """Get patient by MRN using Epic identifier search"""
        try:
            # Search for patient by identifier (MRN)
            search_result = self.fhir_client.search_patients(identifier=mrn)
            
            if search_result and search_result.get('entry'):
                return search_result['entry'][0]['resource']
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding patient by MRN {mrn}: {str(e)}")
            return None
    
    def _aggregate_screening_criteria(self, screening_types: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Aggregate FHIR search criteria from multiple screening types"""
        aggregated = {
            'conditions': [],
            'observations': [],
            'documents': []
        }
        
        for screening_type in screening_types:
            # Generate FHIR search parameters if not already present
            if 'fhir_search_params' not in screening_type:
                search_params = self.mapper.generate_fhir_search_params(screening_type)
                screening_type['fhir_search_params'] = search_params
            else:
                # Parse existing FHIR search params
                if isinstance(screening_type['fhir_search_params'], str):
                    try:
                        search_params = json.loads(screening_type['fhir_search_params'])
                    except:
                        search_params = self.mapper.generate_fhir_search_params(screening_type)
                else:
                    search_params = screening_type['fhir_search_params']
            
            # Add criteria to aggregated lists
            aggregated['conditions'].extend(search_params.get('condition_criteria', []))
            aggregated['observations'].extend(search_params.get('observation_criteria', []))
            aggregated['documents'].extend(search_params.get('document_criteria', []))
        
        # Remove duplicates while preserving order
        for criteria_type in aggregated:
            seen = set()
            unique_criteria = []
            for criteria in aggregated[criteria_type]:
                criteria_str = json.dumps(criteria, sort_keys=True)
                if criteria_str not in seen:
                    seen.add(criteria_str)
                    unique_criteria.append(criteria)
            aggregated[criteria_type] = unique_criteria
        
        return aggregated
    
    def _get_conditions_for_screening(self, patient_id: str, condition_criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get patient conditions relevant for screening evaluation"""
        all_conditions = []
        
        for criteria in condition_criteria:
            try:
                conditions = self.fhir_client.get_conditions(patient_id, **criteria)
                if conditions and conditions.get('entry'):
                    all_conditions.extend(conditions['entry'])
            except Exception as e:
                self.logger.warning(f"Error getting conditions with criteria {criteria}: {str(e)}")
        
        # Remove duplicates based on condition ID
        unique_conditions = {}
        for entry in all_conditions:
            condition_id = entry['resource']['id']
            if condition_id not in unique_conditions:
                unique_conditions[condition_id] = entry
        
        return list(unique_conditions.values())
    
    def _get_observations_for_screening(self, patient_id: str, observation_criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get patient observations (labs/vitals) relevant for screening evaluation"""
        all_observations = []
        
        for criteria in observation_criteria:
            try:
                # Add date range to get recent observations (last 2 years by default)
                criteria_with_date = criteria.copy()
                criteria_with_date['date'] = f"ge{(datetime.now() - timedelta(days=730)).date().isoformat()}"
                
                observations = self.fhir_client.get_observations(patient_id, **criteria_with_date)
                if observations and observations.get('entry'):
                    all_observations.extend(observations['entry'])
            except Exception as e:
                self.logger.warning(f"Error getting observations with criteria {criteria}: {str(e)}")
        
        # Sort by date (most recent first) and remove duplicates
        unique_observations = {}
        for entry in all_observations:
            obs_id = entry['resource']['id']
            if obs_id not in unique_observations:
                unique_observations[obs_id] = entry
        
        sorted_observations = sorted(
            unique_observations.values(),
            key=lambda x: x['resource'].get('effectiveDateTime', ''),
            reverse=True
        )
        
        return sorted_observations
    
    def _get_documents_for_screening(self, patient_id: str, document_criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get patient documents relevant for screening evaluation"""
        all_documents = []
        
        for criteria in document_criteria:
            try:
                documents = self.fhir_client.get_document_references(patient_id, **criteria)
                if documents and documents.get('entry'):
                    all_documents.extend(documents['entry'])
            except Exception as e:
                self.logger.warning(f"Error getting documents with criteria {criteria}: {str(e)}")
        
        # Remove duplicates and sort by date
        unique_documents = {}
        for entry in all_documents:
            doc_id = entry['resource']['id']
            if doc_id not in unique_documents:
                unique_documents[doc_id] = entry
        
        sorted_documents = sorted(
            unique_documents.values(),
            key=lambda x: x['resource'].get('date', ''),
            reverse=True
        )
        
        return sorted_documents
    
    def _get_recent_encounters(self, patient_id: str, days_back: int = 365) -> List[Dict[str, Any]]:
        """Get recent patient encounters for context"""
        try:
            # Get encounters from the last year
            date_filter = (datetime.now() - timedelta(days=days_back)).date().isoformat()
            encounters = self.fhir_client.get_encounters(patient_id, date=f"ge{date_filter}")
            
            if encounters and encounters.get('entry'):
                return encounters['entry']
                
        except Exception as e:
            self.logger.warning(f"Error getting recent encounters: {str(e)}")
        
        return []
    
    def _build_screening_context(self, screening_types: List[Dict[str, Any]], patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build context about which screenings are needed based on patient demographics"""
        context = {
            'patient_demographics': self._extract_patient_demographics(patient_data),
            'applicable_screenings': [],
            'epic_search_summary': {
                'total_screening_types': len(screening_types),
                'condition_based_screenings': 0,
                'age_based_screenings': 0,
                'gender_based_screenings': 0
            }
        }
        
        patient_age = self._calculate_patient_age(patient_data)
        patient_gender = patient_data.get('gender', '').lower()
        
        for screening_type in screening_types:
            applicable = True
            reason = []
            
            # Check age criteria
            if screening_type.get('min_age') and patient_age < screening_type['min_age']:
                applicable = False
                reason.append(f"Patient too young (age {patient_age}, requires {screening_type['min_age']}+)")
            elif screening_type.get('min_age'):
                context['epic_search_summary']['age_based_screenings'] += 1
                
            if screening_type.get('max_age') and patient_age > screening_type['max_age']:
                applicable = False
                reason.append(f"Patient too old (age {patient_age}, max age {screening_type['max_age']})")
            elif screening_type.get('max_age'):
                context['epic_search_summary']['age_based_screenings'] += 1
            
            # Check gender criteria
            eligible_genders = screening_type.get('eligible_genders', 'both')
            if eligible_genders != 'both':
                if (eligible_genders.lower() == 'm' and patient_gender != 'male') or \
                   (eligible_genders.lower() == 'f' and patient_gender != 'female'):
                    applicable = False
                    reason.append(f"Gender criteria not met (patient: {patient_gender}, requires: {eligible_genders})")
                else:
                    context['epic_search_summary']['gender_based_screenings'] += 1
            
            # Check if has trigger conditions
            if screening_type.get('trigger_conditions'):
                context['epic_search_summary']['condition_based_screenings'] += 1
            
            context['applicable_screenings'].append({
                'name': screening_type.get('name'),
                'applicable': applicable,
                'reason': '; '.join(reason) if reason else 'Meets all criteria',
                'requires_condition_check': bool(screening_type.get('trigger_conditions'))
            })
        
        return context
    
    def _extract_patient_demographics(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key demographics from FHIR Patient resource"""
        demographics = {
            'id': patient_data.get('id'),
            'gender': patient_data.get('gender'),
            'birth_date': patient_data.get('birthDate'),
            'age': self._calculate_patient_age(patient_data)
        }
        
        # Extract name
        names = patient_data.get('name', [])
        if names:
            name = names[0]
            demographics['name'] = {
                'family': name.get('family', ''),
                'given': name.get('given', [])
            }
        
        # Extract identifiers (MRN)
        identifiers = patient_data.get('identifier', [])
        for identifier in identifiers:
            if identifier.get('type', {}).get('coding', [{}])[0].get('code') == 'MR':
                demographics['mrn'] = identifier.get('value')
                break
        
        return demographics
    
    def _calculate_patient_age(self, patient_data: Dict[str, Any]) -> int:
        """Calculate patient age from birth date"""
        birth_date_str = patient_data.get('birthDate')
        if not birth_date_str:
            return 0
        
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return age
        except:
            return 0
    
    def sync_screening_data_to_healthprep(self, epic_data: Dict[str, Any], patient_mrn: str) -> bool:
        """Sync Epic screening data to HealthPrep internal models"""
        try:
            from emr.parser import FHIRParser
            
            parser = FHIRParser()
            success = parser.sync_fhir_data(epic_data, patient_mrn)
            
            if success:
                self.logger.info(f"Successfully synced Epic screening data for patient {patient_mrn}")
            else:
                self.logger.error(f"Failed to sync Epic screening data for patient {patient_mrn}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error syncing Epic screening data: {str(e)}")
            return False
    
    def generate_screening_prep_context(self, patient_mrn: str, screening_types: List[Dict[str, Any]], upcoming_encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive context for screening prep sheet generation
        
        Args:
            patient_mrn: Patient MRN
            screening_types: List of screening types to evaluate
            upcoming_encounter_id: Optional encounter ID for context
            
        Returns:
            Dict containing all necessary data for prep sheet generation
        """
        try:
            # Get screening-relevant Epic data
            epic_data = self.get_screening_relevant_data(patient_mrn, screening_types)
            
            # Sync to internal models
            self.sync_screening_data_to_healthprep(epic_data, patient_mrn)
            
            # Build comprehensive context
            prep_context = {
                'patient_info': epic_data.get('patient', {}),
                'screening_context': epic_data.get('screening_context', {}),
                'conditions': epic_data.get('conditions', []),
                'recent_observations': epic_data.get('observations', [])[:10],  # Last 10 observations
                'recent_documents': epic_data.get('documents', [])[:20],  # Last 20 documents
                'recent_encounters': epic_data.get('encounters', [])[:5],  # Last 5 encounters
                'epic_integration_status': {
                    'data_retrieved': True,
                    'patient_found': bool(epic_data.get('patient')),
                    'conditions_count': len(epic_data.get('conditions', [])),
                    'observations_count': len(epic_data.get('observations', [])),
                    'documents_count': len(epic_data.get('documents', [])),
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            if upcoming_encounter_id:
                prep_context['target_encounter'] = self._get_encounter_details(upcoming_encounter_id)
            
            return prep_context
            
        except Exception as e:
            self.logger.error(f"Error generating screening prep context: {str(e)}")
            return {
                'epic_integration_status': {
                    'data_retrieved': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
            }
    
    def _get_encounter_details(self, encounter_id: str) -> Dict[str, Any]:
        """Get details for a specific encounter"""
        try:
            encounter = self.fhir_client.get_encounter(encounter_id)
            return encounter if encounter else {}
        except Exception as e:
            self.logger.warning(f"Error getting encounter details for {encounter_id}: {str(e)}")
            return {}