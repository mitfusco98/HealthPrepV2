"""
Global Screening Presets Seeder

Ensures system-level screening presets exist on startup, similar to root admin seeding.
These presets are owned by the System Organization (org_id=0) and the root admin user.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Hardcoded global preset definitions
# These are seeded on app startup if they don't exist
# 8 specialty presets that persist across AWS migrations
GLOBAL_PRESETS = [
    {
        "name": "Primary Care Preventive Screening Package",
        "description": "Comprehensive primary care preventive screenings with both population-based and condition-specific variants",
        "specialty": "Primary Care",
        "screening_data": {
            "name": "Primary Care Preventive Screening Package",
            "description": "Comprehensive primary care preventive screenings with both population-based and condition-specific variants",
            "specialty": "Primary Care",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Blood Pressure Monitoring", "description": "Standard blood pressure screening for hypertension detection", "keywords": ["blood pressure", "bp check", "hypertension screening", "systolic", "diastolic"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Lipid Panel", "description": "Standard cholesterol and lipid screening", "keywords": ["lipid panel", "cholesterol", "lipids", "ldl", "hdl", "triglycerides"], "min_age": 20, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "A1C Test", "description": "Diabetes screening for general population", "keywords": ["a1c", "hba1c", "diabetes screening", "glucose", "hemoglobin a1c"], "min_age": 35, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Immunization Review", "description": "Routine immunization status review and updates", "keywords": ["immunizations", "vaccines", "vaccination status", "immune status"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Blood Pressure Monitoring - Hypertensive", "description": "Frequent monitoring for diagnosed hypertensive patients", "keywords": ["blood pressure", "bp check", "hypertension monitoring"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.25, "trigger_conditions": ["hypertension", "high blood pressure"], "is_active": True},
                {"name": "A1C Test - Diabetic", "description": "Frequent A1C monitoring for diabetic patients", "keywords": ["a1c", "hba1c", "diabetes monitoring", "glucose control"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.25, "trigger_conditions": ["diabetes mellitus type 1", "diabetes mellitus type 2", "prediabetes"], "is_active": True},
                {"name": "Lipid Panel - High Risk", "description": "Frequent lipid monitoring for cardiovascular risk patients", "keywords": ["lipid panel", "cholesterol", "lipids", "cardiovascular risk"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["diabetes", "coronary artery disease", "familial hypercholesterolemia"], "is_active": True}
            ]
        }
    },
    {
        "name": "Cardiology Preventive Screening Package",
        "description": "Comprehensive cardiovascular screening protocols for primary and secondary prevention with risk-stratified variants",
        "specialty": "Cardiology",
        "screening_data": {
            "name": "Cardiology Preventive Screening Package",
            "description": "Comprehensive cardiovascular screening protocols for primary and secondary prevention with risk-stratified variants",
            "specialty": "Cardiology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Lipid Panel", "description": "Standard cholesterol and lipid screening for cardiovascular risk assessment", "keywords": ["lipid panel", "cholesterol", "lipids", "lipid profile", "LDL", "HDL", "triglycerides"], "min_age": 20, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Lipid Panel - High Risk", "description": "Frequent lipid monitoring for high cardiovascular risk patients", "keywords": ["lipid panel", "cholesterol", "lipids", "lipid profile", "LDL", "HDL", "triglycerides"], "min_age": 20, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["diabetes", "coronary artery disease", "hypertension", "familial hypercholesterolemia"], "is_active": True},
                {"name": "Blood Pressure Monitoring", "description": "Standard blood pressure screening for hypertension detection", "keywords": ["blood pressure", "bp check", "hypertension screening", "systolic", "diastolic"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Blood Pressure Monitoring - Hypertensive", "description": "Frequent blood pressure monitoring for diagnosed hypertensive patients", "keywords": ["blood pressure", "bp check", "hypertension monitoring", "systolic", "diastolic"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.25, "trigger_conditions": ["hypertension", "stage 1 hypertension", "stage 2 hypertension"], "is_active": True},
                {"name": "Electrocardiogram (ECG)", "description": "Baseline ECG for cardiovascular assessment", "keywords": ["ecg", "ekg", "electrocardiogram", "cardiac rhythm", "heart rhythm"], "min_age": 40, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Electrocardiogram (ECG) - High Risk", "description": "Frequent ECG monitoring for high-risk cardiovascular patients", "keywords": ["ecg", "ekg", "electrocardiogram", "cardiac rhythm", "heart rhythm"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["coronary artery disease", "heart failure", "arrhythmia", "cardiomyopathy"], "is_active": True},
                {"name": "Echocardiogram", "description": "Cardiac ultrasound for structural heart assessment", "keywords": ["echocardiogram", "echo", "cardiac ultrasound", "heart ultrasound", "ejection fraction"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Echocardiogram - Heart Failure", "description": "Regular echocardiogram monitoring for heart failure patients", "keywords": ["echocardiogram", "echo", "cardiac ultrasound", "heart ultrasound", "ejection fraction"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["heart failure", "cardiomyopathy", "valvular disease"], "is_active": True},
                {"name": "Stress Test", "description": "Exercise or pharmacological stress testing for coronary assessment", "keywords": ["stress test", "exercise stress test", "treadmill test", "nuclear stress", "cardiac stress"], "min_age": 40, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["chest pain", "coronary artery disease risk"], "is_active": True},
                {"name": "Coronary Artery Calcium Score", "description": "CT calcium scoring for coronary atherosclerosis assessment", "keywords": ["calcium score", "coronary calcium", "cac score", "cardiac ct", "coronary ct"], "min_age": 40, "max_age": 75, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["intermediate cardiovascular risk"], "is_active": True},
                {"name": "Carotid Ultrasound", "description": "Carotid artery ultrasound for stroke risk assessment", "keywords": ["carotid ultrasound", "carotid doppler", "carotid artery", "stroke screening"], "min_age": 65, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["stroke risk", "carotid stenosis", "transient ischemic attack"], "is_active": True},
                {"name": "BNP/NT-proBNP", "description": "Brain natriuretic peptide testing for heart failure assessment", "keywords": ["bnp", "nt-probnp", "brain natriuretic peptide", "heart failure marker"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["heart failure", "shortness of breath", "edema"], "is_active": True}
            ]
        }
    },
    {
        "name": "Women's Health Comprehensive Screening Package",
        "description": "Evidence-based women's health screening protocols including 2024 updated mammography guidelines and risk-stratified approaches",
        "specialty": "Women's Health / OBGYN",
        "screening_data": {
            "name": "Women's Health Comprehensive Screening Package",
            "description": "Evidence-based women's health screening protocols including 2024 updated mammography guidelines and risk-stratified approaches",
            "specialty": "Women's Health / OBGYN",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Mammogram", "description": "Breast cancer screening mammography - 2024 USPSTF updated guidelines", "keywords": ["mammogram", "mammography", "breast imaging", "breast screening", "breast cancer screening"], "min_age": 40, "max_age": 74, "eligible_genders": "female", "frequency_years": 2.0, "trigger_conditions": [], "is_active": True},
                {"name": "Mammogram - High Risk", "description": "Annual mammography for high-risk breast cancer patients", "keywords": ["mammogram", "mammography", "breast imaging", "breast screening", "breast cancer screening"], "min_age": 25, "max_age": None, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": ["BRCA1", "BRCA2", "family history breast cancer", "genetic predisposition"], "is_active": True},
                {"name": "Breast MRI", "description": "High-risk breast cancer screening with MRI", "keywords": ["breast mri", "breast magnetic resonance", "high risk breast screening"], "min_age": 25, "max_age": None, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": ["BRCA1", "BRCA2", "genetic predisposition", "strong family history"], "is_active": True},
                {"name": "Cervical Cancer Screening - Pap Test", "description": "Pap smear for cervical cancer screening (ages 21-29)", "keywords": ["pap smear", "pap test", "cervical screening", "cytology", "cervical cancer screening"], "min_age": 21, "max_age": 29, "eligible_genders": "female", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Cervical Cancer Screening - HPV Primary", "description": "Primary HPV testing for cervical cancer screening (ages 30-65)", "keywords": ["hpv test", "hpv screening", "cervical screening", "human papillomavirus", "cervical cancer screening"], "min_age": 30, "max_age": 65, "eligible_genders": "female", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Cervical Cancer Screening - Co-testing", "description": "Combined Pap and HPV testing for cervical cancer screening", "keywords": ["pap smear", "hpv test", "co-testing", "cervical screening", "cytology"], "min_age": 30, "max_age": 65, "eligible_genders": "female", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Bone Density Scan (DEXA)", "description": "Osteoporosis screening for all women 65 and older", "keywords": ["dexa", "dxa", "bone density", "bone scan", "osteoporosis screening", "bone mineral density"], "min_age": 65, "max_age": None, "eligible_genders": "female", "frequency_years": 2.0, "trigger_conditions": [], "is_active": True},
                {"name": "Bone Density Scan (DEXA) - High Risk", "description": "Earlier osteoporosis screening for high-risk postmenopausal women", "keywords": ["dexa", "dxa", "bone density", "bone scan", "osteoporosis screening"], "min_age": 50, "max_age": 64, "eligible_genders": "female", "frequency_years": 2.0, "trigger_conditions": ["postmenopausal", "family history osteoporosis", "low BMI", "smoking", "steroid use"], "is_active": True},
                {"name": "Pelvic Exam", "description": "Annual pelvic examination for reproductive health assessment", "keywords": ["pelvic exam", "gynecologic exam", "pelvic examination", "reproductive health"], "min_age": 21, "max_age": None, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Ovarian Cancer Screening", "description": "CA-125 and transvaginal ultrasound for high-risk ovarian cancer screening", "keywords": ["ca-125", "ovarian cancer screening", "transvaginal ultrasound", "ovarian ultrasound"], "min_age": 35, "max_age": None, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": ["BRCA1", "BRCA2", "family history ovarian cancer", "Lynch syndrome"], "is_active": True},
                {"name": "Contraceptive Counseling", "description": "Annual contraceptive and reproductive planning counseling", "keywords": ["contraceptive counseling", "family planning", "birth control", "reproductive counseling"], "min_age": 15, "max_age": 50, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Preconception Counseling", "description": "Comprehensive preconception health assessment and counseling", "keywords": ["preconception counseling", "pregnancy planning", "folic acid", "preconception care"], "min_age": 18, "max_age": 45, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": ["planning pregnancy"], "is_active": True}
            ]
        }
    },
    {
        "name": "Oncology Prevention & Screening Package",
        "description": "Comprehensive cancer prevention and early detection protocols with both general population and high-risk variants",
        "specialty": "Oncology",
        "screening_data": {
            "name": "Oncology Prevention & Screening Package",
            "description": "Comprehensive cancer prevention and early detection protocols with both general population and high-risk variants",
            "specialty": "Oncology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Colorectal Cancer Screening", "description": "Standard colorectal cancer screening for average-risk population", "keywords": ["colorectal screening", "colonoscopy", "colon cancer", "fit test", "cologuard"], "min_age": 45, "max_age": 75, "eligible_genders": "both", "frequency_years": 10.0, "trigger_conditions": [], "is_active": True},
                {"name": "Mammogram", "description": "Standard breast cancer screening for average-risk women", "keywords": ["mammogram", "breast cancer screening", "breast imaging", "mammography"], "min_age": 40, "max_age": 74, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Cervical Cancer Screening", "description": "Standard cervical cancer screening with Pap smear and HPV testing", "keywords": ["pap smear", "cervical screening", "hpv test", "cervical cancer"], "min_age": 21, "max_age": 65, "eligible_genders": "female", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Lung Cancer Screening", "description": "Low-dose CT screening for lung cancer in high-risk individuals", "keywords": ["lung cancer screening", "ldct", "low dose ct", "lung screening"], "min_age": 50, "max_age": 80, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["smoking history", "20 pack year history"], "is_active": True},
                {"name": "Colorectal Cancer Screening - High Risk", "description": "Enhanced colorectal cancer screening for high-risk patients", "keywords": ["colorectal screening", "colonoscopy", "colon cancer", "fit test"], "min_age": 40, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["family history colorectal cancer", "inflammatory bowel disease", "lynch syndrome"], "is_active": True},
                {"name": "Mammogram - High Risk", "description": "Enhanced breast cancer screening for high-risk women including MRI", "keywords": ["mammogram", "breast mri", "breast cancer screening", "high risk"], "min_age": 25, "max_age": None, "eligible_genders": "female", "frequency_years": 0.5, "trigger_conditions": ["BRCA mutation", "family history breast cancer", "personal history breast cancer"], "is_active": True},
                {"name": "Cervical Cancer Screening - High Risk", "description": "More frequent cervical cancer screening for high-risk patients", "keywords": ["pap smear", "cervical screening", "hpv test", "cervical cancer"], "min_age": 18, "max_age": None, "eligible_genders": "female", "frequency_years": 1.0, "trigger_conditions": ["HIV", "immunocompromised", "DES exposure", "previous abnormal pap"], "is_active": True},
                {"name": "Prostate Cancer Screening", "description": "PSA testing for prostate cancer screening in appropriate candidates", "keywords": ["psa", "prostate screening", "prostate cancer", "digital rectal exam"], "min_age": 50, "max_age": 70, "eligible_genders": "male", "frequency_years": 2.0, "trigger_conditions": ["family history prostate cancer", "african american"], "is_active": True},
                {"name": "Skin Cancer Screening", "description": "Full-body skin examination for melanoma and skin cancer detection", "keywords": ["skin cancer screening", "dermatology exam", "melanoma screening", "skin check"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["family history melanoma", "multiple moles", "fair skin", "sun exposure history"], "is_active": True},
                {"name": "Genetic Counseling - Cancer", "description": "Genetic counseling and testing for hereditary cancer syndromes", "keywords": ["genetic counseling", "genetic testing", "BRCA", "lynch syndrome", "hereditary cancer"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["family history cancer", "young onset cancer", "multiple primary cancers"], "is_active": True}
            ]
        }
    },
    {
        "name": "Endocrinology Metabolic Screening Package",
        "description": "Comprehensive endocrine and metabolic screening protocols including 2024 diabetes guidelines and thyroid function assessment",
        "specialty": "Endocrinology",
        "screening_data": {
            "name": "Endocrinology Metabolic Screening Package",
            "description": "Comprehensive endocrine and metabolic screening protocols including 2024 diabetes guidelines and thyroid function assessment",
            "specialty": "Endocrinology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Diabetes Screening - A1C", "description": "Hemoglobin A1C screening for diabetes in adults 45+ or high-risk individuals", "keywords": ["a1c", "hemoglobin a1c", "hba1c", "glycohemoglobin", "diabetes screening"], "min_age": 45, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Diabetes Screening - High Risk", "description": "A1C screening for high-risk individuals regardless of age", "keywords": ["a1c", "hemoglobin a1c", "hba1c", "glycohemoglobin", "diabetes screening"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["overweight", "obesity", "family history diabetes", "gestational diabetes history", "PCOS"], "is_active": True},
                {"name": "Diabetes Monitoring - A1C", "description": "Regular A1C monitoring for established diabetic patients", "keywords": ["a1c", "hemoglobin a1c", "hba1c", "diabetes monitoring", "glycemic control"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.25, "trigger_conditions": ["diabetes", "type 1 diabetes", "type 2 diabetes"], "is_active": True},
                {"name": "Fasting Glucose", "description": "Fasting plasma glucose for diabetes screening and monitoring", "keywords": ["fasting glucose", "fpg", "fasting blood sugar", "glucose screening"], "min_age": 45, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Oral Glucose Tolerance Test", "description": "75g OGTT for diabetes diagnosis in unclear cases", "keywords": ["ogtt", "oral glucose tolerance", "glucose tolerance test", "75g glucose"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["prediabetes", "borderline glucose", "gestational diabetes history"], "is_active": True},
                {"name": "Thyroid Function - TSH", "description": "Thyroid stimulating hormone screening for thyroid dysfunction", "keywords": ["tsh", "thyroid stimulating hormone", "thyroid function", "thyroid screening"], "min_age": 35, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Thyroid Function - Complete Panel", "description": "Complete thyroid function testing (TSH, Free T4, Free T3)", "keywords": ["tsh", "free t4", "free t3", "thyroid function", "thyroid panel"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["thyroid disease", "hypothyroidism", "hyperthyroidism", "thyroid symptoms"], "is_active": True},
                {"name": "Thyroid Antibodies", "description": "Thyroid peroxidase and thyroglobulin antibodies for autoimmune thyroid disease", "keywords": ["thyroid antibodies", "tpo antibodies", "anti-thyroglobulin", "thyroid autoimmune"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["family history thyroid disease", "autoimmune disease", "goiter"], "is_active": True},
                {"name": "Vitamin D", "description": "25-hydroxyvitamin D screening for deficiency assessment", "keywords": ["vitamin d", "25-hydroxyvitamin d", "vitamin d3", "calcidiol"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["osteoporosis", "limited sun exposure", "malabsorption"], "is_active": True},
                {"name": "Lipid Panel - Metabolic", "description": "Lipid screening for metabolic syndrome and cardiovascular risk", "keywords": ["lipid panel", "cholesterol", "triglycerides", "HDL", "LDL", "metabolic panel"], "min_age": 20, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Comprehensive Metabolic Panel", "description": "Complete metabolic panel including glucose, electrolytes, kidney function", "keywords": ["cmp", "comprehensive metabolic panel", "basic metabolic panel", "chemistry panel"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["diabetes", "hypertension", "kidney disease", "electrolyte disorders"], "is_active": True},
                {"name": "Microalbumin", "description": "Urine microalbumin for diabetic nephropathy screening", "keywords": ["microalbumin", "microalbuminuria", "urine albumin", "diabetic nephropathy"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["diabetes", "type 1 diabetes", "type 2 diabetes"], "is_active": True},
                {"name": "Testosterone", "description": "Testosterone screening for hypogonadism in symptomatic men", "keywords": ["testosterone", "total testosterone", "free testosterone", "hypogonadism"], "min_age": 30, "max_age": None, "eligible_genders": "male", "frequency_years": 3.0, "trigger_conditions": ["low libido", "fatigue", "erectile dysfunction", "osteoporosis"], "is_active": True},
                {"name": "PCOS Screening", "description": "Hormonal assessment for polycystic ovary syndrome", "keywords": ["pcos", "polycystic ovary", "testosterone", "androgen", "insulin resistance"], "min_age": 15, "max_age": 40, "eligible_genders": "female", "frequency_years": 2.0, "trigger_conditions": ["irregular periods", "hirsutism", "acne", "weight gain"], "is_active": True}
            ]
        }
    },
    {
        "name": "Pulmonology Respiratory Screening Package",
        "description": "Comprehensive pulmonary and respiratory screening protocols including expanded 2024 lung cancer screening guidelines",
        "specialty": "Pulmonology",
        "screening_data": {
            "name": "Pulmonology Respiratory Screening Package",
            "description": "Comprehensive pulmonary and respiratory screening protocols including expanded 2024 lung cancer screening guidelines",
            "specialty": "Pulmonology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Chest X-ray", "description": "Standard chest radiography for general population pulmonary assessment", "keywords": ["chest x-ray", "chest xray", "cxr", "chest radiograph", "lung x-ray"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Pulmonary Function Test", "description": "Basic spirometry screening for general population lung function assessment", "keywords": ["pulmonary function", "spirometry", "pfts", "lung function test", "fev1"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "Blood Pressure Monitoring", "description": "Standard blood pressure screening for pulmonary patients", "keywords": ["blood pressure", "bp check", "hypertension screening", "systolic", "diastolic"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Chest X-ray - High Risk", "description": "Frequent chest radiography for high-risk patients with pulmonary concerns", "keywords": ["chest x-ray", "chest xray", "cxr", "chest radiograph", "lung x-ray"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["chronic cough", "smoking history", "occupational exposure"], "is_active": True},
                {"name": "Lung Cancer Screening", "description": "Low-dose CT screening for lung cancer (2024 expanded guidelines)", "keywords": ["low dose ct", "ldct", "lung cancer screening", "chest ct", "lung screening"], "min_age": 50, "max_age": 80, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["smoking history 20 pack years", "current smoker", "quit smoking within 15 years"], "is_active": True},
                {"name": "Pulmonary Function Test - COPD Monitoring", "description": "Frequent spirometry monitoring for COPD and chronic lung disease patients", "keywords": ["pulmonary function", "spirometry", "pfts", "copd monitoring", "fev1"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.5, "trigger_conditions": ["asthma", "COPD", "chronic cough", "dyspnea"], "is_active": True},
                {"name": "Pulmonary Function Test - Severe COPD", "description": "Intensive spirometry monitoring for severe COPD patients", "keywords": ["pulmonary function", "spirometry", "pfts", "severe copd", "fev1"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 0.25, "trigger_conditions": ["COPD", "chronic obstructive pulmonary disease", "emphysema", "chronic bronchitis"], "is_active": True},
                {"name": "Alpha-1 Antitrypsin", "description": "Alpha-1 antitrypsin deficiency screening for early-onset emphysema", "keywords": ["alpha-1 antitrypsin", "a1at", "alpha-1", "antitrypsin deficiency"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 10.0, "trigger_conditions": ["early emphysema", "family history alpha-1", "liver disease"], "is_active": True},
                {"name": "Tuberculosis Screening", "description": "TB screening with interferon-gamma release assay or tuberculin skin test", "keywords": ["tuberculosis screening", "tb screening", "igra", "quantiferon", "tuberculin skin test"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["high TB risk", "immunocompromised", "healthcare worker", "homeless"], "is_active": True},
                {"name": "Sleep Study Screening", "description": "Sleep apnea screening questionnaire and overnight sleep study", "keywords": ["sleep study", "sleep apnea screening", "polysomnography", "sleep disorder"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["snoring", "sleep apnea symptoms", "daytime sleepiness", "obesity"], "is_active": True},
                {"name": "Occupational Lung Disease Screening", "description": "Screening for occupational lung diseases in high-risk workers", "keywords": ["occupational lung", "pneumoconiosis", "asbestos screening", "silicosis screening"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["asbestos exposure", "silica exposure", "coal mining", "construction work"], "is_active": True},
                {"name": "Asthma Control Assessment", "description": "Regular asthma control evaluation and spirometry", "keywords": ["asthma control", "asthma assessment", "peak flow", "asthma monitoring"], "min_age": 5, "max_age": None, "eligible_genders": "both", "frequency_years": 0.5, "trigger_conditions": ["asthma", "allergic asthma", "exercise-induced asthma"], "is_active": True},
                {"name": "High-Resolution CT Chest", "description": "HRCT for interstitial lung disease and pulmonary fibrosis evaluation", "keywords": ["hrct chest", "high resolution ct", "interstitial lung disease", "pulmonary fibrosis"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["interstitial lung disease", "pulmonary fibrosis", "sarcoidosis", "connective tissue disease"], "is_active": True},
                {"name": "Bronchoscopy Screening", "description": "Flexible bronchoscopy for suspected lung cancer or endobronchial disease", "keywords": ["bronchoscopy", "flexible bronchoscopy", "endobronchial", "lung biopsy"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["suspicious lung nodule", "persistent cough", "hemoptysis"], "is_active": True}
            ]
        }
    },
    {
        "name": "Gastroenterology Digestive Health Screening Package",
        "description": "Comprehensive gastrointestinal screening protocols including colorectal cancer screening and liver disease assessment",
        "specialty": "Gastroenterology",
        "screening_data": {
            "name": "Gastroenterology Digestive Health Screening Package",
            "description": "Comprehensive gastrointestinal screening protocols including colorectal cancer screening and liver disease assessment",
            "specialty": "Gastroenterology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Colonoscopy - Average Risk", "description": "Standard colonoscopy screening for colorectal cancer (average risk)", "keywords": ["colonoscopy", "colon screening", "colorectal screening", "colo screening", "bowel screening"], "min_age": 45, "max_age": 75, "eligible_genders": "both", "frequency_years": 10.0, "trigger_conditions": [], "is_active": True},
                {"name": "Colonoscopy - High Risk", "description": "Enhanced colonoscopy screening for high-risk colorectal cancer patients", "keywords": ["colonoscopy", "colon screening", "colorectal screening", "high risk screening"], "min_age": 40, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["family history colorectal cancer", "Lynch syndrome", "FAP", "inflammatory bowel disease"], "is_active": True},
                {"name": "Flexible Sigmoidoscopy", "description": "Flexible sigmoidoscopy for colorectal cancer screening", "keywords": ["sigmoidoscopy", "flexible sigmoidoscopy", "sigmoid screening", "lower GI"], "min_age": 45, "max_age": 75, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "FIT Test", "description": "Fecal immunochemical test for colorectal cancer screening", "keywords": ["fit test", "fecal immunochemical", "stool test", "fecal occult blood", "fobt"], "min_age": 45, "max_age": 75, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Upper Endoscopy - Surveillance", "description": "EGD surveillance for Barrett's esophagus and gastric pathology", "keywords": ["upper endoscopy", "egd", "esophagogastroduodenoscopy", "gastroscopy"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["Barrett's esophagus", "gastric polyps", "gastric metaplasia"], "is_active": True},
                {"name": "Upper Endoscopy - GERD", "description": "EGD for chronic GERD evaluation and surveillance", "keywords": ["upper endoscopy", "egd", "gerd evaluation", "esophagitis", "reflux"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["chronic GERD", "refractory GERD", "alarm symptoms"], "is_active": True},
                {"name": "Hepatitis B Screening", "description": "Hepatitis B surface antigen and antibody screening", "keywords": ["hepatitis b", "hbsag", "hepatitis b screening", "hbv screening"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["high-risk populations", "injection drug use", "multiple partners"], "is_active": True},
                {"name": "Hepatitis C Screening", "description": "Hepatitis C antibody screening for all adults", "keywords": ["hepatitis c", "hcv", "hepatitis c screening", "hcv antibody"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 10.0, "trigger_conditions": [], "is_active": True},
                {"name": "Liver Function Tests", "description": "Comprehensive liver function panel (ALT, AST, bilirubin, alkaline phosphatase)", "keywords": ["liver function", "lfts", "alt", "ast", "bilirubin", "alkaline phosphatase"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["alcohol use", "fatty liver", "hepatitis", "medication monitoring"], "is_active": True},
                {"name": "Hepatic Ultrasonography", "description": "Liver ultrasound for fatty liver disease and hepatic pathology screening", "keywords": ["liver ultrasound", "hepatic ultrasound", "fatty liver screening", "liver imaging"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["fatty liver disease", "elevated liver enzymes", "metabolic syndrome"], "is_active": True},
                {"name": "Celiac Disease Screening", "description": "Tissue transglutaminase antibody and total IgA for celiac disease", "keywords": ["celiac disease", "tissue transglutaminase", "tTG", "celiac antibodies", "gluten sensitivity"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["chronic diarrhea", "iron deficiency", "family history celiac"], "is_active": True},
                {"name": "H. Pylori Testing", "description": "Helicobacter pylori testing for peptic ulcer disease and gastritis", "keywords": ["h pylori", "helicobacter pylori", "urea breath test", "stool antigen"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["peptic ulcer disease", "gastritis", "family history gastric cancer"], "is_active": True},
                {"name": "Inflammatory Bowel Disease Monitoring", "description": "Regular monitoring for IBD patients with colonoscopy and laboratory studies", "keywords": ["ibd monitoring", "crohn disease", "ulcerative colitis", "inflammatory bowel"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["Crohn's disease", "ulcerative colitis", "inflammatory bowel disease"], "is_active": True},
                {"name": "Pancreatic Cancer Screening - High Risk", "description": "EUS and MRI/MRCP for high-risk pancreatic cancer screening", "keywords": ["pancreatic cancer screening", "eus", "mrcp", "pancreatic imaging"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["BRCA2", "PALB2", "family history pancreatic cancer", "hereditary pancreatitis"], "is_active": True}
            ]
        }
    },
    {
        "name": "Neurology Cognitive & Neurological Screening Package",
        "description": "Comprehensive neurological screening protocols including cognitive assessment, stroke prevention, and neurological monitoring",
        "specialty": "Neurology",
        "screening_data": {
            "name": "Neurology Cognitive & Neurological Screening Package",
            "description": "Comprehensive neurological screening protocols including cognitive assessment, stroke prevention, and neurological monitoring",
            "specialty": "Neurology",
            "created_at": "2025-01-14T00:00:00Z",
            "screening_types": [
                {"name": "Cognitive Assessment - MOCA", "description": "Montreal Cognitive Assessment for mild cognitive impairment screening", "keywords": ["cognitive assessment", "moca", "montreal cognitive", "cognitive screening", "memory test"], "min_age": 65, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Blood Pressure Monitoring", "description": "Standard blood pressure screening for neurological patients", "keywords": ["blood pressure", "bp check", "hypertension screening", "systolic", "diastolic"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": [], "is_active": True},
                {"name": "Basic Neurological Exam", "description": "Routine neurological assessment for general population", "keywords": ["neurological exam", "neuro assessment", "neurological screening", "nerve function"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": [], "is_active": True},
                {"name": "Stroke Risk Assessment", "description": "Basic stroke risk evaluation for general population", "keywords": ["stroke risk", "stroke prevention", "cerebrovascular", "stroke screening"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Lipid Panel", "description": "Standard cholesterol screening for cardiovascular risk in neurology patients", "keywords": ["lipid panel", "cholesterol", "lipids", "ldl", "hdl", "triglycerides"], "min_age": 20, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": [], "is_active": True},
                {"name": "A1C Test", "description": "Diabetes screening for general neurology population (stroke risk factor)", "keywords": ["a1c", "hba1c", "diabetes screening", "glucose", "hemoglobin a1c"], "min_age": 35, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": [], "is_active": True},
                {"name": "Depression Screening", "description": "Standard depression screening for neurological patients", "keywords": ["depression screening", "phq9", "mental health", "mood assessment"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": [], "is_active": True},
                {"name": "Cognitive Assessment - Early Screening", "description": "Early cognitive screening for high-risk individuals", "keywords": ["cognitive assessment", "memory screening", "cognitive evaluation", "dementia screening"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["family history dementia", "mild cognitive impairment", "memory complaints"], "is_active": True},
                {"name": "Stroke Risk Assessment - High Risk", "description": "Comprehensive stroke risk evaluation for high-risk patients including carotid assessment", "keywords": ["stroke risk", "carotid ultrasound", "stroke prevention", "cerebrovascular"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["hypertension", "diabetes", "atrial fibrillation", "smoking"], "is_active": True},
                {"name": "Carotid Ultrasound", "description": "Carotid artery ultrasound for stroke risk assessment", "keywords": ["carotid ultrasound", "carotid doppler", "carotid stenosis", "stroke screening"], "min_age": 65, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["stroke risk factors", "TIA", "carotid bruit"], "is_active": True},
                {"name": "Brain MRI - Cognitive", "description": "Brain MRI for cognitive impairment and dementia evaluation", "keywords": ["brain mri", "mri brain", "cognitive mri", "dementia imaging"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["cognitive decline", "memory loss", "dementia evaluation"], "is_active": True},
                {"name": "EEG Screening", "description": "Electroencephalogram for seizure disorder screening", "keywords": ["eeg", "electroencephalogram", "seizure screening", "epilepsy screening"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["seizure history", "unexplained episodes", "epilepsy"], "is_active": True},
                {"name": "Neuropsychological Testing", "description": "Comprehensive neuropsychological evaluation for cognitive disorders", "keywords": ["neuropsychological testing", "cognitive testing", "neuropsychology", "cognitive evaluation"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 3.0, "trigger_conditions": ["cognitive decline", "head injury", "learning disabilities"], "is_active": True},
                {"name": "Parkinson's Disease Screening", "description": "Movement disorder assessment and Parkinson's disease screening", "keywords": ["parkinson screening", "movement disorder", "tremor assessment", "bradykinesia"], "min_age": 60, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["tremor", "bradykinesia", "family history Parkinson's"], "is_active": True},
                {"name": "Multiple Sclerosis Monitoring", "description": "Regular MRI and clinical monitoring for MS patients", "keywords": ["multiple sclerosis", "ms monitoring", "brain mri", "ms surveillance"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["multiple sclerosis", "demyelinating disease", "optic neuritis"], "is_active": True},
                {"name": "Migraine Assessment", "description": "Comprehensive migraine evaluation and headache disorder screening", "keywords": ["migraine assessment", "headache evaluation", "migraine screening", "headache disorder"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["chronic headaches", "migraine", "headache disorder"], "is_active": True},
                {"name": "Neuropathy Screening", "description": "Peripheral neuropathy assessment and nerve conduction studies", "keywords": ["neuropathy screening", "nerve conduction", "peripheral neuropathy", "diabetic neuropathy"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 1.0, "trigger_conditions": ["diabetes", "peripheral neuropathy", "numbness", "tingling"], "is_active": True},
                {"name": "Sleep Disorder Assessment", "description": "Neurological sleep disorder evaluation including sleep study referral", "keywords": ["sleep disorder", "sleep study", "sleep neurology", "sleep assessment"], "min_age": 18, "max_age": None, "eligible_genders": "both", "frequency_years": 2.0, "trigger_conditions": ["sleep apnea", "insomnia", "narcolepsy", "restless leg syndrome"], "is_active": True},
                {"name": "Alzheimer's Biomarkers", "description": "CSF or blood biomarker testing for Alzheimer's disease", "keywords": ["alzheimer biomarkers", "csf biomarkers", "amyloid", "tau protein"], "min_age": 50, "max_age": None, "eligible_genders": "both", "frequency_years": 5.0, "trigger_conditions": ["cognitive decline", "family history Alzheimer's", "mild cognitive impairment"], "is_active": True}
            ]
        }
    }
]


def ensure_global_presets(db, ScreeningPreset, User):
    """
    Ensure global screening presets exist and are properly owned on startup.
    
    This function:
    1. Finds or creates the root admin user as the preset owner
    2. Seeds any missing global presets from GLOBAL_PRESETS constant
    3. Ensures ALL existing global presets are owned by the system (org_id=0, created_by=root_admin)
    
    Called during app initialization after _ensure_system_organization.
    
    Global presets with org_id=0 and preset_scope='global' are protected from deletion
    and will persist across AWS migrations.
    """
    try:
        # Find root admin user to own the presets
        root_admin = User.query.filter_by(is_root_admin=True).first()
        
        if not root_admin:
            logger.warning("No root admin found - skipping global preset seeding")
            return
        
        changes_made = False
        
        # Step 1: Ensure ALL existing global presets have correct ownership
        # This covers presets that weren't in GLOBAL_PRESETS but are marked as global
        existing_globals = ScreeningPreset.query.filter_by(preset_scope='global').all()
        
        for preset in existing_globals:
            needs_update = False
            
            # Ensure org_id=0 for system ownership
            if preset.org_id != 0:
                logger.info(f"Updating global preset '{preset.name}' (ID: {preset.id}) org_id from {preset.org_id} to 0")
                preset.org_id = 0
                needs_update = True
            
            # Ensure created_by points to root admin
            if preset.created_by != root_admin.id:
                logger.info(f"Updating global preset '{preset.name}' (ID: {preset.id}) created_by from {preset.created_by} to {root_admin.id}")
                preset.created_by = root_admin.id
                needs_update = True
            
            # Ensure shared flag is set
            if not preset.shared:
                preset.shared = True
                needs_update = True
            
            if needs_update:
                preset.updated_at = datetime.utcnow()
                changes_made = True
        
        # Step 2: Seed any missing presets from GLOBAL_PRESETS constant
        for preset_def in GLOBAL_PRESETS:
            existing = ScreeningPreset.query.filter_by(
                name=preset_def["name"],
                preset_scope='global'
            ).first()
            
            if not existing:
                # Create new global preset
                new_preset = ScreeningPreset(
                    name=preset_def["name"],
                    description=preset_def.get("description", ""),
                    specialty=preset_def.get("specialty", "primary_care"),
                    org_id=0,  # System organization
                    shared=True,
                    preset_scope='global',
                    screening_data=preset_def["screening_data"],
                    created_by=root_admin.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_preset)
                changes_made = True
                logger.info(f"Created global preset: {preset_def['name']}")
        
        if changes_made:
            db.session.commit()
            logger.info("Global presets ownership verification completed")
        else:
            logger.info("Global presets verified - no changes needed")
            
    except Exception as e:
        logger.error(f"Error seeding global presets: {str(e)}")
        db.session.rollback()


def reassign_user_global_presets(db, ScreeningPreset, user_id, root_admin_id):
    """
    Reassign global presets from a user to the root admin before user deletion.
    
    This ensures global presets persist when their creator is deleted.
    
    Args:
        db: Database session
        ScreeningPreset: ScreeningPreset model class
        user_id: ID of the user being deleted
        root_admin_id: ID of the root admin to receive ownership
    
    Returns:
        int: Number of presets reassigned
    """
    try:
        # Find all global presets created by this user
        global_presets = ScreeningPreset.query.filter_by(
            created_by=user_id,
            preset_scope='global'
        ).all()
        
        count = 0
        for preset in global_presets:
            preset.created_by = root_admin_id
            preset.org_id = 0  # Ensure system org
            preset.updated_at = datetime.utcnow()
            count += 1
            logger.info(f"Reassigned global preset '{preset.name}' (ID: {preset.id}) from user {user_id} to root admin {root_admin_id}")
        
        if count > 0:
            db.session.flush()
            logger.info(f"Reassigned {count} global presets from user {user_id} to root admin")
        
        return count
        
    except Exception as e:
        logger.error(f"Error reassigning global presets: {str(e)}")
        return 0
