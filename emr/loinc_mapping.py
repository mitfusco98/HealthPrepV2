"""
LOINC Code Mapping for Epic FHIR Integration
Maps FHIR LOINC codes to human-friendly names as suggested in Epic's blueprint
"""

import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LabValueMapping:
    """Lab value with normalized units and reference ranges"""
    code: str
    display: str
    value: Optional[float] = None
    unit: str = ""
    reference_range: str = ""
    category: str = "laboratory"

class LOINCCodeMapper:
    """
    Maps FHIR LOINC codes to human-friendly names for screening purposes
    Implements Epic blueprint suggestion for LOINC code mapping
    """
    
    # Core lab values for screening - LOINC codes commonly used by Epic
    LOINC_MAPPINGS = {
        # Lipid Panel
        "2093-3": {"display": "Total Cholesterol", "unit": "mg/dL", "category": "lipid"},
        "2085-9": {"display": "HDL Cholesterol", "unit": "mg/dL", "category": "lipid"},
        "13457-7": {"display": "LDL Cholesterol", "unit": "mg/dL", "category": "lipid"},
        "2571-8": {"display": "Triglycerides", "unit": "mg/dL", "category": "lipid"},
        
        # Diabetes Monitoring
        "4548-4": {"display": "Hemoglobin A1C", "unit": "%", "category": "diabetes"},
        "33747-0": {"display": "Hemoglobin A1C", "unit": "%", "category": "diabetes"},
        "2345-7": {"display": "Glucose", "unit": "mg/dL", "category": "glucose"},
        "1558-6": {"display": "Fasting Glucose", "unit": "mg/dL", "category": "glucose"},
        
        # Vital Signs
        "8480-6": {"display": "Systolic Blood Pressure", "unit": "mmHg", "category": "vitals"},
        "8462-4": {"display": "Diastolic Blood Pressure", "unit": "mmHg", "category": "vitals"},
        "8867-4": {"display": "Heart Rate", "unit": "BPM", "category": "vitals"},
        "29463-7": {"display": "Body Weight", "unit": "kg", "category": "vitals"},
        "8302-2": {"display": "Body Height", "unit": "cm", "category": "vitals"},
        "39156-5": {"display": "Body Mass Index", "unit": "kg/m2", "category": "vitals"},
        
        # Cancer Screening
        "19123-9": {"display": "PSA", "unit": "ng/mL", "category": "cancer"},
        "2857-1": {"display": "Prostate Specific Antigen", "unit": "ng/mL", "category": "cancer"},
        "33747-0": {"display": "Hemoglobin A1C", "unit": "%", "category": "diabetes"},
        
        # Kidney Function
        "2160-0": {"display": "Creatinine", "unit": "mg/dL", "category": "renal"},
        "33914-3": {"display": "eGFR", "unit": "mL/min/1.73m2", "category": "renal"},
        
        # Liver Function
        "1742-6": {"display": "ALT", "unit": "U/L", "category": "liver"},
        "1920-8": {"display": "AST", "unit": "U/L", "category": "liver"},
        
        # Bone Health
        "2000-8": {"display": "Calcium", "unit": "mg/dL", "category": "bone"},
        "14879-1": {"display": "Vitamin D", "unit": "ng/mL", "category": "bone"},
        
        # Thyroid Function
        "3016-3": {"display": "TSH", "unit": "mIU/L", "category": "thyroid"},
        "3024-7": {"display": "Free T4", "unit": "ng/dL", "category": "thyroid"},
    }
    
    # Unit conversion mappings for Epic compatibility
    UNIT_CONVERSIONS = {
        # Height conversions
        ("cm", "in"): lambda x: x * 0.393701,
        ("m", "in"): lambda x: x * 39.3701,
        ("in", "cm"): lambda x: x * 2.54,
        
        # Weight conversions
        ("kg", "lbs"): lambda x: x * 2.20462,
        ("lbs", "kg"): lambda x: x * 0.453592,
        
        # Temperature conversions
        ("C", "F"): lambda x: (x * 9/5) + 32,
        ("F", "C"): lambda x: (x - 32) * 5/9,
        
        # Glucose conversions
        ("mmol/L", "mg/dL"): lambda x: x * 18.018,
        ("mg/dL", "mmol/L"): lambda x: x / 18.018,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def map_loinc_code(self, loinc_code: str) -> Optional[Dict[str, str]]:
        """
        Map LOINC code to human-friendly display name and metadata
        Returns dict with display, unit, and category information
        """
        mapping = self.LOINC_MAPPINGS.get(loinc_code)
        if mapping:
            return {
                "code": loinc_code,
                "display": mapping["display"],
                "unit": mapping["unit"],
                "category": mapping["category"]
            }
        return None
    
    def parse_observation_value(self, observation: Dict[str, Any]) -> Optional[LabValueMapping]:
        """
        Parse FHIR Observation resource into structured lab value
        Implements blueprint suggestion for FHIR data parsing
        """
        try:
            # Extract LOINC code
            loinc_code = None
            display_name = "Unknown"
            
            if "code" in observation and "coding" in observation["code"]:
                for coding in observation["code"]["coding"]:
                    if coding.get("system") == "http://loinc.org":
                        loinc_code = coding.get("code")
                        display_name = coding.get("display", "Unknown")
                        break
            
            if not loinc_code:
                return None
            
            # Map to human-friendly name
            mapping = self.map_loinc_code(loinc_code)
            if mapping:
                display_name = mapping["display"]
                expected_unit = mapping["unit"]
                category = mapping["category"]
            else:
                expected_unit = ""
                category = "other"
            
            # Extract value and unit
            value = None
            unit = ""
            
            if "valueQuantity" in observation:
                value_qty = observation["valueQuantity"]
                value = value_qty.get("value")
                unit = value_qty.get("unit", value_qty.get("code", ""))
                
                # Normalize unit
                unit = self._normalize_unit(unit)
                
                # Convert units if needed for Epic compatibility
                if expected_unit and unit != expected_unit:
                    converted_value = self.convert_units(value, unit, expected_unit)
                    if converted_value is not None:
                        value = converted_value
                        unit = expected_unit
            
            elif "valueString" in observation:
                # Handle string values (e.g., "Positive", "Negative")
                value_str = observation["valueString"]
                return LabValueMapping(
                    code=loinc_code,
                    display=display_name,
                    value=None,
                    unit=value_str,
                    category=category
                )
            
            # Extract reference range if available
            reference_range = ""
            if "referenceRange" in observation and observation["referenceRange"]:
                ref_range = observation["referenceRange"][0]
                if "text" in ref_range:
                    reference_range = ref_range["text"]
                else:
                    low = ref_range.get("low", {}).get("value", "")
                    high = ref_range.get("high", {}).get("value", "")
                    if low and high:
                        reference_range = f"{low}-{high} {unit}"
            
            return LabValueMapping(
                code=loinc_code,
                display=display_name,
                value=value,
                unit=unit,
                reference_range=reference_range,
                category=category
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing observation: {str(e)}")
            return None
    
    def convert_units(self, value: float, from_unit: str, to_unit: str) -> Optional[float]:
        """
        Convert lab values between units for Epic compatibility
        Implements blueprint suggestion for unit conversion
        """
        if not value or from_unit == to_unit:
            return value
        
        # Normalize unit names
        from_unit_norm = self._normalize_unit(from_unit)
        to_unit_norm = self._normalize_unit(to_unit)
        
        conversion_key = (from_unit_norm, to_unit_norm)
        
        if conversion_key in self.UNIT_CONVERSIONS:
            try:
                converter = self.UNIT_CONVERSIONS[conversion_key]
                converted = converter(value)
                self.logger.debug(f"Converted {value} {from_unit} to {converted} {to_unit}")
                return round(converted, 3)
            except Exception as e:
                self.logger.error(f"Unit conversion error: {str(e)}")
        
        return None
    
    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit strings for consistent mapping"""
        if not unit:
            return ""
        
        # Common Epic unit normalizations
        unit_mapping = {
            "mg/dl": "mg/dL",
            "g/dl": "g/dL", 
            "mmol/l": "mmol/L",
            "iu/l": "IU/L",
            "u/l": "U/L",
            "ng/ml": "ng/mL",
            "pg/ml": "pg/mL",
            "celsius": "C",
            "fahrenheit": "F",
            "/min": "/min",
            "bpm": "BPM",
            "beats/min": "BPM"
        }
        
        normalized = unit.lower().strip()
        return unit_mapping.get(normalized, unit)
    
    def create_screening_data_structure(self, patient_data: Dict[str, Any], 
                                      observations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create consolidated screening input data structure
        Implements blueprint suggestion for combined data structure
        """
        screening_data = {
            "patient": {
                "id": patient_data.get("id"),
                "mrn": self._extract_mrn(patient_data),
                "name": self._extract_patient_name(patient_data),
                "birth_date": patient_data.get("birthDate"),
                "gender": patient_data.get("gender"),
                "age": self._calculate_age(patient_data.get("birthDate"))
            },
            "vital_signs": {},
            "lab_results": {},
            "conditions": [],
            "last_updated": observations.get("meta", {}).get("lastUpdated")
        }
        
        # Process observations into categories
        if "entry" in observations:
            for entry in observations["entry"]:
                if entry.get("resource", {}).get("resourceType") == "Observation":
                    obs = entry["resource"]
                    parsed_value = self.parse_observation_value(obs)
                    
                    if parsed_value:
                        if parsed_value.category == "vitals":
                            screening_data["vital_signs"][parsed_value.display] = {
                                "value": parsed_value.value,
                                "unit": parsed_value.unit,
                                "date": obs.get("effectiveDateTime")
                            }
                        elif parsed_value.category in ["lipid", "diabetes", "glucose", "renal", "liver", "bone", "thyroid", "cancer"]:
                            screening_data["lab_results"][parsed_value.display] = {
                                "value": parsed_value.value,
                                "unit": parsed_value.unit,
                                "reference_range": parsed_value.reference_range,
                                "date": obs.get("effectiveDateTime"),
                                "category": parsed_value.category
                            }
        
        return screening_data
    
    def _extract_mrn(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Extract MRN from patient identifiers"""
        if "identifier" in patient_data:
            for identifier in patient_data["identifier"]:
                if identifier.get("type", {}).get("coding", [{}])[0].get("code") == "MR":
                    return identifier.get("value")
        return None
    
    def _extract_patient_name(self, patient_data: Dict[str, Any]) -> str:
        """Extract formatted patient name"""
        if "name" in patient_data and patient_data["name"]:
            name = patient_data["name"][0]
            given_names = name.get("given", [])
            family_name = name.get("family", "")
            
            full_name = " ".join(given_names + [family_name])
            return full_name.strip()
        
        return "Unknown Patient"
    
    def _calculate_age(self, birth_date_str: str) -> Optional[int]:
        """Calculate patient age from birth date"""
        if not birth_date_str:
            return None
        
        try:
            from datetime import datetime
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
            today = datetime.now()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except:
            return None


# Factory function for easy access
def get_loinc_mapper() -> LOINCCodeMapper:
    """Get LOINC code mapper instance"""
    return LOINCCodeMapper()