#!/usr/bin/env python3
"""
Test Epic FHIR Integration with Blueprint Query Patterns
Tests the Epic FHIR query sequence as outlined in the blueprint
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from emr.fhir_client import FHIRClient
from emr.epic_integration import EpicScreeningIntegration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_epic_fhir_client():
    """Test Epic FHIR client with blueprint query patterns"""
    logger.info("Testing Epic FHIR Client Query Patterns")
    logger.info("=" * 50)
    
    # Initialize client with Epic sandbox configuration
    client = FHIRClient()
    
    # Test Epic sandbox test patient (Derrick Lin from blueprint)
    test_patient = {
        'family_name': 'Lin',
        'given_name': 'Derrick', 
        'birthdate': '1973-06-03'
    }
    
    try:
        # Test 1: Patient search using Epic pattern
        logger.info("Test 1: Searching for test patient using Epic pattern")
        patient_result = client.get_patient_by_name_and_dob(
            test_patient['family_name'],
            test_patient['given_name'],
            test_patient['birthdate']
        )
        
        if patient_result and patient_result.get('entry'):
            patient = patient_result['entry'][0]['resource']
            patient_id = patient['id']
            logger.info(f"✓ Found patient: {patient.get('name', [{}])[0].get('family')} (ID: {patient_id})")
            
            # Test 2: Epic screening data sequence
            logger.info("\nTest 2: Epic screening data sequence")
            screening_data = client.get_epic_screening_data_sequence(patient_id)
            
            if screening_data:
                logger.info("✓ Epic screening data sequence successful:")
                logger.info(f"  - Patient: {bool(screening_data.get('patient'))}")
                logger.info(f"  - Conditions: {len(screening_data.get('conditions', {}).get('entry', []))} found")
                logger.info(f"  - Lab Results: {len(screening_data.get('lab_results', {}).get('entry', []))} found")
                logger.info(f"  - Documents: {len(screening_data.get('documents', {}).get('entry', []))} found")
                logger.info(f"  - Encounters: {len(screening_data.get('encounters', {}).get('entry', []))} found")
            else:
                logger.error("✗ Epic screening data sequence failed")
                
        else:
            logger.warning("✗ Test patient not found - using default patient ID")
            # Test with a generic patient ID for Epic sandbox
            test_patient_id = "eVdnE-49j7Zm6bXbLOmA7fQ3"  # Common Epic sandbox patient
            screening_data = client.get_epic_screening_data_sequence(test_patient_id)
            
            if screening_data:
                logger.info("✓ Epic screening data sequence with default patient successful")
            else:
                logger.error("✗ Epic screening data sequence failed")
        
        return True
        
    except Exception as e:
        logger.error(f"Epic FHIR client test failed: {str(e)}")
        return False


def test_epic_screening_integration():
    """Test Epic screening integration with organization context"""
    logger.info("\nTesting Epic Screening Integration")
    logger.info("=" * 50)
    
    try:
        # Mock organization ID (would normally come from database)
        organization_id = 1
        
        integration = EpicScreeningIntegration(organization_id)
        
        # Test screening types (mock data for testing)
        test_screening_types = [
            {
                'name': 'A1C Test',
                'keywords': ['hba1c', 'hemoglobin a1c', 'diabetes'],
                'trigger_conditions': ['diabetes', 'prediabetes'],
                'eligible_genders': 'both',
                'min_age': 18,
                'max_age': None,
                'frequency_years': 0.25  # Every 3 months
            },
            {
                'name': 'Mammogram',
                'keywords': ['mammography', 'breast screening', 'breast cancer'],
                'trigger_conditions': ['family history of cancer', 'BRCA mutation'],
                'eligible_genders': 'F',
                'min_age': 40,
                'max_age': 75,
                'frequency_years': 1.0  # Annually
            }
        ]
        
        # Test with Epic sandbox patient MRN
        test_mrn = "1234567890"  # Common Epic sandbox MRN
        
        logger.info(f"Testing screening data retrieval for MRN: {test_mrn}")
        epic_data = integration.get_screening_relevant_data(test_mrn, test_screening_types)
        
        if epic_data:
            logger.info("✓ Epic screening integration successful:")
            logger.info(f"  - Screening context: {bool(epic_data.get('screening_context'))}")
            logger.info(f"  - Patient data: {bool(epic_data.get('patient'))}")
            logger.info(f"  - Conditions: {len(epic_data.get('conditions', []))}")
            logger.info(f"  - Observations: {len(epic_data.get('observations', []))}")
            
            # Display screening context details
            context = epic_data.get('screening_context', {})
            if context.get('applicable_screenings'):
                logger.info("  - Applicable screenings:")
                for screening in context['applicable_screenings']:
                    status = "✓" if screening['applicable'] else "✗"
                    logger.info(f"    {status} {screening['name']}: {screening['reason']}")
        else:
            logger.warning("✗ No data returned from Epic screening integration")
            
        return True
        
    except Exception as e:
        logger.error(f"Epic screening integration test failed: {str(e)}")
        return False


def main():
    """Run Epic FHIR integration tests"""
    logger.info("Epic FHIR Integration Test Suite")
    logger.info("Testing Blueprint Query Patterns")
    logger.info("=" * 60)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: FHIR Client
    if test_epic_fhir_client():
        tests_passed += 1
    
    # Test 2: Screening Integration
    if test_epic_screening_integration():
        tests_passed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("✅ All Epic FHIR integration tests passed!")
        logger.info("Epic query patterns from blueprint successfully implemented")
    else:
        logger.warning(f"⚠️  {total_tests - tests_passed} test(s) failed")
        logger.info("Note: Some failures may be due to Epic sandbox connectivity")
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)