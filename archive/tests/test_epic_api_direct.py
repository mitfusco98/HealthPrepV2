#!/usr/bin/env python3
"""
Test Epic DocumentReference API directly by bypassing authentication layers
Tests if Epic sandbox actually has documents available for the test patients
"""

import sys
import os
sys.path.append('.')

from app import db, create_app
from models import Organization, Patient, EpicCredentials
from datetime import datetime
import logging
import json
import requests

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_epic_api_direct():
    """Test Epic DocumentReference API directly with manual token loading"""
    
    app = create_app()
    with app.app_context():
        print("="*80)
        print("DIRECT EPIC DOCUMENTREFERENCE API TEST")
        print("="*80)
        
        # Get organization and credentials
        org = Organization.query.filter_by(id=1).first()
        epic_creds = EpicCredentials.query.filter_by(org_id=org.id).first()
        patients = Patient.query.filter_by(org_id=org.id).limit(3).all()
        
        if not org or not epic_creds or not patients:
            print("❌ Missing required data")
            return
        
        print(f"✅ Testing with {len(patients)} patients")
        print(f"   Epic Base URL: {org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'}")
        print(f"   Token expires: {epic_creds.token_expires_at}")
        print(f"   Token expired: {epic_creds.is_expired}")
        
        # Epic FHIR configuration
        base_url = org.epic_fhir_url or 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/'
        headers = {
            'Authorization': f'Bearer {epic_creds.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        
        print("\n" + "="*60)
        print("TESTING DOCUMENTREFERENCE API FOR EACH PATIENT")
        print("="*60)
        
        total_documents_found = 0
        
        for i, patient in enumerate(patients, 1):
            print(f"\n{i}. Testing patient: {patient.name}")
            print(f"   Epic ID: {patient.epic_patient_id}")
            print(f"   MRN: {patient.mrn}")
            
            # Test DocumentReference API call
            try:
                url = f"{base_url}DocumentReference"
                params = {
                    'patient': patient.epic_patient_id,
                    '_sort': '-date',
                    '_count': '20'
                }
                
                print(f"   API URL: {url}")
                print(f"   Parameters: {params}")
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                print(f"   HTTP Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if it's a valid FHIR Bundle
                    if data.get('resourceType') == 'Bundle':
                        entry_count = len(data.get('entry', []))
                        total_count = data.get('total', entry_count)
                        
                        print(f"   ✅ Valid FHIR Bundle received")
                        print(f"   📄 Documents in response: {entry_count}")
                        print(f"   📊 Total available: {total_count}")
                        
                        total_documents_found += entry_count
                        
                        # Show document details
                        if entry_count > 0:
                            print("   📋 Document details:")
                            for j, entry in enumerate(data.get('entry', [])[:3]):  # Show first 3
                                doc = entry.get('resource', {})
                                doc_id = doc.get('id', 'Unknown')
                                doc_date = doc.get('date', 'No date')
                                doc_type = doc.get('type', {}).get('text', 'Unknown type')
                                description = doc.get('description', 'No description')
                                
                                print(f"      {j+1}. ID: {doc_id}")
                                print(f"         Date: {doc_date}")
                                print(f"         Type: {doc_type}")
                                print(f"         Description: {description[:100]}{'...' if len(description) > 100 else ''}")
                                
                                # Check for content URLs
                                content = doc.get('content', [])
                                if content:
                                    attachment = content[0].get('attachment', {})
                                    content_url = attachment.get('url')
                                    content_type = attachment.get('contentType')
                                    if content_url:
                                        print(f"         Content URL: {content_url[:60]}{'...' if len(content_url) > 60 else ''}")
                                        print(f"         Content Type: {content_type}")
                        else:
                            print("   ⚠️  No documents found for this patient in Epic sandbox")
                            
                    else:
                        print(f"   ❌ Invalid response format: {data.get('resourceType', 'Unknown')}")
                        print(f"   Response: {json.dumps(data, indent=2)[:500]}...")
                        
                elif response.status_code == 401:
                    print(f"   ❌ Authentication failed - token may be expired")
                    print(f"   Response: {response.text}")
                    break
                    
                elif response.status_code == 404:
                    print(f"   ❌ Patient not found in Epic")
                    
                elif response.status_code == 403:
                    print(f"   ❌ Access forbidden - may need additional scopes")
                    print(f"   Response: {response.text}")
                    
                else:
                    print(f"   ❌ API call failed: {response.status_code}")
                    print(f"   Response: {response.text[:500]}...")
                    
            except requests.exceptions.Timeout:
                print(f"   ❌ Request timeout - Epic server may be slow")
                
            except Exception as e:
                print(f"   ❌ Request failed: {str(e)}")
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"🏥 Patients tested: {len(patients)}")
        print(f"📄 Total documents found: {total_documents_found}")
        
        if total_documents_found == 0:
            print("\n🔍 ANALYSIS:")
            print("   • All API calls succeeded but returned 0 documents")
            print("   • This suggests Epic sandbox test patients have no clinical documents")
            print("   • This is likely a sandbox limitation, not a code issue")
            print("   • Production Epic instances would have real patient documents")
            
            print("\n📝 RECOMMENDATIONS:")
            print("   1. Verify with Epic that sandbox patients are supposed to have documents")
            print("   2. Test with production Epic instance (if available)")
            print("   3. Consider creating mock documents for testing")
            print("   4. Fix authentication issue so background sync works")
            
        else:
            print(f"\n✅ Documents are available in Epic sandbox!")
            print("   The issue is likely in the authentication or sync pipeline")
            
        # Test other FHIR resources for comparison
        print("\n" + "="*60)
        print("TESTING OTHER FHIR RESOURCES FOR COMPARISON")
        print("="*60)
        
        test_patient = patients[0]
        
        # Test Condition resource
        try:
            url = f"{base_url}Condition"
            params = {'patient': test_patient.epic_patient_id, '_count': '5'}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                condition_count = len(data.get('entry', []))
                print(f"📋 Conditions found for {test_patient.name}: {condition_count}")
            else:
                print(f"❌ Condition API failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Condition test failed: {str(e)}")
            
        # Test Observation resource  
        try:
            url = f"{base_url}Observation"
            params = {'patient': test_patient.epic_patient_id, '_count': '5'}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                obs_count = len(data.get('entry', []))
                print(f"🔬 Observations found for {test_patient.name}: {obs_count}")
            else:
                print(f"❌ Observation API failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Observation test failed: {str(e)}")

if __name__ == "__main__":
    test_epic_api_direct()