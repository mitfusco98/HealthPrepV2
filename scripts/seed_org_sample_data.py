#!/usr/bin/env python3
"""
Organization Sample Data Seeder

Seeds new organizations with sample data for immediate demonstration:
- 4 manual sample documents on /admin/documents
- Sample immunization records (Flu, Pneumococcal, Shingles, COVID-19)
- Stale test patients visible on /screening/list

This script can be run standalone or called during organization creation.

Usage:
    python scripts/seed_org_sample_data.py [--org-id ORG_ID] [--clear]

Options:
    --org-id    Target organization ID (required if standalone)
    --clear     Remove existing sample data before seeding
"""

import sys
import os
import argparse
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CVX Vaccine Codes Reference:
# https://www2a.cdc.gov/vaccines/iis/iisstandards/vaccines.asp?rpt=cvx
CVX_CODES = {
    'Influenza': {
        'codes': ['141', '158', '185'],
        'names': {
            '141': 'Influenza, seasonal, injectable',
            '158': 'Influenza, injectable, quadrivalent',
            '185': 'Influenza, recombinant, quadrivalent'
        }
    },
    'Pneumococcal': {
        'codes': ['33', '109'],
        'names': {
            '33': 'Pneumococcal polysaccharide PPV23',
            '109': 'Pneumococcal, PCV13'
        }
    },
    'Shingles': {
        'codes': ['121', '187'],
        'names': {
            '121': 'Zoster, live',
            '187': 'Zoster recombinant (Shingrix)'
        }
    },
    'COVID-19': {
        'codes': ['207', '208', '218'],
        'names': {
            '207': 'COVID-19, mRNA, LNP-S, PF, 100 mcg/0.5 mL (Moderna)',
            '208': 'COVID-19, mRNA, LNP-S, PF, 30 mcg/0.3 mL (Pfizer)',
            '218': 'COVID-19, mRNA, LNP-S, PF, bivalent (Pfizer)'
        }
    }
}

# Sample document content (PHI-free demonstration data)
SAMPLE_DOCUMENTS = [
    {
        'filename': 'SAMPLE_Colonoscopy_Report.pdf',
        'document_type': 'imaging',
        'content': '''SAMPLE COLONOSCOPY REPORT
        
Date of Procedure: [Sample Date]
Procedure: Diagnostic Colonoscopy with Biopsy

FINDINGS:
- Cecum reached and identified by appendiceal orifice
- Terminal ileum intubated
- Overall good bowel preparation
- No polyps identified
- No masses or lesions
- Normal vascular pattern throughout

IMPRESSION:
Normal colonoscopy examination

RECOMMENDATION:
Routine screening colonoscopy in 10 years per guidelines.

This is sample demonstration data for HealthPrep onboarding.''',
        'days_ago': 30
    },
    {
        'filename': 'SAMPLE_Mammogram_Results.pdf',
        'document_type': 'imaging',
        'content': '''SAMPLE MAMMOGRAM REPORT

Date of Study: [Sample Date]
Study Type: Bilateral Screening Mammogram

CLINICAL HISTORY:
Routine screening mammogram

TECHNIQUE:
Digital mammography with tomosynthesis

FINDINGS:
Breasts are heterogeneously dense.
No suspicious masses, architectural distortion, or suspicious calcifications.
No significant change from prior study.

IMPRESSION:
BI-RADS Category 1: Negative
Normal mammogram. Recommend routine screening.

This is sample demonstration data for HealthPrep onboarding.''',
        'days_ago': 60
    },
    {
        'filename': 'SAMPLE_Lab_Panel_CBC.pdf',
        'document_type': 'lab',
        'content': '''SAMPLE LABORATORY REPORT

Date Collected: [Sample Date]
Test: Complete Blood Count (CBC) with Differential

RESULTS:
WBC: 7.2 x10^3/uL (4.5-11.0)
RBC: 4.8 x10^6/uL (4.0-5.5)
Hemoglobin: 14.2 g/dL (12.0-16.0)
Hematocrit: 42% (36-46)
MCV: 88 fL (80-100)
MCH: 30 pg (27-33)
MCHC: 34 g/dL (32-36)
Platelet Count: 250 x10^3/uL (150-400)

INTERPRETATION:
All values within normal limits.

This is sample demonstration data for HealthPrep onboarding.''',
        'days_ago': 14
    },
    {
        'filename': 'SAMPLE_Lipid_Panel.pdf',
        'document_type': 'lab',
        'content': '''SAMPLE LABORATORY REPORT

Date Collected: [Sample Date]
Test: Lipid Panel

RESULTS:
Total Cholesterol: 195 mg/dL (<200 desirable)
HDL Cholesterol: 55 mg/dL (>40 desirable)
LDL Cholesterol: 120 mg/dL (<100 optimal, <130 near optimal)
Triglycerides: 100 mg/dL (<150 desirable)
VLDL Cholesterol: 20 mg/dL (<30)
Total Cholesterol/HDL Ratio: 3.5 (<5.0)

INTERPRETATION:
Lipid panel within acceptable limits. Continue current lifestyle modifications.

This is sample demonstration data for HealthPrep onboarding.''',
        'days_ago': 45
    }
]

