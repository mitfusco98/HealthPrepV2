"""
HIPAA-Compliant Document Type Vocabulary

This module provides a controlled vocabulary for document type codes and display names.
It maps FHIR/LOINC document type codes to safe, standardized display names that
contain NO patient-specific information (PHI-free by design).

SECURITY DESIGN:
- Only structured codes and pre-approved vocabulary are used
- No free-text parsing that could leak patient names
- All display names are deterministic and non-PHI
"""

import logging

logger = logging.getLogger(__name__)


# LOINC Document Type Codes -> Safe Display Names
# Source: https://loinc.org/document-ontology/
LOINC_DOCUMENT_TYPES = {
    # Clinical Notes
    '11488-4': 'Consultation Note',
    '11506-3': 'Progress Note',
    '11502-2': 'Laboratory Report',
    '11503-0': 'Medical Records',
    '11504-8': 'Surgical Operation Note',
    '11505-5': 'Procedure Note',
    '11507-1': 'Occupational Therapy Note',
    '11508-9': 'Physical Therapy Note',
    '11509-7': 'Podiatry Note',
    '11510-5': 'Psychology Note',
    '18842-5': 'Discharge Summary',
    '18823-5': 'Alcohol/Drug Abuse Note',
    '18841-7': 'Hospital Consultations',
    '28570-0': 'Procedure Note',
    '28568-4': 'Physician Attending Progress Note',
    '28569-2': 'Physician Consulting Progress Note',
    '28579-1': 'Discharge Summary',
    '28582-5': 'Transfer Summary',
    '28583-3': 'Dentist Note',
    '28614-6': 'Physical Medicine Note',
    '28615-3': 'Audiology Note',
    '28616-1': 'Physician Note',
    '28617-9': 'Dental Note',
    '28618-7': 'Dentistry Note',
    '28619-5': 'Ophthalmology Note',
    '28623-7': 'Nurse Note',
    '28624-5': 'Podiatry Note',
    '28625-2': 'Psychiatry Note',
    '28626-0': 'Physician History',
    '28627-8': 'Psychiatry History',
    '28628-6': 'Psychiatry Progress Note',
    '28634-4': 'Miscellaneous Note',
    '28635-1': 'Psychiatry Treatment Plan',
    '28636-9': 'Initial Psychiatric Note',
    '29749-9': 'Dialysis Record',
    '29750-7': 'Dialysis Summary',
    '29751-5': 'Critical Care Records',
    '29752-3': 'Perioperative Record',
    '29753-1': 'Nurse Anesthesia Record',
    '29754-9': 'Neonatal Intensive Care Record',
    '29755-6': 'Labor and Delivery Record',
    '29756-4': 'Intraoperative Record',
    '29757-2': 'Anesthesia Intraoperative Record',
    '29761-4': 'Dentistry Discharge Summary',
    '34099-2': 'Cardiology Consult Note',
    '34100-8': 'Intensive Care Unit Note',
    '34104-0': 'Hospital Discharge Physical',
    '34105-7': 'Hospital Discharge Summary',
    '34106-5': 'Physician Hospital Discharge Summary',
    '34108-1': 'Outpatient Note',
    '34109-9': 'Evaluation and Management Note',
    '34111-5': 'Emergency Department Note',
    '34112-3': 'Hospital Admission Note',
    '34117-2': 'History and Physical Note',
    '34129-7': 'Preoperative Note',
    '34130-5': 'Postoperative Note',
    '34131-3': 'Outpatient Progress Note',
    '34133-9': 'Summarization of Episode Note',
    '34134-7': 'Physician Attending Note',
    '34135-4': 'Physician Cardiology Note',
    '34136-2': 'Physician Attending Admission Note',
    '34137-0': 'Physician Outpatient Progress Note',
    '34138-8': 'Physician Targeted History and Physical Note',
    '34139-6': 'Nurse Targeted History and Physical Note',
    '34744-3': 'Nurse Telephone Encounter Note',
    '34745-0': 'Nurse Discharge Summary',
    '34746-8': 'Nurse Progress Note',
    '34747-6': 'Preoperative Evaluation Note',
    '34748-4': 'Telephone Encounter Note',
    '34749-2': 'Anesthesiology Note',
    '34750-0': 'Anesthesiology Preoperative Note',
    '34751-8': 'Anesthesiology Note',
    '34752-6': 'Cardiology Note',
    '34753-4': 'Critical Care Medicine Note',
    '34754-2': 'Dentistry Note',
    '34755-9': 'Dermatology Note',
    '34756-7': 'Diabetology Note',
    '34757-5': 'Emergency Medicine Note',
    '34758-3': 'Endocrinology Note',
    '34759-1': 'Gastroenterology Note',
    '34760-9': 'General Medicine Note',
    '34761-7': 'General Surgery Note',
    '34762-5': 'Geriatric Medicine Note',
    '34763-3': 'Hematology/Oncology Note',
    '34764-1': 'Infectious Disease Note',
    '34765-8': 'Nephrology Note',
    '34766-6': 'Neurology Note',
    '34767-4': 'Neurosurgery Note',
    '34768-2': 'Nursing Note',
    '34769-0': 'Nutrition/Dietetics Note',
    '34770-8': 'Occupational Therapy Note',
    '34771-6': 'Oncology Note',
    '34772-4': 'Ophthalmology Note',
    '34773-2': 'Oral/Maxillofacial Surgery Note',
    '34774-0': 'Orthopedics Note',
    '34775-7': 'Otolaryngology Note',
    '34776-5': 'Pathology Note',
    '34777-3': 'Pediatrics Note',
    '34778-1': 'Physical Medicine Note',
    '34779-9': 'Plastic Surgery Note',
    '34780-7': 'Podiatry Note',
    '34781-5': 'Psychology Note',
    '34782-3': 'Psychiatry Note',
    '34783-1': 'Pulmonology Note',
    '34784-9': 'Radiation Oncology Note',
    '34785-6': 'Radiology Note',
    '34786-4': 'Recreational Therapy Note',
    '34787-2': 'Respiratory Therapy Note',
    '34788-0': 'Rheumatology Note',
    '34789-8': 'Social Work Note',
    '34790-6': 'Speech-Language Pathology Note',
    '34791-4': 'Surgery Note',
    '34792-2': 'Thoracic Surgery Note',
    '34793-0': 'Transplant Surgery Note',
    '34794-8': 'Urology Note',
    '34795-5': 'Vascular Surgery Note',
    '34796-3': 'Womens Health Note',
    '34797-1': 'Unknown Specialty Note',
    '34798-9': 'Evaluation and Management Note',
    '34799-7': 'Gynecology Note',
    '34800-3': 'Obstetrics Note',
    '34801-1': 'Audiology Note',
    '34802-9': 'Cardiovascular Surgery Note',
    '34803-7': 'Chiropractic Note',
    '34804-5': 'Colon/Rectal Surgery Note',
    '34805-2': 'Neonatology Note',
    '34806-0': 'Optometry Note',
    '34807-8': 'Palliative Care Note',
    '34808-6': 'Physical Therapy Note',
    '34809-4': 'Preventive Medicine Note',
    '34810-2': 'Sleep Medicine Note',
    '34811-0': 'Sports Medicine Note',
    '47039-3': 'Admission Note',
    '47042-7': 'Counseling Note',
    '47044-3': 'Study Report',
    '47045-0': 'Study Protocol',
    '47046-8': 'Summary Note',
    '47047-6': 'Team Conference Note',
    '51845-6': 'Outpatient Consultation Note',
    '51846-4': 'Emergency Department Note',
    '51847-2': 'Assessment and Plan Note',
    '51848-0': 'Assessment Note',
    '51849-8': 'Admission History Note',
    '51850-6': 'Physical Examination Note',
    '51851-4': 'Administrative Note',
    '51852-2': 'Letter',
    '51854-8': 'Patient Consent',
    '51855-5': 'Patient Note',
    '51856-3': 'Progress Report',
    '51897-7': 'Healthcare Communication',
    '52027-0': 'Pharmacist Medication Note',
    '57133-1': 'Referral Note',
    '57134-9': 'Dentistry Referral Note',
    '57135-6': 'Dermatology Referral Note',
    '57136-4': 'Gastroenterology Referral Note',
    '57137-2': 'General Medicine Referral Note',
    '57138-0': 'Neurology Referral Note',
    '57139-8': 'Ophthalmology Referral Note',
    '57140-6': 'Orthopedics Referral Note',
    '57141-4': 'Otolaryngology Referral Note',
    '57142-2': 'Plastic Surgery Referral Note',
    '57143-0': 'Podiatry Referral Note',
    '57144-8': 'Psychiatry Referral Note',
    '57145-5': 'Pulmonology Referral Note',
    '57146-3': 'Radiation Oncology Referral Note',
    '57147-1': 'Radiology Referral Note',
    '57148-9': 'Rheumatology Referral Note',
    '57149-7': 'Social Work Referral Note',
    '57150-5': 'Surgery Referral Note',
    '57151-3': 'Urology Referral Note',
    '57152-1': 'Cardiology Referral Note',
    '57153-9': 'Hematology/Oncology Referral Note',
    '57154-7': 'Infectious Disease Referral Note',
    '57155-4': 'Internal Medicine Referral Note',
    '57156-2': 'Nephrology Referral Note',
    '57157-0': 'Pediatrics Referral Note',
    '57170-3': 'Cardiovascular Surgery Referral Note',
    '57171-1': 'Neonatology Referral Note',
    '57172-9': 'Neurosurgery Referral Note',
    '57173-7': 'Palliative Care Referral Note',
    '57174-5': 'Physical Medicine Referral Note',
    '57175-2': 'Physical Therapy Referral Note',
    '57176-0': 'Respiratory Therapy Referral Note',
    '57177-8': 'Thoracic Surgery Referral Note',
    '60280-5': 'Emergency Medicine Transfer Note',
    '60591-5': 'Patient Summary',
    '60593-1': 'Medication Dispensed',
    '64289-3': 'Health Insurance Card',
    '64299-2': 'Legal Document',
    '68608-9': 'Summary Note',
    '68609-7': 'Education Note',
    '68613-9': 'Transition of Care Note',
    '68624-6': 'Hospitalization Summary',
    '68825-9': 'Obstetrics Referral Note',
    '68826-7': 'Gynecology Referral Note',
    '68827-5': 'Oncology Referral Note',
    '68828-3': 'Sleep Medicine Referral Note',
    '68829-1': 'Sports Medicine Referral Note',
    '68830-9': 'Optometry Referral Note',
    '68831-7': 'Pharmacy Referral Note',
    '68832-5': 'Audiology Referral Note',
    '68834-1': 'Preventive Medicine Referral Note',
    '68836-6': 'Geriatric Medicine Referral Note',
    '68837-4': 'Diabetology Referral Note',
    '68838-2': 'Endocrinology Referral Note',
    '68839-0': 'Genetics Referral Note',
    '68840-8': 'Nursing Referral Note',
    '68849-9': 'Anesthesiology Referral Note',
    '74156-1': 'Oncology Treatment Plan and Summary',
    '74207-2': 'Prehospital Summary Note',
    '74209-8': 'Injury Discharge Note',
    '74213-0': 'Discharge Instructions',
    '74264-3': 'HIV Summary Note',
    '78249-0': 'Care Team Information',
    '78448-8': 'Telehealth Note',
    '80396-8': 'Care Plan',
    '80565-8': 'Nutrition/Dietetics Consultation Note',
    '80737-3': 'Urgent Care Note',
    '80761-3': 'Palliative Care Consultation Note',
    '80771-2': 'Immunization Evaluation',
    '80785-2': 'Genetics Consultation Note',
    '80792-8': 'Cardiac Rehabilitation Note',
    '80817-3': 'Medication Therapy Management Note',
    '81228-2': 'Behavioral Health Note',
    '81229-0': 'Substance Abuse Referral Note',
    '83521-8': 'Case Manager Note',
    '83894-9': 'Pain Management Note',
    '83935-0': 'Primary Care Referral Note',
    '85205-5': 'Antepartum Summary',
    '85208-9': 'Labor and Delivery Summary',
    '85433-3': 'Patient History Note',
    '85440-8': 'Medication Administration Note',
    '87254-1': 'Telehealth Consultation Note',
    '88349-8': 'Immunization Record',
    '89429-7': 'Family History',
    '89459-4': 'Insurance Card',
    
    # Diagnostic Reports
    '11502-2': 'Laboratory Report',
    '18748-4': 'Diagnostic Imaging Study',
    '18782-3': 'Radiology Study',
    '18842-5': 'Discharge Summary',
    '24604-1': 'Breast Imaging Report',
    '24606-6': 'CT Scan Report',
    '24610-8': 'Ultrasound Report',
    '24725-4': 'MRI Report',
    '24727-0': 'Nuclear Medicine Report',
    '24729-6': 'PET Scan Report',
    '26436-6': 'Laboratory Studies',
    '27898-6': 'Pathology Report',
    '29272-2': 'Eye Exam Report',
    '29750-7': 'Dialysis Report',
    '30954-2': 'Relevant Diagnostic Tests',
    '43789-2': 'Screening Report',
    '47519-4': 'Diagnostic Imaging Report',
    '57129-9': 'Full Unstructured Report',
    '57133-1': 'Referral Note',
    '58477-1': 'Pulmonary Function Study',
    '59258-4': 'Emergency Department Report',
    '68608-9': 'Summary Note',
    '70004-7': 'Diagnostic Study Note',
    '74213-0': 'Discharge Instructions',
    '74264-3': 'HIV Summary Report',
    '82593-5': 'Immunization Evaluation Report',
    '83909-3': 'EKG/ECG Report',
    '85208-9': 'Labor and Delivery Summary',
    '87273-1': 'Fetal Imaging Report',
    '88348-0': 'Outpatient Encounter Report',

    # Patient Care Forms
    '51850-6': 'Physical Examination',
    '51854-8': 'Consent Form',
    '56445-0': 'Medication List',
    '57016-8': 'Privacy Notice',
    '57833-6': 'Prescription Request',
    '60591-5': 'Patient Summary Document',
    '64288-5': 'Insurance Card',
    '69730-0': 'Instructions',
    '74156-1': 'Treatment Plan',
    '77599-9': 'Administrative Document',
    '85898-7': 'Screening Form',
    
    # Procedure/Surgery Documents
    '11504-8': 'Surgical Operation Note',
    '28570-0': 'Procedure Note',
    '28579-1': 'Discharge Summary',
    '29752-3': 'Perioperative Record',
    '29756-4': 'Intraoperative Record',
    '34129-7': 'Preoperative Note',
    '34130-5': 'Postoperative Note',
    '59282-4': 'Stress Test Report',
    '83944-2': 'Procedure Findings',
}

