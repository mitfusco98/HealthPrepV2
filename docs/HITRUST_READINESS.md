# HITRUST CSF Readiness Checklist

## Overview

This document maps HealthPrep security controls to HITRUST CSF domains for Coalfire assessment preparation. Last updated: February 2026.

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
| Risk assessment | NIST 800-30 based | `/docs/NIST_800_30_RISK_REGISTER.md` | Implemented |
| Vulnerability management | AWS Inspector ECR scanning + Dockerfile patches | `/docs/security/vulnerability-remediation-log.md` | Implemented |
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
| Backup strategy | AWS RDS automated daily snapshots | `/docs/BUSINESS_CONTINUITY_PLAN.md` | Implemented |
| Recovery procedures | Documented RTO/RPO with runbooks | `/docs/BUSINESS_CONTINUITY_PLAN.md` | Implemented |
| DR testing | Monthly backup verification, quarterly restore drills | `/docs/security/dr-drill-log.md` | Implemented |
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

- [x] Network architecture diagram (`/docs/security/aws-network-architecture.md`) - *VPC, subnets, security groups, traffic flow*
- [x] Data flow diagram showing PHI paths (`/docs/security/aws-network-architecture.md`) - *Included in network architecture*
- [x] Encryption key management documentation (`/docs/security/key-management-policy.md`)
- [x] Access control matrix - *Implemented in code: User.role (root/admin/user), org_id scoping*
- [x] Audit log samples (anonymized) - *Available via `/admin/logs` export*
- [ ] Penetration test results - *Pending third-party engagement*
- [x] Vulnerability scan reports - *AWS Inspector enabled, 100% CVE accountability achieved*
  - `/docs/security/vulnerability-remediation-log.md` - Detailed CVE tracking
  - `/docs/security/inspector-findings-summary.md` - Point-in-time Inspector evidence

### Administrative Evidence

- [x] Information Security Policy (`/docs/SECURITY_WHITEPAPER.md`)
- [x] Access Control Policy - *Documented in User.role implementation, multi-tenancy isolation*
- [x] Incident Response Plan (`/docs/INCIDENT_RESPONSE_PLAN.md`)
- [x] Business Continuity Plan (`/docs/BUSINESS_CONTINUITY_PLAN.md`) - *Includes AWS resource ARNs, DR procedures*
- [ ] Workforce Training Records - *Organizational responsibility*
- [x] Vendor Risk Assessment (`/docs/security/vendor-risk-assessments.md`) - *AWS, Epic, Stripe, Resend assessed*
- [ ] BAA with AWS - *Required before production deployment*

### Audit Trail Evidence

- [x] User access logs (AdminLog exports) - *Available via `/admin/logs`*
- [x] Document processing audit trail (`/admin/documents`) - *Implemented with DocumentAuditLogger*
- [x] Security event logs - *Implemented via `services/security_alerts.py`*
- [x] Change management records - *Git commit history + Replit checkpoints*

## Pre-Assessment Actions

1. ~~**Complete NIST 800-30 Risk Register**~~ - ✅ Complete (`/docs/NIST_800_30_RISK_REGISTER.md`)
2. ~~**Finalize AWS Architecture**~~ - ✅ Complete (`/docs/security/aws-network-architecture.md`)
3. **Conduct Penetration Test** - Engage third-party for security assessment
4. ~~**Review All Policies**~~ - ✅ Policies match technical implementations
5. **Train Staff** - Document HIPAA/HITRUST awareness training completion
6. **Sign AWS BAA** - Execute Business Associate Agreement with AWS

## Gap Summary & Remediation Plan

### Resolved Items

| Item | Resolution | Date |
|------|------------|------|
| Formal incident response plan | Created `/docs/INCIDENT_RESPONSE_PLAN.md` | January 2026 |
| Key management documentation | Created `/docs/security/key-management-policy.md` | January 2026 |
| NIST 800-30 risk assessment | Created `/docs/NIST_800_30_RISK_REGISTER.md` | January 2026 |
| Security whitepaper | Created `/docs/SECURITY_WHITEPAPER.md` | January 2026 |
| PHI filter implementation | Implemented in `ocr/phi_filter.py` | January 2026 |
| Audit logging | Implemented via AdminLog + DocumentAuditLogger | January 2026 |
| Security alerting | Implemented via Resend integration | January 2026 |
| CSP hardening | Nonce-based CSP with FHIR URL auto-detection in `utils/security_headers.py` | January 2026 |
| HITRUST shared responsibility matrix | Created `/docs/security/hitrust-shared-responsibility-matrix.md` | February 2026 |
| Business Continuity Plan | Created `/docs/BUSINESS_CONTINUITY_PLAN.md` with AWS resource ARNs | February 2026 |
| DR drill log and procedures | Created `/docs/security/dr-drill-log.md` | February 2026 |
| Vendor risk assessments | Created `/docs/security/vendor-risk-assessments.md` (AWS, Epic, Stripe, Resend) | February 2026 |
| Vulnerability scanning | AWS Inspector enabled for ECR container scanning | February 2026 |
| Vulnerability remediation log | Created `/docs/security/vulnerability-remediation-log.md` | February 2026 |
| First backup verification drill | Completed and logged in DR drill log | February 2026 |
| ECR image cleanup | Removed vulnerable images, only patched image remains | February 2026 |
| 100% CVE accountability | 2 active findings (0 Critical, 0 High), all documented | February 2026 |
| Inspector findings summary | Created `/docs/security/inspector-findings-summary.md` for HITRUST evidence | February 2026 |
| Network architecture diagram | Created `/docs/security/aws-network-architecture.md` with VPC, subnets, security groups, PHI data flow | February 2026 |

