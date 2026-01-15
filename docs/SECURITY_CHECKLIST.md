# Security Checklist for Production Deployment

This checklist documents the security controls required for HIPAA-compliant production deployment of HealthPrep.

## Pre-Deployment Security Checks

### Critical (Must Fix Before Production)

- [ ] **CORS Configuration**
  - Set `CORS_ALLOWED_ORIGINS` environment variable to specific domains
  - Example: `CORS_ALLOWED_ORIGINS=https://marketing.example.com,https://app.example.com`
  - Never use `"*"` in production

- [ ] **Encryption Key**
  - Set `ENCRYPTION_KEY` environment variable (required in production)
  - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  - This encrypts Epic OAuth credentials and sensitive data

- [ ] **Database**
  - Set `DATABASE_URL` to PostgreSQL connection string
  - SQLite is blocked in production
  - Example: `postgresql://user:pass@host:5432/healthprep`

- [ ] **Flask Environment**
  - Set `FLASK_ENV=production` to enable production security checks

### High Priority

- [ ] **Redis for Rate Limiting**
  - Set `REDIS_URL` for distributed rate limiting across instances
  - Without Redis, rate limiting is per-instance only
  - Example: `redis://redis-host:6379/0`

- [ ] **Session Security**
  - `SECRET_KEY` is required and validated at startup
  - Session cookies are `Secure`, `HttpOnly`, and `SameSite=Lax` in production

### Medium Priority

- [ ] **CSP Headers**
  - CSP is enabled by default with Bootstrap-compatible settings
  - For stricter CSP (no inline scripts), set `CSP_STRICT_MODE=true`
  - Requires migrating all inline scripts to external files

- [ ] **HTTPS**
  - HSTS headers are automatically set for HTTPS connections
  - Configure reverse proxy (Replit, AWS ALB) to set `X-Forwarded-Proto: https`

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_ENV` | Yes | Set to `production` for production mode |
| `SECRET_KEY` | Yes | Flask session secret (32+ chars) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ENCRYPTION_KEY` | Prod only | Fernet encryption key for sensitive data |
| `CORS_ALLOWED_ORIGINS` | Prod only | Comma-separated list of allowed origins |
| `REDIS_URL` | Recommended | Redis URL for distributed rate limiting |
| `CSP_STRICT_MODE` | Optional | Set to `true` for strict CSP (no inline) |

## Security Features Implemented

### PHI Protection (HIPAA)
- Regex-based PHI filtering with idempotency protection
- SSN, phone, email, MRN, insurance, addresses, names, dates
- Financial IDs (account numbers, credit cards)
- Government IDs (driver's license, passport)
- Provider IDs (NPI, DEA, medical license)
- PHI-bearing URLs
- Thread-safe settings snapshot for batch processing

### Rate Limiting
- IP-based rate limiting for login, password reset, security questions
- Redis support for distributed rate limiting (production)
- Automatic lockout after threshold exceeded
- Configurable per-endpoint limits

### Authentication & Authorization
- Role-based access control (user, admin, root_admin)
- Security question verification for admin login
- Account lockout after failed attempts
- Password hashing with Werkzeug defaults

### Encryption
- Fernet symmetric encryption for sensitive database fields
- Epic OAuth credentials encrypted at rest
- Key rotation support

### Audit Logging
- All PHI access logged for HIPAA compliance
- Security events (login, lockout, brute force) logged
- 7-year log retention policy

## Running Security Audit

```bash
python scripts/security_audit.py
```

Exit codes:
- 0: All checks passed
- 1: Critical issues found
- 2: Warnings found

## CI/CD Integration

Add to your CI pipeline:

```yaml
security-audit:
  script:
    - python scripts/security_audit.py
  allow_failure: false  # Block deployment on critical issues
```