# Sample test patients with demographics for screening eligibility
SAMPLE_PATIENTS = [
    {
        'name': 'SAMPLE_Williams_Mary',
        'mrn': 'SAMPLE001',
        'gender': 'female',
        'age_years': 52,
        'conditions': ['diabetes type 2'],
        'is_stale': True
    },
    {
        'name': 'SAMPLE_Johnson_Robert',
        'mrn': 'SAMPLE002',
        'gender': 'male',
        'age_years': 67,
        'conditions': ['hypertension', 'copd'],
        'is_stale': True
    },
    {
        'name': 'SAMPLE_Davis_Patricia',
        'mrn': 'SAMPLE003',
        'gender': 'female',
        'age_years': 45,
        'conditions': [],
        'is_stale': True
    }
]


def seed_organization_data(org_id, provider_id=None, clear_existing=False):
    """
    Seed an organization with sample data for demonstration.
    
    Args:
        org_id: Organization ID to seed
        provider_id: Optional provider ID (will use first active provider if not specified)
        clear_existing: If True, remove existing sample data before seeding
    
    Returns:
        dict with counts of created items
    """
    from app import db
    from models import (
        Organization, Provider, Patient, Document, 
        Appointment, Screening, FHIRImmunization, PatientCondition
    )
    
    org = Organization.query.get(org_id)
    if not org:
        logger.error(f"Organization {org_id} not found")
        return None
    
    logger.info(f"Seeding sample data for organization: {org.name} (ID: {org_id})")
    
    # Get or find provider
    if provider_id:
        provider = Provider.query.get(provider_id)
    else:
        provider = Provider.query.filter_by(org_id=org_id, is_active=True).first()
    
    if not provider:
        logger.warning(f"No active provider found for org {org_id}, creating sample provider")
        provider = Provider(
            name='Sample Provider',
            specialty='Family Medicine',
            org_id=org_id,
            is_active=True
        )
        db.session.add(provider)
        db.session.flush()
    
    # Clear existing sample data if requested
    if clear_existing:
        _clear_sample_data(org_id)
    
    results = {
        'patients_created': 0,
        'documents_created': 0,
        'immunizations_created': 0,
        'appointments_created': 0
    }
    
    # Create sample patients
    created_patients = []
    for patient_config in SAMPLE_PATIENTS:
        existing = Patient.query.filter_by(mrn=patient_config['mrn'], org_id=org_id).first()
        if existing:
            logger.info(f"Patient {patient_config['mrn']} already exists, using existing")
            created_patients.append(existing)
            continue
        
        dob = datetime.now() - relativedelta(years=patient_config['age_years'])
        
        patient = Patient(
            name=patient_config['name'],
            mrn=patient_config['mrn'],
            date_of_birth=dob.date(),
            gender=patient_config['gender'],
            org_id=org_id,
            provider_id=provider.id
        )
        db.session.add(patient)
        db.session.flush()
        
        created_patients.append(patient)
        results['patients_created'] += 1
        logger.info(f"Created sample patient: {patient.name}")
        
        # Create PatientCondition records for trigger condition testing
        for condition_name in patient_config.get('conditions', []):
            condition = PatientCondition(
                patient_id=patient.id,
                condition_name=condition_name,
                is_active=True
            )
            db.session.add(condition)
            logger.info(f"  Added condition: {condition_name}")
        
        # Create past appointment to make patient "stale"
        if patient_config.get('is_stale'):
            days_ago = 45  # Outside typical 14-day prioritization window
            past_appt = Appointment(
                patient_id=patient.id,
                provider_id=provider.id,
                org_id=org_id,
                appointment_date=datetime.now() - timedelta(days=days_ago),
                appointment_type='Follow-up Visit',
                status='completed',
                notes='Sample past appointment for stale patient demonstration'
            )
            db.session.add(past_appt)
            results['appointments_created'] += 1
    
    db.session.flush()
    
    # Create sample documents for each patient
    for patient in created_patients:
        for doc_config in SAMPLE_DOCUMENTS:
            doc_date = date.today() - timedelta(days=doc_config['days_ago'])
            
            existing_doc = Document.query.filter_by(
                patient_id=patient.id,
                org_id=org_id,
                filename=doc_config['filename']
            ).first()
            
            if existing_doc:
                continue
            
            doc = Document(
                patient_id=patient.id,
                org_id=org_id,
                filename=doc_config['filename'],
                document_type=doc_config['document_type'],
                document_date=doc_date,
                processed_at=datetime.now(),
                phi_filtered=True
            )
            # Set content using property setter (applies PHI filtering)
            doc._ocr_text = doc_config['content']
            doc._content = doc_config['content']
            db.session.add(doc)
            results['documents_created'] += 1
    
    db.session.flush()
    
    # Create sample immunization records
    for patient in created_patients:
        for vaccine_group, vaccine_info in CVX_CODES.items():
            # Pick one random CVX code from the group
            cvx_code = vaccine_info['codes'][0]
            vaccine_name = vaccine_info['names'][cvx_code]
            
            # Create immunization from 6-18 months ago
            months_ago = 6 + (hash(patient.mrn + vaccine_group) % 12)
            admin_date = date.today() - relativedelta(months=months_ago)
            
            existing_imm = FHIRImmunization.query.filter_by(
                patient_id=patient.id,
                org_id=org_id,
                cvx_code=cvx_code
            ).first()
            
            if existing_imm:
                continue
            
            immunization = FHIRImmunization(
                patient_id=patient.id,
                org_id=org_id,
                provider_id=provider.id,
                cvx_code=cvx_code,
                vaccine_name=vaccine_name,
                vaccine_group=vaccine_group,
                administration_date=admin_date,
                status='completed',
                route='Intramuscular',
                site='Left Deltoid',
                performer_organization=org.name,
                is_manual_entry=True,
                is_sample_data=True
            )
            db.session.add(immunization)
            results['immunizations_created'] += 1
    
    db.session.commit()
    
    # Run screening engine to create screenings for patients
    try:
        from core.engine import ScreeningEngine
        engine = ScreeningEngine()
        
        for patient in created_patients:
            updated = engine.refresh_patient_screenings(patient.id, force_refresh=True)
            
            # Mark screenings as dormant/stale
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            for screening in screenings:
                screening.is_dormant = True
                screening.last_processed = datetime.now() - timedelta(days=30)
            
            logger.info(f"Created {updated} screenings for {patient.name} (marked as stale)")
        
        db.session.commit()
    except Exception as e:
        logger.warning(f"Could not run screening engine: {e}")
    
    logger.info(f"\n=== SEEDING COMPLETE ===")
    logger.info(f"Patients created: {results['patients_created']}")
    logger.info(f"Documents created: {results['documents_created']}")
    logger.info(f"Immunizations created: {results['immunizations_created']}")
    logger.info(f"Appointments created: {results['appointments_created']}")
    
    return results


