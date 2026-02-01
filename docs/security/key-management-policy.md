# HealthPrep Key Management Policy

**Document Version:** 1.0  
**Effective Date:** January 2026  
**Review Frequency:** Annual  
**HITRUST CSF Alignment:** Control 10.g (Cryptographic Key Management)

---

## 1. Purpose

This policy establishes procedures for the secure generation, distribution, storage, rotation, and destruction of cryptographic keys and secrets used by HealthPrep. It ensures HIPAA compliance, supports HITRUST certification, and provides continuity across infrastructure migrations (Replit → AWS).

---

## 2. Scope

This policy applies to all secrets, API keys, and encryption keys used by HealthPrep including:

| Secret | Classification | Rotation Frequency |
|--------|---------------|-------------------|
| ENCRYPTION_KEY | Critical - PHI | Annual + on compromise |
| SESSION_SECRET | Critical - Auth | Annual + on compromise |
| SECRET_KEY | Critical - Auth | Annual (with SESSION_SECRET) |
| P_KEY_2025_08_A | Critical - Epic Prod | Per Epic requirements |
| NP_KEY_2025_08_A | Sensitive - Epic Sandbox | Per Epic requirements |
| STRIPE_SECRET_KEY | Sensitive - Payment | Annual + per Stripe policy |
| RESEND_API_KEY | Standard - Email | Annual |
| EPIC_NONPROD_CLIENT_ID | Standard - Epic Sandbox | Per Epic requirements |
| DATABASE_URL / PG* | Managed | Platform-managed |

---

## 3. Current Environment: Replit

### 3.1 Secret Storage Location

Secrets are stored in Replit's encrypted Secrets Manager, accessible via:
- Replit Dashboard → Tools → Secrets
- Environment variables at runtime

### 3.2 Rotation Procedure (Replit)

#### Standard Secrets (STRIPE_SECRET_KEY, RESEND_API_KEY)

1. **Generate new key** from the provider's dashboard (Stripe/Resend)
2. **Update in Replit:**
   - Open Replit Dashboard → Tools → Secrets
   - Locate the secret and click Edit
   - Paste new value and Save
3. **Restart workflow** to pick up new value:
   ```bash
   # Workflows auto-restart on secret change
   ```
4. **Verify functionality** by testing the integration
5. **Revoke old key** in provider dashboard after verification
6. **Log rotation** in security audit log with timestamp

#### Session Secrets (SESSION_SECRET, SECRET_KEY)

**Impact:** All active user sessions will be invalidated.

1. **Schedule maintenance window** (low-traffic period)
2. **Notify stakeholders** of upcoming session reset
3. **Generate new secret:**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
4. **Update both secrets simultaneously** in Replit Secrets
5. **Restart application workflow**
6. **Verify:** Confirm login works, existing sessions require re-auth
7. **Document** rotation in audit log

---

## 4. Target Environment: AWS

### 4.1 Secret Storage Architecture

```
AWS Secrets Manager
├── /healthprep/prod/
│   ├── encryption-key          (ENCRYPTION_KEY)
│   ├── session-secret          (SESSION_SECRET)
│   ├── secret-key              (SECRET_KEY)
│   ├── epic/prod-key           (P_KEY_2025_08_A)
│   ├── epic/client-id          (Epic production client)
│   ├── stripe/secret-key       (STRIPE_SECRET_KEY)
│   ├── resend/api-key          (RESEND_API_KEY)
│   └── database/url            (DATABASE_URL)
├── /healthprep/staging/
│   └── ... (mirrors prod structure)
└── /healthprep/dev/
    ├── epic/nonprod-key        (NP_KEY_2025_08_A)
    └── ... (dev-specific secrets)
```

### 4.2 Migration Mapping: Replit → AWS Secrets Manager

