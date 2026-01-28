# HITRUST CSF Readiness Checklist

## Overview

This document maps HealthPrep security controls to HITRUST CSF domains for Coalfire assessment preparation. Last updated: January 2026.

## Authentication Context: Epic MFA Justification

**HealthPrep operates within an Epic-authenticated healthcare environment.** Epic Hyperspace/Hyperdrive requires Multi-Factor Authentication (MFA) for:
- EPCS workflows (DEA mandate, FIPS 140-2 Level 1 required)
- Epic UserWeb, Cosmos, and Vendor Services access
- Client logins via Duo, Okta, EntraID, or native TOTP

**Justification for HealthPrep 2FA approach:** Healthcare staff already complete MFA authentication to access Epic before interacting with patient data. HealthPrep's additional 2FA layer (password + session token) provides defense-in-depth within this already-authenticated EMR context, meeting HIPAA access control requirements without duplicating full MFA flows that would impede clinical workflows.

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
| Risk assessment | NIST 800-30 based | `/docs/security/NIST_800_30_RISK_REGISTER.md` | Implemented |
| Vulnerability management | Formal policy with scanning | `/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md` | Implemented |
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
| Incident Response Plan | Formal IRP with HIPAA procedures | `/docs/security/INCIDENT_RESPONSE_PLAN.md` | Implemented |
| Incident lifecycle logging | IncidentLogger class | `services/security_alerts.py` | Implemented |
| Account lockout alerts | Email to org admins | `services/security_alerts.py` | Implemented |
| Brute force detection | 10 attempts/5 min threshold | `services/security_alerts.py` | Implemented |
| PHI filter failure alerts | Email notifications | `services/security_alerts.py` | Implemented |
| Incident logging | AdminLog with alert events | `models.py` | Implemented |
| Breach notification tracking | 60-day HIPAA deadline logging | `services/security_alerts.py` | Implemented |

### 10.0 Business Continuity

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Business Continuity Plan | Formal BCP/DRP | `/docs/security/BUSINESS_CONTINUITY_PLAN.md` | Implemented |
| Backup strategy | AWS RDS PITR | BCP Section 4 | Implemented |
| Recovery procedures | Documented DR procedures | BCP Section 5 | Implemented |
| Data retention | Configurable per org | Organization model | Implemented |

### 10.g Cryptographic Key Management

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| Key generation procedures | Cryptographically secure generation | `/docs/security/key-management-policy.md` | Implemented |
| Key distribution | AWS Secrets Manager / Replit Secrets with IAM/RBAC | Key Management Policy Section 4 | Implemented |
| Key storage | Encrypted at rest in platform secret stores | Key Management Policy Section 3-4 | Implemented |
| Key rotation | Defined schedules and procedures | Key Management Policy Section 2, 10 | Implemented |
| Key destruction | Secure destruction, no retention | Key Management Policy Section 5.2 | Implemented |
| Key compromise handling | Emergency rotation procedure | Key Management Policy Section 5.3 | Implemented |
| Audit logging | CloudTrail (AWS) / Platform logs (Replit) | Key Management Policy Section 9 | Implemented |

### 11.0 Information Privacy

| Requirement | HealthPrep Implementation | Evidence Location | Status |
|-------------|---------------------------|-------------------|--------|
| PHI redaction | Regex-based filtering | `ocr/phi_filter.py` | Implemented |
| Minimal data storage | LOINC-based titles | `utils/document_types.py` | Implemented |
| Secure file deletion | 3-pass overwrite | `utils/secure_delete.py` | Implemented |
| Encryption at rest | Database field encryption | `models.py` | Implemented |

## Evidence Collection Checklist

### Technical Evidence

- [ ] Network architecture diagram (AWS VPC design) - *Pending AWS migration*
- [ ] Data flow diagram showing PHI paths - *Can be generated from codebase*
- [x] Encryption key management documentation (`/docs/security/key-management-policy.md`)
- [x] Access control matrix - *Implemented in code: User.role (root/admin/user), org_id scoping*
- [x] Audit log samples (anonymized) - *Available via `/admin/logs` export*
- [ ] Penetration test results - *Pending third-party engagement*
- [ ] Vulnerability scan reports - *Pending third-party engagement*

### Administrative Evidence

- [x] Information Security Policy (`/docs/SECURITY_WHITEPAPER.md`)
- [x] Access Control Policy - *Documented in User.role implementation, multi-tenancy isolation*
- [x] Incident Response Plan (`/docs/security/INCIDENT_RESPONSE_PLAN.md`)
- [x] Business Continuity Plan (`/docs/security/BUSINESS_CONTINUITY_PLAN.md`)
- [x] Security Awareness & Training Policy (`/docs/security/SECURITY_AWARENESS_TRAINING_POLICY.md`)
- [x] System Hardening Standards (`/docs/security/SYSTEM_HARDENING_STANDARDS.md`)
- [x] Vulnerability Management Policy (`/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md`)
- [x] Vendor Risk Assessment (`/docs/security/VENDOR_RISK_ASSESSMENTS.md`)
- [ ] Workforce Training Records - *Organizational responsibility*
- [ ] BAA with AWS - *Required before production deployment*

### Audit Trail Evidence

- [x] User access logs (AdminLog exports) - *Available via `/admin/logs`*
- [x] Document processing audit trail (`/admin/documents`) - *Implemented with DocumentAuditLogger*
- [x] Security event logs - *Implemented via `services/security_alerts.py`*
- [x] Change management records - *Git commit history + Replit checkpoints*

## Pre-Assessment Actions

