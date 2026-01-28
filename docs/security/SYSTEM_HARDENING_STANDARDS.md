# System Hardening Standards

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep DevOps Team | Initial release |

**Classification**: Internal Use Only  
**Review Frequency**: Annual or after major infrastructure changes  
**Next Review**: January 2027  
**HITRUST CSF Alignment**: Domain 06.d (Technical Compliance Checking)

---

## 1. Purpose

This document establishes baseline security configuration standards for all HealthPrep systems, ensuring consistent security posture across development, staging, and production environments. These standards support HIPAA Security Rule technical safeguards and HITRUST CSF compliance.

---

## 2. Scope

These standards apply to:
- Application servers (Replit, AWS ECS)
- Database systems (PostgreSQL/RDS)
- Container images
- Web application components
- Third-party integrations (Epic FHIR, Stripe, Resend)

---

## 3. Application Server Hardening

### 3.1 Operating System Configuration

**Base Image Requirements**:
| Setting | Standard | Rationale |
|---------|----------|-----------|
| Base OS | NixOS (Replit) / Amazon Linux 2023 (AWS) | Maintained, security patched |
| Automatic updates | Enabled | Timely security patches |
| Unnecessary services | Disabled | Reduced attack surface |
| Root login | Disabled | Principle of least privilege |

**File System**:
| Setting | Standard | Rationale |
|---------|----------|-----------|
| /tmp | noexec, nosuid | Prevent execution of malicious code |
| Application directories | Restricted permissions (755/644) | Minimum necessary access |
| Log directories | Append-only where possible | Log integrity |
| Sensitive files | 600 permissions | Protect secrets |

### 3.2 Network Configuration

**Firewall Rules (AWS Security Groups)**:
| Port | Source | Purpose |
|------|--------|---------|
| 443 (HTTPS) | 0.0.0.0/0 | Application access |
| 5432 (PostgreSQL) | Application SG only | Database access |
| All other ports | Blocked | Default deny |

**TLS Configuration**:
| Setting | Standard | Rationale |
|---------|----------|-----------|
| Minimum TLS version | 1.2 | Industry standard |
| Preferred TLS version | 1.3 | Latest security |
| Weak ciphers | Disabled | Prevent downgrade attacks |
| HSTS | Enabled (max-age=31536000) | Force HTTPS |

---

## 4. Database Hardening (PostgreSQL/RDS)

### 4.1 Access Control

| Setting | Standard | Implementation |
|---------|----------|----------------|
| Authentication | Password + SSL required | `pg_hba.conf`: hostssl |
| Default accounts | Disabled/removed | No postgres superuser access |
| Application accounts | Minimum privileges | GRANT SELECT, INSERT, UPDATE on required tables |
| Admin accounts | Separate, MFA protected | Console access only |

### 4.2 Network Security

| Setting | Standard | Implementation |
|---------|----------|----------------|
| Port exposure | VPC internal only | Security group restriction |
| SSL/TLS | Required | `rds.force_ssl = 1` |
| Encryption at rest | AES-256 | KMS-managed keys |
| Encryption in transit | TLS 1.2+ | Required for all connections |

### 4.3 Audit Configuration

| Setting | Standard | Implementation |
|---------|----------|----------------|
| Connection logging | Enabled | `log_connections = on` |
| Disconnection logging | Enabled | `log_disconnections = on` |
| Statement logging | DDL and errors | `log_statement = 'ddl'` |
| Log destination | CloudWatch Logs | Centralized monitoring |

### 4.4 AWS RDS Settings

