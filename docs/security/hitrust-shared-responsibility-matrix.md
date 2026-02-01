# HealthPrep HITRUST CSF Shared Responsibility Matrix

**Document Version:** 1.0  
**Effective Date:** February 2026  
**AWS HITRUST Certification:** CSF v11.5.1 (177 services certified)  
**Review Frequency:** Annual or upon significant changes  
**Alignment:** HITRUST CSF v11 domain structure

---

## 1. Purpose and Scope

### Purpose

This document maps HITRUST CSF control requirements across three responsibility layers:

| Layer | Owner | Description |
|-------|-------|-------------|
| **AWS Inherited** | Amazon Web Services | Controls covered by AWS HITRUST certification (verify via AWS Artifact) |
| **HealthPrep Application** | HealthPrep Development | Controls implemented in application code with specific evidence paths |
| **Customer Organizational** | Healthcare Organization | Controls customers must implement (policies, training, physical security) |

**Note:** AWS inherited controls require verification via AWS Artifact certification letter. Claims in this document are based on AWS's published HITRUST scope but should be validated against current AWS documentation.

### Scope

This matrix covers **primary technical control domains** most relevant to the HealthPrep application:

| Domain | Covered | Rationale |
|--------|---------|-----------|
| 01.x Access Control | Yes | Core application security controls |
| 02.x Human Resources | Partial | Customer organizational responsibility; see Section 4 |
| 03.x Risk Management | Yes | Application risk assessment documented |
| 04.x Security Policy | Partial | HealthPrep provides templates; customer adopts |
| 05.x Endpoint Protection | Yes | Input validation, XSS/SQLi prevention |
| 06.x Compliance | Partial | PHI handling implemented; regulatory notification is customer responsibility |
| 07.x Asset Management | Customer | Organizational asset management is customer responsibility |
| 08.x Physical Security | AWS Inherited | AWS data center controls; verify via AWS Artifact |
| 09.x Audit & Incident | Yes | Comprehensive audit logging and incident alerting |
| 10.x Business Continuity | Partial | DR documented; full BCP is customer responsibility |
| 10.g Key Management | Yes | Full key lifecycle documented |
| 11.x Privacy | Yes | PHI filtering, secure deletion, encryption |
| 12.x Supplier Management | Customer | Vendor risk assessment is customer responsibility |

For detailed control mappings, also reference: `docs/HITRUST_READINESS.md`

**Note:** Domains marked "Customer" or "Partial" above do not have detailed mappings in Section 2 below. For those domains, customers should develop their own control documentation.

---

## 2. Control Domain Mapping

This section provides detailed mappings only for domains where HealthPrep has implemented technical controls. Domains 02.x, 04.x, 06.x, 07.x, 08.x, and 12.x are primarily customer or AWS responsibilities - see Section 4 for customer requirements.

### 01.0 Information Protection Program

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Information security policy | Customer + HealthPrep | HealthPrep provides technical policy documentation | `docs/SECURITY_WHITEPAPER.md` |
| Data classification | HealthPrep | PHI classification and filtering | `ocr/phi_filter.py` (PHIFilter class) |
| Encryption requirements | HealthPrep | Fernet AES-256 field encryption | `utils/encryption.py`, `models.py` (encrypt_field/decrypt_field usage) |

---

### 01.1 Access Control

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| User authentication | HealthPrep | Flask-Login with Werkzeug password hashing | `routes/auth_routes.py`, `models.py` (User.check_password) |
| Role-based access control | HealthPrep | Three-tier roles: root_admin, admin, user | `models.py` (User.role field, lines ~790-800) |
| Multi-tenancy isolation | HealthPrep | Organization-scoped queries via org_id | `utils/multi_tenancy.py`, `models.py` (User.org_id) |
| Session management | HealthPrep | Configurable timeout, secure cookies | `app.py` (session config), `models.py` (session_timeout_minutes) |
| Account lockout | HealthPrep | 5-attempt lockout (is_account_locked field) | `models.py` (User.is_account_locked, lines ~802-808) |
| Security lockout | HealthPrep | Permanent lock for security events (security_locked field) | `models.py` (User.security_locked, lines ~804-807) |
| Rate limiting | HealthPrep | IP-based rate limiting with Redis support | `utils/security.py` (RateLimiter class) |

---

### 01.2 Risk Management

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Risk assessment | HealthPrep | NIST 800-30 based threat/vulnerability analysis | `docs/NIST_800_30_RISK_REGISTER.md` |
| Vulnerability management | HealthPrep | Dependency version management | `pyproject.toml`, `requirements.txt` |
| Penetration testing | Planned | Third-party engagement recommended | `docs/HITRUST_READINESS.md` (gap analysis) |

