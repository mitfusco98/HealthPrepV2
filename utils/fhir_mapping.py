"""
FHIR Resource Mapping Utilities
Maps HealthPrep screening criteria to FHIR search parameters and resource codes
for Epic interoperability
"""
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class FHIRResourceMapper:
    """Maps HealthPrep screening criteria to FHIR resource queries"""
    
    def __init__(self):
        self.document_type_mapping = self._init_document_type_mapping()
        self.condition_code_mapping = self._init_condition_code_mapping()
        self.observation_code_mapping = self._init_observation_code_mapping()
        
    def _init_document_type_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Map HealthPrep document keywords to FHIR DocumentReference categories/types"""
        return {
            # Laboratory/Lab Results
            'laboratory': {
                'category': 'laboratory',
                'type_codes': ['11502-2', '33743-4', '11526-1'],  # LOINC codes
                'epic_types': ['LAB', 'LabReport', 'Laboratory'],
                'keywords': ['lab', 'laboratory', 'blood', 'urine', 'chemistry', 'hematology', 'microbiology']
            },
            
            # Radiology/Imaging
            'radiology': {
                'category': 'radiology',
                'type_codes': ['18748-4', '18747-6', '11541-0'],  # LOINC codes
                'epic_types': ['RAD', 'Radiology', 'Imaging'],
                'keywords': ['radiology', 'imaging', 'xray', 'x-ray', 'ct', 'mri', 'ultrasound', 'mammogram', 'dexa']
            },
            
            # Cardiology
            'cardiology': {
                'category': 'cardiology',
                'type_codes': ['11524-6', '28010-7'],  # LOINC codes
                'epic_types': ['ECG', 'EKG', 'Cardiology', 'Echo'],
                'keywords': ['ecg', 'ekg', 'echo', 'stress', 'cardiac', 'heart', 'cardiology']
            },
            
            # Pathology
            'pathology': {
                'category': 'pathology',
                'type_codes': ['11529-5', '60567-5'],  # LOINC codes  
                'epic_types': ['PATH', 'Pathology', 'Biopsy'],
                'keywords': ['pathology', 'biopsy', 'tissue', 'cytology', 'pap']
            },
            
            # Consultation Notes
            'consultation': {
                'category': 'consultation',
                'type_codes': ['11488-4', '28570-0'],  # LOINC codes
                'epic_types': ['NOTE', 'Consultation', 'Progress'],
                'keywords': ['consult', 'consultation', 'note', 'visit', 'evaluation']
            },
            
            # Discharge Summaries
            'discharge': {
                'category': 'discharge-summary',
                'type_codes': ['18842-5', '11490-0'],  # LOINC codes
                'epic_types': ['DS', 'Discharge', 'Summary'],
                'keywords': ['discharge', 'summary', 'hospital', 'admission']
            }
        }
    
    def _init_condition_code_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Map HealthPrep condition keywords to FHIR Condition codes (ICD-10/SNOMED CT)"""
        return {
            'diabetes': {
                'icd10_codes': ['E11.9', 'E10.9', 'E08.9', 'E09.9', 'E13.9'],
                'snomed_codes': ['44054006', '46635009', '73211009'],
                'epic_terms': ['Diabetes mellitus', 'Type 2 diabetes', 'Type 1 diabetes'],
                'keywords': ['diabetes', 'diabetic', 'DM', 'T1DM', 'T2DM', 'insulin']
            },
            
            'hypertension': {
                'icd10_codes': ['I10', 'I11.9', 'I12.9', 'I13.10', 'I15.9'],
                'snomed_codes': ['38341003', '59621000'],
                'epic_terms': ['Essential hypertension', 'High blood pressure', 'HTN'],
                'keywords': ['hypertension', 'high blood pressure', 'HTN', 'elevated BP']
            },
            
            'cardiovascular': {
                'icd10_codes': ['I25.9', 'I50.9', 'I48.91', 'Z87.891'],
                'snomed_codes': ['53741008', '84114007', '49436004'],
                'epic_terms': ['Coronary artery disease', 'Heart failure', 'Atrial fibrillation'],
                'keywords': ['CAD', 'CHF', 'AFib', 'cardiac', 'heart disease', 'MI']
            },
            
            'hyperlipidemia': {
                'icd10_codes': ['E78.5', 'E78.0', 'E78.1', 'E78.2'],
                'snomed_codes': ['55822004', '267434000'],
                'epic_terms': ['Hyperlipidemia', 'High cholesterol', 'Dyslipidemia'],
                'keywords': ['hyperlipidemia', 'high cholesterol', 'dyslipidemia', 'lipid']
            },
            
            'obesity': {
                'icd10_codes': ['E66.9', 'E66.01', 'E66.02', 'Z68.3'],
                'snomed_codes': ['414915002', '408512008'],
                'epic_terms': ['Obesity', 'Morbid obesity', 'BMI > 30'],
                'keywords': ['obesity', 'obese', 'BMI', 'overweight', 'morbid obesity']
            },
            
            'smoking': {
                'icd10_codes': ['Z87.891', 'F17.210', 'F17.220'],
                'snomed_codes': ['8517006', '365980008'],
                'epic_terms': ['History of tobacco use', 'Tobacco use disorder', 'Smoking'],
                'keywords': ['smoking', 'tobacco', 'cigarettes', 'nicotine', 'former smoker']
            },
            
            'family_history_cancer': {
                'icd10_codes': ['Z80.9', 'Z80.0', 'Z80.1', 'Z80.2', 'Z80.3'],
                'snomed_codes': ['275937001', '266892002'],
                'epic_terms': ['Family history of malignant neoplasm', 'Family history of cancer'],
                'keywords': ['family history', 'cancer', 'malignancy', 'BRCA', 'genetic']
            }
        }
    
    def _init_observation_code_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Map screening requirements to FHIR Observation LOINC codes"""
        return {
            'hemoglobin_a1c': {
                'loinc_codes': ['4548-4', '17856-6', '59261-8'],
                'epic_names': ['Hemoglobin A1c', 'HbA1c', 'Glycated hemoglobin'],
                'keywords': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin', 'diabetes control']
            },
            
            'cholesterol': {
                'loinc_codes': ['2093-3', '18262-6', '57698-3'],
                'epic_names': ['Cholesterol total', 'Lipid panel', 'Cholesterol'],
                'keywords': ['cholesterol', 'lipid', 'hdl', 'ldl', 'triglycerides']
            },
            
            'blood_pressure': {
                'loinc_codes': ['85354-9', '8480-6', '8462-4'],
                'epic_names': ['Blood pressure', 'Systolic BP', 'Diastolic BP'],
                'keywords': ['blood pressure', 'BP', 'systolic', 'diastolic', 'hypertension']
            },
            
            'mammography': {
                'loinc_codes': ['24604-1', '36319-2', '69150-1'],
                'epic_names': ['Mammography', 'Breast imaging', 'Mammogram'],
                'keywords': ['mammography', 'mammogram', 'breast imaging', 'breast cancer screening']
            },
            
            'colonoscopy': {
                'loinc_codes': ['34111-5', '33717-0', '58453-2'],
                'epic_names': ['Colonoscopy', 'Colon cancer screening', 'Endoscopy'],
                'keywords': ['colonoscopy', 'endoscopy', 'colon', 'colorectal', 'screening']
            },
            
            'psa': {
                'loinc_codes': ['2857-1', '10508-0', '33747-0'],
                'epic_names': ['Prostate specific antigen', 'PSA', 'PSA total'],
                'keywords': ['psa', 'prostate specific antigen', 'prostate cancer screening']
            },
            
            'bone_density': {
                'loinc_codes': ['38269-7', '24701-5', '46278-8'],
                'epic_names': ['DXA scan', 'Bone density', 'DEXA'],
                'keywords': ['dxa', 'dexa', 'bone density', 'osteoporosis', 'bone scan']
            }
        }
    
    def generate_fhir_search_params(self, screening_type: Dict[str, Any]) -> Dict[str, Any]:
        """Generate FHIR search parameters for a screening type"""
        search_params = {
            'patient_criteria': self._build_patient_criteria(screening_type),
            'condition_criteria': self._build_condition_criteria(screening_type),
            'observation_criteria': self._build_observation_criteria(screening_type),
            'document_criteria': self._build_document_criteria(screening_type)
        }
        
        return search_params
    
    def _build_patient_criteria(self, screening_type: Dict[str, Any]) -> Dict[str, Any]:
        """Build Patient resource search criteria"""
        criteria = {}
        
        # Gender criteria
        if screening_type.get('eligible_genders') and screening_type['eligible_genders'] != 'both':
            criteria['gender'] = screening_type['eligible_genders'].lower()
        
        # Age criteria (converted to birthdate ranges)
        if screening_type.get('min_age') or screening_type.get('max_age'):
            current_date = datetime.now().date()
            
            if screening_type.get('max_age'):
                # Birthdate must be after this date to be young enough
                min_birthdate = current_date - timedelta(days=int(screening_type['max_age'] * 365.25))
                criteria['birthdate'] = f'ge{min_birthdate.isoformat()}'
            
            if screening_type.get('min_age'):
                # Birthdate must be before this date to be old enough  
                max_birthdate = current_date - timedelta(days=int(screening_type['min_age'] * 365.25))
                if 'birthdate' in criteria:
                    # Combine with existing criteria
                    criteria['birthdate'] = f"{criteria['birthdate']}&birthdate=le{max_birthdate.isoformat()}"
                else:
                    criteria['birthdate'] = f'le{max_birthdate.isoformat()}'
        
        return criteria
    
    def _build_condition_criteria(self, screening_type: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Condition resource search criteria from trigger conditions"""
        criteria_list = []
        
        trigger_conditions = screening_type.get('trigger_conditions', [])
        if isinstance(trigger_conditions, str):
            try:
                trigger_conditions = json.loads(trigger_conditions)
            except:
                trigger_conditions = []
        
        for condition_name in trigger_conditions:
            condition_key = self._normalize_condition_name(condition_name)
            
            if condition_key in self.condition_code_mapping:
                mapping = self.condition_code_mapping[condition_key]
                
                # Primary search by ICD-10 codes
                criteria = {
                    'code': '|'.join(mapping['icd10_codes']),
                    'clinical-status': 'active',
                    'category': 'problem-list-item'
                }
                
                # Alternative search by SNOMED CT codes
                criteria_alt = {
                    'code': '|'.join([f"http://snomed.info/sct|{code}" for code in mapping['snomed_codes']]),
                    'clinical-status': 'active'
                }
                
                criteria_list.extend([criteria, criteria_alt])
        
        return criteria_list
    
    def _build_observation_criteria(self, screening_type: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Observation resource search criteria for lab/vital requirements"""
        criteria_list = []
        
        keywords = screening_type.get('keywords', [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except:
                keywords = []
        
        for keyword in keywords:
            normalized_keyword = keyword.lower().replace(' ', '_').replace('-', '_')
            
            if normalized_keyword in self.observation_code_mapping:
                mapping = self.observation_code_mapping[normalized_keyword]
                
                criteria = {
                    'code': '|'.join([f"http://loinc.org|{code}" for code in mapping['loinc_codes']]),
                    'category': 'laboratory',
                    'status': 'final'
                }
                
                criteria_list.append(criteria)
        
        return criteria_list
    
    def _build_document_criteria(self, screening_type: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build DocumentReference search criteria from keywords"""
        criteria_list = []
        
        keywords = screening_type.get('keywords', [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except:
                keywords = []
        
        # Group keywords by document type
        document_types = set()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for doc_type, mapping in self.document_type_mapping.items():
                if any(kw in keyword_lower for kw in mapping['keywords']):
                    document_types.add(doc_type)
        
        # Create search criteria for each document type
        for doc_type in document_types:
            mapping = self.document_type_mapping[doc_type]
            
            criteria = {
                'category': mapping['category'],
                'type': '|'.join([f"http://loinc.org|{code}" for code in mapping['type_codes']]),
                'status': 'current'
            }
            
            criteria_list.append(criteria)
        
        return criteria_list
    
    def _normalize_condition_name(self, condition_name: str) -> str:
        """Normalize condition name to match mapping keys"""
        condition_lower = condition_name.lower()
        
        # Direct matches
        if condition_lower in self.condition_code_mapping:
            return condition_lower
        
        # Fuzzy matches
        for key, mapping in self.condition_code_mapping.items():
            if any(keyword in condition_lower for keyword in mapping['keywords']):
                return key
        
        return condition_lower
    
    def generate_epic_query_context(self, screening_type: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Epic-specific query context for screening type"""
        search_params = self.generate_fhir_search_params(screening_type)
        
        return {
            'screening_name': screening_type.get('name'),
            'fhir_search_params': search_params,
            'epic_integration': {
                'required_scopes': ['patient/*.read', 'user/*.read'],
                'resource_types': ['Patient', 'Condition', 'Observation', 'DocumentReference'],
                'search_strategy': 'comprehensive'  # or 'targeted' based on criteria complexity
            },
            'data_requirements': {
                'patient_demographics': bool(screening_type.get('min_age') or screening_type.get('max_age') or screening_type.get('eligible_genders')),
                'active_conditions': bool(screening_type.get('trigger_conditions')),
                'lab_results': any('lab' in kw.lower() for kw in screening_type.get('keywords', [])),
                'clinical_documents': bool(screening_type.get('keywords'))
            }
        }


class ScreeningTypeFHIREnhancer:
    """Enhances ScreeningType model with FHIR mapping capabilities"""
    
    def __init__(self):
        self.mapper = FHIRResourceMapper()
    
    def add_fhir_mapping_to_screening_type(self, screening_type_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add FHIR mapping fields to screening type data"""
        enhanced_data = screening_type_data.copy()
        
        # Generate FHIR search parameters
        fhir_params = self.mapper.generate_fhir_search_params(screening_type_data)
        enhanced_data['fhir_search_params'] = json.dumps(fhir_params)
        
        # Generate Epic query context
        epic_context = self.mapper.generate_epic_query_context(screening_type_data)
        enhanced_data['epic_query_context'] = json.dumps(epic_context)
        
        # Add standardized condition codes
        if screening_type_data.get('trigger_conditions'):
            enhanced_data['fhir_condition_codes'] = self._extract_condition_codes(
                screening_type_data['trigger_conditions']
            )
        
        # Add standardized observation codes  
        if screening_type_data.get('keywords'):
            enhanced_data['fhir_observation_codes'] = self._extract_observation_codes(
                screening_type_data['keywords']
            )
        
        return enhanced_data
    
    def _extract_condition_codes(self, trigger_conditions) -> str:
        """Extract standardized condition codes (ICD-10/SNOMED CT)"""
        if isinstance(trigger_conditions, str):
            try:
                conditions = json.loads(trigger_conditions)
            except:
                conditions = [trigger_conditions]
        else:
            conditions = trigger_conditions or []
        
        all_codes = []
        for condition in conditions:
            normalized = self.mapper._normalize_condition_name(condition)
            if normalized in self.mapper.condition_code_mapping:
                mapping = self.mapper.condition_code_mapping[normalized]
                all_codes.extend(mapping['icd10_codes'])
                all_codes.extend([f"SNOMED:{code}" for code in mapping['snomed_codes']])
        
        return json.dumps(list(set(all_codes)))
    
    def _extract_observation_codes(self, keywords) -> str:
        """Extract standardized observation codes (LOINC)"""
        if isinstance(keywords, str):
            try:
                keyword_list = json.loads(keywords)
            except:
                keyword_list = [keywords]
        else:
            keyword_list = keywords or []
        
        all_codes = []
        for keyword in keyword_list:
            normalized = keyword.lower().replace(' ', '_').replace('-', '_')
            if normalized in self.mapper.observation_code_mapping:
                mapping = self.mapper.observation_code_mapping[normalized]
                all_codes.extend([f"LOINC:{code}" for code in mapping['loinc_codes']])
        
        return json.dumps(list(set(all_codes)))