| Replit Secret | AWS Secrets Manager Path | Notes |
|---------------|-------------------------|-------|
| ENCRYPTION_KEY | /healthprep/prod/encryption-key | Requires data re-encryption |
| SESSION_SECRET | /healthprep/prod/session-secret | Direct migration |
| SECRET_KEY | /healthprep/prod/secret-key | Direct migration |
| P_KEY_2025_08_A | /healthprep/prod/epic/prod-key | Epic production |
| NP_KEY_2025_08_A | /healthprep/dev/epic/nonprod-key | Epic sandbox only |
| STRIPE_SECRET_KEY | /healthprep/prod/stripe/secret-key | Direct migration |
| RESEND_API_KEY | /healthprep/prod/resend/api-key | Direct migration |
| EPIC_NONPROD_CLIENT_ID | /healthprep/dev/epic/client-id | Sandbox only |
| DATABASE_URL | /healthprep/prod/database/url | RDS connection string |

### 4.3 AWS Rotation Procedure: Manual (Console)

#### Step 1: Access Secrets Manager

1. Sign in to AWS Console
2. Navigate to **Secrets Manager** → **Secrets**
3. Select the secret to rotate (e.g., `/healthprep/prod/stripe/secret-key`)

#### Step 2: Store New Secret Version

1. Click **Retrieve secret value** to view current
2. Click **Edit**
3. Paste new secret value
4. Click **Save**

#### Step 3: Verify Application Picks Up New Value

For ECS/Fargate:
```bash
# Force new task deployment to pick up secret
aws ecs update-service \
  --cluster healthprep-cluster \
  --service healthprep-service \
  --force-new-deployment
```

For EKS:
```bash
# Restart deployment to refresh secrets
kubectl rollout restart deployment/healthprep -n production
```

#### Step 4: Audit Log Entry

Secrets Manager automatically logs to CloudTrail. Verify entry:
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutSecretValue \
  --start-time $(date -d '1 hour ago' --iso-8601=seconds)
```

### 4.4 AWS Rotation Procedure: CLI

#### Rotate Standard Secret

```bash
# Generate new secret value
NEW_VALUE=$(python -c "import secrets; print(secrets.token_hex(32))")

# Update in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id /healthprep/prod/session-secret \
  --secret-string "$NEW_VALUE"

# Force ECS deployment
aws ecs update-service \
  --cluster healthprep-cluster \
  --service healthprep-service \
  --force-new-deployment

# Verify new task is running
aws ecs describe-services \
  --cluster healthprep-cluster \
  --services healthprep-service \
  --query 'services[0].deployments'
```

#### Rotate with Staging Value

```bash
# Update staging value in secret (multi-value secret)
aws secretsmanager put-secret-value \
  --secret-id /healthprep/prod/stripe/secret-key \
  --secret-string '{"current":"sk_live_xxx","previous":"sk_live_old"}' \
  --version-stage AWSPENDING

# After verification, promote to current
aws secretsmanager update-secret-version-stage \
  --secret-id /healthprep/prod/stripe/secret-key \
  --version-stage AWSCURRENT \
  --move-to-version-id <new-version-id>
```

### 4.5 Automatic Rotation with Lambda

For secrets that support automatic rotation (database credentials, some API keys):

```bash
# Enable automatic rotation (30-day schedule)
aws secretsmanager rotate-secret \
  --secret-id /healthprep/prod/database/url \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:ACCOUNT:function:SecretsManagerRDSRotation \
  --rotation-rules AutomaticallyAfterDays=30
```

**Note:** ENCRYPTION_KEY cannot use automatic rotation due to data re-encryption requirements.

### 4.6 IAM Policy for Secret Rotation

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerRotation",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecretVersionStage",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:/healthprep/*"
    },
    {
      "Sid": "ECSDeployment",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices"
      ],
      "Resource": "arn:aws:ecs:*:*:service/healthprep-cluster/*"
    }
  ]
}
```

---

## 5. ENCRYPTION_KEY Rotation (Dual-Key Procedure)

**This procedure applies to both Replit and AWS environments.**

The ENCRYPTION_KEY encrypts PHI at rest. Rotation requires re-encrypting all protected data.

### 5.1 Pre-Rotation Checklist

