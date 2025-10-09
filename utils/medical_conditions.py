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
        """Load comprehensive medical conditions database with FHIR codes
        
        ENHANCED with 100+ variants including:
        - Clinical modifiers (mild, moderate, severe, chronic, acute)
        - Medical abbreviations (PCOS, COPD, MI, CAD, etc.)
        - Variant spellings and formats (Type 2 diabetes = diabetes mellitus type 2)
        - Condition-specific terminology
        """
        return {
            'diabetes': [
                # Standard forms
                'diabetes mellitus', 'diabetes', 'diabetic', 'DM',
                # Type 1 variants
                'type 1 diabetes', 'type I diabetes', 'diabetes mellitus type 1', 
                'diabetes mellitus type I', 'T1DM', 'insulin dependent diabetes', 'IDDM',
                # Type 2 variants  
                'type 2 diabetes', 'type II diabetes', 'diabetes mellitus type 2',
                'diabetes mellitus type II', 'T2DM', 'non insulin dependent diabetes', 'NIDDM',
                # Other forms
                'gestational diabetes', 'GDM', 'prediabetes', 'pre diabetes',
                'impaired glucose tolerance', 'IGT', 'impaired fasting glucose', 'IFG'
            ],
            'cardiovascular': [
                # Heart disease variants
                'heart disease', 'cardiac disease', 'cardiovascular disease', 'CVD',
                'ischemic heart disease', 'IHD', 'coronary heart disease', 'CHD',
                'coronary artery disease', 'CAD', 'atherosclerotic heart disease', 'ASHD',
                # Myocardial infarction
                'myocardial infarction', 'MI', 'heart attack', 'old myocardial infarction',
                'old MI', 'previous MI', 'history of MI', 'STEMI', 'NSTEMI',
                # Heart failure
                'heart failure', 'cardiac failure', 'CHF', 'congestive heart failure',
                'systolic heart failure', 'diastolic heart failure', 'HFrEF', 'HFpEF',
                # Hypertension
                'hypertension', 'high blood pressure', 'HTN', 'elevated blood pressure',
                'essential hypertension', 'primary hypertension', 'secondary hypertension',
                # Arrhythmias
                'atrial fibrillation', 'AFib', 'AF', 'a fib', 'atrial flutter',
                # Lipids
                'hyperlipidemia', 'dyslipidemia', 'high cholesterol', 'hypercholesterolemia',
                # Other cardiovascular
                'peripheral vascular disease', 'PVD', 'PAD', 'peripheral artery disease',
                'stroke', 'CVA', 'cerebrovascular accident', 'TIA', 'transient ischemic attack'
            ],
            'oncology': [
                'cancer', 'malignancy', 'tumor', 'neoplasm', 'carcinoma', 'CA',
                'breast cancer', 'breast CA', 'prostate cancer', 'prostate CA',
                'colorectal cancer', 'colon cancer', 'rectal cancer', 'CRC',
                'lung cancer', 'lung CA', 'NSCLC', 'SCLC', 'skin cancer', 
                'melanoma', 'basal cell carcinoma', 'BCC', 'squamous cell carcinoma', 'SCC',
                'lymphoma', 'Hodgkin lymphoma', 'non-Hodgkin lymphoma', 'NHL',
                'leukemia', 'AML', 'CML', 'ALL', 'CLL',
                'family history of cancer', 'FH cancer', 'BRCA mutation', 'BRCA positive',
                'BRCA1', 'BRCA2', 'genetic predisposition to cancer'
            ],
            'pulmonary': [
                # Asthma variants - CRITICAL for Linda's condition
                'asthma', 'asthmatic', 'bronchial asthma',
                'persistent asthma', 'intermittent asthma', 
                'mild persistent asthma', 'moderate persistent asthma', 'severe persistent asthma',
                'mild intermittent asthma', 'exercise induced asthma', 'EIA',
                'allergic asthma', 'non-allergic asthma', 'asthma exacerbation',
                'acute asthma', 'chronic asthma', 'asthma with exacerbation',
                # COPD variants
                'COPD', 'chronic obstructive pulmonary disease', 'chronic obstructive lung disease',
                'mild COPD', 'moderate COPD', 'severe COPD', 'very severe COPD',
                'COPD exacerbation', 'acute exacerbation of COPD', 'AECOPD',
                # Emphysema & bronchitis
                'emphysema', 'chronic emphysema', 'pulmonary emphysema',
                'chronic bronchitis', 'bronchitis', 'acute bronchitis', 
                'acute bronchitis unspecified', 'recurrent bronchitis',
                # Pneumonia variants - CRITICAL for Elijah's condition
                'pneumonia', 'lobar pneumonia', 'bacterial pneumonia', 'viral pneumonia',
                'aspiration pneumonia', 'community acquired pneumonia', 'CAP',
                'hospital acquired pneumonia', 'HAP', 'ventilator associated pneumonia', 'VAP',
                'pneumonia unspecified organism', 'unspecified pneumonia',
                # Other pulmonary
                'smoking history', 'tobacco use', 'tobacco use disorder', 
                'current smoker', 'former smoker', 'nicotine dependence',
                'pulmonary fibrosis', 'interstitial lung disease', 'ILD',
                'sleep apnea', 'obstructive sleep apnea', 'OSA', 'respiratory disease', 'lung disease'
            ],
            'gastrointestinal': [
                'IBD', 'inflammatory bowel disease', 'Crohns disease', 'Crohn disease',
                'ulcerative colitis', 'UC', 'IBS', 'irritable bowel syndrome',
                'GERD', 'gastroesophageal reflux disease', 'acid reflux', 'reflux disease',
                'peptic ulcer', 'gastric ulcer', 'duodenal ulcer', 'PUD',
                'hepatitis', 'hepatitis B', 'hepatitis C', 'hep B', 'hep C', 'HBV', 'HCV',
                'cirrhosis', 'liver cirrhosis', 'hepatic cirrhosis', 
                'liver disease', 'fatty liver', 'NAFLD', 'non-alcoholic fatty liver disease',
                'celiac disease', 'celiac sprue', 'gluten sensitivity'
            ],
            'endocrine': [
                'thyroid disease', 'thyroid disorder', 'hypothyroidism', 'hyperthyroidism',
                'Hashimoto thyroiditis', 'Graves disease', 'thyroid nodule', 'goiter',
                'adrenal insufficiency', 'Addisons disease', 'Cushings syndrome', 'Cushing syndrome',
                'osteoporosis', 'osteopenia', 'low bone density', 'bone loss',
                'metabolic syndrome', 'syndrome X', 'obesity', 'morbid obesity', 
                'BMI > 30', 'overweight', 'BMI > 25'
            ],
            'renal': [
                'chronic kidney disease', 'CKD', 'chronic renal disease', 'CRD',
                'renal insufficiency', 'kidney disease', 'renal disease',
                'nephropathy', 'diabetic nephropathy', 'hypertensive nephropathy',
                'dialysis', 'hemodialysis', 'peritoneal dialysis', 'ESRD', 'end stage renal disease',
                'kidney transplant', 'renal transplant', 'proteinuria', 'hematuria',
                'acute kidney injury', 'AKI', 'acute renal failure', 'ARF'
            ],
            'autoimmune': [
                'rheumatoid arthritis', 'RA', 'inflammatory arthritis',
                'systemic lupus erythematosus', 'SLE', 'lupus',
                'multiple sclerosis', 'MS', 'psoriatic arthritis', 'PsA',
                'ankylosing spondylitis', 'AS', 'Sjögrens syndrome', 'Sjogren syndrome',
                'scleroderma', 'systemic sclerosis', 'polymyalgia rheumatica', 'PMR'
            ],
            'mental_health': [
                'depression', 'major depressive disorder', 'MDD', 'major depression',
                'depressive disorder', 'clinical depression', 'unipolar depression',
                'anxiety disorder', 'anxiety', 'generalized anxiety disorder', 'GAD',
                'panic disorder', 'social anxiety', 'bipolar disorder', 'bipolar I', 'bipolar II',
                'PTSD', 'post traumatic stress disorder', 'posttraumatic stress disorder',
                'substance use disorder', 'SUD', 'drug abuse', 'substance abuse',
                'alcohol use disorder', 'AUD', 'alcoholism', 'alcohol dependence'
            ],
            'reproductive': [
                # PCOS variants - CRITICAL for Camila's condition
                'PCOS', 'polycystic ovary syndrome', 'polycystic ovarian syndrome',
                'polycystic ovaries', 'PCO', 'Stein-Leventhal syndrome',
                # Other reproductive
                'pregnancy', 'pregnant', 'gravida', 'gestational',
                'postmenopausal', 'post menopausal', 'menopause', 'climacteric',
                'perimenopause', 'peri menopausal', 'menopausal',
                'endometriosis', 'infertility', 'female infertility', 'male infertility',
                'contraceptive use', 'birth control', 'hormone replacement therapy',
                'HRT', 'estrogen therapy', 'testosterone therapy'
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
    
    def get_fhir_codes_for_condition(self, condition_name: str) -> Dict[str, List[str]]:
        """Get FHIR-compatible codes (ICD-10, SNOMED CT) for a condition"""
        condition_mapping = {
            'diabetes': {
                'icd10': ['E11.9', 'E10.9', 'E08.9', 'E09.9', 'E13.9'],
                'snomed': ['44054006', '46635009', '73211009'],
                'epic_search_terms': ['Diabetes mellitus', 'Type 2 diabetes', 'Type 1 diabetes']
            },
            'hypertension': {
                'icd10': ['I10', 'I11.9', 'I12.9', 'I13.10', 'I15.9'],
                'snomed': ['38341003', '59621000'],
                'epic_search_terms': ['Essential hypertension', 'High blood pressure', 'HTN']
            },
            'cardiovascular': {
                'icd10': ['I25.9', 'I50.9', 'I48.91', 'Z87.891'],
                'snomed': ['53741008', '84114007', '49436004'],
                'epic_search_terms': ['Coronary artery disease', 'Heart failure', 'Atrial fibrillation']
            },
            'hyperlipidemia': {
                'icd10': ['E78.5', 'E78.0', 'E78.1', 'E78.2'],
                'snomed': ['55822004', '267434000'],
                'epic_search_terms': ['Hyperlipidemia', 'High cholesterol', 'Dyslipidemia']
            },
            'obesity': {
                'icd10': ['E66.9', 'E66.01', 'E66.02', 'Z68.3'],
                'snomed': ['414915002', '408512008'],
                'epic_search_terms': ['Obesity', 'Morbid obesity', 'BMI > 30']
            },
            'smoking': {
                'icd10': ['Z87.891', 'F17.210', 'F17.220'],
                'snomed': ['8517006', '365980008'],
                'epic_search_terms': ['History of tobacco use', 'Tobacco use disorder', 'Smoking']
            },
            'family_history_cancer': {
                'icd10': ['Z80.9', 'Z80.0', 'Z80.1', 'Z80.2', 'Z80.3'],
                'snomed': ['275937001', '266892002'],
                'epic_search_terms': ['Family history of malignant neoplasm', 'Family history of cancer']
            }
        }
        
        # Find matching condition
        condition_lower = condition_name.lower()
        for category, conditions in self.conditions.items():
            if any(cond.lower() in condition_lower for cond in conditions):
                return condition_mapping.get(category, {})
        
        return {}
    
    def get_epic_search_terms(self, condition_name: str) -> List[str]:
        """Get Epic-specific search terms for a condition"""
        codes = self.get_fhir_codes_for_condition(condition_name)
        return codes.get('epic_search_terms', [])
    
    def normalize_condition_name(self, condition_name: str) -> str:
        """Normalize a condition name by removing clinical modifiers and standardizing format
        
        Removes:
        - Severity modifiers (mild, moderate, severe, very severe)
        - Temporal modifiers (acute, chronic, persistent, intermittent, recurrent)
        - Status modifiers (uncomplicated, unspecified, with exacerbation)
        - Qualifiers (primary, secondary, essential, old, previous)
        
        Also standardizes spelling variants:
        - "ovarian" → "ovary" (polycystic ovarian syndrome = polycystic ovary syndrome)
        - "ischemic" ↔ "ischaemic"
        
        Examples:
        - "Moderate persistent asthma, uncomplicated" → "asthma"
        - "Old myocardial infarction" → "myocardial infarction"
        - "Acute bronchitis, unspecified" → "bronchitis"
        - "Lobar pneumonia, unspecified organism" → "lobar pneumonia"
        - "Polycystic ovarian syndrome" → "polycystic ovary syndrome"
        """
        if not condition_name:
            return ""
        
        # Normalize to lowercase for processing
        normalized = condition_name.lower().strip()
        
        # Standardize common medical spelling variants (before modifier removal)
        spelling_variants = {
            r'\bovarian\b': 'ovary',
            r'\bischaemic\b': 'ischemic',
            r'\boesophageal\b': 'esophageal',
            r'\bhaemorrhage\b': 'hemorrhage',
            r'\banaemia\b': 'anemia',
        }
        
        for variant_pattern, standard_form in spelling_variants.items():
            normalized = re.sub(variant_pattern, standard_form, normalized)
        
        # List of clinical modifiers to remove (order matters - more specific first)
        modifiers_to_remove = [
            # Compound modifiers (must be before individual words)
            r'\bmild persistent\b',
            r'\bmoderate persistent\b', 
            r'\bsevere persistent\b',
            r'\bmild intermittent\b',
            r'\bvery severe\b',
            r'\bacute exacerbation of\b',
            r'\bwith exacerbation\b',
            r'\bwithout exacerbation\b',
            r'\bunspecified organism\b',
            r'\bunspecified arm\b',
            r'\bunspecified side\b',
            r'\binitial encounter for\b',
            r'\bclosed fracture\b',
            r'\bopen fracture\b',
            # Single-word severity modifiers
            r'\bmild\b',
            r'\bmoderate\b',
            r'\bsevere\b',
            # Temporal modifiers
            r'\bacute\b',
            r'\bchronic\b',
            r'\bpersistent\b',
            r'\bintermittent\b',
            r'\brecurrent\b',
            r'\bepisodic\b',
            # Status modifiers
            r'\buncomplicated\b',
            r'\bcomplicated\b',
            r'\bunspecified\b',
            r'\buncontrolled\b',
            r'\bcontrolled\b',
            r'\bunstable\b',
            r'\bstable\b',
            # Qualifiers
            r'\bprimary\b',
            r'\bsecondary\b',
            r'\bessential\b',
            r'\bnon-essential\b',
            r'\bold\b',
            r'\bprevious\b',
            r'\bhistory of\b',
            r'\bwith\b',
            r'\bwithout\b',
        ]
        
        # Remove each modifier pattern
        for modifier_pattern in modifiers_to_remove:
            normalized = re.sub(modifier_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove common suffixes that don't add medical meaning
        suffixes_to_remove = [
            r',\s*unspecified.*$',
            r',\s*nos\b.*$',  # "not otherwise specified"
            r'\s+disorder\s*$' if 'use disorder' not in normalized else r'(?!use)\s+disorder\s*$',
        ]
        
        for suffix_pattern in suffixes_to_remove:
            normalized = re.sub(suffix_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and commas
        normalized = re.sub(r'\s*,\s*,\s*', ', ', normalized)  # Remove double commas
        normalized = re.sub(r'\s*,\s*$', '', normalized)  # Remove trailing comma
        normalized = re.sub(r'^\s*,\s*', '', normalized)  # Remove leading comma
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def extract_severity_level(self, condition_name: str) -> str:
        """Extract severity level from condition name
        
        Returns: 'mild', 'moderate', 'severe', 'very_severe', or None
        
        Examples:
        - "Moderate persistent asthma" → "moderate"
        - "Severe COPD" → "severe"
        - "Asthma" → None
        """
        if not condition_name:
            return None
        
        condition_lower = condition_name.lower()
        
        # Check for severity indicators (order matters - most specific first)
        if re.search(r'\bvery severe\b', condition_lower):
            return 'very_severe'
        elif re.search(r'\bsevere\b', condition_lower):
            return 'severe'
        elif re.search(r'\bmoderate\b', condition_lower):
            return 'moderate'
        elif re.search(r'\bmild\b', condition_lower):
            return 'mild'
        
        return None
    
    def fuzzy_match_condition(self, patient_condition: str, trigger_condition: str) -> bool:
        """Enhanced fuzzy matching for medical conditions using word boundaries
        
        Matches if:
        1. Normalized forms match exactly
        2. Trigger condition exists as complete words in patient condition (word boundary)
        3. Both match database variants (abbreviations, synonyms) EXCLUDING false pairs
        
        Examples of MATCHES:
        - "Moderate persistent asthma, uncomplicated" matches "asthma" ✓
        - "Diabetes mellitus type 2" matches "type 2 diabetes" ✓
        - "Polycystic ovarian syndrome" matches "PCOS" ✓
        - "Old myocardial infarction" matches "MI" ✓
        
        Examples of NON-MATCHES:
        - "diabetes" does NOT match "prediabetes" ✗ (different conditions)
        - "type 2 diabetes" does NOT match "type 1 diabetes" ✗ (different types)
        """
        if not patient_condition or not trigger_condition:
            return False
        
        # Normalize both conditions
        normalized_patient = self.normalize_condition_name(patient_condition)
        normalized_trigger = self.normalize_condition_name(trigger_condition)
        
        # CRITICAL: Check false positive pairs FIRST before any matching
        false_positive_pairs = {
            ('diabetes', 'prediabetes'),
            ('prediabetes', 'diabetes'),
            ('diabetes mellitus', 'prediabetes'),
            ('prediabetes', 'diabetes mellitus'),
            ('type 1 diabetes', 'type 2 diabetes'),
            ('type 2 diabetes', 'type 1 diabetes'),
            ('diabetes mellitus type 1', 'diabetes mellitus type 2'),
            ('diabetes mellitus type 2', 'diabetes mellitus type 1'),
            ('t1dm', 't2dm'),
            ('t2dm', 't1dm'),
        }
        
        pair = (normalized_patient, normalized_trigger)
        if pair in false_positive_pairs:
            return False
        
        # 1. Check exact match of normalized forms
        if normalized_patient == normalized_trigger:
            return True
        
        # 2. Handle word order variations (e.g., "diabetes mellitus type 2" = "type 2 diabetes mellitus")
        patient_words = set(normalized_patient.split())
        trigger_words = set(normalized_trigger.split())
        
        # If they have the exact same words (just different order), they match
        if patient_words == trigger_words and len(patient_words) > 1:
            return True
        
        # 3. Check if normalized trigger exists with word boundaries in patient condition
        trigger_pattern = r'\b' + re.escape(normalized_trigger) + r'\b'
        if re.search(trigger_pattern, normalized_patient, re.IGNORECASE):
            return True
        
        # 4. Check if patient normalized condition exists in trigger (reverse check)
        patient_pattern = r'\b' + re.escape(normalized_patient) + r'\b'
        if re.search(patient_pattern, normalized_trigger, re.IGNORECASE):
            return True
        
        # 4. Check database variants with false positive prevention
        patient_variants = self._get_matching_variants(normalized_patient)
        trigger_variants = self._get_matching_variants(normalized_trigger)
        
        if patient_variants and trigger_variants:
            # Check if they share at least one common variant
            if patient_variants & trigger_variants:
                return True
            
            # SPECIAL CASE: Check for known false positive pairs to exclude
            # Even if in same category, these should NOT match
            false_positive_pairs = {
                ('diabetes', 'prediabetes'),
                ('prediabetes', 'diabetes'),
                ('diabetes mellitus', 'prediabetes'),
                ('prediabetes', 'diabetes mellitus'),
                ('type 1 diabetes', 'type 2 diabetes'),
                ('type 2 diabetes', 'type 1 diabetes'),
                ('diabetes mellitus type 1', 'diabetes mellitus type 2'),
                ('diabetes mellitus type 2', 'diabetes mellitus type 1'),
                ('t1dm', 't2dm'),
                ('t2dm', 't1dm'),
            }
            
            pair = (normalized_patient, normalized_trigger)
            if pair in false_positive_pairs:
                return False
            
            # Check if both are in same category (for abbreviation matching)
            patient_category = self._find_condition_category(normalized_patient) 
            trigger_category = self._find_condition_category(normalized_trigger)
            
            if patient_category and trigger_category and patient_category == trigger_category:
                # Same category - check if one is likely an abbreviation of the other
                # This handles cases like MI <-> myocardial infarction, PCOS <-> polycystic ovarian syndrome
                if self._is_likely_abbreviation(normalized_patient, normalized_trigger):
                    return True
        
        return False
    
    def _is_likely_abbreviation(self, cond1: str, cond2: str) -> bool:
        """Check if one condition is likely an abbreviation of the other
        
        Examples:
        - MI is abbreviation of myocardial infarction ✓
        - PCOS is abbreviation of polycystic ovarian syndrome ✓  
        - T2DM is abbreviation of type 2 diabetes mellitus ✓
        - diabetes is NOT abbreviation of prediabetes ✗
        """
        # Known special abbreviation mappings (for complex cases)
        special_abbreviations = {
            'pcos': ['polycystic ovary syndrome', 'polycystic ovarian syndrome'],
            't1dm': ['type 1 diabetes mellitus', 'type 1 diabetes', 'diabetes mellitus type 1'],
            't2dm': ['type 2 diabetes mellitus', 'type 2 diabetes', 'diabetes mellitus type 2'],
            'mi': ['myocardial infarction'],
            'cad': ['coronary artery disease'],
            'chf': ['congestive heart failure'],
            'copd': ['chronic obstructive pulmonary disease'],
            'ckd': ['chronic kidney disease'],
        }
        
        cond1_lower = cond1.lower()
        cond2_lower = cond2.lower()
        
        # Check special abbreviations
        if cond1_lower in special_abbreviations:
            if cond2_lower in special_abbreviations[cond1_lower]:
                return True
        if cond2_lower in special_abbreviations:
            if cond1_lower in special_abbreviations[cond2_lower]:
                return True
        
        # Standard abbreviation detection - one must be significantly shorter
        if len(cond1) < 6 and len(cond2) > len(cond1) * 2:
            # cond1 might be abbreviation of cond2
            words2 = cond2.split()
            if len(words2) >= 2:  # Need at least 2 words for abbreviation
                # Build initials from all words
                initials_all = ''.join([w[0] for w in words2 if w])
                # Also try meaningful words only (skip common words)
                skip_words = {'of', 'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at'}
                initials_meaningful = ''.join([w[0] for w in words2 if w and w.lower() not in skip_words])
                
                if cond1.upper() == initials_all.upper()[:len(cond1)]:
                    return True
                if cond1.upper() == initials_meaningful.upper()[:len(cond1)]:
                    return True
        
        if len(cond2) < 6 and len(cond1) > len(cond2) * 2:
            # cond2 might be abbreviation of cond1
            words1 = cond1.split()
            if len(words1) >= 2:
                # Build initials
                initials_all = ''.join([w[0] for w in words1 if w])
                skip_words = {'of', 'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at'}
                initials_meaningful = ''.join([w[0] for w in words1 if w and w.lower() not in skip_words])
                
                if cond2.upper() == initials_all.upper()[:len(cond2)]:
                    return True
                if cond2.upper() == initials_meaningful.upper()[:len(cond2)]:
                    return True
        
        return False
    
    def _get_matching_variants(self, condition_name: str) -> Set[str]:
        """Get all database variants that match the given condition
        
        Returns a set of matching variant strings from the conditions database.
        Used to determine if two conditions are synonyms.
        
        Examples:
        - "PCOS" returns {"PCOS", "polycystic ovary syndrome", "polycystic ovarian syndrome", ...}
        - "MI" returns {"MI", "myocardial infarction", "heart attack", ...}
        - "diabetes" returns all diabetes-related variants
        """
        if not condition_name:
            return set()
        
        condition_lower = condition_name.lower().strip()
        matching_variants = set()
        
        # Check each category's condition list
        for category, condition_list in self.conditions.items():
            for known_condition in condition_list:
                known_lower = known_condition.lower()
                
                # Exact match
                if condition_lower == known_lower:
                    # Return ALL variants from this category that are synonyms
                    # Determine which specific group this belongs to
                    matching_variants.add(known_lower)
                    continue
                
                # Word boundary match
                pattern = r'\b' + re.escape(known_lower) + r'\b'
                if re.search(pattern, condition_lower):
                    matching_variants.add(known_lower)
                    continue
                
                # Reverse check
                reverse_pattern = r'\b' + re.escape(condition_lower) + r'\b'
                if re.search(reverse_pattern, known_lower):
                    matching_variants.add(known_lower)
        
        return matching_variants
    
    def _find_condition_category(self, condition_name: str) -> str:
        """Find which category a condition belongs to
        
        Returns the category key (e.g., 'diabetes', 'cardiovascular', 'pulmonary')
        """
        if not condition_name:
            return None
        
        condition_lower = condition_name.lower().strip()
        
        # Check each category's condition list
        for category, condition_list in self.conditions.items():
            for known_condition in condition_list:
                # Check if condition matches any known variant
                known_lower = known_condition.lower()
                
                # Exact match
                if condition_lower == known_lower:
                    return category
                
                # Word boundary match
                pattern = r'\b' + re.escape(known_lower) + r'\b'
                if re.search(pattern, condition_lower):
                    return category
                
                # Reverse check
                reverse_pattern = r'\b' + re.escape(condition_lower) + r'\b'
                if re.search(reverse_pattern, known_lower):
                    return category
        
        return None

# Global instance
medical_conditions_db = MedicalConditionsDB()