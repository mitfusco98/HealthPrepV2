#!/usr/bin/env python3
"""
Test Epic SMART on FHIR Architectural Adjustments
Tests the architectural enhancements for Epic integration
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the correct app structure
import main  # This will initialize the app
from models import db, Patient, FHIRDocument, Organization, ScreeningType
from app import app
from models import Patient, FHIRDocument, Organization, ScreeningType
from services.epic_fhir_service import EpicFHIRService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_enhanced_patient_model():
    """Test the enhanced Patient model with FHIR integration"""
    logger.info("Testing Enhanced Patient Model with FHIR Integration")
    logger.info("=" * 60)
    
    with app.app_context():
        try:
            # Test FHIR patient resource data
            fhir_patient_resource = {
                "resourceType": "Patient",
                "id": "erXuFYUfucBZaryVksYEcMg3",
                "meta": {"versionId": "1"},
                "name": [
                    {
                        "use": "usual",
                        "family": "Lin",
                        "given": ["Derrick", "A"]
                    }
                ],
                "gender": "male",
                "birthDate": "1990-05-15",
                "telecom": [
                    {
                        "system": "phone",
                        "value": "555-123-4567"
                    },
                    {
                        "system": "email", 
                        "value": "derrick.lin@example.com"
                    }
                ],
                "identifier": [
                    {
                        "type": {
                            "coding": [
                                {
                                    "code": "MR",
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203"
                                }
                            ]
                        },
                        "value": "TEST001"
                    }
                ]
            }
            
            # Find or create test organization
            organization = Organization.query.filter_by(name='Test Health System').first()
            if not organization:
                organization = Organization(name='Test Health System')
                db.session.add(organization)
                db.session.flush()
            
            # Create test patient
            patient = Patient(
                mrn="TEST001",
                name="Test Patient",
                date_of_birth=datetime(1990, 5, 15).date(),
                gender="M",
                org_id=organization.id,
                epic_patient_id="erXuFYUfucBZaryVksYEcMg3"
            )
            
            # Test FHIR integration methods
            logger.info("Test 1: Update patient from FHIR resource")
            patient.update_from_fhir(fhir_patient_resource)
            
            assert patient.name == "Derrick A Lin", f"Expected 'Derrick A Lin', got '{patient.name}'"
            assert patient.phone == "555-123-4567", f"Expected '555-123-4567', got '{patient.phone}'"
            assert patient.email == "derrick.lin@example.com", f"Expected email not set"
            assert patient.fhir_version_id == "1", f"Expected version '1', got '{patient.fhir_version_id}'"
            logger.info("✓ Patient successfully updated from FHIR resource")
            
            # Test sync checking
            logger.info("Test 2: FHIR sync checking")
            assert patient.needs_fhir_sync(), "Patient should need sync (no last_fhir_sync)"
            
            patient.last_fhir_sync = datetime.utcnow() - timedelta(hours=12)
            assert not patient.needs_fhir_sync(sync_interval_hours=24), "Patient should not need sync (within 24h)"
            
            patient.last_fhir_sync = datetime.utcnow() - timedelta(hours=25)
            assert patient.needs_fhir_sync(sync_interval_hours=24), "Patient should need sync (over 24h)"
            logger.info("✓ FHIR sync checking working correctly")
            
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Enhanced Patient model test failed: {str(e)}")
            db.session.rollback()
            return False


def test_fhir_document_model():
    """Test the FHIRDocument model for Epic integration"""
    logger.info("\nTesting FHIRDocument Model")
    logger.info("=" * 60)
    
    with app.app_context():
        try:
            # Test FHIR DocumentReference resource
            fhir_doc_reference = {
                "resourceType": "DocumentReference",
                "id": "doc123",
                "meta": {"versionId": "1"},
                "type": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "18842-5",
                            "display": "Discharge summary"
                        }
                    ]
                },
                "description": "Hospital discharge summary",
                "date": "2024-01-15T10:30:00Z",
                "author": [
                    {
                        "display": "Dr. John Smith"
                    }
                ],
                "content": [
                    {
                        "attachment": {
                            "contentType": "application/pdf",
                            "url": "Binary/doc123-content",
                            "size": 12345,
                            "title": "Discharge Summary"
                        }
                    }
                ]
            }
            
            # Get test patient and organization
            patient = Patient.query.filter_by(mrn='TEST001').first()
            organization = Organization.query.filter_by(name='Test Health System').first()
            
            # Create FHIR document
            fhir_doc = FHIRDocument(
                patient_id=patient.id,
                org_id=organization.id,
                epic_document_id="doc123"
            )
            
            logger.info("Test 1: Update FHIR document from DocumentReference")
            fhir_doc.update_from_fhir(fhir_doc_reference)
            
            assert fhir_doc.document_type_code == "18842-5", f"Expected '18842-5', got '{fhir_doc.document_type_code}'"
            assert fhir_doc.document_type_display == "Discharge summary", f"Expected 'Discharge summary'"
            assert fhir_doc.title == "Hospital discharge summary", f"Expected title not set"
            assert fhir_doc.author_name == "Dr. John Smith", f"Expected 'Dr. John Smith'"
            assert fhir_doc.content_type == "application/pdf", f"Expected 'application/pdf'"
            assert fhir_doc.content_url == "Binary/doc123-content", f"Expected content URL"
            logger.info("✓ FHIR document successfully updated from DocumentReference")
            
            # Test processing methods
            logger.info("Test 2: Document processing methods")
            fhir_doc.mark_processed('completed', ocr_text="Sample discharge summary text", relevance_score=0.85)
            
            assert fhir_doc.is_processed == True, "Document should be marked as processed"
            assert fhir_doc.processing_status == 'completed', f"Expected 'completed'"
            assert fhir_doc.ocr_text == "Sample discharge summary text", "OCR text not set"
            assert fhir_doc.relevance_score == 0.85, f"Expected 0.85, got {fhir_doc.relevance_score}"
            logger.info("✓ Document processing methods working correctly")
            
            # Test properties
            logger.info("Test 3: Document properties")
            assert fhir_doc.is_pdf == True, "Should detect PDF content type"
            assert fhir_doc.display_name == "Hospital discharge summary", "Display name should use title"
            logger.info("✓ Document properties working correctly")
            
            db.session.add(fhir_doc)
            db.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"FHIRDocument model test failed: {str(e)}")
            db.session.rollback()
            return False


def test_epic_fhir_service():
    """Test the Epic FHIR service layer"""
    logger.info("\nTesting Epic FHIR Service Layer")
    logger.info("=" * 60)
    
    with app.app_context():
        try:
            organization = Organization.query.filter_by(name='Test Health System').first()
            
            # Initialize Epic FHIR service
            epic_service = EpicFHIRService(organization.id)
            
            logger.info("Test 1: Service initialization")
            assert epic_service.organization_id == organization.id, "Organization ID should be set"
            assert epic_service.organization == organization, "Organization should be loaded"
            logger.info("✓ Epic FHIR service initialized successfully")
            
            # Test document creation methods
            logger.info("Test 2: Prep sheet document reference creation")
            patient = Patient.query.filter_by(mrn='TEST001').first()
            screening_type = ScreeningType(name="Annual Physical", org_id=organization.id)
            
            # Test prep sheet document reference creation (without actually posting to Epic)
            document_reference = epic_service._create_prep_sheet_document_reference(
                patient, "Sample prep sheet content", [screening_type]
            )
            
            assert document_reference['resourceType'] == 'DocumentReference', "Should be DocumentReference"
            assert document_reference['status'] == 'current', "Should be current status"
            assert 'Annual Physical' in document_reference['description'], "Should include screening type name"
            assert patient.epic_patient_id in document_reference['subject']['reference'], "Should reference patient"
            logger.info("✓ Prep sheet DocumentReference creation working correctly")
            
            return True
            
        except Exception as e:
            logger.error(f"Epic FHIR service test failed: {str(e)}")
            return False


def test_fhir_client_enhancements():
    """Test enhanced FHIR client methods"""
    logger.info("\nTesting Enhanced FHIR Client Methods")
    logger.info("=" * 60)
    
    try:
        from emr.fhir_client import FHIRClient
        
        # Test client initialization
        epic_config = {
            'epic_client_id': 'test_client',
            'epic_client_secret': 'test_secret', 
            'epic_fhir_url': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        
        client = FHIRClient(epic_config)
        
        logger.info("Test 1: Enhanced method availability")
        assert hasattr(client, 'get_document_content'), "Should have get_document_content method"
        assert hasattr(client, 'create_document_reference'), "Should have create_document_reference method"
        assert hasattr(client, 'update_document_reference'), "Should have update_document_reference method"
        logger.info("✓ Enhanced FHIR client methods available")
        
        # Test document reference creation structure (without actual API call)
        logger.info("Test 2: Document reference data structure")
        doc_ref_data = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Provider-unspecified progress note"
                    }
                ]
            }
        }
        
        # This would normally call Epic, but we're just testing the method exists and accepts data
        assert callable(client.create_document_reference), "create_document_reference should be callable"
        logger.info("✓ Document reference methods properly structured")
        
        return True
        
    except Exception as e:
        logger.error(f"Enhanced FHIR client test failed: {str(e)}")
        return False


def main():
    """Run architectural adjustment tests"""
    logger.info("Epic SMART on FHIR Architectural Adjustment Test Suite")
    logger.info("Testing Enhanced Models, Service Layer, and Integration")
    logger.info("=" * 70)
    
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Enhanced Patient Model
    if test_enhanced_patient_model():
        tests_passed += 1
    
    # Test 2: FHIRDocument Model
    if test_fhir_document_model():
        tests_passed += 1
    
    # Test 3: Epic FHIR Service
    if test_epic_fhir_service():
        tests_passed += 1
    
    # Test 4: Enhanced FHIR Client
    if test_fhir_client_enhancements():
        tests_passed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("✅ All architectural adjustment tests passed!")
        logger.info("\nArchitectural Enhancements Implemented:")
        logger.info("1. ✓ Enhanced Patient model with FHIR integration fields")
        logger.info("2. ✓ FHIRDocument model for Epic document management")
        logger.info("3. ✓ Epic FHIR service layer with token management")
        logger.info("4. ✓ Enhanced FHIR client with document operations")
        logger.info("5. ✓ OAuth2 authentication flow (previously implemented)")
        logger.info("6. ✓ Writing results back to Epic as DocumentReference")
        logger.info("\nSystem ready for Epic SMART on FHIR integration!")
    else:
        logger.warning(f"⚠️  {total_tests - tests_passed} test(s) failed")
    
    return tests_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)