- [ ] Schedule maintenance window (2-4 hours depending on data volume)
- [ ] Notify stakeholders of PHI system downtime
- [ ] Create database backup
- [ ] Generate new encryption key
- [ ] Test decryption with current key on backup

### 5.2 Dual-Key Migration Steps

#### Step 1: Generate New Key

```bash
# Generate cryptographically secure key
python -c "import secrets; print(secrets.token_hex(32))"
# Example output: a1b2c3d4e5f6...
```

#### Step 2: Add New Key as Secondary

**Replit:**
- Add new secret: `ENCRYPTION_KEY_NEW` with new value

**AWS:**
```bash
aws secretsmanager put-secret-value \
  --secret-id /healthprep/prod/encryption-key \
  --secret-string '{"current":"OLD_KEY","pending":"NEW_KEY"}'
```

#### Step 3: Deploy Dual-Key Application Code

The application must temporarily support both keys:

```python
# services/encryption.py - Dual-key support
import os
from cryptography.fernet import Fernet, InvalidToken

class DualKeyEncryption:
    def __init__(self):
        self.current_key = os.environ.get('ENCRYPTION_KEY')
        self.new_key = os.environ.get('ENCRYPTION_KEY_NEW')
        
        self.current_fernet = Fernet(self.current_key) if self.current_key else None
        self.new_fernet = Fernet(self.new_key) if self.new_key else None
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Try new key first, fall back to current key."""
        if self.new_fernet:
            try:
                return self.new_fernet.decrypt(ciphertext)
            except InvalidToken:
                pass
        return self.current_fernet.decrypt(ciphertext)
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """Always encrypt with new key if available."""
        fernet = self.new_fernet if self.new_fernet else self.current_fernet
        return fernet.encrypt(plaintext)
```

#### Step 4: Run Re-Encryption Migration

```bash
# Run migration script (during maintenance window)
python scripts/reencrypt_phi_data.py --dry-run  # Verify first
python scripts/reencrypt_phi_data.py --execute  # Perform migration
```

Migration script pseudocode:
```python
def reencrypt_all_phi():
    """Re-encrypt all PHI fields with new key."""
    from models import Patient, FHIRDocument
    from services.encryption import DualKeyEncryption
    
    encryptor = DualKeyEncryption()
    
    # Process in batches
    for patient in Patient.query.yield_per(100):
        if patient.encrypted_ssn:
            # Decrypt with old, encrypt with new
            plaintext = encryptor.decrypt(patient.encrypted_ssn)
            patient.encrypted_ssn = encryptor.encrypt(plaintext)
        db.session.commit()
    
    # Repeat for all PHI-containing tables
    # Log each record processed for audit trail
```

#### Step 5: Verify Re-Encryption

```bash
# Verify sample records decrypt correctly with new key only
python scripts/verify_encryption.py --sample-size=100
```

#### Step 6: Promote New Key to Primary

**Replit:**
1. Copy value from `ENCRYPTION_KEY_NEW` to `ENCRYPTION_KEY`
2. Delete `ENCRYPTION_KEY_NEW`
3. Remove dual-key code, deploy standard encryption

**AWS:**
```bash
# Promote new key to current
aws secretsmanager put-secret-value \
  --secret-id /healthprep/prod/encryption-key \
  --secret-string "NEW_KEY_VALUE"

# Force deployment
aws ecs update-service --cluster healthprep-cluster \
  --service healthprep-service --force-new-deployment
```

#### Step 7: Post-Rotation Verification

- [ ] Verify application starts without encryption errors
- [ ] Test PHI retrieval on sample patients
- [ ] Confirm audit log entries for all re-encrypted records
- [ ] Securely destroy old key (do not retain)

### 5.3 Emergency Rotation (Compromise Response)

If ENCRYPTION_KEY is suspected compromised:

1. **Immediately** generate new key
2. **Disable** API access if breach is active
3. **Execute** dual-key migration as above (expedited)
4. **Notify** security team and begin incident response
5. **Document** timeline for compliance reporting
6. **Assess** data exposure using audit logs

