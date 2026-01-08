# HITRUST CSF Readiness Checklist

## Overview

This document maps HealthPrep security controls to HITRUST CSF domains for Coalfire assessment preparation. Last updated: January 2026.

## Control Domain Mapping

### 01.0 Information Protection Program

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Information security policy | SECURITY_WHITEPAPER.md | `/docs/SECURITY_WHITEPAPER.md` | Implemented |
| Data classification | PHI classification in code | `ocr/phi_filter.py` | Implemented |
| Encryption requirements | AES-256 field encryption | `models.py` (EncryptedType) | Implemented |

### 01.1 Access Control

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| User authentication | Flask-Login with password hashing | `routes/auth_routes.py` | Implemented |
| Role-based access control | Admin/User/Root roles | `models.py` (User.role) | Implemented |
| Multi-tenancy isolation | Organization-scoped queries | `utils/multi_tenancy.py` | Implemented |
| Session management | Secure cookies, timeout | `app.py` (session config) | Implemented |
| Account lockout | 5-attempt lockout | `models.py` (is_account_locked) | Implemented |
| Rate limiting | IP-based rate limiting | `utils/security.py` (RateLimiter) | Implemented |

### 01.2 Risk Management

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Risk assessment | NIST 800-30 based | `/docs/NIST_800_30_RISK_REGISTER.md` | Implemented |
| Vulnerability management | Dependency updates | `requirements.txt` versioning | In Progress |
| Penetration testing | Recommended pre-launch | DEPLOYMENT_READINESS.md | Planned |

### 05.0 Endpoint Protection

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Input validation | Form validation, CSRF | `forms.py`, Flask-WTF | Implemented |
| XSS prevention | Template auto-escaping, CSP | `utils/security_headers.py` | Implemented |
| SQL injection prevention | SQLAlchemy ORM | All database queries | Implemented |

### 09.0 Audit Logging & Monitoring

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Access logging | AdminLog table | `models.py` (AdminLog) | Implemented |
| Document processing audit | DocumentAuditLogger | `utils/document_audit.py` | Implemented |
| PHI access logging | Structured audit events | `utils/document_audit.py` | Implemented |
| Log retention | 7-year retention policy | Organization.audit_retention_years | Implemented |
| Security alerting | Email alerts via Resend | `services/security_alerts.py` | Implemented |

### 09.1 Incident Management

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Incident Response Plan | Formal IRP with HIPAA procedures | `/docs/INCIDENT_RESPONSE_PLAN.md` | Implemented |
| Incident lifecycle logging | IncidentLogger class | `services/security_alerts.py` | Implemented |
| Account lockout alerts | Email to org admins | `services/security_alerts.py` | Implemented |
| Brute force detection | 10 attempts/5 min threshold | `services/security_alerts.py` | Implemented |
| PHI filter failure alerts | Email notifications | `services/security_alerts.py` | Implemented |
| Incident logging | AdminLog with alert events | `models.py` | Implemented |
| Breach notification tracking | 60-day HIPAA deadline logging | `services/security_alerts.py` | Implemented |

### 10.0 Business Continuity

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Backup strategy | AWS RDS PITR | SECURITY_WHITEPAPER.md | Designed |
| Recovery procedures | Deterministic recovery | SECURITY_WHITEPAPER.md | Documented |
| Data retention | Configurable per org | Organization model | Implemented |

### 11.0 Information Privacy

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| PHI redaction | Regex-based filtering | `ocr/phi_filter.py` | Implemented |
| Minimal data storage | LOINC-based titles | `utils/document_types.py` | Implemented |
| Secure file deletion | 3-pass overwrite | `utils/secure_delete.py` | Implemented |
| Encryption at rest | Database field encryption | `models.py` | Implemented |

## Evidence Collection Checklist

### Technical Evidence

- [ ] Network architecture diagram (AWS VPC design)
- [ ] Data flow diagram showing PHI paths
- [ ] Encryption key management documentation
- [ ] Access control matrix
- [ ] Audit log samples (anonymized)
- [ ] Penetration test results
- [ ] Vulnerability scan reports

### Administrative Evidence

- [ ] Information Security Policy
- [ ] Access Control Policy
- [x] Incident Response Plan (`/docs/INCIDENT_RESPONSE_PLAN.md`)
- [ ] Business Continuity Plan
- [ ] Workforce Training Records
- [ ] Vendor Risk Assessment (Epic, AWS)
- [ ] BAA with AWS

### Audit Trail Evidence

- [ ] User access logs (AdminLog exports)
- [ ] Document processing audit trail (`/admin/documents`)
- [ ] Security event logs
- [ ] Change management records

## Pre-Assessment Actions

1. **Complete NIST 800-30 Risk Register** - Document all identified threats and mitigations
2. **Finalize AWS Architecture** - Complete VPC design and security group documentation
3. **Conduct Penetration Test** - Engage third-party for security assessment
4. **Review All Policies** - Ensure written policies match technical implementations
5. **Train Staff** - Document HIPAA/HITRUST awareness training completion
6. **Sign AWS BAA** - Execute Business Associate Agreement with AWS

## Gap Summary

| Gap | Priority | Remediation Plan | Target Date |
|-----|----------|------------------|-------------|
| Production CSP hardening | Medium | Remove unsafe-inline | Pre-launch |
| TOTP 2FA implementation | Low | Planned feature | Future |
| ~~Formal incident response plan~~ | ~~High~~ | ~~Create IRP document~~ | ~~Complete~~ |
| Formal incident response testing | Medium | Tabletop exercise per IRP | Pre-launch |

## Assessor Contact Points

- **Security Officer**: [To be designated]
- **Technical Lead**: Development team
- **Evidence Repository**: This documentation + code repository
- **Audit Log Access**: `/admin/documents` and `/admin/logs`
