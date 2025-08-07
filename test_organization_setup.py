
"""
Test script to create a default organization and admin user for testing
"""
from app import create_app, db
from models import Organization, User
from datetime import datetime

def setup_test_organization():
    """Create a test organization and admin user"""
    app = create_app()
    with app.app_context():
        try:
            # Check if default organization exists
            org = Organization.query.filter_by(name='Default Organization').first()
            if not org:
                print("Creating default organization...")
                org = Organization(
                    name='Default Organization',
                    display_name='Default Healthcare Organization',
                    contact_email='admin@healthprep.com',
                    setup_status='live',
                    custom_presets_enabled=True,
                    auto_sync_enabled=False
                )
                db.session.add(org)
                db.session.commit()
                print(f"   ✓ Created organization with ID: {org.id}")
            else:
                print(f"   ✓ Default organization already exists (ID: {org.id})")
            
            # Check if admin user exists
            admin_user = User.query.filter_by(username='admin', org_id=org.id).first()
            if not admin_user:
                print("Creating admin user...")
                admin_user = User(
                    username='admin',
                    email='admin@healthprep.com',
                    org_id=org.id,
                    role='admin',
                    is_admin=True,
                    is_active_user=True,
                    last_activity=datetime.utcnow()
                )
                admin_user.set_password('admin123')  # Change this in production!
                db.session.add(admin_user)
                db.session.commit()
                print(f"   ✓ Created admin user (ID: {admin_user.id})")
                print("   ⚠️  Default password is 'admin123' - change this immediately!")
            else:
                print(f"   ✓ Admin user already exists (ID: {admin_user.id})")
            
            print("\n✅ Test organization setup completed!")
            print("You can now log in with:")
            print("  Username: admin")
            print("  Password: admin123")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Setup failed: {e}")
            raise

if __name__ == "__main__":
    setup_test_organization()
