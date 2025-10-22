#!/usr/bin/env python3
"""
Test script to investigate condition-based eligibility in the Health-Prep screening engine.
Tests how the system determines if patients with specific medical conditions get appropriate 
screening protocols based on trigger conditions.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from app import db
from models import Patient, PatientCondition, ScreeningType, Screening
from core.engine import ScreeningEngine
from core.criteria import EligibilityCriteria
from datetime import datetime, date
import json

def test_condition_eligibility():
    """Test condition-based eligibility system comprehensively"""
    with app.app_context():
        print("="*80)
        print("CONDITION-BASED ELIGIBILITY INVESTIGATION")
        print("="*80)
        
        # Initialize components
        engine = ScreeningEngine()
        criteria = EligibilityCriteria()
        
        print("\n1. PATIENT CONDITIONS ANALYSIS")
        print("-" * 50)
        
        # Get all patients with conditions
        patients_with_conditions = db.session.query(Patient).join(PatientCondition).distinct().all()
        
        print(f"Found {len(patients_with_conditions)} patients with conditions")
        
        for patient in patients_with_conditions:
            print(f"\nPatient: {patient.name} (Age: {patient.age}, Gender: {patient.gender})")
            active_conditions = [c for c in patient.conditions if c.is_active]
            print(f"  Active Conditions: {[c.condition_name for c in active_conditions]}")
            
            # Test eligibility for screening types with trigger conditions
            condition_screening_types = ScreeningType.query.filter(
                ScreeningType.trigger_conditions.isnot(None),
                ScreeningType.trigger_conditions != '',
                ScreeningType.trigger_conditions != '[]'
            ).all()
            
            eligible_screenings = []
            for st in condition_screening_types:
                if criteria.is_patient_eligible(patient, st):
                    eligible_screenings.append(st.name)
            
            print(f"  Eligible for Condition-Based Screenings: {eligible_screenings}")
        
        print("\n\n2. SCREENING TYPES WITH TRIGGER CONDITIONS")
        print("-" * 50)
        
        condition_screening_types = ScreeningType.query.filter(
            ScreeningType.trigger_conditions.isnot(None),
            ScreeningType.trigger_conditions != '',
            ScreeningType.trigger_conditions != '[]'
        ).all()
        
        for st in condition_screening_types:
            try:
                trigger_conditions = json.loads(st.trigger_conditions) if st.trigger_conditions else []
            except:
                trigger_conditions = [st.trigger_conditions] if st.trigger_conditions else []
                
            print(f"\nScreening: {st.name}")
            print(f"  Trigger Conditions: {trigger_conditions}")
            print(f"  Age Range: {st.min_age or 'Any'} - {st.max_age or 'Any'}")
            print(f"  Gender: {st.eligible_genders or 'Both'}")
            
            # Count eligible patients
            all_patients = Patient.query.all()
            eligible_count = 0
            eligible_patients = []
            
            for patient in all_patients:
                if criteria.is_patient_eligible(patient, st):
                    eligible_count += 1
                    eligible_patients.append(patient.name)
            
            print(f"  Eligible Patients ({eligible_count}): {eligible_patients}")
        
        print("\n\n3. SPECIFIC CONDITION MATCHING TESTS")
        print("-" * 50)
        
        # Test specific condition matching scenarios
        test_cases = [
            ("asthma", ["Pulmonary Function Test - COPD Monitoring"]),
            ("diabetes", ["A1C Test", "Diabetic Eye Exam"]),
            ("COPD", ["Pulmonary Function Test - COPD Monitoring", "Pulmonary Function Test - Severe COPD"]),
            ("heart disease", [])  # Should not match diabetes or asthma screenings
        ]
        
        for condition_keyword, expected_screenings in test_cases:
            print(f"\nTesting condition keyword: '{condition_keyword}'")
            
            # Find patients with conditions containing this keyword
            patients_with_condition = []
            for patient in Patient.query.all():
                patient_conditions = [c.condition_name.lower() for c in patient.conditions if c.is_active]
                if any(condition_keyword in pc for pc in patient_conditions):
                    patients_with_condition.append(patient)
            
            print(f"  Patients with condition: {[p.name for p in patients_with_condition]}")
            
            # Test eligibility for each patient
            for patient in patients_with_condition:
                eligible_screenings = []
                for st in condition_screening_types:
                    if criteria.is_patient_eligible(patient, st):
                        eligible_screenings.append(st.name)
                
                print(f"    {patient.name} is eligible for: {eligible_screenings}")
                
                # Verify expected screenings
                for expected in expected_screenings:
                    if expected in eligible_screenings:
                        print(f"    ✓ Correctly eligible for {expected}")
                    else:
                        print(f"    ✗ Should be eligible for {expected} but is not!")
        
        print("\n\n4. TRIGGER CONDITION MATCHING LOGIC TEST")
        print("-" * 50)
        
        # Test the _check_trigger_conditions method directly
        patient_with_asthma = next((p for p in Patient.query.all() 
                                   if any('asthma' in c.condition_name.lower() for c in p.conditions if c.is_active)), None)
        
        if patient_with_asthma:
            print(f"Testing trigger logic with patient: {patient_with_asthma.name}")
            
            # Get asthma-triggered screening
            copd_screening = next((st for st in condition_screening_types 
                                 if 'COPD Monitoring' in st.name), None)
            
            if copd_screening:
                print(f"Testing screening: {copd_screening.name}")
                
                # Test trigger conditions step by step
                patient_conditions = [c.condition_name.lower() for c in patient_with_asthma.conditions if c.is_active]
                print(f"  Patient conditions: {patient_conditions}")
                
                trigger_conditions = json.loads(copd_screening.trigger_conditions)
                print(f"  Trigger conditions: {trigger_conditions}")
                
                # Test each trigger condition
                matches_found = []
                for trigger in trigger_conditions:
                    trigger_lower = trigger.lower().strip()
                    for patient_condition in patient_conditions:
                        if trigger_lower in patient_condition or patient_condition in trigger_lower:
                            matches_found.append((trigger, patient_condition))
                            break
                
                print(f"  Matches found: {matches_found}")
                
                # Test the actual method
                is_eligible = criteria._check_trigger_conditions(patient_with_asthma, copd_screening)
                print(f"  Final eligibility result: {is_eligible}")
        
        print("\n\n5. END-TO-END SCREENING ASSIGNMENT TEST")
        print("-" * 50)
        
        # Test the full screening engine refresh for condition-based eligibility
        print("Testing screening engine refresh...")
        
        try:
            # Get current screening count
            initial_screenings = Screening.query.count()
            print(f"Initial screening count: {initial_screenings}")
            
            # Refresh screenings for a specific patient with conditions
            if patient_with_asthma:
                print(f"Refreshing screenings for {patient_with_asthma.name}...")
                updated_count = engine.refresh_patient_screenings(patient_with_asthma.id)
                print(f"Updated {updated_count} screenings")
                
                # Check what screenings are now assigned
                patient_screenings = Screening.query.filter_by(patient_id=patient_with_asthma.id).all()
                print(f"Total screenings for {patient_with_asthma.name}: {len(patient_screenings)}")
                
                for screening in patient_screenings:
                    print(f"  - {screening.screening_type.name}: {screening.status}")
        
        except Exception as e:
            print(f"Error testing screening engine: {e}")
        
        print("\n\n6. SUMMARY & FINDINGS")
        print("-" * 50)
        
        # Summarize findings
        total_patients = Patient.query.count()
        patients_with_conditions_count = len(patients_with_conditions)
        condition_screening_count = len(condition_screening_types)
        
        print(f"Total patients: {total_patients}")
        print(f"Patients with conditions: {patients_with_conditions_count}")
        print(f"Screening types with trigger conditions: {condition_screening_count}")
        
        # Check if condition-based eligibility is working
        working_correctly = True
        issues_found = []
        
        # Test: Patient with asthma should be eligible for COPD monitoring
        asthma_patients = [p for p in Patient.query.all() 
                          if any('asthma' in c.condition_name.lower() for c in p.conditions if c.is_active)]
        
        copd_monitoring = next((st for st in condition_screening_types 
                               if 'COPD Monitoring' in st.name), None)
        
        if asthma_patients and copd_monitoring:
            for patient in asthma_patients:
                if not criteria.is_patient_eligible(patient, copd_monitoring):
                    working_correctly = False
                    issues_found.append(f"Patient {patient.name} with asthma should be eligible for COPD monitoring")
        
        print(f"\nCondition-based eligibility working correctly: {working_correctly}")
        if issues_found:
            print("Issues found:")
            for issue in issues_found:
                print(f"  - {issue}")
        
        print("="*80)

if __name__ == "__main__":
    test_condition_eligibility()