---

## 6. Epic Credential Rotation

Epic credentials (P_KEY, NP_KEY, CLIENT_ID) follow Epic's App Orchard requirements.

### 6.1 Production Key Rotation

1. **Request new credentials** via Epic App Orchard
2. **Update** in Replit Secrets or AWS Secrets Manager
3. **Test** OAuth flow with Epic sandbox first
4. **Deploy** to production
5. **Revoke** old credentials in App Orchard

### 6.2 Non-Production Key Rotation

Non-production keys can be rotated during development without coordination:

```bash
# Update sandbox credentials
aws secretsmanager put-secret-value \
  --secret-id /healthprep/dev/epic/nonprod-key \
  --secret-string "new_sandbox_key_value"
```

---

## 7. Docker/Container Considerations

Containerization does not affect key management policy. Secrets are injected at runtime:

### 7.1 ECS/Fargate Secret Injection

```json
{
  "containerDefinitions": [{
    "secrets": [
      {
        "name": "ENCRYPTION_KEY",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:/healthprep/prod/encryption-key"
      },
      {
        "name": "SESSION_SECRET",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:/healthprep/prod/session-secret"
      }
    ]
  }]
}
```

### 7.2 EKS Secret Injection (External Secrets Operator)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: healthprep-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: healthprep-secrets
  data:
    - secretKey: ENCRYPTION_KEY
      remoteRef:
        key: /healthprep/prod/encryption-key
    - secretKey: SESSION_SECRET
      remoteRef:
        key: /healthprep/prod/session-secret
```

### 7.3 Post-Rotation Container Refresh

After any secret rotation, containers must be refreshed:

```bash
# ECS
aws ecs update-service --cluster healthprep-cluster \
  --service healthprep-service --force-new-deployment

# EKS
kubectl rollout restart deployment/healthprep -n production

# Docker Compose (local/staging)
docker-compose down && docker-compose up -d
```

---

## 8. HITRUST Control Alignment

This policy satisfies **HITRUST CSF Control 10.g - Cryptographic Key Management**:

| Requirement | Implementation |
|-------------|----------------|
| Key generation procedures | Section 5.2 Step 1 (cryptographically secure generation) |
| Key distribution | AWS Secrets Manager / Replit Secrets with IAM/RBAC |
| Key storage | Encrypted at rest in platform secret stores |
| Key rotation | Defined schedules (Section 2) and procedures (Sections 3-6) |
| Key destruction | Section 5.2 Step 7 (secure destruction, no retention) |
| Key compromise handling | Section 5.3 (emergency rotation procedure) |
| Audit logging | CloudTrail (AWS) / Platform logs (Replit) |

---

## 9. Audit Trail Requirements

All key rotation events must be logged with:

- Timestamp (UTC)
- Secret identifier (never the value)
- Operator identity
- Reason for rotation (scheduled/emergency/compromise)
- Verification status

### 9.1 Log Entry Template

```json
{
  "event_type": "secret_rotation",
  "timestamp": "2026-01-23T14:30:00Z",
  "secret_id": "ENCRYPTION_KEY",
  "operator": "admin@healthprep.com",
  "reason": "scheduled_annual",
  "verification_status": "success",
  "affected_records": 1247,
  "notes": "Annual rotation per policy"
}
```

### 9.2 Retention

Rotation audit logs must be retained for:
- **HIPAA:** 6 years minimum
- **HITRUST:** 7 years recommended

---

## 10. Rotation Schedule Summary

| Secret | Frequency | Next Rotation | Owner |
|--------|-----------|---------------|-------|
| ENCRYPTION_KEY | Annual | January 2027 | Security Admin |
| SESSION_SECRET | Annual | January 2027 | DevOps |
| SECRET_KEY | Annual | January 2027 | DevOps |
| STRIPE_SECRET_KEY | Annual | January 2027 | Finance/DevOps |
| RESEND_API_KEY | Annual | January 2027 | DevOps |
| Epic Production Keys | Per Epic | Per Epic schedule | Epic Integration Lead |

---

## 11. AWS Migration - JWKS URL Configuration

### 11.1 Environment Variables for Epic Integration

After migrating to AWS, the following environment variables must be configured in ECS task definitions:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `JWKS_BASE_URL` | Base URL for JWKS endpoints | `https://healthprep-v-201.com` |
| `REDIRECT_URI` | OAuth callback URL for Epic | `https://healthprep-v-201.com/oauth/epic-callback` |
| `NP_KEY_2025_08_A` | Non-production RSA private key (PEM format) | `-----BEGIN RSA PRIVATE KEY-----...` |
| `P_KEY_2025_08_A` | Production RSA private key (PEM format) | `-----BEGIN RSA PRIVATE KEY-----...` |

