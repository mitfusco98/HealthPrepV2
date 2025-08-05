"""
Medical Terminology Database
Provides keyword suggestions and terminology import for screening types
"""
import json
import re
from typing import List, Dict, Set

class MedicalTerminologyDB:
    """Medical terminology database for keyword suggestions and imports"""
    
    def __init__(self):
        self.terminology = self._load_medical_terminology()
        self.screening_categories = self._load_screening_categories()
    
    def _load_medical_terminology(self) -> Dict[str, List[str]]:
        """Load comprehensive medical terminology database"""
        return {
            'mammography': [
                'mammogram', 'mammography', 'breast imaging', 'breast cancer screening',
                'bilateral mammogram', 'unilateral mammogram', 'diagnostic mammogram',
                'screening mammogram', 'digital mammography', 'tomosynthesis',
                'breast compression', 'mammographic density', 'BI-RADS'
            ],
            'cervical_screening': [
                'pap smear', 'pap test', 'cervical cytology', 'cervical cancer screening',
                'HPV test', 'liquid-based cytology', 'conventional pap',
                'cervical biopsy', 'colposcopy', 'ASCUS', 'LSIL', 'HSIL'
            ],
            'diabetes_monitoring': [
                'A1C', 'hemoglobin A1C', 'HbA1c', 'glycated hemoglobin',
                'glucose tolerance test', 'fasting glucose', 'random glucose',
                'diabetic screening', 'prediabetes', 'diabetes mellitus',
                'glucose monitoring', 'glycemic control'
            ],
            'cardiovascular': [
                'ECG', 'EKG', 'electrocardiogram', 'stress test', 'echocardiogram',
                'cardiac catheterization', 'angiogram', 'lipid panel',
                'cholesterol screening', 'blood pressure monitoring',
                'hypertension screening', 'cardiac risk assessment'
            ],
            'colonoscopy': [
                'colonoscopy', 'colorectal screening', 'sigmoidoscopy',
                'fecal occult blood test', 'FOBT', 'FIT test',
                'cologuard', 'stool DNA test', 'polyp screening',
                'colon cancer screening', 'bowel preparation'
            ],
            'bone_health': [
                'DEXA scan', 'bone density', 'osteoporosis screening',
                'dual-energy X-ray absorptiometry', 'T-score', 'Z-score',
                'fracture risk assessment', 'bone mineral density',
                'osteopenia', 'FRAX score'
            ],
            'pulmonary': [
                'chest X-ray', 'chest CT', 'pulmonary function test',
                'spirometry', 'lung cancer screening', 'low-dose CT',
                'tuberculosis screening', 'PPD test', 'interferon gamma',
                'bronchoscopy', 'sputum cytology'
            ],
            'laboratory': [
                'complete blood count', 'CBC', 'comprehensive metabolic panel',
                'CMP', 'lipid panel', 'thyroid function', 'TSH',
                'liver function tests', 'kidney function', 'creatinine',
                'BUN', 'electrolytes', 'urinalysis'
            ],
            'dermatology': [
                'skin cancer screening', 'melanoma screening', 'mole check',
                'dermatoscopy', 'full body skin exam', 'biopsy',
                'basal cell carcinoma', 'squamous cell carcinoma',
                'suspicious lesion', 'skin examination'
            ],
            'ophthalmology': [
                'eye exam', 'visual acuity', 'glaucoma screening',
                'diabetic retinopathy screening', 'macular degeneration',
                'intraocular pressure', 'fundoscopy', 'retinal examination',
                'visual field test', 'optical coherence tomography'
            ]
        }
    
    def _load_screening_categories(self) -> Dict[str, Dict]:
        """Load screening type categories with metadata"""
        return {
            'Mammogram': {
                'category': 'mammography',
                'gender': 'F',
                'age_range': [40, 74],
                'frequency_years': 1.0,
                'conditions': ['family history of breast cancer', 'BRCA mutation']
            },
            'Pap Smear': {
                'category': 'cervical_screening',
                'gender': 'F',
                'age_range': [21, 65],
                'frequency_years': 3.0,
                'conditions': ['HPV positive', 'abnormal cervical cytology']
            },
            'A1C Test': {
                'category': 'diabetes_monitoring',
                'gender': 'both',
                'age_range': [18, 999],
                'frequency_years': 0.25,
                'conditions': ['diabetes', 'prediabetes', 'metabolic syndrome']
            },
            'Colonoscopy': {
                'category': 'colonoscopy',
                'gender': 'both',
                'age_range': [45, 75],
                'frequency_years': 10.0,
                'conditions': ['family history of colorectal cancer', 'IBD']
            },
            'DEXA Scan': {
                'category': 'bone_health',
                'gender': 'F',
                'age_range': [65, 999],
                'frequency_years': 2.0,
                'conditions': ['osteoporosis risk', 'postmenopausal']
            },
            'Chest X-ray': {
                'category': 'pulmonary',
                'gender': 'both',
                'age_range': [18, 999],
                'frequency_years': 1.0,
                'conditions': ['smoking history', 'respiratory symptoms']
            },
            'Lipid Panel': {
                'category': 'cardiovascular',
                'gender': 'both',
                'age_range': [20, 999],
                'frequency_years': 5.0,
                'conditions': ['hyperlipidemia', 'cardiovascular risk factors']
            },
            'Thyroid Function (TSH)': {
                'category': 'laboratory',
                'gender': 'both',
                'age_range': [35, 999],
                'frequency_years': 5.0,
                'conditions': ['thyroid disease', 'hypothyroidism symptoms']
            },
            'Skin Cancer Screening': {
                'category': 'dermatology',
                'gender': 'both',
                'age_range': [18, 999],
                'frequency_years': 1.0,
                'conditions': ['family history of melanoma', 'high sun exposure']
            },
            'Eye Exam': {
                'category': 'ophthalmology',
                'gender': 'both',
                'age_range': [18, 999],
                'frequency_years': 2.0,
                'conditions': ['diabetes', 'glaucoma risk factors']
            }
        }
    
    def get_keywords_for_screening(self, screening_name: str) -> List[str]:
        """Get medical keywords for a specific screening type"""
        # Direct match
        if screening_name in self.screening_categories:
            category = self.screening_categories[screening_name]['category']
            return self.terminology.get(category, [])
        
        # Fuzzy match
        screening_lower = screening_name.lower()
        for category, keywords in self.terminology.items():
            if any(keyword.lower() in screening_lower for keyword in keywords):
                return keywords
        
        # Search by partial name match
        for name, data in self.screening_categories.items():
            if screening_lower in name.lower() or name.lower() in screening_lower:
                category = data['category']
                return self.terminology.get(category, [])
        
        return []
    
    def search_keywords(self, query: str, limit: int = 10) -> List[str]:
        """Search for keywords matching the query"""
        query_lower = query.lower()
        matches = set()
        
        for category, keywords in self.terminology.items():
            for keyword in keywords:
                if query_lower in keyword.lower():
                    matches.add(keyword)
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        
        return list(matches)[:limit]
    
    def get_category_keywords(self, category: str) -> List[str]:
        """Get all keywords for a specific medical category"""
        return self.terminology.get(category, [])
    
    def get_all_categories(self) -> List[str]:
        """Get list of all medical categories"""
        return list(self.terminology.keys())
    
    def suggest_screening_config(self, screening_name: str) -> Dict:
        """Suggest configuration for a screening type based on medical standards"""
        if screening_name in self.screening_categories:
            config = self.screening_categories[screening_name].copy()
            config['keywords'] = self.get_keywords_for_screening(screening_name)
            return config
        
        # Try to find partial matches
        screening_lower = screening_name.lower()
        for name, config in self.screening_categories.items():
            if screening_lower in name.lower() or name.lower() in screening_lower:
                result = config.copy()
                result['keywords'] = self.get_keywords_for_screening(name)
                return result
        
        return {}
    
    def import_standard_keywords(self, screening_name: str) -> List[str]:
        """Import standard medical keywords for a screening type"""
        keywords = self.get_keywords_for_screening(screening_name)
        
        # Add common variations
        additional_keywords = []
        for keyword in keywords:
            # Add plural forms
            if not keyword.endswith('s') and not keyword.endswith('y'):
                additional_keywords.append(keyword + 's')
            
            # Add acronym forms
            words = keyword.split()
            if len(words) > 1:
                acronym = ''.join(word[0].upper() for word in words if word[0].isalpha())
                if len(acronym) > 1:
                    additional_keywords.append(acronym)
        
        return list(set(keywords + additional_keywords))

# Global instance
medical_terminology_db = MedicalTerminologyDB()