def _clear_sample_data(org_id):
    """Remove all sample data for an organization"""
    from app import db
    from models import Patient, Document, FHIRImmunization, Appointment, Screening, PatientCondition
    
    logger.info(f"Clearing existing sample data for org {org_id}...")
    
    # Find sample patients
    sample_patients = Patient.query.filter(
        Patient.org_id == org_id,
        Patient.mrn.like('SAMPLE%')
    ).all()
    
    patient_ids = [p.id for p in sample_patients]
    
    if patient_ids:
        # Delete related data
        Screening.query.filter(Screening.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        FHIRImmunization.query.filter(FHIRImmunization.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        Document.query.filter(Document.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        Appointment.query.filter(Appointment.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        PatientCondition.query.filter(PatientCondition.patient_id.in_(patient_ids)).delete(synchronize_session=False)
        Patient.query.filter(Patient.id.in_(patient_ids)).delete(synchronize_session=False)
        
        db.session.commit()
        logger.info(f"Cleared {len(patient_ids)} sample patients and their associated data")


def seed_on_org_creation(org_id, provider_id=None):
    """
    Convenience function to call during organization creation workflow.
    Wraps seed_organization_data with app context handling.
    
    Args:
        org_id: Organization ID to seed
        provider_id: Optional provider ID
    
    Returns:
        dict with counts of created items, or None on error
    """
    from flask import current_app, has_app_context
    
    if has_app_context():
        return seed_organization_data(org_id, provider_id)
    else:
        from app import app
        with app.app_context():
            return seed_organization_data(org_id, provider_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed organization with sample data')
    parser.add_argument('--org-id', type=int, help='Organization ID to seed')
    parser.add_argument('--clear', action='store_true', help='Clear existing sample data first')
    
    args = parser.parse_args()
    
    from app import app
    
    with app.app_context():
        if args.org_id:
            seed_organization_data(args.org_id, clear_existing=args.clear)
        else:
            # If no org-id specified, seed all organizations
            from models import Organization
            orgs = Organization.query.filter(Organization.id > 0).all()
            
            if not orgs:
                logger.error("No organizations found. Please create an organization first.")
                sys.exit(1)
            
            for org in orgs:
                print(f"\n{'='*50}")
                seed_organization_data(org.id, clear_existing=args.clear)