---

### 05.0 Endpoint Protection

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Input validation | HealthPrep | Flask-WTF form validation, CSRF protection | `forms/*.py` (LoginForm, etc.), Flask-WTF CSRF |
| XSS prevention | HealthPrep | Jinja2 auto-escaping, nonce-based CSP | `utils/security_headers.py` |
| SQL injection prevention | HealthPrep | SQLAlchemy ORM parameterized queries | All database operations use SQLAlchemy |

---

### 09.0 Audit Logging & Monitoring

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Access logging | HealthPrep | AdminLog table with structured events | `models.py` (AdminLog class), `services/enhanced_audit_logging.py` |
| Document processing audit | HealthPrep | DocumentAuditLogger for PHI access | `utils/document_audit.py` |
| PHI access logging | HealthPrep | HIPAA-compliant audit with identifier hashing | `services/enhanced_audit_logging.py` (HIPAAAuditLogger class, lines 19-100) |
| Log retention | HealthPrep | 7-year configurable retention | `models.py` (Organization.audit_retention_days, line ~53) |
| Security alerting | HealthPrep | Email alerts via Resend integration | `services/security_alerts.py` (SecurityAlertService class) |

---

### 09.1 Incident Management

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Incident Response Plan | HealthPrep | Formal IRP with HIPAA procedures | `docs/INCIDENT_RESPONSE_PLAN.md` |
| Account lockout alerts | HealthPrep | Email notifications to org admins | `services/security_alerts.py` (send_account_lockout_alert, lines 35-100) |
| Brute force detection | HealthPrep | 10 attempts/5 min threshold with alerts | `services/security_alerts.py` (ALERT_THRESHOLDS, lines 19-23) |
| PHI filter failure alerts | HealthPrep | Email notifications on filter failures | `services/security_alerts.py` (ALERT_EVENT_TYPES, lines 25-32) |
| Breach notification tracking | HealthPrep | 60-day HIPAA deadline logging | `services/security_alerts.py` |

---

### 10.0 Business Continuity

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Backup strategy | Customer + AWS | Customer must configure AWS RDS backups; verify via AWS console | Customer AWS configuration |
| Data retention | HealthPrep | Configurable per organization | `models.py` (Organization.audit_retention_days) |
| Recovery procedures | HealthPrep | Documented recovery steps | `docs/BUSINESS_CONTINUITY_PLAN.md` |

---

### 10.g Cryptographic Key Management

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| Key generation | HealthPrep | Cryptographically secure generation | `docs/security/key-management-policy.md` Section 5.2 |
| Key storage | HealthPrep + AWS | AWS Secrets Manager / Platform secrets | `docs/security/key-management-policy.md` Section 4 |
| Key rotation | HealthPrep | Annual rotation schedule with procedures | `docs/security/key-management-policy.md` Section 2, 10 |
| Key destruction | HealthPrep | Secure destruction, no retention | `docs/security/key-management-policy.md` Section 5.2 Step 7 |
| Dual-key migration | HealthPrep | PHI re-encryption procedures | `docs/security/key-management-policy.md` Section 5 |

---

### 11.0 Information Privacy

| Requirement | Responsibility | HealthPrep Implementation | Evidence Location |
|-------------|----------------|---------------------------|-------------------|
| PHI redaction | HealthPrep | Regex-based filtering (15+ pattern categories) | `ocr/phi_filter.py` (PHIFilter class) |
| Minimal data storage | HealthPrep | LOINC-based document titles (PHI-free) | `utils/document_types.py` |
| Secure file deletion | HealthPrep | 3-pass overwrite with crash-safe registry | `utils/secure_delete.py` (OVERWRITE_PASSES=3, lines 23-24) |
| Encryption at rest | HealthPrep | Fernet symmetric encryption for sensitive fields | `utils/encryption.py`, `models.py` (Epic credentials encryption) |

---

## 3. AWS Infrastructure Controls

AWS HITRUST-certified controls can be inherited when using AWS services. **All claims below require verification via AWS Artifact and customer AWS configuration.**

| Control Area | Verification Required |
|--------------|----------------------|
| Physical security | AWS Artifact HITRUST certification letter |
| Infrastructure availability | AWS Artifact + customer service configuration |
| Network isolation | AWS Artifact + customer VPC/security group configuration |
| Encryption in transit | AWS Artifact + customer load balancer/database configuration |
| Encryption at rest | AWS Artifact + customer database/storage configuration |
| Backup and recovery | AWS Artifact + customer backup configuration |