1. ~~**Complete NIST 800-30 Risk Register**~~ - ✅ Complete (`/docs/NIST_800_30_RISK_REGISTER.md`)
2. **Finalize AWS Architecture** - Complete VPC design and security group documentation
3. **Conduct Penetration Test** - Engage third-party for security assessment
4. ~~**Review All Policies**~~ - ✅ Policies match technical implementations
5. **Train Staff** - Document HIPAA/HITRUST awareness training completion
6. **Sign AWS BAA** - Execute Business Associate Agreement with AWS

## Gap Summary & Remediation Plan

### Resolved Items

| Item | Resolution | Date |
|------|------------|------|
| Formal incident response plan | Created `/docs/security/INCIDENT_RESPONSE_PLAN.md` | January 2026 |
| Key management documentation | Created `/docs/security/key-management-policy.md` | January 2026 |
| NIST 800-30 risk assessment | Created `/docs/security/NIST_800_30_RISK_REGISTER.md` | January 2026 |
| Security whitepaper | Created `/docs/SECURITY_WHITEPAPER.md` | January 2026 |
| PHI filter implementation | Implemented in `ocr/phi_filter.py` | January 2026 |
| Audit logging | Implemented via AdminLog + DocumentAuditLogger | January 2026 |
| Security alerting | Implemented via Resend integration | January 2026 |
| CSP hardening | Nonce-based CSP with FHIR URL auto-detection in `utils/security_headers.py` | January 2026 |
| Business Continuity Plan | Created `/docs/security/BUSINESS_CONTINUITY_PLAN.md` | January 2026 |
| Security Awareness & Training Policy | Created `/docs/security/SECURITY_AWARENESS_TRAINING_POLICY.md` | January 2026 |
| System Hardening Standards | Created `/docs/security/SYSTEM_HARDENING_STANDARDS.md` | January 2026 |
| Vulnerability Management Policy | Created `/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md` | January 2026 |
| Vendor Risk Assessments | Created `/docs/security/VENDOR_RISK_ASSESSMENTS.md` | January 2026 |
| HITRUST i1 Gap Analysis | Created `/docs/security/HITRUST_I1_GAP_ANALYSIS.md` | January 2026 |

### Remaining Gaps

| Gap | Priority | Owner | Remediation Plan | Target Date |
|-----|----------|-------|------------------|-------------|
| Formal incident response testing | Medium | Security Officer | Conduct tabletop exercise per IRP procedures | Pre-launch |
| TOTP 2FA implementation | Low | Dev Team | Optional enhancement (justified by Epic MFA context) | Future |
| Network architecture diagram | Medium | DevOps | Document AWS VPC, security groups, subnets | AWS migration |
| Data flow diagram | Medium | Dev Team | Generate PHI flow documentation from codebase | Pre-launch |
| Penetration test | High | Security Officer | Engage third-party security firm | Pre-launch |
| AWS BAA | Critical | Legal/Admin | Execute Business Associate Agreement with AWS | AWS migration |

### Remediation Timeline

**Phase 1: Pre-Launch (Current → Production)**
- [x] CSP hardening (nonce-based, FHIR URL auto-detection)
- [x] Security Awareness & Training Policy
- [x] System Hardening Standards
- [x] Vulnerability Management Policy
- [x] Vendor Risk Assessments (Epic, AWS, Stripe, Resend)
- [x] HITRUST i1 Gap Analysis (19 domains)
- [ ] Incident response tabletop exercise
- [ ] Data flow diagram
- [ ] Penetration test engagement

**Phase 2: AWS Migration**
- [ ] Network architecture diagram
- [x] Business Continuity Plan
- [ ] AWS BAA execution
- [ ] Secret migration to AWS Secrets Manager

**Phase 3: Ongoing**
- [ ] Annual key rotation (per Key Management Policy)
- [ ] Workforce training records maintenance
- [ ] TOTP 2FA enhancement (optional)

## Assessor Contact Points

- **Security Officer**: [To be designated]
- **Technical Lead**: Development team
- **Evidence Repository**: This documentation + code repository
- **Audit Log Access**: `/admin/documents` and `/admin/logs`

## Document References

| Document | Location | Purpose |
|----------|----------|---------|
| Security Whitepaper | `/docs/SECURITY_WHITEPAPER.md` | Overall security architecture |
| Incident Response Plan | `/docs/security/INCIDENT_RESPONSE_PLAN.md` | Breach handling procedures |
| Business Continuity Plan | `/docs/security/BUSINESS_CONTINUITY_PLAN.md` | Disaster recovery procedures |
| NIST 800-30 Risk Register | `/docs/security/NIST_800_30_RISK_REGISTER.md` | Threat analysis and mitigations |
| Key Management Policy | `/docs/security/key-management-policy.md` | Encryption key lifecycle |
| Security Checklist | `/docs/security/SECURITY_CHECKLIST.md` | Pre-deployment verification |
| HITRUST i1 Gap Analysis | `/docs/security/HITRUST_I1_GAP_ANALYSIS.md` | 19-domain compliance mapping |
| Security Awareness & Training | `/docs/security/SECURITY_AWARENESS_TRAINING_POLICY.md` | Training requirements (Domain 02) |
| System Hardening Standards | `/docs/security/SYSTEM_HARDENING_STANDARDS.md` | Configuration baselines (Domain 06) |
| Vulnerability Management | `/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md` | Scanning and patching (Domain 07) |
| Vendor Risk Assessments | `/docs/security/VENDOR_RISK_ASSESSMENTS.md` | Third-party assurance (Domain 14) |
