#!/usr/bin/env python3
"""
Test Epic DocumentReference API calls directly
Investigates document retrieval issues despite successful patient sync
"""

import sys
import os
sys.path.append('.')

from app import db, create_app
import os
os.environ.setdefault('FLASK_ENV', 'development')
from models import Organization, Patient, EpicCredentials, FHIRDocument
from emr.fhir_client import FHIRClient
from services.epic_fhir_service import EpicFHIRService
from services.comprehensive_emr_sync import ComprehensiveEMRSync
import logging
import json
import requests

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_epic_document_retrieval():
    """Test Epic document retrieval pipeline step by step"""
    
    app = create_app()
    with app.app_context():
        print("="*80)
        print("EPIC DOCUMENT RETRIEVAL DIAGNOSIS")
        print("="*80)
        
        # Step 1: Check organization and credentials
        org = Organization.query.get(1)  # Default Organization
        if not org:
            print("❌ No organization found")
            return
        
        print(f"✅ Organization: {org.name}")
        print(f"   Epic Client ID: {org.epic_client_id}")
        print(f"   Epic Connected: {org.is_epic_connected}")
        print(f"   Last Epic Sync: {org.last_epic_sync}")
        print(f"   Last Epic Error: {org.last_epic_error}")
        
        # Step 2: Check Epic credentials
        epic_creds = EpicCredentials.query.filter_by(org_id=org.id).first()
        if not epic_creds:
            print("❌ No Epic credentials found")
            return
        
        print(f"✅ Epic Credentials found:")
        print(f"   Has Access Token: {bool(epic_creds.access_token)}")
        print(f"   Has Refresh Token: {bool(epic_creds.refresh_token)}")
        print(f"   Token Expires: {epic_creds.token_expires_at}")
        print(f"   Is Expired: {epic_creds.is_expired}")
        print(f"   Expires Soon: {epic_creds.expires_soon}")
        
        # Step 3: Check patients
        patients = Patient.query.filter_by(org_id=org.id).all()
        print(f"✅ Patients found: {len(patients)}")
        if not patients:
            print("❌ No patients to test document retrieval")
            return
        
        test_patient = patients[0]
        print(f"   Testing with patient: {test_patient.name}")
        print(f"   Epic Patient ID: {test_patient.epic_patient_id}")
        print(f"   MRN: {test_patient.mrn}")
        
        # Step 4: Test EpicFHIRService authentication
        print("\n" + "="*50)
        print("TESTING EPIC FHIR SERVICE AUTHENTICATION")
        print("="*50)
        
        epic_service = EpicFHIRService(org.id)
        print(f"   FHIR Client exists: {bool(epic_service.fhir_client)}")
        
        if epic_service.fhir_client:
            print(f"   FHIR Client access token: {bool(epic_service.fhir_client.access_token)}")
            print(f"   FHIR Client base URL: {epic_service.fhir_client.base_url}")
            
            # Test authentication
            auth_result = epic_service.ensure_authenticated()
            print(f"   Authentication result: {auth_result}")
            
            if not auth_result:
                print("❌ FHIR Service authentication failed")
                print("   This is the root cause - investigating...")
                
                # Debug: Check if tokens are being loaded
                if hasattr(epic_service.fhir_client, 'access_token'):
                    print(f"   FHIR client access_token: {bool(epic_service.fhir_client.access_token)}")
                if hasattr(epic_service.fhir_client, 'token_expires'):
                    print(f"   FHIR client token_expires: {epic_service.fhir_client.token_expires}")
        
        # Step 5: Test direct FHIR client creation
        print("\n" + "="*50)
        print("TESTING DIRECT FHIR CLIENT")
        print("="*50)
        
        # Create FHIR client directly with organization config
        epic_config = {
            'epic_client_id': org.epic_client_id,
            'epic_client_secret': org.epic_client_secret,
            'epic_fhir_url': org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        }
        
        direct_client = FHIRClient(epic_config, organization=org)
        print(f"✅ Direct FHIR client created")
        print(f"   Base URL: {direct_client.base_url}")
        print(f"   Client ID: {direct_client.client_id}")
        
        # Load tokens manually
        if epic_creds.access_token:
            from datetime import datetime, timedelta
            expires_in = int((epic_creds.token_expires_at - datetime.utcnow()).total_seconds()) if epic_creds.token_expires_at else 3600
            
            direct_client.access_token = epic_creds.access_token
            direct_client.refresh_token = epic_creds.refresh_token
            direct_client.token_expires = epic_creds.token_expires_at
            
            print(f"✅ Tokens loaded manually")
            print(f"   Token expires in: {expires_in} seconds")
            
            # Step 6: Test DocumentReference API call directly
            print("\n" + "="*50)
            print("TESTING EPIC DOCUMENTREFERENCE API")
            print("="*50)
            
            try:
                # Test with the first patient
                patient_id = test_patient.epic_patient_id
                print(f"   Testing DocumentReference API for patient: {patient_id}")
                
                documents = direct_client.get_document_references(patient_id)
                print(f"   API call result: {type(documents)}")
                
                if documents:
                    print(f"   Documents returned: {json.dumps(documents, indent=2)[:500]}...")
                    
                    # Count entries
                    entry_count = len(documents.get('entry', [])) if documents.get('entry') else 0
                    print(f"   Document entries found: {entry_count}")
                    
                    if entry_count == 0:
                        print("⚠️  Epic sandbox may have no documents for test patients")
                        print("   This could be the root cause - sandbox limitation")
                else:
                    print("❌ No documents returned from Epic API")
                    
            except Exception as e:
                logger.error(f"DocumentReference API call failed: {str(e)}")
                print(f"❌ DocumentReference API call failed: {str(e)}")
        
        # Step 7: Test comprehensive sync
        print("\n" + "="*50)
        print("TESTING COMPREHENSIVE EMR SYNC")
        print("="*50)
        
        try:
            sync_service = ComprehensiveEMRSync(org.id)
            print(f"✅ ComprehensiveEMRSync created")
            
            # Test if it has authentication
            auth_result = sync_service.epic_service.ensure_authenticated()
            print(f"   Sync service authentication: {auth_result}")
            
            if auth_result:
                # Test document sync for first patient
                result = sync_service._sync_patient_documents(
                    test_patient, 
                    None,  # last_encounter_date
                    sync_service._get_default_sync_options()
                )
                print(f"   Document sync result: {result}")
            else:
                print("❌ Comprehensive sync authentication failed")
                
        except Exception as e:
            logger.error(f"Comprehensive sync test failed: {str(e)}")
            print(f"❌ Comprehensive sync test failed: {str(e)}")
        
        # Step 8: Database document check
        print("\n" + "="*50)
        print("CURRENT DATABASE STATE")
        print("="*50)
        
        fhir_docs = FHIRDocument.query.filter_by(org_id=org.id).all()
        print(f"   FHIR Documents in database: {len(fhir_docs)}")
        
        for doc in fhir_docs[:5]:  # Show first 5
            print(f"     - {doc.epic_document_id}: {doc.title}")

if __name__ == "__main__":
    test_epic_document_retrieval()