**Important:** 
- AWS inherited controls apply only when customers configure AWS services appropriately
- Customers must verify their specific AWS configuration aligns with AWS's HITRUST certification
- HealthPrep does not maintain AWS infrastructure documentation - customers are responsible for their own AWS architecture documentation

---

## 4. Customer Organizational Controls

Healthcare organizations using HealthPrep are responsible for:

### Required for HITRUST Compliance

| Control | Customer Action | HealthPrep Support |
|---------|-----------------|-------------------|
| Security policies | Adopt/customize organizational security policies | `docs/SECURITY_WHITEPAPER.md` template |
| User access reviews | Periodic review of user access rights | Admin dashboard: `/admin/users` |
| Workforce training | HIPAA/security awareness training | Training materials not included |
| Termination procedures | Revoke access on employee departure | User deactivation in admin panel |
| Physical workstation security | Secure access to workstations | N/A (customer facility) |
| Incident reporting | Internal incident reporting procedures | Alert integration via `services/security_alerts.py` |
| Breach notification | Regulatory notification (60-day HIPAA) | Alerts provide initial detection |

### Required Before Production

- [ ] Sign Business Associate Agreement (BAA) with HealthPrep
- [ ] Sign AWS BAA via AWS Artifact
- [ ] Complete organizational risk assessment
- [ ] Document workforce training records
- [ ] Establish incident response procedures

---

## 5. Evidence Collection for Assessors

### Technical Evidence (HealthPrep Provides)

| Evidence Type | Location | Description |
|---------------|----------|-------------|
| Access control implementation | `models.py`, `routes/auth_routes.py` | User, role, session management code |
| Encryption implementation | `utils/encryption.py`, `models.py` | Fernet encryption for Epic credentials |
| Audit logging | `services/enhanced_audit_logging.py` | HIPAA-compliant audit trail |
| PHI protection | `ocr/phi_filter.py` | Redaction patterns and filtering |
| Secure deletion | `utils/secure_delete.py` | 3-pass overwrite implementation |
| Security alerting | `services/security_alerts.py` | Incident detection and notification |
| Key management | `docs/security/key-management-policy.md` | Rotation and lifecycle procedures |

### AWS Evidence (Via AWS Artifact)

- AWS HITRUST CSF v11.5.1 Certification Letter
- AWS Shared Responsibility Matrix
- AWS SOC 2 Type II Report
- AWS BAA (customer-specific)

### Customer Evidence (Organization Provides)

- Organizational security policies
- Workforce training records
- Access review documentation
- Incident response procedures
- Physical security documentation

---

## 6. Gap Analysis Summary

### Implemented Controls

| Domain | Status | Notes |
|--------|--------|-------|
| 01.1 Access Control | Implemented | Full RBAC, session management, lockout |
| 05.0 Endpoint Protection | Implemented | Input validation, XSS/SQLi prevention |
| 09.0 Audit Logging | Implemented | 7-year retention, PHI-safe logging |
| 09.1 Incident Management | Implemented | Automated alerting, IRP documented |
| 10.g Key Management | Implemented | Full key lifecycle documented |
| 11.0 Information Privacy | Implemented | PHI filtering, secure deletion |

### Pending Controls

| Gap | Priority | Target | Notes |
|-----|----------|--------|-------|
| Penetration testing | High | Pre-launch | Third-party engagement required |
| Vulnerability scanning | High | Pre-launch | Automated scanning tooling |
| Network architecture diagram | Medium | AWS migration | VPC documentation |
| Formal BCP testing | Medium | Post-launch | DR drill documentation |

---

## 7. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | February 2026 | HealthPrep Security | Initial shared responsibility matrix aligned with HITRUST CSF domains |

---

## 8. References

| Document | Location | Purpose |
|----------|----------|---------|
| AWS HITRUST Certification | AWS Artifact | Verify AWS inherited controls |
| HITRUST CSF v11 | HITRUST Alliance | Official control framework |
| HealthPrep Security Whitepaper | `docs/SECURITY_WHITEPAPER.md` | Overall security architecture |
| Incident Response Plan | `docs/INCIDENT_RESPONSE_PLAN.md` | Breach handling procedures |
| Key Management Policy | `docs/security/key-management-policy.md` | Cryptographic key lifecycle |
| HITRUST Readiness Checklist | `docs/HITRUST_READINESS.md` | Pre-assessment preparation |
| NIST 800-30 Risk Register | `docs/NIST_800_30_RISK_REGISTER.md` | Threat analysis |
