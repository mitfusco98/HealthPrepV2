# Production Database Fix Instructions

## Problem
Production database is missing the "System Organization" (org_id=0), causing:
1. ❌ Login failures for root admin (500 error on `/auth/verify-login-security`)
2. ❌ Organization rejection failures (foreign key violation)

## Solution
Run the initialization script to create System Organization in production database.

## Steps to Fix Production

### Option 1: Run via Replit Shell (Recommended)
1. Open your **production deployment** in Replit
2. Click **"Shell"** at the bottom of the screen
3. Run:
   ```bash
   python init_system_org.py
   ```
4. You should see: `✅ System Organization (org_id=0) created successfully!`

### Option 2: Run via SSH (If you have SSH access)
1. SSH into your production server
2. Navigate to the application directory
3. Run:
   ```bash
   python init_system_org.py
   ```

### Option 3: Manual SQL (If Python access not available)
If you can't run Python scripts, execute this SQL directly on production database:

```sql
INSERT INTO organizations (
    id, name, display_name, specialty, site, 
    contact_email, billing_email, 
    onboarding_status, setup_status, subscription_status,
    creation_method, max_users, created_at
) VALUES (
    0, 'System Organization', 'System Organization', 'System', 'System',
    'system@healthprep.com', 'system@healthprep.com',
    'completed', 'live', 'manual_billing',
    'system', 1000, NOW()
)
ON CONFLICT (id) DO NOTHING;
```

## Verification

After running the fix, verify it worked:

### 1. Check Database
```sql
SELECT id, name, onboarding_status FROM organizations WHERE id = 0;
```
Should return: `0 | System Organization | completed`

### 2. Test Login
1. Go to: `https://health-prep-v-201-mitchfusillo.replit.app/auth/login`
2. Log in as rootadmin
3. Complete security questions
4. Should successfully reach dashboard (no 500 error)

### 3. Test Organization Rejection
1. Create a test organization via marketing website signup
2. Log into root admin dashboard
3. Try rejecting the test organization
4. Should complete without foreign key error

## What Was Fixed

### Code Changes
1. **routes/auth_routes.py** (line 268-271):
   - Changed from: `org_id=user.org_id` (which was None for root admin)
   - Changed to: `org_id=0 if user.is_root_admin else user.org_id`
   - Prevents NULL constraint violation when logging root admin events

### Database Changes
1. **System Organization created** (org_id=0):
   - Used for all root admin audit logging
   - Prevents foreign key violations
   - Matches development database structure

## Deployment

The code fix is already in this codebase. To deploy:

1. **Deploy the updated code** to production (if not auto-deployed)
2. **Run the initialization script** (see steps above)
3. **Verify** login and organization management work

## Why This Happened

The production and development databases diverged:
- **Development**: Has System Organization (org_id=0) ✅
- **Production**: Missing System Organization ❌

This caused production-only failures because root admin audit logging expects org_id=0 to exist.

## Future Prevention

The `init_system_org.py` script is **idempotent** - it's safe to run multiple times and can be added to your deployment process to ensure System Organization always exists.
