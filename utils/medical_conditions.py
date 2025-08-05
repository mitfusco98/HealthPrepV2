"""
Medical Conditions Database
Provides FHIR-compatible condition codes and trigger conditions for screening variants
"""
import json
import re
from typing import List, Dict, Set

class MedicalConditionsDB:
    """Medical conditions database for trigger condition management and FHIR codes"""
    
    def __init__(self):
        self.conditions = self._load_medical_conditions()
        self.condition_categories = self._load_condition_categories()
    
    def _load_medical_conditions(self) -> Dict[str, List[str]]:
        """Load comprehensive medical conditions database with FHIR codes"""
        return {
            'diabetes': [
                'diabetes mellitus', 'type 1 diabetes', 'type 2 diabetes', 
                'gestational diabetes', 'diabetic', 'DM', 'T1DM', 'T2DM',
                'insulin dependent diabetes', 'non insulin dependent diabetes',
                'diabetes mellitus type 1', 'diabetes mellitus type 2',
                'prediabetes', 'impaired glucose tolerance', 'IGT'
            ],
            'cardiovascular': [
                'hypertension', 'high blood pressure', 'HTN', 'cardiac disease',
                'coronary artery disease', 'CAD', 'myocardial infarction', 'MI',
                'heart failure', 'CHF', 'atrial fibrillation', 'AFib',
                'hyperlipidemia', 'dyslipidemia', 'high cholesterol',
                'peripheral vascular disease', 'PVD', 'stroke', 'CVA'
            ],
            'oncology': [
                'cancer', 'malignancy', 'tumor', 'neoplasm', 'carcinoma',
                'breast cancer', 'prostate cancer', 'colorectal cancer',
                'lung cancer', 'skin cancer', 'melanoma', 'lymphoma',
                'leukemia', 'family history of cancer', 'BRCA mutation',
                'genetic predisposition to cancer'
            ],
            'pulmonary': [
                'asthma', 'COPD', 'chronic obstructive pulmonary disease',
                'emphysema', 'chronic bronchitis', 'smoking history',
                'tobacco use disorder', 'pulmonary fibrosis',
                'sleep apnea', 'respiratory disease', 'lung disease'
            ],
            'gastrointestinal': [
                'IBD', 'inflammatory bowel disease', 'Crohns disease',
                'ulcerative colitis', 'IBS', 'irritable bowel syndrome',
                'GERD', 'gastroesophageal reflux disease', 'peptic ulcer',
                'hepatitis', 'cirrhosis', 'liver disease', 'celiac disease'
            ],
            'endocrine': [
                'thyroid disease', 'hypothyroidism', 'hyperthyroidism',
                'thyroid nodule', 'goiter', 'adrenal insufficiency',
                'Cushings syndrome', 'osteoporosis', 'osteopenia',
                'metabolic syndrome', 'obesity', 'BMI > 30'
            ],
            'renal': [
                'chronic kidney disease', 'CKD', 'renal insufficiency',
                'kidney disease', 'nephropathy', 'dialysis',
                'kidney transplant', 'proteinuria', 'hematuria',
                'hypertensive nephropathy', 'diabetic nephropathy'
            ],
            'autoimmune': [
                'rheumatoid arthritis', 'RA', 'systemic lupus erythematosus',
                'SLE', 'lupus', 'multiple sclerosis', 'MS',
                'inflammatory arthritis', 'psoriatic arthritis',
                'ankylosing spondylitis', 'Sjögrens syndrome'
            ],
            'mental_health': [
                'depression', 'major depressive disorder', 'MDD',
                'anxiety disorder', 'generalized anxiety disorder', 'GAD',
                'bipolar disorder', 'PTSD', 'post traumatic stress disorder',
                'substance use disorder', 'alcohol use disorder'
            ],
            'reproductive': [
                'pregnancy', 'pregnant', 'postmenopausal', 'menopause',
                'PCOS', 'polycystic ovary syndrome', 'endometriosis',
                'infertility', 'contraceptive use', 'hormone replacement therapy',
                'HRT', 'estrogen therapy'
            ]
        }
    
    def _load_condition_categories(self) -> Dict[str, Dict]:
        """Load condition categories with screening implications"""
        return {
            'Diabetes Mellitus': {
                'category': 'diabetes',
                'screening_impact': {
                    'A1C Test': {'frequency_months': 3, 'age_start': 18},
                    'Eye Exam': {'frequency_months': 12, 'age_start': 18},
                    'Lipid Panel': {'frequency_months': 12, 'age_start': 18},
                    'Kidney Function': {'frequency_months': 12, 'age_start': 18}
                },
                'fhir_codes': ['E10', 'E11', 'E13', 'E14', '250']
            },
            'Hypertension': {
                'category': 'cardiovascular',
                'screening_impact': {
                    'Blood Pressure Check': {'frequency_months': 3, 'age_start': 18},
                    'Lipid Panel': {'frequency_months': 12, 'age_start': 18},
                    'ECG': {'frequency_months': 12, 'age_start': 40},
                    'Kidney Function': {'frequency_months': 12, 'age_start': 18}
                },
                'fhir_codes': ['I10', 'I11', 'I12', 'I13', '401']
            },
            'Family History of Cancer': {
                'category': 'oncology',
                'screening_impact': {
                    'Mammogram': {'frequency_months': 12, 'age_start': 40},
                    'Colonoscopy': {'frequency_months': 60, 'age_start': 45},
                    'Skin Cancer Screening': {'frequency_months': 6, 'age_start': 18}
                },
                'fhir_codes': ['Z80', 'Z85']
            },
            'BRCA Mutation': {
                'category': 'oncology',
                'screening_impact': {
                    'Mammogram': {'frequency_months': 6, 'age_start': 25},
                    'Breast MRI': {'frequency_months': 6, 'age_start': 25},
                    'Genetic Counseling': {'frequency_months': 12, 'age_start': 18}
                },
                'fhir_codes': ['Z15.01', 'Z15.02']
            },
            'Smoking History': {
                'category': 'pulmonary',
                'screening_impact': {
                    'Chest X-ray': {'frequency_months': 12, 'age_start': 50},
                    'Low-dose CT': {'frequency_months': 12, 'age_start': 50},
                    'Pulmonary Function Test': {'frequency_months': 24, 'age_start': 40}
                },
                'fhir_codes': ['Z87.891', 'F17']
            },
            'Chronic Kidney Disease': {
                'category': 'renal',
                'screening_impact': {
                    'Kidney Function': {'frequency_months': 6, 'age_start': 18},
                    'Bone Density': {'frequency_months': 12, 'age_start': 50},
                    'Cardiovascular Screening': {'frequency_months': 12, 'age_start': 18}
                },
                'fhir_codes': ['N18', '585']
            },
            'Osteoporosis Risk': {
                'category': 'endocrine',
                'screening_impact': {
                    'DEXA Scan': {'frequency_months': 12, 'age_start': 50},
                    'Vitamin D Level': {'frequency_months': 12, 'age_start': 50},
                    'Fracture Risk Assessment': {'frequency_months': 24, 'age_start': 50}
                },
                'fhir_codes': ['M80', 'M81', '733.0']
            },
            'Postmenopausal': {
                'category': 'reproductive',
                'screening_impact': {
                    'DEXA Scan': {'frequency_months': 24, 'age_start': 50},
                    'Mammogram': {'frequency_months': 12, 'age_start': 50},
                    'Lipid Panel': {'frequency_months': 12, 'age_start': 50}
                },
                'fhir_codes': ['N95.1', '627.2']
            }
        }
    
    def get_conditions_for_category(self, category: str) -> List[str]:
        """Get medical conditions for a specific category"""
        return self.conditions.get(category, [])
    
    def search_conditions(self, query: str, limit: int = 10) -> List[str]:
        """Search for conditions matching the query"""
        query_lower = query.lower()
        matches = set()
        
        for category, conditions in self.conditions.items():
            for condition in conditions:
                if query_lower in condition.lower():
                    matches.add(condition)
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        
        return list(matches)[:limit]
    
    def get_all_categories(self) -> List[str]:
        """Get list of all condition categories"""
        return list(self.conditions.keys())
    
    def get_standard_conditions(self) -> List[str]:
        """Get list of standard trigger conditions"""
        return list(self.condition_categories.keys())
    
    def get_condition_impact(self, condition_name: str) -> Dict:
        """Get screening impact for a specific condition"""
        return self.condition_categories.get(condition_name, {}).get('screening_impact', {})
    
    def get_fhir_codes(self, condition_name: str) -> List[str]:
        """Get FHIR codes for a specific condition"""
        return self.condition_categories.get(condition_name, {}).get('fhir_codes', [])
    
    def import_standard_conditions(self, screening_name: str) -> List[str]:
        """Import standard trigger conditions for a screening type"""
        relevant_conditions = []
        
        # Find conditions that impact this screening
        for condition_name, data in self.condition_categories.items():
            screening_impact = data.get('screening_impact', {})
            if screening_name in screening_impact:
                relevant_conditions.append(condition_name)
        
        # Add common conditions based on screening name
        screening_lower = screening_name.lower()
        if 'a1c' in screening_lower or 'diabetes' in screening_lower:
            relevant_conditions.extend(['Diabetes Mellitus', 'Hypertension'])
        elif 'mammogram' in screening_lower or 'breast' in screening_lower:
            relevant_conditions.extend(['Family History of Cancer', 'BRCA Mutation', 'Postmenopausal'])
        elif 'colonoscopy' in screening_lower or 'colon' in screening_lower:
            relevant_conditions.extend(['Family History of Cancer'])
        elif 'chest' in screening_lower or 'lung' in screening_lower:
            relevant_conditions.extend(['Smoking History'])
        elif 'dexa' in screening_lower or 'bone' in screening_lower:
            relevant_conditions.extend(['Osteoporosis Risk', 'Postmenopausal'])
        elif 'cardiac' in screening_lower or 'heart' in screening_lower:
            relevant_conditions.extend(['Hypertension', 'Diabetes Mellitus'])
        
        return list(set(relevant_conditions))
    
    def suggest_screening_variants(self, screening_name: str, conditions: List[str]) -> List[Dict]:
        """Suggest screening variants based on trigger conditions"""
        variants = []
        
        for condition in conditions:
            if condition in self.condition_categories:
                condition_data = self.condition_categories[condition]
                screening_impact = condition_data.get('screening_impact', {})
                
                if screening_name in screening_impact:
                    impact = screening_impact[screening_name]
                    variant = {
                        'condition': condition,
                        'frequency_months': impact.get('frequency_months'),
                        'age_start': impact.get('age_start'),
                        'fhir_codes': condition_data.get('fhir_codes', [])
                    }
                    variants.append(variant)
        
        return variants

# Global instance
medical_conditions_db = MedicalConditionsDB()