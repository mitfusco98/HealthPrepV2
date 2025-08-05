"""
Standardized Screening Names Database
Provides autocomplete suggestions for screening type names to prevent user input errors
"""

from typing import List, Dict, Set
import re

class StandardizedScreeningNames:
    """Database of standardized screening names with fuzzy matching"""
    
    def __init__(self):
        self.screening_names = self._load_standardized_names()
        self.aliases = self._load_common_aliases()
    
    def _load_standardized_names(self) -> List[str]:
        """Load comprehensive list of standardized screening names"""
        return [
            # Cancer Screenings
            'Mammogram',
            'Pap Smear',
            'Colonoscopy',
            'Sigmoidoscopy',
            'Chest CT (Low-Dose)',
            'Skin Cancer Screening',
            'Prostate Cancer Screening',
            'Cervical Cancer Screening',
            'Colorectal Cancer Screening',
            'Lung Cancer Screening',
            'Breast Cancer Screening',
            
            # Cardiovascular Screenings
            'Electrocardiogram (ECG)',
            'Echocardiogram',
            'Stress Test',
            'Cardiac Catheterization',
            'Lipid Panel',
            'Cholesterol Screening',
            'Blood Pressure Monitoring',
            'Carotid Ultrasound',
            'Ankle-Brachial Index',
            
            # Diabetes & Metabolic
            'A1C Test',
            'Hemoglobin A1C',
            'Glucose Tolerance Test',
            'Fasting Glucose',
            'Random Glucose',
            'Diabetic Eye Exam',
            'Diabetic Foot Exam',
            
            # Bone Health
            'DEXA Scan',
            'Bone Density Test',
            'Osteoporosis Screening',
            
            # Vision & Hearing
            'Comprehensive Eye Exam',
            'Glaucoma Screening',
            'Diabetic Retinopathy Screening',
            'Macular Degeneration Screening',
            'Hearing Test',
            'Audiometry',
            
            # Laboratory Tests
            'Complete Blood Count (CBC)',
            'Comprehensive Metabolic Panel',
            'Thyroid Function Test',
            'TSH Test',
            'Liver Function Tests',
            'Kidney Function Tests',
            'Urinalysis',
            'Vitamin D Test',
            'B12 Test',
            'Iron Studies',
            
            # Imaging Studies
            'Chest X-ray',
            'Abdominal Ultrasound',
            'Pelvic Ultrasound',
            'Thyroid Ultrasound',
            'CT Scan',
            'MRI',
            'Nuclear Stress Test',
            
            # Infectious Disease Screening
            'Tuberculosis Screening',
            'PPD Test',
            'Hepatitis B Screening',
            'Hepatitis C Screening',
            'HIV Screening',
            'STD Screening',
            'Chlamydia Screening',
            'Gonorrhea Screening',
            
            # Preventive Care
            'Annual Physical Exam',
            'Well-Woman Exam',
            'Well-Child Visit',
            'Immunization Review',
            'Fall Risk Assessment',
            'Depression Screening',
            'Cognitive Assessment',
            'Substance Abuse Screening',
            
            # Specialty Screenings
            'Pulmonary Function Test',
            'Spirometry',
            'Sleep Study',
            'Endoscopy',
            'Bronchoscopy',
            'Cystoscopy',
            'Arthroscopy',
            'Cardiac Stress Test',
            'Holter Monitor',
            'Event Monitor'
        ]
    
    def _load_common_aliases(self) -> Dict[str, str]:
        """Load common aliases and their standardized equivalents"""
        return {
            # Mammogram variants
            'mammography': 'Mammogram',
            'breast screening': 'Mammogram',
            'breast imaging': 'Mammogram',
            
            # Pap smear variants
            'pap test': 'Pap Smear',
            'cervical cytology': 'Pap Smear',
            'cervical screening': 'Cervical Cancer Screening',
            
            # A1C variants
            'hba1c': 'A1C Test',
            'hemoglobin a1c': 'Hemoglobin A1C',
            'glycated hemoglobin': 'A1C Test',
            
            # ECG variants
            'ekg': 'Electrocardiogram (ECG)',
            'electrocardiogram': 'Electrocardiogram (ECG)',
            
            # Colonoscopy variants
            'colon screening': 'Colonoscopy',
            'colorectal screening': 'Colorectal Cancer Screening',
            'bowel screening': 'Colonoscopy',
            
            # DEXA variants
            'bone scan': 'DEXA Scan',
            'bone density': 'Bone Density Test',
            'dxa scan': 'DEXA Scan',
            
            # Cholesterol variants
            'lipids': 'Lipid Panel',
            'cholesterol': 'Cholesterol Screening',
            'lipid profile': 'Lipid Panel',
            
            # Blood pressure variants
            'bp check': 'Blood Pressure Monitoring',
            'hypertension screening': 'Blood Pressure Monitoring',
            
            # Eye exam variants
            'eye exam': 'Comprehensive Eye Exam',
            'vision screening': 'Comprehensive Eye Exam',
            'retinal exam': 'Diabetic Retinopathy Screening',
            
            # Lab test variants
            'cbc': 'Complete Blood Count (CBC)',
            'cmp': 'Comprehensive Metabolic Panel',
            'tsh': 'TSH Test',
            'thyroid test': 'Thyroid Function Test',
            
            # Imaging variants
            'chest xray': 'Chest X-ray',
            'cxr': 'Chest X-ray',
            'ultrasound': 'Abdominal Ultrasound',
            
            # Cancer screening variants
            'prostate screening': 'Prostate Cancer Screening',
            'skin check': 'Skin Cancer Screening',
            'mole check': 'Skin Cancer Screening',
            'lung screening': 'Lung Cancer Screening'
        }
    
    def search_screening_names(self, query: str, limit: int = 10) -> List[str]:
        """Search for screening names with fuzzy matching"""
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.lower().strip()
        results = []
        
        # Exact matches first
        for name in self.screening_names:
            if query == name.lower():
                results.append(name)
        
        # Check aliases for exact matches
        for alias, standard_name in self.aliases.items():
            if query == alias.lower() and standard_name not in results:
                results.append(standard_name)
        
        # Starts with matches
        for name in self.screening_names:
            if name.lower().startswith(query) and name not in results:
                results.append(name)
        
        # Check aliases for starts with
        for alias, standard_name in self.aliases.items():
            if alias.lower().startswith(query) and standard_name not in results:
                results.append(standard_name)
        
        # Contains matches
        for name in self.screening_names:
            if query in name.lower() and name not in results:
                results.append(name)
        
        # Check aliases for contains
        for alias, standard_name in self.aliases.items():
            if query in alias.lower() and standard_name not in results:
                results.append(standard_name)
        
        # Fuzzy matching - check for partial word matches
        query_words = query.split()
        for name in self.screening_names:
            if name not in results:
                name_words = name.lower().split()
                if any(word.startswith(q_word) for q_word in query_words for word in name_words):
                    results.append(name)
        
        return results[:limit]
    
    def get_standardized_name(self, input_name: str) -> str:
        """Get the standardized name for a given input, or return original if no match"""
        if not input_name:
            return input_name
        
        # Check if it's already a standard name
        for standard_name in self.screening_names:
            if input_name.lower() == standard_name.lower():
                return standard_name
        
        # Check aliases
        for alias, standard_name in self.aliases.items():
            if input_name.lower() == alias.lower():
                return standard_name
        
        # No match found, return original
        return input_name
    
    def suggest_corrections(self, input_name: str, threshold: float = 0.8) -> List[str]:
        """Suggest corrections for potentially misspelled screening names"""
        if not input_name or len(input_name.strip()) < 3:
            return []
        
        suggestions = []
        input_lower = input_name.lower()
        
        # Simple Levenshtein-like distance check
        for name in self.screening_names:
            name_lower = name.lower()
            similarity = self._calculate_similarity(input_lower, name_lower)
            if similarity >= threshold:
                suggestions.append(name)
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate simple similarity between two strings"""
        if not str1 or not str2:
            return 0.0
        
        # Count common characters
        common_chars = sum(1 for c in str1 if c in str2)
        max_len = max(len(str1), len(str2))
        
        return common_chars / max_len if max_len > 0 else 0.0
    
    def get_all_names(self) -> List[str]:
        """Get all standardized screening names"""
        return sorted(self.screening_names)
    
    def get_category_suggestions(self, category: str) -> List[str]:
        """Get screening suggestions by category"""
        category_mappings = {
            'cancer': [name for name in self.screening_names if 'cancer' in name.lower() or 
                      any(cancer_term in name.lower() for cancer_term in ['mammogram', 'pap', 'colonoscopy', 'skin'])],
            'cardiovascular': [name for name in self.screening_names if 
                             any(cardio_term in name.lower() for cardio_term in ['cardiac', 'heart', 'ecg', 'echo', 'lipid', 'cholesterol', 'blood pressure'])],
            'diabetes': [name for name in self.screening_names if 
                        any(diabetes_term in name.lower() for diabetes_term in ['a1c', 'glucose', 'diabetic'])],
            'laboratory': [name for name in self.screening_names if 
                          any(lab_term in name.lower() for lab_term in ['test', 'panel', 'blood', 'urine', 'lab'])],
            'imaging': [name for name in self.screening_names if 
                       any(imaging_term in name.lower() for imaging_term in ['x-ray', 'ct', 'mri', 'ultrasound', 'scan'])]
        }
        
        return category_mappings.get(category.lower(), [])

# Global instance
standardized_screening_names = StandardizedScreeningNames()