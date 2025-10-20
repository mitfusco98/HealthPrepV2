# Security Setup Guide for HealthPrep v2

## Overview

HealthPrep v2 implements comprehensive security measures for HIPAA compliance and data protection:

1. **Field-level encryption** for sensitive credentials
2. **Secrets management** via environment variables
3. **Security headers** (HSTS, CSP, X-Frame-Options, etc.)
4. **TLS enforcement** in production
5. **Audit logging** for all PHI access
6. **Multi-tenant data isolation**

## Quick Start

### 1. Generate Required Secrets

```bash
# Generate SECRET_KEY (Flask session encryption)
python -c "import secrets; print(secrets.token_hex(32))"

# Generate ENCRYPTION_KEY (database field encryption)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Critical variables:**
- `SECRET_KEY` - Flask session security (minimum 32 chars)
- `ENCRYPTION_KEY` - Fernet key for Epic credentials (exactly 44 chars)
- `DATABASE_URL` - PostgreSQL connection string

### 3. Verify Secrets

The application validates all required secrets on startup. If any are missing, it will fail with a helpful error message.

## Encryption Architecture

### What Gets Encrypted

1. **Epic OAuth Credentials**
   - `Organization.epic_client_secret`
   - `EpicCredentials.access_token`
   - `EpicCredentials.refresh_token`

2. **Encryption Method**
   - Uses Fernet symmetric encryption (AES-128 in CBC mode)
   - Encryption key loaded from `ENCRYPTION_KEY` environment variable
   - Automatic encryption/decryption via SQLAlchemy hybrid properties

### How It Works

```python
# When you set a value, it's automatically encrypted
org.epic_client_secret = "my-secret"  # Encrypted before saving to DB

# When you read it, it's automatically decrypted
secret = org.epic_client_secret  # Returns decrypted value
```

### Encryption Key Management

**Development:**
- Store `ENCRYPTION_KEY` in Replit Secrets or local `.env`

**Production:**
- Use AWS Secrets Manager, Azure Key Vault, or similar
- Rotate keys periodically using the `EncryptionService.rotate_key()` method
- Never commit encryption keys to version control

## Security Headers

### Implemented Headers

1. **HSTS (Strict-Transport-Security)**
   - Forces HTTPS for 1 year
   - Includes subdomains
   - Preload eligible

2. **Content-Security-Policy (CSP)**
   - Restricts script/style sources
   - Prevents XSS attacks
   - Allows Bootstrap/jQuery CDNs

3. **X-Frame-Options: SAMEORIGIN**
   - Prevents clickjacking attacks

4. **X-Content-Type-Options: nosniff**
   - Prevents MIME-sniffing attacks

5. **Referrer-Policy: strict-origin-when-cross-origin**
   - Controls referrer information leakage

6. **Permissions-Policy**
   - Disables unnecessary browser features (camera, microphone, geolocation)

### HTTPS Enforcement

- **Development:** HTTP allowed for localhost
- **Production:** Automatic redirect to HTTPS
- Set `FLASK_ENV=production` to enable HTTPS enforcement

## Secrets Management Best Practices

### Never Store Secrets In:
- ❌ Source code
- ❌ Configuration files committed to Git
- ❌ Database (except encrypted fields)
- ❌ Client-side JavaScript
- ❌ Logs or error messages

### Always Store Secrets In:
- ✅ Environment variables
- ✅ Secrets management services (AWS Secrets Manager, etc.)
- ✅ Replit Secrets (for Replit deployment)
- ✅ Encrypted configuration files (with separate key management)

### Secrets Validation

The application validates secrets on startup:

```python
# Automatically runs in app.py
from utils.secrets_validator import validate_secrets_on_startup

