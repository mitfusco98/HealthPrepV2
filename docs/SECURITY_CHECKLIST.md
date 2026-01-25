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

- [ ] **Redis for Rate Limiting (REQUIRED for AWS multi-instance)**
  - Set `REDIS_URL` for distributed rate limiting across instances
  - Without Redis, rate limiting is per-instance only (attacker can bypass by hitting different instances)
  - Example: `redis://redis-host:6379/0`
  
  **AWS ElastiCache Configuration:**
  ```
  # Recommended: Redis 7.x with encryption
  Engine: Redis
  Node Type: cache.t3.micro (start small, scale as needed)
  Encryption at-rest: Enabled
  Encryption in-transit: Enabled
  Auth Token: Required (set as REDIS_AUTH_TOKEN secret)
  VPC: Same as ECS cluster
  Security Group: Allow 6379 from ECS security group only
  ```
  
  **Connection String Format:**
  ```
  # Without auth
  REDIS_URL=redis://your-elasticache-endpoint:6379/0
  
  # With auth token
  REDIS_URL=redis://:your-auth-token@your-elasticache-endpoint:6379/0
  ```
  
  **Verification:**
  - Check logs on startup for "Redis rate limiter initialized"
  - Warning logged if Redis unavailable: "Rate limiting using in-memory store"

- [ ] **Session Security**
  - `SECRET_KEY` is required and validated at startup
  - Session cookies are `Secure`, `HttpOnly`, and `SameSite=Lax` in production

### Medium Priority

- [x] **CSP Headers** (Completed January 2026)
  - CSP is enabled by default with Bootstrap-compatible settings
  - All inline scripts now use nonce attribute (`nonce="{{ g.csp_nonce }}"`)
  - Set `CSP_STRICT_MODE=true` or deploy with production FHIR URL for strict nonce-based CSP
  - Production mode automatically detected via FHIR URL (no unsafe-inline for scripts)

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

## Incident Response Testing

Regular IR testing is required for HITRUST i1 certification. Full test procedures are documented in [INCIDENT_RESPONSE_PLAN.md](./INCIDENT_RESPONSE_PLAN.md) Appendix C.

### IR Test Scenarios (Quarterly)

| # | Scenario | Priority | Last Tested | Result | Next Due |
|---|----------|----------|-------------|--------|----------|
| 1 | Account Lockout (5 failed logins) | P3 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 2 | Brute Force Detection (10+ IPs) | P2 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 3 | Unauthorized Admin Access | P3 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 4 | PHI Filter Failure | P2 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 5 | Suspicious Access Pattern | P3 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 6 | Password Reset Abuse | P4 | [ ] | [ ] Pass / [ ] Fail | [ ] |
| 7 | Epic OAuth Failure | P3 | [ ] | [ ] Pass / [ ] Fail | [ ] |

### Test Completion Checklist

- [ ] All 7 scenarios executed in test environment
- [ ] Pass/fail results documented above
- [ ] Remediation tasks created for any failures
- [ ] Test evidence archived for HITRUST audit
- [ ] Next quarterly test scheduled