```terraform
resource "aws_db_instance" "healthprep" {
  engine                     = "postgres"
  engine_version             = "15.4"
  instance_class             = "db.t3.medium"
  
  # Encryption
  storage_encrypted          = true
  kms_key_id                 = aws_kms_key.healthprep_db.arn
  
  # Networking
  publicly_accessible        = false
  vpc_security_group_ids     = [aws_security_group.db.id]
  db_subnet_group_name       = aws_db_subnet_group.private.name
  
  # Backup and Recovery
  backup_retention_period    = 35
  backup_window              = "03:00-04:00"
  maintenance_window         = "sun:04:00-sun:05:00"
  delete_automated_backups   = false
  deletion_protection        = true
  
  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true
  monitoring_interval             = 60
  
  # Security
  iam_database_authentication_enabled = true
  auto_minor_version_upgrade          = true
}
```

---

## 5. Container Hardening

### 5.1 Base Image Security

| Setting | Standard | Rationale |
|---------|----------|-----------|
| Base image | Official Python slim | Minimal attack surface |
| Image scanning | Enabled (ECR/Snyk) | Vulnerability detection |
| Image signing | Enabled | Image integrity |
| Non-root user | Required | Least privilege |

### 5.2 Dockerfile Standards

```dockerfile
FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r healthprep && useradd -r -g healthprep healthprep

# Security: Install only required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Security: Set restrictive permissions
WORKDIR /app
COPY --chown=healthprep:healthprep . .

# Security: Run as non-root
USER healthprep

# Security: Read-only root filesystem (when possible)
# Note: Some paths may require write access

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]
```

### 5.3 Runtime Security

| Setting | Standard | Implementation |
|---------|----------|----------------|
| Privileged mode | Disabled | `--privileged=false` |
| Root filesystem | Read-only (where possible) | `--read-only` |
| Capabilities | Dropped | `--cap-drop ALL` |
| Resource limits | Enforced | CPU and memory limits |
| Health checks | Required | Application health endpoint |

---

## 6. Web Application Hardening

### 6.1 HTTP Security Headers

Implemented in `utils/security_headers.py`:

| Header | Value | Purpose |
|--------|-------|---------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Force HTTPS |
| Content-Security-Policy | Nonce-based (production) | XSS prevention |
| X-Content-Type-Options | nosniff | MIME type sniffing prevention |
| X-Frame-Options | DENY | Clickjacking prevention |
| X-XSS-Protection | 1; mode=block | XSS filter |
| Referrer-Policy | strict-origin-when-cross-origin | Referrer leakage prevention |
| Permissions-Policy | geolocation=(), microphone=(), camera=() | Feature restrictions |

### 6.2 Input Validation

| Control | Implementation | Location |
|---------|----------------|----------|
| Form validation | Flask-WTF with validators | `forms.py` |
| CSRF protection | Flask-WTF CSRF tokens | All forms |
| SQL injection prevention | SQLAlchemy ORM | All database queries |
| XSS prevention | Jinja2 auto-escaping | All templates |

### 6.3 Session Security

```python
# app.py session configuration
app.config.update(
    SESSION_COOKIE_SECURE=True,        # HTTPS only
    SESSION_COOKIE_HTTPONLY=True,      # No JavaScript access
    SESSION_COOKIE_SAMESITE='Lax',     # CSRF protection
    PERMANENT_SESSION_LIFETIME=1800,   # 30-minute timeout
)
```

### 6.4 Authentication Security

| Control | Standard | Implementation |
|---------|----------|----------------|
| Password hashing | PBKDF2-SHA256 | Werkzeug default |
| Account lockout | 5 failed attempts | `models.py` |
| Session timeout | 30 minutes | Flask configuration |
| Rate limiting | 5 attempts/minute | `RateLimiter` class |
| Brute force detection | 10 attempts/5 min | `security_alerts.py` |

---

## 7. Third-Party Integration Hardening

### 7.1 Epic FHIR Integration

| Control | Standard | Rationale |
|---------|----------|-----------|
| OAuth tokens | Short-lived, rotated | Token security |
| API scope | Minimum required | Least privilege |
| TLS | Required | Data in transit |
| Error handling | No PHI in logs | PHI protection |

### 7.2 Stripe Integration