validate_secrets_on_startup(environment='production')
# Raises SecretsValidationError if required secrets are missing
```

## HIPAA Compliance Checklist

### ✅ Implemented

- [x] Encryption at rest (Epic credentials)
- [x] Encryption in transit (TLS/HTTPS)
- [x] Access controls (role-based)
- [x] Audit logging (all PHI access)
- [x] Session timeout (30 minutes default)
- [x] Account lockout (5 failed login attempts)
- [x] Multi-tenant data isolation
- [x] PHI filtering in logs
- [x] Security headers

### 🔄 Additional Requirements (Deployment-Specific)

- [ ] Business Associate Agreement (BAA) with hosting provider
- [ ] Encrypted database backups
- [ ] Network isolation (VPC/security groups)
- [ ] Regular security audits
- [ ] Incident response plan
- [ ] Staff training on HIPAA compliance

## Migration to AWS

### Pre-Migration Security Setup

1. **Create Encryption Keys in AWS Secrets Manager**
   ```bash
   aws secretsmanager create-secret \
     --name healthprep/encryption-key \
     --secret-string "$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
   ```

2. **Configure RDS with Encryption**
   - Enable encryption at rest
   - Use encrypted backups
   - Enable SSL/TLS connections

3. **Set Up VPC Security Groups**
   - Database: Only accessible from app servers
   - App servers: Only accessible from load balancer
   - Load balancer: HTTPS only (port 443)

4. **Configure ALB/CloudFront**
   - Force HTTPS redirects
   - Enable TLS 1.2+
   - Add security headers (redundant with app, but defense in depth)

### Environment Variables on AWS

**For ECS/Fargate:**
```json
{
  "secrets": [
    {
      "name": "SECRET_KEY",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:healthprep/secret-key"
    },
    {
      "name": "ENCRYPTION_KEY",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:healthprep/encryption-key"
    }
  ]
}
```

**For Elastic Beanstalk:**
- Use environment properties in Beanstalk console
- Or store in AWS Systems Manager Parameter Store

## Troubleshooting

### Application Won't Start

**Error:** `SECRET_KEY environment variable is required`
- **Solution:** Add SECRET_KEY to environment variables

**Error:** `ENCRYPTION_KEY should be 44 characters`
- **Solution:** Generate a new Fernet key (it must be exactly 44 chars)

### Encryption Errors

**Error:** `Failed to decrypt epic_client_secret`
- **Cause:** ENCRYPTION_KEY changed or corrupted
- **Solution:** If key lost, you must re-enter Epic credentials

**Error:** `Encryption not enabled - storing value in plaintext`
- **Cause:** ENCRYPTION_KEY not set
- **Impact:** Epic credentials stored unencrypted (security risk)
- **Solution:** Set ENCRYPTION_KEY and re-save credentials

### Security Headers Not Applied

**Issue:** Headers missing in browser devtools
- **Check:** Is `configure_security_middleware()` called in `app.py`?
- **Check:** Are you testing over HTTPS? (HSTS only applies to HTTPS)
- **Solution:** Ensure middleware is registered before routes

## Security Monitoring

### Logs to Monitor

1. **Failed Login Attempts**
   - Pattern: `WARNING:...Login failed for user`
   - Action: Investigate after 3+ failures from same IP

2. **Encryption Errors**
   - Pattern: `ERROR:...Failed to decrypt`
   - Action: Check ENCRYPTION_KEY hasn't changed

3. **Secrets Validation Errors**
   - Pattern: `ERROR:...Secrets validation failed`
   - Action: Ensure all required secrets are set

4. **PHI Access**
   - All logged in `admin_logs` table
   - Review regularly for unauthorized access

### Recommended Alerts

- Failed login rate > 10/minute from single IP
- Any decryption failures
- Unusual PHI access patterns
- Missing required secrets on startup

## Key Rotation

### Rotating ENCRYPTION_KEY

**⚠️ WARNING:** Rotating encryption key requires re-encrypting all existing data

```python
from utils.encryption import EncryptionService
from models import Organization, EpicCredentials

# 1. Get old and new keys
old_key = "old-encryption-key-here"
new_key = "new-encryption-key-here"

# 2. Rotate for all organizations
for org in Organization.query.all():
    if org._epic_client_secret:
        org._epic_client_secret = EncryptionService().rotate_key(
            old_key, new_key, org._epic_client_secret
        )

# 3. Rotate for all credentials
for cred in EpicCredentials.query.all():
    if cred._access_token:
        cred._access_token = EncryptionService().rotate_key(
            old_key, new_key, cred._access_token
        )
    if cred._refresh_token:
        cred._refresh_token = EncryptionService().rotate_key(
            old_key, new_key, cred._refresh_token
        )

db.session.commit()

# 4. Update ENCRYPTION_KEY environment variable to new_key
```

### Rotating SECRET_KEY

1. Update SECRET_KEY environment variable
2. Restart application
3. All users will be logged out (sessions invalidated)
4. No data migration needed

## Additional Resources

- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Cryptography Library Docs](https://cryptography.io/en/latest/fernet/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/stable/security/)
