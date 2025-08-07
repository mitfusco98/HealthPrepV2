# HealthPrepV2 Multi-Tenancy Implementation

## Overview
This document outlines the multi-tenancy groundwork implemented for HealthPrepV2, enabling secure scaling across clinics, physician groups, and hospital systems with role-based access control (RBAC).

## 🏗️ **Core Components Implemented**

### 1. **Organization Model** (`models.py`)
Represents tenants (clinics, groups, hospitals):
- **Basic Info**: name, display_name, address, contact_email, phone
- **Epic FHIR Config**: client_id, client_secret, fhir_url, environment
- **Settings**: setup_status, custom_presets_enabled, auto_sync_enabled, max_users
- **Relationships**: users, epic_credentials, patients, screenings, documents, etc.

### 2. **Enhanced User Model** (`models.py`)
Updated with multi-tenancy support:
- **Organization Link**: `org_id` foreign key (with unique constraints)
- **Epic Integration**: `epic_user_id` for FHIR user mapping
- **Security Features**: 2FA, session timeout, account locking, activity tracking
- **Unique Constraints**: username and email unique within organization

### 3. **EpicCredentials Model** (`models.py`)
Secure credential storage per organization:
- **Token Management**: access_token, refresh_token, expiration tracking
- **User Context**: epic_user_id, user mapping
- **Security**: Encrypted token storage (production ready)

### 4. **Data Isolation** (All Models)
Added `org_id` to core models for data isolation:
- ✅ **Patient**: org_id + unique MRN per organization
- ✅ **Screening**: org_id for screening records
- ✅ **Document**: org_id for document access
- ✅ **ScreeningType**: org_id for organization-specific screening types
- ✅ **ScreeningPreset**: org_id + preset_scope for shared/org-specific presets

### 5. **Enhanced Audit Logging** (`models.py`)
HIPAA-compliant audit trail with organization scope:
- **Organization Context**: `org_id` for all logs
- **Enhanced Fields**: patient_id, resource_type, resource_id, action_details
- **Security Tracking**: session_id, user_agent, IP address
- **Compliance**: Immutable logs with 6+ year retention support

## 🛠️ **Multi-Tenancy Utilities** (`utils/multi_tenancy.py`)

### OrganizationScope Class
Data access utilities:
- `get_user_org_id()` - Get current user's organization
- `filter_by_org()` - Apply organization filters to queries
- `get_org_patients()`, `get_org_screenings()`, etc. - Organization-scoped data access

### Security Decorators
- `@require_organization_access()` - Enforce organization access control
- `@require_role()` - Role-based access control

### AuditLogger Class
Enhanced audit logging:
- `log_user_action()` - Comprehensive action logging
- `log_patient_access()` - HIPAA-compliant patient access logging
- `log_document_access()` - Document access tracking

### OrganizationOnboarding Class
Tenant onboarding utilities:
- `create_organization()` - Create org + admin user
- `setup_epic_credentials()` - Configure FHIR credentials
- `activate_organization()` - Enable sync and go live

### SessionManager Class
Security and session management:
- Session timeout enforcement
- Failed login attempt tracking
- Account locking after multiple failures

## 🔄 **Migration Process**

### Database Migration (`migrate_multi_tenancy.py`)
Comprehensive migration script that:
1. **Creates new tables**: organizations, epic_credentials
2. **Adds org_id columns** to existing tables
3. **Creates default organization** for existing data
4. **Migrates existing data** to default organization
5. **Adds unique constraints** within organizations
6. **Creates performance indexes**

### Migration Steps:
```bash
# Run the migration script
python migrate_multi_tenancy.py

# Or manually execute the SQL commands in PostgreSQL
# (See migrate_multi_tenancy.py for complete SQL)
```

## 🔐 **Security Implementation**

### Data Isolation
- **Row-level filtering**: Every query filtered by org_id
- **Unique constraints**: Usernames/emails/MRNs unique within organization
- **Cross-org protection**: Users cannot access other organizations' data

### Role-Based Access Control (RBAC)
- **Admin**: Full organization management, user creation, Epic config
- **MA (Medical Assistant)**: Screening management, prep sheet generation
- **Nurse**: Basic screening management, patient care

### Session Security
- **Session timeout**: Configurable per user (default 30 min)
- **Account locking**: 5 failed attempts = 30 min lockout
- **Activity tracking**: Last activity timestamp for session management

### Audit Compliance
- **HIPAA logging**: All patient/document access logged
- **Immutable logs**: Cannot be modified after creation
- **Comprehensive context**: User, IP, session, resource details

## 🚀 **Onboarding Flow**

### New Organization Setup:
1. **Create Organization** - Admin creates org record
2. **Setup Admin User** - First admin user created with invite link
3. **Configure Epic Credentials** - FHIR client ID, secret, URL
4. **Import Screening Presets** - Choose from templates or create custom
5. **Activate Sync** - Enable Epic integration and patient sync

### User Management Within Org:
1. **Admin creates users** - Assigns roles (MA, nurse, admin)
2. **Email invitations** - Secure one-time setup links
3. **Role enforcement** - UI and API access controlled by role

## 📊 **Enhanced Features**

### ScreeningPreset Multi-Tenancy
- **Organization-scoped presets**: Custom presets per organization
- **Global shared presets**: System-wide templates
- **Access control**: Users can only access org presets + shared
- **Import/Export**: Organization-specific preset management

### Epic Integration per Organization
- **Per-org credentials**: Each organization has own Epic config
- **Sandbox/Production**: Support for different environments
- **Token management**: Encrypted storage with auto-refresh

## 🔧 **Usage Examples**

### Organization-Scoped Queries:
```python
from utils.multi_tenancy import OrganizationScope

# Get patients for current user's organization
patients = OrganizationScope.get_org_patients()

# Get screenings with explicit org_id
screenings = OrganizationScope.get_org_screenings(org_id=123)

# Apply org filter to any query
query = Patient.query.filter(Patient.name.like('%John%'))
org_patients = OrganizationScope.filter_by_org(query, Patient)
```

### Security Decorators:
```python
from utils.multi_tenancy import require_organization_access, require_role

@require_organization_access()
@require_role('admin')
def create_user():
    # Only admins in the same org can access
    pass
```

### Audit Logging:
```python
from utils.multi_tenancy import AuditLogger

# Log patient access for HIPAA compliance
AuditLogger.log_patient_access(patient_id=123, action_type='view')

# Log document access
AuditLogger.log_document_access(document_id=456, action_type='download')
```

## 🎯 **Next Steps**

This groundwork provides the foundation for:
1. **Organization onboarding UI** - Admin dashboard for tenant management
2. **Epic SMART launch per org** - Organization-specific FHIR flows
3. **Advanced role management** - Custom roles and permissions
4. **Multi-org admin tools** - Super admin capabilities
5. **Billing integration** - Usage tracking per organization
6. **Backup/restore per org** - Organization-specific data management

## ⚠️ **Important Notes**

- **Run migration** before using multi-tenancy features
- **Update queries** to use OrganizationScope utilities
- **Test role enforcement** in all admin routes
- **Encrypt Epic credentials** in production
- **Monitor audit logs** for compliance
- **Set appropriate session timeouts** for security

The multi-tenancy foundation is now in place and ready for organization onboarding and scaling HealthPrepV2 across healthcare institutions.