# Category codes for broader grouping
CATEGORY_CODES = {
    'clinical-note': 'Clinical Note',
    'imaging': 'Imaging Report', 
    'laboratory': 'Laboratory Report',
    'pathology': 'Pathology Report',
    'procedure-note': 'Procedure Note',
    'discharge-summary': 'Discharge Summary',
    'referral': 'Referral',
    'administrative': 'Administrative Document',
    'consent': 'Consent Form',
    'other': 'Document',
}


def get_safe_document_type(type_coding = None, category = None, fallback_code = None) -> str:
    """
    Get a PHI-safe document type display name from FHIR type coding or category.
    
    This function ONLY uses structured codes to generate display names.
    It NEVER uses free-text fields that could contain patient names.
    
    Args:
        type_coding: List of coding objects from DocumentReference.type.coding
        category: List of category objects from DocumentReference.category
        fallback_code: A code to use if no match found
        
    Returns:
        Safe display name (never contains PHI)
    """
    # Try type coding first (most specific)
    if type_coding:
        for coding in type_coding:
            code = coding.get('code', '')
            
            # Check LOINC codes
            if code in LOINC_DOCUMENT_TYPES:
                return LOINC_DOCUMENT_TYPES[code]
            
            # Check system to determine code type
            system = coding.get('system', '')
            if 'loinc' in system.lower():
                if code in LOINC_DOCUMENT_TYPES:
                    return LOINC_DOCUMENT_TYPES[code]
    
    # Try category (broader classification)
    if category:
        for cat in category:
            cat_coding = cat.get('coding', [])
            for coding in cat_coding:
                code = coding.get('code', '')
                if code in CATEGORY_CODES:
                    return CATEGORY_CODES[code]
    
    # Fallback to generic if code provided
    if fallback_code:
        if fallback_code in LOINC_DOCUMENT_TYPES:
            return LOINC_DOCUMENT_TYPES[fallback_code]
        if fallback_code in CATEGORY_CODES:
            return CATEGORY_CODES[fallback_code]
        # Return code itself with prefix to indicate it's structured
        return f"Document ({fallback_code})"
    
    # Ultimate fallback
    return "Document"


