
#!/usr/bin/env python3
"""
Utility script to clean up orphaned test organization and user
"""

from app import create_app, db
from models import User, Organization
import sys

def cleanup_test_org():
    """Clean up test organization and orphaned users"""
    app = create_app()
    
    with app.app_context():
        try:
            # Find test organization
            test_org = Organization.query.filter_by(name='Test Organization').first()
            if not test_org:
                print("❌ Test Organization not found")
                return False
            
            print(f"📋 Found Test Organization (ID: {test_org.id})")
            
            # Find all users in test organization
            test_users = User.query.filter_by(org_id=test_org.id).all()
            print(f"👥 Found {len(test_users)} users in Test Organization:")
            
            for user in test_users:
                print(f"   - {user.username} ({user.email}) - Role: {user.role}")
                print(f"     Created: {user.created_at}")
                print(f"     Last Login: {user.last_login}")
                print(f"     Last Activity: {user.last_activity}")
            
            # Ask for confirmation
            response = input("\n⚠️  Do you want to delete the Test Organization and all its users? (yes/no): ")
            
            if response.lower() != 'yes':
                print("❌ Operation cancelled")
                return False
            
            # Delete users first (due to foreign key constraints)
            for user in test_users:
                print(f"🗑️  Deleting user: {user.username}")
                db.session.delete(user)
            
            # Delete the organization
            print(f"🗑️  Deleting organization: {test_org.name}")
            db.session.delete(test_org)
            
            # Commit the changes
            db.session.commit()
            
            print("✅ Test Organization and all users deleted successfully!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during cleanup: {e}")
            return False

def create_admin_for_test_org():
    """Alternative: Create an admin user for the test organization"""
    app = create_app()
    
    with app.app_context():
        try:
            # Find test organization
            test_org = Organization.query.filter_by(name='Test Organization').first()
            if not test_org:
                print("❌ Test Organization not found")
                return False
            
            print(f"📋 Found Test Organization (ID: {test_org.id})")
            
            # Check if admin already exists
            existing_admin = User.query.filter_by(org_id=test_org.id, role='admin').first()
            if existing_admin:
                print(f"✅ Admin user already exists: {existing_admin.username}")
                return True
            
            # Create admin user
            admin_username = input("Enter username for new admin: ")
            admin_email = input("Enter email for new admin: ")
            admin_password = input("Enter password for new admin: ")
            
            # Check if username already exists in the organization
            existing_user = User.query.filter_by(username=admin_username, org_id=test_org.id).first()
            if existing_user:
                print(f"❌ Username {admin_username} already exists in this organization")
                return False
            
            admin_user = User()
            admin_user.username = admin_username
            admin_user.email = admin_email
            admin_user.role = 'admin'
            admin_user.is_admin = True
            admin_user.is_active_user = True
            admin_user.org_id = test_org.id
            admin_user.set_password(admin_password)
            
            db.session.add(admin_user)
            db.session.commit()
            
            print(f"✅ Admin user created successfully: {admin_user.username}")
            print(f"   Organization: {test_org.name}")
            print(f"   You can now log in and manage users through the admin dashboard")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating admin user: {e}")
            return False

def main():
    """Main function to handle user choice"""
    print("🧹 Test Organization Cleanup Utility")
    print("=" * 40)
    print("1. Delete Test Organization and all users")
    print("2. Create admin user for Test Organization")
    print("3. Exit")
    
    choice = input("\nSelect an option (1-3): ")
    
    if choice == '1':
        cleanup_test_org()
    elif choice == '2':
        create_admin_for_test_org()
    elif choice == '3':
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
