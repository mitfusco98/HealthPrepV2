"""
Test Patient Generator Script

Creates TEST_ prefixed patients with:
- Past appointment dates (outside prioritization window)
- Age/sex/conditions to trigger screening creation
- Cloned documents from existing patients

Usage: python scripts/create_test_patients.py [org_id]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_patients(org_id=None, num_patients=5):
    """Create test patients with past appointments and appropriate demographics"""
    from app import create_app, db
    from models import Patient, Provider, Appointment, Document, Screening, Organization, PatientCondition
    
    app = create_app()
    with app.app_context():
        if org_id is None:
            org = Organization.query.filter(Organization.id > 0).first()
            if not org:
                logger.error("No organization found. Please create an organization first.")
                return
            org_id = org.id
            logger.info(f"Using organization: {org.name} (ID: {org_id})")
        
        provider = Provider.query.filter_by(org_id=org_id).first()
        if not provider:
            logger.error(f"No provider found for org_id {org_id}")
            return
        
        existing_docs = Document.query.filter(
            Document.org_id == org_id,
            Document.ocr_text.isnot(None)
        ).limit(10).all()
        
        test_configs = [
            {
                'name': 'TEST_Smith_Jane',
                'mrn': 'TEST001',
                'sex': 'female',
                'age_years': 55,
                'conditions': ['diabetes', 'hypertension']
            },
            {
                'name': 'TEST_Johnson_Robert',
                'mrn': 'TEST002', 
                'sex': 'male',
                'age_years': 68,
                'conditions': ['copd', 'heart disease']
            },
            {
                'name': 'TEST_Williams_Mary',
                'mrn': 'TEST003',
                'sex': 'female',
                'age_years': 45,
                'conditions': ['asthma']
            },
            {
                'name': 'TEST_Brown_Michael',
                'mrn': 'TEST004',
                'sex': 'male',
                'age_years': 72,
                'conditions': ['diabetes', 'kidney disease']
            },
            {
                'name': 'TEST_Davis_Sarah',
                'mrn': 'TEST005',
                'sex': 'female',
                'age_years': 38,
                'conditions': []
            }
        ]
        
        created_patients = []
        
        for i, config in enumerate(test_configs[:num_patients]):
            existing = Patient.query.filter_by(mrn=config['mrn'], org_id=org_id).first()
            if existing:
                logger.info(f"Patient {config['mrn']} already exists, skipping...")
                created_patients.append(existing)
                continue
            
            dob = datetime.now() - relativedelta(years=config['age_years'])
            
            patient = Patient(
                name=config['name'],
                mrn=config['mrn'],
                date_of_birth=dob.date(),
                gender=config['sex'],
                org_id=org_id,
                provider_id=provider.id
            )
            db.session.add(patient)
            db.session.flush()
            
            days_ago = random.randint(20, 60)
            past_appointment = Appointment(
                patient_id=patient.id,
                provider_id=provider.id,
                org_id=org_id,
                appointment_date=datetime.now() - timedelta(days=days_ago),
                appointment_type='Follow-up',
                status='completed'
            )
            db.session.add(past_appointment)
            
            if existing_docs:
                source_doc = random.choice(existing_docs)
                cloned_doc = Document(
                    patient_id=patient.id,
                    org_id=org_id,
                    filename=f"TEST_clone_{source_doc.filename}",
                    document_type=source_doc.document_type
                )
                cloned_doc.ocr_text = source_doc.ocr_text
                db.session.add(cloned_doc)
                logger.info(f"  Cloned document: {cloned_doc.filename}")
            
            # Create PatientCondition records for trigger condition testing
            for condition_name in config['conditions']:
                condition = PatientCondition(
                    patient_id=patient.id,
                    condition_name=condition_name,
                    is_active=True
                )
                db.session.add(condition)
                logger.info(f"  Added condition: {condition_name}")
            
            created_patients.append(patient)
            logger.info(f"Created patient: {config['name']} (MRN: {config['mrn']}, Age: {config['age_years']}, Sex: {config['sex']})")
            logger.info(f"  Past appointment: {days_ago} days ago")
            logger.info(f"  Conditions: {config['conditions']}")
        
        db.session.commit()
        
        from core.engine import ScreeningEngine
        engine = ScreeningEngine()
        
        for patient in created_patients:
            updated = engine.refresh_patient_screenings(patient.id, force_refresh=True)
            
            for screening in Screening.query.filter_by(patient_id=patient.id).all():
                screening.is_dormant = True
                screening.last_processed = datetime.now() - timedelta(days=30)
            
            logger.info(f"Created {updated} screenings for {patient.name} (marked as dormant)")
        
        db.session.commit()
        
        logger.info(f"\n=== SUMMARY ===")
        logger.info(f"Created/updated {len(created_patients)} test patients")
        logger.info(f"All patients have PAST appointments (outside prioritization window)")
        logger.info(f"All screenings marked as DORMANT (stale)")
        logger.info(f"View in /screening/list - should show refresh icons")


def cleanup_test_patients(org_id=None):
    """Remove all TEST_ prefixed patients"""
    from app import create_app, db
    from models import Patient, Appointment, Document, Screening, Organization, PatientCondition
    
    app = create_app()
    with app.app_context():
        if org_id is None:
            org = Organization.query.filter(Organization.id > 0).first()
            if not org:
                return
            org_id = org.id
        
        test_patients = Patient.query.filter(
            Patient.org_id == org_id,
            Patient.mrn.like('TEST%')
        ).all()
        
        for patient in test_patients:
            Screening.query.filter_by(patient_id=patient.id).delete()
            Document.query.filter_by(patient_id=patient.id).delete()
            Appointment.query.filter_by(patient_id=patient.id).delete()
            PatientCondition.query.filter_by(patient_id=patient.id).delete()
            db.session.delete(patient)
            logger.info(f"Deleted test patient: {patient.name}")
        
        db.session.commit()
        logger.info(f"Cleaned up {len(test_patients)} test patients")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Create or cleanup test patients')
    parser.add_argument('--org-id', type=int, help='Organization ID')
    parser.add_argument('--cleanup', action='store_true', help='Remove test patients instead of creating')
    parser.add_argument('--count', type=int, default=5, help='Number of patients to create')
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_test_patients(args.org_id)
    else:
        create_test_patients(args.org_id, args.count)