def get_document_type_code(type_coding = None, category = None) -> str:
    """
    Extract the primary document type code from FHIR coding.
    
    Returns the LOINC code if available, otherwise a category code.
    
    Args:
        type_coding: List of coding objects from DocumentReference.type.coding
        category: List of category objects from DocumentReference.category
        
    Returns:
        Document type code (LOINC preferred) or empty string
    """
    # Try type coding first (most specific)
    if type_coding:
        for coding in type_coding:
            system = coding.get('system', '')
            code = coding.get('code', '')
            
            # Prefer LOINC codes
            if 'loinc' in system.lower() or code in LOINC_DOCUMENT_TYPES:
                return code
            
            # Return first non-empty code
            if code:
                return code
    
    # Try category codes
    if category:
        for cat in category:
            cat_coding = cat.get('coding', [])
            for coding in cat_coding:
                code = coding.get('code', '')
                if code:
                    return code
    
    return ""


def sanitize_title_to_code_only(raw_title, type_coding = None, category = None) -> str:
    """
    DEPRECATED: Use get_safe_document_type() instead.
    
    This function is kept for backward compatibility but should not be used
    for new code. The raw_title parameter is ignored to prevent PHI leakage.
    
    Args:
        raw_title: Ignored - do not use free text
        type_coding: List of coding objects from DocumentReference.type.coding
        category: List of category objects from DocumentReference.category
        
    Returns:
        Safe display name derived only from structured codes
    """
    logger.warning("sanitize_title_to_code_only() is deprecated - use get_safe_document_type()")
    return get_safe_document_type(type_coding, category)


