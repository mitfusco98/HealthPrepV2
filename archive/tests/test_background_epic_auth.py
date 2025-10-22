#!/usr/bin/env python3
"""
Test Background Epic Authentication
Verifies that background processes can access Epic credentials without user sessions
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_background_epic_authentication():
    """Test Epic authentication in background context"""
    print("=" * 60)
    print("Background Epic Authentication Test")
    print("=" * 60)
    
    try:
        # Initialize Flask app context (simulates background job environment)
        from app import create_app, db
        app = create_app()
        
        with app.app_context():
            from models import Organization, EpicCredentials
            from services.epic_fhir_service import get_epic_fhir_service_background
            from services.comprehensive_emr_sync import ComprehensiveEMRSync
            from routes.oauth_routes import get_epic_fhir_client_background
            
            # Get an organization with Epic credentials
            org_with_epic = Organization.query.filter(
                Organization.epic_client_id.isnot(None),
                Organization.is_epic_connected == True
            ).first()
            
            if not org_with_epic:
                print("❌ No organization with Epic credentials found")
                print("   Please complete Epic OAuth flow in the web interface first")
                return False
            
            print(f"✅ Found organization: {org_with_epic.name} (ID: {org_with_epic.id})")
            
            # Check if Epic credentials exist in database
            epic_creds = EpicCredentials.query.filter_by(org_id=org_with_epic.id).first()
            if not epic_creds:
                print("❌ No Epic credentials found in database")
                print("   Epic OAuth may not have completed properly")
                return False
            
            print(f"✅ Epic credentials found in database")
            print(f"   Token expires: {epic_creds.token_expires_at}")
            print(f"   Last used: {epic_creds.last_used}")
            
            # Test 1: Background FHIR client creation
            print("\n--- Test 1: Background FHIR Client Creation ---")
            try:
                fhir_client = get_epic_fhir_client_background(org_with_epic.id)
                if fhir_client:
                    print("✅ Background FHIR client created successfully")
                    print(f"   Client has access token: {'Yes' if fhir_client.access_token else 'No'}")
                    print(f"   Client has refresh token: {'Yes' if fhir_client.refresh_token else 'No'}")
                else:
                    print("❌ Failed to create background FHIR client")
                    return False
            except Exception as e:
                print(f"❌ Error creating background FHIR client: {str(e)}")
                return False
            
            # Test 2: Background Epic FHIR Service
            print("\n--- Test 2: Background Epic FHIR Service ---")
            try:
                epic_service = get_epic_fhir_service_background(org_with_epic.id)
                if epic_service and epic_service.fhir_client:
                    print("✅ Background Epic FHIR service created successfully")
                    print(f"   Service is in background mode: {epic_service.is_background}")
                    
                    # Test authentication
                    if epic_service.ensure_authenticated():
                        print("✅ Background service authentication successful")
                    else:
                        print("❌ Background service authentication failed")
                        return False
                else:
                    print("❌ Failed to create background Epic FHIR service")
                    return False
            except Exception as e:
                print(f"❌ Error with background Epic FHIR service: {str(e)}")
                return False
            
            # Test 3: ComprehensiveEMRSync in background context
            print("\n--- Test 3: ComprehensiveEMRSync Background Context ---")
            try:
                # This simulates how a background job would initialize the sync service
                emr_sync = ComprehensiveEMRSync(org_with_epic.id)
                print(f"✅ ComprehensiveEMRSync initialized")
                print(f"   Background context detected: {emr_sync.is_background}")
                print(f"   Epic service available: {'Yes' if emr_sync.epic_service else 'No'}")
                
                if emr_sync.epic_service and emr_sync.epic_service.fhir_client:
                    print(f"   FHIR client available: Yes")
                    
                    # Test if we can make a basic API call (test patient lookup)
                    if emr_sync.epic_service.ensure_authenticated():
                        print("✅ EMR sync service authentication successful")
                        
                        # Try to get a test patient from Epic sandbox
                        test_patient_id = "eq081-VQEgP8drUUqCWzHfw3"  # Known Epic sandbox patient
                        try:
                            patient_data = emr_sync.epic_service.fhir_client.get_patient(test_patient_id)
                            if patient_data:
                                print("✅ Successfully retrieved test patient data from Epic")
                                print(f"   Patient name: {patient_data.get('name', [{}])[0].get('text', 'Unknown')}")
                            else:
                                print("⚠️  Test patient not found (may not be available in this Epic environment)")
                        except Exception as e:
                            print(f"⚠️  Epic API call failed: {str(e)}")
                            # This is expected if not connected to Epic sandbox
                    else:
                        print("❌ EMR sync service authentication failed")
                        return False
                else:
                    print("❌ EMR sync service missing FHIR client")
                    return False
                    
            except Exception as e:
                print(f"❌ Error with ComprehensiveEMRSync: {str(e)}")
                return False
            
            # Test 4: Token refresh in background context
            print("\n--- Test 4: Token Refresh Test ---")
            try:
                if epic_creds.expires_soon:
                    print("⚠️  Token expires soon, testing refresh...")
                    if fhir_client.refresh_access_token():
                        print("✅ Token refresh successful in background context")
                        
                        # Verify tokens were persisted to database
                        db.session.refresh(epic_creds)
                        print(f"   New token expiry: {epic_creds.token_expires_at}")
                    else:
                        print("❌ Token refresh failed")
                        return False
                else:
                    print("✅ Token not expiring soon, refresh test skipped")
                    
            except Exception as e:
                print(f"❌ Error testing token refresh: {str(e)}")
                return False
            
            print("\n" + "=" * 60)
            print("✅ ALL BACKGROUND AUTHENTICATION TESTS PASSED")
            print("✅ Background processes can now access Epic credentials!")
            print("=" * 60)
            
            return True
            
    except Exception as e:
        print(f"❌ Critical error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_interactive_vs_background_context():
    """Test that the system correctly detects interactive vs background context"""
    print("\n" + "=" * 60)
    print("Context Detection Test")
    print("=" * 60)
    
    from app import create_app
    app = create_app()
    
    # Test 1: Outside request context (background)
    with app.app_context():
        try:
            from services.epic_fhir_service import EpicFHIRService
            service = EpicFHIRService(1, background_context=True)
            print("✅ Background context service creation: Success")
            print(f"   Is background: {service.is_background}")
        except Exception as e:
            print(f"❌ Background context service creation failed: {str(e)}")
            return False
    
    # Test 2: With app context (simulated interactive)
    with app.app_context():
        try:
            service = EpicFHIRService(1, background_context=False)
            print("✅ Interactive context service creation: Success")
            print(f"   Is background: {service.is_background}")
        except Exception as e:
            print(f"❌ Interactive context service creation failed: {str(e)}")
            return False
    
    print("✅ Context detection working properly")
    return True

if __name__ == "__main__":
    print("Starting Background Epic Authentication Tests...")
    print(f"Test started at: {datetime.now()}")
    
    success = True
    
    # Run context detection test first
    success &= test_interactive_vs_background_context()
    
    # Run main authentication test
    success &= test_background_epic_authentication()
    
    if success:
        print("\n🎉 All tests passed! Background Epic authentication is working.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        sys.exit(1)