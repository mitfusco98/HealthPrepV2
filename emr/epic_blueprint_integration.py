"""
Epic FHIR Blueprint Integration Module
Implements specific patterns suggested in Epic's FHIR integration blueprint
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .fhir_client import FHIRClient
from .loinc_mapping import LOINCCodeMapper, get_loinc_mapper
from .parser import FHIRParser

logger = logging.getLogger(__name__)

class EpicBlueprintIntegration:
    """
    Implements Epic FHIR integration patterns exactly as specified in the blueprint
    Consolidates all blueprint-specific functionality in one module
    """
    
    def __init__(self, organization_config: Dict[str, str] = None):
        self.fhir_client = FHIRClient(organization_config)
        self.loinc_mapper = get_loinc_mapper()
        self.fhir_parser = FHIRParser()
        self.logger = logging.getLogger(__name__)
    
    def api_get(self, org, resource_path: str) -> Optional[Dict[str, Any]]:
        """
        Base function to issue API calls as per Epic blueprint
        Reads org.epic_fhir_url, ensures valid access token, handles 401 errors
        """
        if not org:
            self.logger.error("Organization required for Epic API calls")
            return None
        
        try:
            # Read base URL from organization
            base_url = getattr(org, 'epic_fhir_url', None) or getattr(org, 'epic_production_base_url', None)
            if not base_url:
                self.logger.error(f"No Epic FHIR URL configured for organization {org.name}")
                return None
            
            # Update client configuration
            if base_url != self.fhir_client.base_url:
                self.fhir_client.base_url = base_url.rstrip('/') + '/'
                if not self.fhir_client.base_url.endswith('/api/FHIR/R4/'):
                    self.fhir_client.base_url += 'api/FHIR/R4/'
            
            # Construct full URL
            full_url = f"{self.fhir_client.base_url.rstrip('/')}/{resource_path.lstrip('/')}"
            
            # Use enhanced retry logic with 401 handling
            result = self.fhir_client._api_get_with_retry(full_url)
            
            if result:
                self.logger.info(f"Successfully retrieved {resource_path} for org {org.name}")
            else:
                self.logger.warning(f"No data retrieved for {resource_path} from org {org.name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in api_get for {resource_path}: {str(e)}")
            return None
    
    def fetch_patient(self, org, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Patient resource by ID as per Epic blueprint
        Returns patient demographics parsed from FHIR JSON
        """
        try:
            fhir_patient = self.api_get(org, f"Patient/{patient_id}")
            
            if not fhir_patient:
                self.logger.warning(f"Patient {patient_id} not found in Epic for org {org.name}")
                return None
            
            # Parse FHIR Patient resource into structured data
            parsed_patient = self.fhir_parser.parse_patient(fhir_patient)
            
            # Create consolidated screening data structure
            return self.loinc_mapper.create_screening_data_structure(fhir_patient, {})
            
        except Exception as e:
            self.logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            return None
    
    def fetch_observations(self, org, patient_id: str, category: str = "vital-signs") -> Dict[str, Any]:
        """
        Retrieve key Observation resources for the patient as per Epic blueprint
        Query by category or codes to limit to relevant observations
        """
        try:
            observations_bundle = self.api_get(org, f"Observation?patient={patient_id}&category={category}&_sort=-date&_count=50")
            
            if not observations_bundle or "entry" not in observations_bundle:
                self.logger.info(f"No {category} observations found for patient {patient_id}")
                return {}
            
            # Process observations with LOINC mapping
            processed_observations = {}
            
            for entry in observations_bundle.get("entry", []):
                if entry.get("resource", {}).get("resourceType") == "Observation":
                    obs = entry["resource"]
                    
                    # Parse observation value with LOINC mapping
                    parsed_value = self.loinc_mapper.parse_observation_value(obs)
                    
                    if parsed_value:
                        # Map to human-friendly names for screening
                        key = parsed_value.display or f"Unknown_{parsed_value.code}"
                        processed_observations[key] = {
                            "value": parsed_value.value,
                            "unit": parsed_value.unit,
                            "reference_range": parsed_value.reference_range,
                            "date": obs.get("effectiveDateTime"),
                            "loinc_code": parsed_value.code,
                            "category": parsed_value.category
                        }
            
            self.logger.info(f"Processed {len(processed_observations)} {category} observations for patient {patient_id}")
            return processed_observations
            
        except Exception as e:
            self.logger.error(f"Error fetching observations for patient {patient_id}: {str(e)}")
            return {}
    
    def fetch_conditions(self, org, patient_id: str, clinical_status: str = "active") -> List[Dict[str, Any]]:
        """
        Get a list of current and past conditions for the patient as per Epic blueprint
        Parse to identify chronic conditions like diabetes, hypertension
        """
        try:
            conditions_bundle = self.api_get(org, f"Condition?patient={patient_id}&clinical-status={clinical_status}&_sort=-onset-date")
            
            if not conditions_bundle or "entry" not in conditions_bundle:
                self.logger.info(f"No conditions found for patient {patient_id}")
                return []
            
            processed_conditions = []
            
            for entry in conditions_bundle.get("entry", []):
                if entry.get("resource", {}).get("resourceType") == "Condition":
                    condition = entry["resource"]
                    
                    # Extract condition information
                    condition_info = {
                        "id": condition.get("id"),
                        "clinical_status": condition.get("clinicalStatus", {}).get("coding", [{}])[0].get("code"),
                        "verification_status": condition.get("verificationStatus", {}).get("coding", [{}])[0].get("code"),
                        "code": None,
                        "display": "Unknown Condition",
                        "onset_date": condition.get("onsetDateTime") or condition.get("onsetPeriod", {}).get("start"),
                        "recorded_date": condition.get("recordedDate")
                    }
                    
                    # Extract condition code and display name
                    if "code" in condition and "coding" in condition["code"]:
                        coding = condition["code"]["coding"][0]
                        condition_info["code"] = coding.get("code")
                        condition_info["display"] = coding.get("display", "Unknown Condition")
                        condition_info["system"] = coding.get("system")
                    
                    processed_conditions.append(condition_info)
            
            self.logger.info(f"Processed {len(processed_conditions)} conditions for patient {patient_id}")
            return processed_conditions
            
        except Exception as e:
            self.logger.error(f"Error fetching conditions for patient {patient_id}: {str(e)}")
            return []
    
    def fetch_procedures(self, org, patient_id: str) -> List[Dict[str, Any]]:
        """
        Query Procedure resources if screening logic needs past procedures
        Extract relevant info (types of procedures or dates)
        """
        try:
            procedures_bundle = self.api_get(org, f"Procedure?patient={patient_id}&_sort=-performed-date&_count=50")
            
            if not procedures_bundle or "entry" not in procedures_bundle:
                self.logger.info(f"No procedures found for patient {patient_id}")
                return []
            
            processed_procedures = []
            
            for entry in procedures_bundle.get("entry", []):
                if entry.get("resource", {}).get("resourceType") == "Procedure":
                    procedure = entry["resource"]
                    
                    # Extract procedure information
                    procedure_info = {
                        "id": procedure.get("id"),
                        "status": procedure.get("status"),
                        "code": None,
                        "display": "Unknown Procedure",
                        "performed_date": procedure.get("performedDateTime") or 
                                       procedure.get("performedPeriod", {}).get("start"),
                        "recorded_date": procedure.get("recordedDate")
                    }
                    
                    # Extract procedure code and display name
                    if "code" in procedure and "coding" in procedure["code"]:
                        coding = procedure["code"]["coding"][0]
                        procedure_info["code"] = coding.get("code")
                        procedure_info["display"] = coding.get("display", "Unknown Procedure")
                        procedure_info["system"] = coding.get("system")
                    
                    processed_procedures.append(procedure_info)
            
            self.logger.info(f"Processed {len(processed_procedures)} procedures for patient {patient_id}")
            return processed_procedures
            
        except Exception as e:
            self.logger.error(f"Error fetching procedures for patient {patient_id}: {str(e)}")
            return []
    
    def get_comprehensive_screening_data(self, org, patient_id: str) -> Dict[str, Any]:
        """
        Consolidated screening input data structure as per Epic blueprint
        Combines Patient info and key observations in usable format
        """
        try:
            self.logger.info(f"Fetching comprehensive screening data for patient {patient_id}")
            
            # Fetch patient demographics
            patient_data = self.fetch_patient(org, patient_id)
            if not patient_data:
                self.logger.error(f"Could not retrieve patient data for {patient_id}")
                return {}
            
            # Fetch vital signs and lab results
            vital_signs = self.fetch_observations(org, patient_id, "vital-signs")
            lab_results = self.fetch_observations(org, patient_id, "laboratory")
            
            # Fetch conditions and procedures
            conditions = self.fetch_conditions(org, patient_id)
            procedures = self.fetch_procedures(org, patient_id)
            
            # Create consolidated screening data structure
            screening_data = {
                "patient": patient_data.get("patient", {}),
                "vital_signs": vital_signs,
                "lab_results": lab_results,
                "conditions": conditions,
                "procedures": procedures,
                "data_retrieved_at": datetime.utcnow().isoformat(),
                "organization": {
                    "id": org.id,
                    "name": org.name,
                    "epic_endpoint": getattr(org, 'epic_production_base_url', 'Unknown')
                }
            }
            
            # Handle missing data gracefully
            if not vital_signs and not lab_results:
                self.logger.warning(f"No vital signs or lab results found for patient {patient_id}")
                screening_data["data_quality_warning"] = "Limited clinical data available"
            
            # Unit conversions if necessary for screening compatibility
            screening_data = self._apply_screening_unit_conversions(screening_data)
            
            self.logger.info(f"Successfully compiled comprehensive screening data for patient {patient_id}")
            return screening_data
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive screening data: {str(e)}")
            return {}
    
    def _apply_screening_unit_conversions(self, screening_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply unit conversions as suggested in Epic blueprint
        Convert units like height in cm to inches for screening compatibility
        """
        try:
            # Convert height to inches if needed
            if "Body Height" in screening_data.get("vital_signs", {}):
                height_data = screening_data["vital_signs"]["Body Height"]
                if height_data.get("unit") == "cm":
                    height_cm = height_data.get("value")
                    if height_cm:
                        height_inches = self.loinc_mapper.convert_units(height_cm, "cm", "in")
                        if height_inches:
                            height_data["value_inches"] = height_inches
                            height_data["original_cm"] = height_cm
            
            # Convert weight to lbs if needed  
            if "Body Weight" in screening_data.get("vital_signs", {}):
                weight_data = screening_data["vital_signs"]["Body Weight"]
                if weight_data.get("unit") == "kg":
                    weight_kg = weight_data.get("value")
                    if weight_kg:
                        weight_lbs = self.loinc_mapper.convert_units(weight_kg, "kg", "lbs")
                        if weight_lbs:
                            weight_data["value_lbs"] = weight_lbs
                            weight_data["original_kg"] = weight_kg
            
            # Convert glucose units if needed
            for lab_name in ["Glucose", "Fasting Glucose"]:
                if lab_name in screening_data.get("lab_results", {}):
                    glucose_data = screening_data["lab_results"][lab_name]
                    if glucose_data.get("unit") == "mmol/L":
                        glucose_mmol = glucose_data.get("value")
                        if glucose_mmol:
                            glucose_mg_dl = self.loinc_mapper.convert_units(glucose_mmol, "mmol/L", "mg/dL")
                            if glucose_mg_dl:
                                glucose_data["value_mg_dl"] = glucose_mg_dl
                                glucose_data["original_mmol_l"] = glucose_mmol
            
            return screening_data
            
        except Exception as e:
            self.logger.error(f"Error applying unit conversions: {str(e)}")
            return screening_data


def get_epic_blueprint_integration(organization_config: Dict[str, str] = None) -> EpicBlueprintIntegration:
    """Factory function to get Epic blueprint integration instance"""
    return EpicBlueprintIntegration(organization_config)