LOINC_TO_PREP_SHEET_CATEGORY = {
    'lab': [
        '11502-2',  # Laboratory Report
        '26436-6',  # Laboratory Report
        '26438-2',  # Chemistry Report
        '26439-0',  # Hematology Report
        '26440-8',  # Urinalysis Report
        '26441-6',  # Coagulation Report
        '26442-4',  # Microbiology Report
        '26443-2',  # Blood Bank Report
        '26444-0',  # Cytology Report
        '26445-7',  # Surgical Pathology Report
        '27898-6',  # Pathology Report
        '60567-5',  # Comprehensive Pathology Report
        '34776-5',  # Pathology Note
    ],
    'imaging': [
        '18748-4',  # Diagnostic Imaging Study
        '18782-3',  # Radiology Study
        '47519-4',  # Diagnostic Imaging Report
        '34785-6',  # Radiology Note
        '57147-1',  # Radiology Referral Note
        '70004-7',  # Diagnostic Study Note
        '87273-1',  # Fetal Imaging Report
        '83909-3',  # EKG/ECG Report
        '59282-4',  # Stress Test Report
        '58477-1',  # Pulmonary Function Study
    ],
    'consult': [
        '11488-4',  # Consultation Note
        '18841-7',  # Hospital Consultations
        '28569-2',  # Physician Consulting Progress Note
        '51845-6',  # Outpatient Consultation Note
        '57133-1',  # Referral Note
        '57134-9',  # Dentistry Referral Note
        '57135-6',  # Dermatology Referral Note
        '57136-4',  # Gastroenterology Referral Note
        '57137-2',  # General Medicine Referral Note
        '57138-0',  # Neurology Referral Note
        '57139-8',  # Ophthalmology Referral Note
        '57140-6',  # Orthopedics Referral Note
        '57141-4',  # Otolaryngology Referral Note
        '57142-2',  # Plastic Surgery Referral Note
        '57143-0',  # Podiatry Referral Note
        '57144-8',  # Psychiatry Referral Note
        '57145-5',  # Pulmonology Referral Note
        '57146-3',  # Radiation Oncology Referral Note
        '57148-9',  # Rheumatology Referral Note
        '57149-7',  # Social Work Referral Note
        '57150-5',  # Surgery Referral Note
        '57151-3',  # Urology Referral Note
        '57152-1',  # Cardiology Referral Note
        '57153-9',  # Hematology/Oncology Referral Note
        '57154-7',  # Infectious Disease Referral Note
        '57155-4',  # Internal Medicine Referral Note
        '57156-2',  # Nephrology Referral Note
        '57157-0',  # Pediatrics Referral Note
        '34099-2',  # Cardiology Consult Note
        '34752-6',  # Cardiology Note
        '34758-3',  # Endocrinology Note
        '34759-1',  # Gastroenterology Note
        '34763-3',  # Hematology/Oncology Note
        '34764-1',  # Infectious Disease Note
        '34765-8',  # Nephrology Note
        '34766-6',  # Neurology Note
        '34771-6',  # Oncology Note
        '34783-1',  # Pulmonology Note
        '34788-0',  # Rheumatology Note
    ],
    'hospital': [
        '18842-5',  # Discharge Summary
        '28579-1',  # Discharge Summary
        '34105-7',  # Hospital Discharge Summary
        '34106-5',  # Physician Hospital Discharge Summary
        '34112-3',  # Hospital Admission Note
        '68624-6',  # Hospitalization Summary
        '11506-3',  # Progress Note
        '28568-4',  # Physician Attending Progress Note
        '34746-8',  # Nurse Progress Note
        '34100-8',  # Intensive Care Unit Note
        '29751-5',  # Critical Care Records
        '47039-3',  # Admission Note
        '34136-2',  # Physician Attending Admission Note
        '28582-5',  # Transfer Summary
        '68613-9',  # Transition of Care Note
        '34745-0',  # Nurse Discharge Summary
        '34111-5',  # Emergency Department Note
        '51846-4',  # Emergency Department Note
        '59258-4',  # Emergency Department Report
        '60280-5',  # Emergency Medicine Transfer Note
    ],
}