### Remaining Gaps

| Gap | Priority | Owner | Remediation Plan | Target Date |
|-----|----------|-------|------------------|-------------|
| Formal incident response testing | Medium | Mitchell Fusillo | Conduct tabletop exercise per IRP procedures | Pre-launch |
| TOTP 2FA implementation | Low | Dev Team | Optional enhancement (justified by Epic MFA context) | Future |
| Penetration test | High | Mitchell Fusillo | Engage third-party security firm | Pre-launch |
| Workforce training records | Low | HR/Org Admin | Document HIPAA/HITRUST training completion | Pre-launch |
| AWS BAA | Critical | Mitchell Fusillo | Execute Business Associate Agreement with AWS | AWS migration |
| Expat/sqlite3 CVE remediation | Low | Mitchell Fusillo | Monitor Debian for patch releases (2 active findings) | Ongoing |

### Remediation Timeline

**Phase 1: Pre-Launch (Current → Production)**
- [x] CSP hardening (nonce-based, FHIR URL auto-detection)
- [x] Vulnerability scanning (AWS Inspector enabled February 2026)
- [x] Vendor risk assessment documentation (AWS, Epic, Stripe, Resend)
- [x] Data flow diagram (included in `/docs/security/aws-network-architecture.md`)
- [ ] Incident response tabletop exercise
- [ ] Penetration test engagement

**Phase 2: AWS Migration**
- [x] Business Continuity Plan (`/docs/BUSINESS_CONTINUITY_PLAN.md`)
- [x] DR drill procedures and logging (`/docs/security/dr-drill-log.md`)
- [x] Network architecture diagram (`/docs/security/aws-network-architecture.md`)
- [ ] AWS BAA execution
- [ ] Secret migration to AWS Secrets Manager

**Phase 3: Ongoing**
- [x] Monthly backup verification drills (first drill completed February 2026)
- [ ] Quarterly database restore drills
- [ ] Annual key rotation (per Key Management Policy)
- [ ] Workforce training records maintenance
- [ ] Vulnerability remediation monitoring (`/docs/security/vulnerability-remediation-log.md`)
- [ ] TOTP 2FA enhancement (optional)

## Assessor Contact Points

- **Security Officer**: Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567)
- **Technical Lead**: Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567)
- **Evidence Repository**: This documentation + code repository
- **Audit Log Access**: `/admin/documents` and `/admin/logs`

## Document References

| Document | Location | Purpose |
|----------|----------|---------|
| Security Whitepaper | `/docs/SECURITY_WHITEPAPER.md` | Overall security architecture |
| Incident Response Plan | `/docs/INCIDENT_RESPONSE_PLAN.md` | Breach handling procedures |
| NIST 800-30 Risk Register | `/docs/NIST_800_30_RISK_REGISTER.md` | Threat analysis and mitigations |
| Key Management Policy | `/docs/security/key-management-policy.md` | Encryption key lifecycle |
| Security Checklist | `/docs/SECURITY_CHECKLIST.md` | Pre-deployment verification |
| Business Continuity Plan | `/docs/BUSINESS_CONTINUITY_PLAN.md` | DR procedures, RTO/RPO, AWS resources |
| HITRUST Shared Responsibility Matrix | `/docs/security/hitrust-shared-responsibility-matrix.md` | AWS vs HealthPrep vs Customer controls |
| DR Drill Log | `/docs/security/dr-drill-log.md` | BCP/DR test execution records |
| Vendor Risk Assessments | `/docs/security/vendor-risk-assessments.md` | Third-party vendor risk analysis |
| Vulnerability Remediation Log | `/docs/security/vulnerability-remediation-log.md` | CVE tracking and remediation evidence |
| Inspector Findings Summary | `/docs/security/inspector-findings-summary.md` | Point-in-time AWS Inspector evidence |
| AWS Network Architecture | `/docs/security/aws-network-architecture.md` | VPC design, security groups, PHI data flow |
