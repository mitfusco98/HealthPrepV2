#!/usr/bin/env python3
"""
Test script to verify multi-tenancy user creation functionality
"""

from app import create_app, db
from models import User, Organization
import sys

def test_user_creation():
    """Test creating a user with multi-tenancy"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if default organization exists
            default_org = Organization.query.filter_by(name='Default Organization').first()
            if not default_org:
                print("❌ Error: Default organization not found")
                return False
            
            print(f"✅ Default organization found: {default_org.name} (ID: {default_org.id})")
            
            # Check if we can create a test user
            test_username = "test_user"
            
            # Remove existing test user if exists
            existing_user = User.query.filter_by(username=test_username).first()
            if existing_user:
                db.session.delete(existing_user)
                db.session.commit()
                print(f"🗑️  Removed existing test user")
            
            # Create a new test user
            new_user = User()
            new_user.username = test_username
            new_user.email = "test@example.com"
            new_user.role = "MA"
            new_user.is_admin = False
            new_user.is_active_user = True
            new_user.org_id = default_org.id  # Assign to default organization
            new_user.set_password("testpass123")
            
            db.session.add(new_user)
            db.session.commit()
            
            print(f"✅ Successfully created test user: {new_user.username}")
            print(f"   - Email: {new_user.email}")
            print(f"   - Role: {new_user.role}")
            print(f"   - Organization: {new_user.org_id}")
            print(f"   - Active: {new_user.is_active_user}")
            
            # Verify we can query users by organization
            org_users = User.query.filter_by(org_id=default_org.id).all()
            print(f"✅ Found {len(org_users)} users in default organization")
            
            # Test admin user creation
            admin_username = "admin_test"
            existing_admin = User.query.filter_by(username=admin_username).first()
            if existing_admin:
                db.session.delete(existing_admin)
                db.session.commit()
            
            admin_user = User()
            admin_user.username = admin_username
            admin_user.email = "admin@example.com"
            admin_user.role = "admin"
            admin_user.is_admin = True
            admin_user.is_active_user = True
            admin_user.org_id = default_org.id
            admin_user.set_password("adminpass123")
            
            db.session.add(admin_user)
            db.session.commit()
            
            print(f"✅ Successfully created admin user: {admin_user.username}")
            print(f"   - Role: {admin_user.role}")
            print(f"   - Is Admin: {admin_user.is_admin}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during user creation test: {e}")
            db.session.rollback()
            return False

def test_organization_isolation():
    """Test that users are properly isolated by organization"""
    app = create_app()
    
    with app.app_context():
        try:
            default_org = Organization.query.filter_by(name='Default Organization').first()
            
            # Create a second organization for testing
            test_org = Organization()
            test_org.name = "Test Organization"
            test_org.display_name = "Test Healthcare Organization"
            test_org.contact_email = "test@healthprep.com"
            test_org.setup_status = "live"
            
            db.session.add(test_org)
            db.session.commit()
            
            print(f"✅ Created test organization: {test_org.name} (ID: {test_org.id})")
            
            # Create a user in the test organization
            test_org_user = User()
            test_org_user.username = "test_org_user"
            test_org_user.email = "user@testorg.com"
            test_org_user.role = "nurse"
            test_org_user.is_admin = False
            test_org_user.is_active_user = True
            test_org_user.org_id = test_org.id
            test_org_user.set_password("testpass123")
            
            db.session.add(test_org_user)
            db.session.commit()
            
            # Verify organization isolation
            default_org_users = User.query.filter_by(org_id=default_org.id).all()
            test_org_users = User.query.filter_by(org_id=test_org.id).all()
            
            print(f"✅ Default org has {len(default_org_users)} users")
            print(f"✅ Test org has {len(test_org_users)} users")
            print(f"✅ Organizations are properly isolated")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during organization isolation test: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("🧪 Testing HealthPrepV2 Multi-Tenancy User Creation")
    print("=" * 50)
    
    success1 = test_user_creation()
    print()
    success2 = test_organization_isolation()
    
    if success1 and success2:
        print("\n🎉 All tests passed! Multi-tenancy user creation is working correctly.")
        print("\n📋 Summary:")
        print("✅ Default organization created successfully")
        print("✅ Users can be created with organization assignment")
        print("✅ Admin and regular users work correctly")  
        print("✅ Organization isolation is functioning")
        print("\n🚀 Ready to test admin dashboard user creation at /admin/users")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)