LOINC_CODE_TO_CATEGORY = {}
for category, codes in LOINC_TO_PREP_SHEET_CATEGORY.items():
    for code in codes:
        LOINC_CODE_TO_CATEGORY[code] = category


def get_prep_sheet_category(document_type_code: str = None, document_type_display: str = None) -> str:
    """
    Map a FHIR document type code to a prep sheet category (lab, imaging, consult, hospital).
    
    Args:
        document_type_code: LOINC code from FHIRDocument.document_type_code
        document_type_display: Display name from FHIRDocument.document_type_display
        
    Returns:
        Category string ('lab', 'imaging', 'consult', 'hospital') or None if no match
    """
    if document_type_code and document_type_code in LOINC_CODE_TO_CATEGORY:
        return LOINC_CODE_TO_CATEGORY[document_type_code]
    
    if document_type_display:
        display_lower = document_type_display.lower()
        
        if any(term in display_lower for term in ['laboratory', 'lab report', 'pathology', 'blood test', 'urinalysis', 'microbiology']):
            return 'lab'
        if any(term in display_lower for term in ['imaging', 'radiology', 'x-ray', 'ct scan', 'mri', 'ultrasound', 'diagnostic imaging', 'ekg', 'ecg', 'echo']):
            return 'imaging'
        if any(term in display_lower for term in ['consult', 'referral', 'specialist']):
            return 'consult'
        if any(term in display_lower for term in ['hospital', 'admission', 'discharge', 'inpatient', 'emergency department', 'progress note', 'icu', 'critical care', 'procedure']):
            return 'hospital'
    
    return None