| Control | Standard | Rationale |
|---------|----------|-----------|
| API key storage | Secrets Manager | Key protection |
| Webhook verification | Signature validation | Request authenticity |
| PCI scope | SAQ-A eligible | Minimal card data handling |

### 7.3 Resend (Email) Integration

| Control | Standard | Rationale |
|---------|----------|-----------|
| API key storage | Secrets Manager | Key protection |
| Email content | No PHI | HIPAA compliance |
| Rate limiting | Per Resend limits | Prevent abuse |

---

## 8. Secret Management

### 8.1 Storage Standards

| Environment | Storage | Access |
|-------------|---------|--------|
| Development | Replit Secrets | Developer access |
| Production | AWS Secrets Manager | IAM roles |

### 8.2 Secret Categories

| Category | Rotation | Examples |
|----------|----------|----------|
| Critical | Annual + on compromise | ENCRYPTION_KEY, SESSION_SECRET |
| Sensitive | Annual | STRIPE_SECRET_KEY, Epic keys |
| Standard | Annual | RESEND_API_KEY |

See `/docs/security/key-management-policy.md` for detailed procedures.

---

## 9. Logging and Monitoring

### 9.1 Required Logs

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Application logs | 90 days | CloudWatch Logs |
| Access logs | 7 years | S3 (compliance) |
| Security events | 7 years | AdminLog table |
| Database logs | 90 days | CloudWatch Logs |

### 9.2 Monitoring Alerts

| Metric | Threshold | Action |
|--------|-----------|--------|
| Failed logins | 10/5 min | Security alert |
| Account lockouts | Any | Email notification |
| Error rate | >5% | Operations alert |
| Latency | P95 > 2s | Operations alert |

---

## 10. Compliance Verification

### 10.1 Automated Scanning

| Tool | Frequency | Scope |
|------|-----------|-------|
| CodeQL | Every commit | Source code |
| Container scanning | Every build | Docker images |
| Dependency check | Weekly | Python packages |
| SSL Labs test | Monthly | TLS configuration |

### 10.2 Manual Reviews

| Review | Frequency | Reviewer |
|--------|-----------|----------|
| Configuration audit | Quarterly | Security team |
| Access review | Quarterly | Security + managers |
| Penetration test | Annually | Third party |
| Hardening verification | After changes | DevOps |

---

## 11. Hardening Checklist

### 11.1 New System Deployment

- [ ] Base image verified and scanned
- [ ] Non-root user configured
- [ ] Network security groups configured
- [ ] TLS certificates installed
- [ ] Security headers enabled
- [ ] Logging configured
- [ ] Secrets in secure storage
- [ ] Backup configuration verified
- [ ] Monitoring alerts configured
- [ ] Documentation updated

### 11.2 Periodic Verification

- [ ] All patches applied (monthly)
- [ ] SSL certificate validity (monthly)
- [ ] Security group review (quarterly)
- [ ] Access control review (quarterly)
- [ ] Log review (monthly)
- [ ] Backup test (quarterly)

---

## 12. Exception Process

### 12.1 Exception Requests

Deviations from these standards require:
1. Written justification
2. Risk assessment
3. Compensating controls
4. Security Officer approval
5. Time-limited approval (max 6 months)

### 12.2 Exception Documentation

| Field | Required |
|-------|----------|
| System affected | Yes |
| Standard deviation | Yes |
| Business justification | Yes |
| Risk assessment | Yes |
| Compensating controls | Yes |
| Approval signature | Yes |
| Expiration date | Yes |

---

## 13. References

| Document | Location |
|----------|----------|
| CIS Benchmarks | https://cisecurity.org/benchmarks |
| NIST 800-123 | Server Security Guide |
| AWS Security Best Practices | AWS Documentation |
| Key Management Policy | /docs/security/key-management-policy.md |
| Security Whitepaper | /docs/SECURITY_WHITEPAPER.md |

---

## Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| DevOps Lead | [TBD] | | |
| Security Officer | [TBD] | | |
| Technical Lead | [TBD] | | |