### 11.2 JWKS Endpoints

Production JWKS URLs for Epic App Orchard registration:

- **Production:** `https://healthprep-v-201.com/.well-known/jwks.json`
- **Non-Production:** `https://healthprep-v-201.com/nonprod/.well-known/jwks.json`

### 11.3 Key Availability Verification

If JWKS endpoints return emergency placeholder keys (kid contains "emergency"), the private key environment variables are not properly configured. Verify:

1. `P_KEY_*` environment variables exist for production
2. `NP_KEY_*` environment variables exist for non-production
3. Keys are valid PEM-formatted RSA private keys
4. ECS task was redeployed after adding secrets

### 11.4 AWS Secrets Manager Paths for Epic Keys

```
AWS Secrets Manager
├── /healthprep/prod/epic/
│   ├── prod-key           (P_KEY_2025_08_A)
│   ├── client-id          (Epic production client ID)
│   └── redirect-uri       (https://healthprep-v-201.com/oauth/epic-callback)
└── /healthprep/dev/epic/
    ├── nonprod-key        (NP_KEY_2025_08_A)
    └── client-id          (Epic sandbox client ID)
```

### 11.5 ECS Task Definition Secret Injection

Add the following to your ECS task definition to inject Epic keys from Secrets Manager:

```json
{
  "containerDefinitions": [{
    "name": "healthprep",
    "secrets": [
      {
        "name": "P_KEY_2025_08_A",
        "valueFrom": "arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:/healthprep/prod/epic/prod-key"
      },
      {
        "name": "NP_KEY_2025_08_A",
        "valueFrom": "arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:/healthprep/dev/epic/nonprod-key"
      }
    ],
    "environment": [
      {
        "name": "JWKS_BASE_URL",
        "value": "https://healthprep-v-201.com"
      },
      {
        "name": "REDIRECT_URI",
        "value": "https://healthprep-v-201.com/oauth/epic-callback"
      }
    ]
  }]
}
```

### 11.6 Verifying Key Injection in AWS

After deploying to ECS, verify that keys are properly injected (not fallback/emergency):

```bash
# Check production JWKS - kid should NOT contain "fallback" or "emergency"
curl -s https://healthprep-v-201.com/.well-known/jwks.json | jq '.keys[].kid'

# Expected output: "2025_08_A" (or similar date-based kid)
# Bad output: "prod-emergency" or "prod-fallback"

# Check non-production JWKS
curl -s https://healthprep-v-201.com/nonprod/.well-known/jwks.json | jq '.keys[].kid'
```

If JWKS returns emergency/fallback kids:
1. Verify Secrets Manager secrets exist at the specified ARNs
2. Verify ECS task IAM role has `secretsmanager:GetSecretValue` permission
3. Force new ECS deployment: `aws ecs update-service --cluster healthprep-cluster --service healthprep-service --force-new-deployment`
4. Check ECS task logs for key loading errors

---

## 12. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Security | Initial policy |
| 1.1 | February 2026 | HealthPrep Security | Added AWS migration JWKS configuration (Section 11) |

---

## 13. Approval

| Role | Name | Date |
|------|------|------|
| Security Officer | | |
| CTO | | |
| Compliance Officer | | |
