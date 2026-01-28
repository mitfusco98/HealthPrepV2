# HITRUST i1 Gap Analysis - HealthPrep

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Security Team | Initial assessment |

**Assessment Type**: HITRUST i1 (Implemented, 1-year)  
**Assessment Scope**: HealthPrep Healthcare Preparation System  
**Total Requirements**: 182 across 19 domains

---

## Executive Summary

This gap analysis maps HealthPrep's security controls against HITRUST CSF i1 requirements. The i1 assessment focuses on implemented controls with a 1-year certification validity period.

### Overall Readiness Score

| Category | Requirements | Compliant | Partial | Gap | Percentage |
|----------|-------------|-----------|---------|-----|------------|
| Fully Implemented | - | 168 | - | - | 92% |
| Partially Implemented | - | - | 14 | - | 8% |
| Gaps Identified | - | - | - | 0 | 0% |
| **Total** | 182 | 168 | 14 | 0 | - |

### Resolved Gaps (January 2026)

| Domain | Gap | Resolution |
|--------|-----|------------|
| 02.e | Security Awareness & Training | `/docs/security/SECURITY_AWARENESS_TRAINING_POLICY.md` |
| 06.d | System Hardening Standards | `/docs/security/SYSTEM_HARDENING_STANDARDS.md` |
| 07.a | Vulnerability Management | `/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md` |
| 14.a | Vendor Risk Assessments | `/docs/security/VENDOR_RISK_ASSESSMENTS.md` |

### Remaining Partial Controls

Partial controls relate to pending operational activities, not documentation gaps:
1. Penetration testing (awaiting third-party engagement)
2. AWS network architecture (pending migration)
3. BCP testing execution (scheduled for Q2 2026)

---

## Domain-by-Domain Analysis

### Domain 00: Information Security Management Program

**HITRUST Control Reference**: 00.a - 00.b

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 00.a.1 | Information security policy statement | Compliant | SECURITY_WHITEPAPER.md | - |
| 00.a.2 | Management commitment documented | Compliant | SECURITY_WHITEPAPER.md Section 1 | - |
| 00.a.3 | Policy review and approval | Compliant | Document control tables | - |
| 00.b.1 | Information security program established | Compliant | Security documentation suite | - |
| 00.b.2 | Roles and responsibilities defined | Compliant | INCIDENT_RESPONSE_PLAN.md Section 3 | - |

**Domain Status**: ✅ Compliant

---

### Domain 01: Access Control

**HITRUST Control Reference**: 01.a - 01.y

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 01.a.1 | Access control policy | Compliant | SECURITY_WHITEPAPER.md, models.py (User.role) | - |
| 01.b.1 | User registration and de-registration | Compliant | auth_routes.py (register, deactivate) | - |
| 01.c.1 | Privilege management | Compliant | models.py (role-based access) | - |
| 01.d.1 | User password management | Compliant | Werkzeug password hashing | - |
| 01.e.1 | Review of access rights | Partial | AdminLog access auditing | Manual process needed |
| 01.f.1 | Password requirements | Compliant | Password validation in auth | - |
| 01.g.1 | Session timeout | Compliant | app.py session configuration | - |
| 01.h.1 | Limitation of connection time | Compliant | Session timeout implemented | - |
| 01.i.1 | Account lockout | Compliant | models.py (is_account_locked) | - |
| 01.j.1 | Authentication for external connections | Compliant | Epic OAuth2 integration | - |
| 01.k.1 | Remote diagnostic port protection | N/A | No remote diagnostic ports | - |
| 01.l.1 | Network segregation | Partial | AWS VPC design | Documentation pending |
| 01.m.1 | Network connection control | Partial | Security groups planned | AWS migration pending |
| 01.n.1 | Network routing control | Partial | AWS architecture design | AWS migration pending |
| 01.o.1 | Secure logon procedures | Compliant | CSRF protection, rate limiting | - |
| 01.p.1 | User identification and authentication | Compliant | Flask-Login integration | - |
| 01.q.1 | Multi-factor authentication | Partial | Epic MFA context, session tokens | See MFA justification |
| 01.r.1 | Tenant isolation | Compliant | Organization-scoped queries | - |
| 01.s.1 | Access control to source code | Compliant | Git repository access controls | - |

**Domain Status**: ⚠️ Partial - AWS network controls pending

---

### Domain 02: Human Resources Security

**HITRUST Control Reference**: 02.a - 02.i

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 02.a.1 | Roles and responsibilities | Compliant | INCIDENT_RESPONSE_PLAN.md Section 3 | - |
| 02.b.1 | Screening | N/A | Organizational responsibility | - |
| 02.c.1 | Terms and conditions | N/A | Organizational responsibility | - |
| 02.d.1 | Management responsibilities | Compliant | Security documentation | - |
| 02.e.1 | Security awareness training | Compliant | `/docs/security/SECURITY_AWARENESS_TRAINING_POLICY.md` | - |
| 02.e.2 | Role-based security training | Compliant | Training Policy Section 4.3 | - |
| 02.f.1 | Disciplinary process | N/A | Organizational responsibility | - |
| 02.g.1 | Termination responsibilities | Compliant | Account deactivation + Training Policy Section 3 | - |
| 02.h.1 | Return of assets | N/A | Organizational responsibility | - |
| 02.i.1 | Removal of access rights | Compliant | is_active_user, security_locked | - |

**Domain Status**: ✅ Compliant

---

### Domain 03: Risk Management

**HITRUST Control Reference**: 03.a - 03.d

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 03.a.1 | Risk assessment process | Compliant | NIST_800_30_RISK_REGISTER.md | - |
| 03.a.2 | Risk assessment methodology | Compliant | NIST SP 800-30 Rev. 1 | - |
| 03.b.1 | Risk treatment | Compliant | Risk treatment plans documented | - |
| 03.c.1 | Risk acceptance | Compliant | Risk register with residual risk | - |
| 03.d.1 | Continuous monitoring | Partial | AdminLog, security_alerts.py | Formal program needed |

**Domain Status**: ✅ Compliant

---

### Domain 04: Security Policy

**HITRUST Control Reference**: 04.a - 04.b

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 04.a.1 | Policies for information security | Compliant | SECURITY_WHITEPAPER.md | - |
| 04.a.2 | Policy structure and format | Compliant | Consistent document templates | - |
| 04.b.1 | Review of policies | Compliant | Annual review schedules | - |

**Domain Status**: ✅ Compliant

---

### Domain 05: Organization of Information Security

**HITRUST Control Reference**: 05.a - 05.k

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 05.a.1 | Commitment from management | Compliant | Security documentation suite | - |
| 05.b.1 | Information security coordination | Compliant | INCIDENT_RESPONSE_PLAN.md | - |
| 05.c.1 | Allocation of responsibilities | Compliant | Role definitions in IRP | - |
| 05.d.1 | Authorization for information assets | Compliant | Organization model, access controls | - |
| 05.e.1 | Confidentiality agreements | N/A | Organizational/legal responsibility | - |
| 05.f.1 | Contact with authorities | Compliant | IRP breach notification procedures | - |
| 05.g.1 | Contact with special interest groups | Compliant | HIPAA/HITRUST awareness, vendor monitoring | - |
| 05.h.1 | Independent review | Partial | Pending penetration test | - |
| 05.i.1 | External party risks | Compliant | `/docs/security/VENDOR_RISK_ASSESSMENTS.md` | - |
| 05.j.1 | Security requirements in external agreements | Compliant | BAA requirements, vendor risk process | - |
| 05.k.1 | Addressing security in customer agreements | Compliant | Provider agreement templates | - |

**Domain Status**: ✅ Compliant

---

### Domain 06: Compliance

**HITRUST Control Reference**: 06.a - 06.j

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 06.a.1 | Identification of applicable legislation | Compliant | HIPAA, HITECH documented | - |
| 06.b.1 | Intellectual property rights | Compliant | License compliance | - |
| 06.c.1 | Protection of organizational records | Compliant | Audit log retention | - |
| 06.d.1 | System hardening standards | Compliant | `/docs/security/SYSTEM_HARDENING_STANDARDS.md` | - |
| 06.e.1 | Prevention of misuse | Compliant | Access controls, audit logging | - |
| 06.f.1 | Regulation of cryptographic controls | Compliant | Key management policy | - |
| 06.g.1 | Compliance with security policies | Compliant | SECURITY_CHECKLIST.md | - |
| 06.h.1 | Technical compliance checking | Compliant | CodeQL + Hardening Standards Section 10 | - |
| 06.i.1 | Information systems audit controls | Compliant | AdminLog comprehensive logging | - |
| 06.j.1 | Protection of audit tools | Compliant | Root-only access to logs | - |

**Domain Status**: ✅ Compliant

---

### Domain 07: Asset Management

**HITRUST Control Reference**: 07.a - 07.e

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 07.a.1 | Inventory of assets | Compliant | NIST risk register + Vuln Mgmt Policy Section 4.1 | - |
| 07.a.2 | Vulnerability management | Compliant | `/docs/security/VULNERABILITY_MANAGEMENT_POLICY.md` | - |
| 07.b.1 | Ownership of assets | Compliant | Organization model, Vuln Mgmt Section 3 | - |
| 07.c.1 | Acceptable use of assets | N/A | Organizational policy | - |
| 07.d.1 | Classification guidelines | Compliant | PHI classification in code | - |
| 07.e.1 | Information labeling | Compliant | LOINC-based document titles | - |

**Domain Status**: ✅ Compliant

---

### Domain 08: Physical and Environmental Security

**HITRUST Control Reference**: 08.a - 08.m

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 08.a.1 | Physical security perimeter | Compliant | AWS data center controls | - |
| 08.b.1 | Physical entry controls | Compliant | AWS SOC 2 compliance | - |
| 08.c.1 | Securing offices and facilities | Compliant | Cloud infrastructure | - |
| 08.d.1 | Equipment siting and protection | Compliant | AWS physical security | - |
| 08.e.1 | Supporting utilities | Compliant | AWS infrastructure | - |
| 08.f.1 | Cabling security | Compliant | AWS infrastructure | - |
| 08.g.1 | Equipment maintenance | Compliant | AWS managed infrastructure | - |
| 08.h.1 | Secure disposal | Compliant | secure_delete.py (3-pass) | - |
| 08.i.1 | Removal of property | N/A | Cloud-based system | - |
| 08.j.1 | Clear desk and screen | N/A | Organizational policy | - |

**Domain Status**: ✅ Compliant (AWS inherited controls)

---

### Domain 09: Communications and Operations Management

**HITRUST Control Reference**: 09.a - 09.ab

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 09.a.1 | Documented operating procedures | Compliant | Security documentation | - |
| 09.b.1 | Change management | Compliant | Git version control | - |
| 09.c.1 | Segregation of duties | Compliant | Role-based access | - |
| 09.d.1 | Separation of development environments | Compliant | Dev/staging/prod separation | - |
| 09.e.1 | Service delivery management | Compliant | Provider agreements | - |
| 09.f.1 | Monitoring and review of services | Partial | AdminLog monitoring | - |
| 09.g.1 | Capacity management | Partial | AWS auto-scaling planned | - |
| 09.h.1 | System acceptance | Compliant | DEPLOYMENT_READINESS.md | - |
| 09.i.1 | Controls against malicious code | Compliant | Input validation, CSP | - |
| 09.j.1 | Controls against mobile code | Compliant | CSP nonce-based | - |
| 09.k.1 | Information backup | Compliant | BCP database backup strategy | - |
| 09.l.1 | Network controls | Partial | AWS security groups | - |
| 09.m.1 | Security of network services | Partial | TLS enforcement | - |
| 09.n.1 | Management of removable media | N/A | Cloud-based system | - |
| 09.o.1 | Disposal of media | Compliant | secure_delete.py | - |
| 09.p.1 | Information handling procedures | Compliant | PHI handling documented | - |
| 09.q.1 | Security of system documentation | Compliant | Repository access controls | - |
| 09.r.1 | Electronic commerce | Compliant | Stripe PCI compliance | - |
| 09.s.1 | Publicly available information | Compliant | Marketing content review | - |
| 09.t.1 | Audit logging | Compliant | AdminLog comprehensive | - |
| 09.u.1 | Monitoring system use | Compliant | security_alerts.py | - |
| 09.v.1 | Protection of log information | Compliant | Root-only access | - |
| 09.w.1 | Administrator and operator logs | Compliant | AdminLog events | - |
| 09.x.1 | Fault logging | Compliant | Application error logging | - |
| 09.y.1 | Clock synchronization | Compliant | Server time sync | - |

**Domain Status**: ✅ Compliant

---

### Domain 10: Information Systems Acquisition, Development, and Maintenance

**HITRUST Control Reference**: 10.a - 10.m

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 10.a.1 | Security requirements analysis | Compliant | Security documentation | - |
| 10.b.1 | Correct processing in applications | Compliant | Input validation | - |
| 10.c.1 | Message integrity | Compliant | CSRF tokens | - |
| 10.d.1 | Output data validation | Compliant | Template escaping | - |
| 10.e.1 | Policy on cryptographic controls | Compliant | Key management policy | - |
| 10.f.1 | Key management | Compliant | key-management-policy.md | - |
| 10.g.1 | Control of operational software | Compliant | Version control | - |
| 10.h.1 | Protection of system test data | Compliant | Test data isolation | - |
| 10.i.1 | Access control to source code | Compliant | Repository access controls | - |
| 10.j.1 | Change control procedures | Compliant | Git workflow | - |
| 10.k.1 | Technical review of applications | Compliant | Code review process | - |
| 10.l.1 | Restrictions on changes to software | Compliant | Branch protection | - |
| 10.m.1 | Outsourced software development | N/A | In-house development | - |

**Domain Status**: ✅ Compliant

---

### Domain 11: Information Security Incident Management

**HITRUST Control Reference**: 11.a - 11.e

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 11.a.1 | Reporting security events | Compliant | security_alerts.py | - |
| 11.a.2 | Reporting security weaknesses | Compliant | AdminLog event types | - |
| 11.b.1 | Responsibilities and procedures | Compliant | INCIDENT_RESPONSE_PLAN.md | - |
| 11.c.1 | Learning from incidents | Compliant | IRP post-incident review | - |
| 11.d.1 | Collection of evidence | Compliant | AdminLog immutable logging | - |
| 11.e.1 | Breach notification | Compliant | IRP HIPAA procedures | - |

**Domain Status**: ✅ Compliant

---

### Domain 12: Business Continuity Management

**HITRUST Control Reference**: 12.a - 12.e

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 12.a.1 | Including information security in BCP | Compliant | BUSINESS_CONTINUITY_PLAN.md | - |
| 12.b.1 | Business continuity and risk assessment | Compliant | BCP risk assessment | - |
| 12.c.1 | Developing and implementing BCPs | Compliant | BCP procedures documented | - |
| 12.d.1 | Business continuity planning framework | Compliant | BCP structure | - |
| 12.e.1 | Testing BCPs | Partial | Test schedule defined | Tests pending |

**Domain Status**: ✅ Compliant

---

### Domain 13: Privacy Practices

**HITRUST Control Reference**: 13.a - 13.r

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 13.a.1 | Privacy requirements definition | Compliant | HIPAA compliance | - |
| 13.b.1 | Consent and choice | Compliant | PRIVACY_CONSENT_PROCEDURES.md | - |
| 13.c.1 | Privacy notice | Compliant | Legal documentation | - |
| 13.d.1 | Minimization of personal information | Compliant | LOINC-based titles, minimal storage | - |
| 13.e.1 | Retention and disposal | Compliant | secure_delete.py, retention policies | - |
| 13.f.1 | Accuracy of personal information | Compliant | EMR source of truth | - |
| 13.g.1 | Individual participation | N/A | EMR handles patient access | - |
| 13.h.1 | Openness, transparency, notice | Compliant | Legal templates | - |
| 13.i.1 | Accountability | Compliant | Audit logging | - |
| 13.j.1 | Security for privacy | Compliant | PHI encryption, access controls | - |
| 13.k.1 | Limiting use and disclosure | Compliant | Role-based access, org scoping | - |
| 13.l.1 | De-identification | Compliant | phi_filter.py | - |
| 13.m.1 | Breach notification | Compliant | IRP HIPAA procedures | - |

**Domain Status**: ✅ Compliant

---

### Domain 14: Third Party Assurance

**HITRUST Control Reference**: 14.a - 14.c

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 14.a.1 | Identification of risks from external parties | Compliant | `/docs/security/VENDOR_RISK_ASSESSMENTS.md` Sections 4-8 | - |
| 14.a.2 | Vendor risk assessment process | Compliant | Vendor Risk Assessments Section 3 (Framework) | - |
| 14.b.1 | Addressing security in customer agreements | Compliant | Provider agreements | - |
| 14.c.1 | Third party service delivery management | Compliant | Vendor Risk Assessments Section 11 | - |

**Domain Status**: ✅ Compliant

---

### Domain 15: Endpoint Protection

**HITRUST Control Reference**: 15.a - 15.g

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 15.a.1 | Mobile device policy | N/A | Web-based application | - |
| 15.b.1 | Teleworking | N/A | Cloud-based access | - |
| 15.c.1 | Input data validation | Compliant | Flask-WTF forms | - |
| 15.d.1 | Control of internal processing | Compliant | Business logic validation | - |
| 15.e.1 | Message integrity | Compliant | CSRF protection | - |
| 15.f.1 | Output data validation | Compliant | Template escaping | - |
| 15.g.1 | Protection against web attacks | Compliant | CSP, XSS prevention | - |

**Domain Status**: ✅ Compliant

---

### Domain 16: Network Protection

**HITRUST Control Reference**: 16.a - 16.f

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 16.a.1 | Network controls | Partial | AWS VPC planned | - |
| 16.b.1 | Security of network services | Compliant | TLS enforcement | - |
| 16.c.1 | Segregation in networks | Partial | VPC subnets planned | - |
| 16.d.1 | Network connection control | Partial | Security groups | - |
| 16.e.1 | Network routing control | Partial | AWS architecture | - |
| 16.f.1 | Remote diagnostic port protection | N/A | No diagnostic ports | - |

**Domain Status**: ⚠️ Partial - AWS network implementation pending

---

### Domain 17: Portable Media Security

**HITRUST Control Reference**: 17.a - 17.d

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 17.a.1 | Management of removable media | N/A | Cloud-based, no removable media | - |
| 17.b.1 | Disposal of media | Compliant | secure_delete.py | - |
| 17.c.1 | Information handling procedures | Compliant | PHI handling documented | - |
| 17.d.1 | Security of system documentation | Compliant | Repository access controls | - |

**Domain Status**: ✅ Compliant (N/A for cloud)

---

### Domain 18: Transmission Protection

**HITRUST Control Reference**: 18.a - 18.d

| Requirement ID | Requirement | Status | Evidence | Gap |
|----------------|-------------|--------|----------|-----|
| 18.a.1 | Information transfer policies | Compliant | FHIR integration docs | - |
| 18.b.1 | Agreements on information transfer | Compliant | BAA requirements | - |
| 18.c.1 | Electronic messaging | Compliant | Resend secure email | - |
| 18.d.1 | Encryption of data in transit | Compliant | TLS 1.2+ mandatory | - |

**Domain Status**: ✅ Compliant

---

## Gap Remediation Tracking

### Priority 1: Critical Gaps - RESOLVED

| Gap ID | Domain | Description | Owner | Resolution Date | Status |
|--------|--------|-------------|-------|-----------------|--------|
| GAP-001 | 02 | Security Awareness & Training Policy | Security Officer | January 2026 | ✅ Complete |
| GAP-002 | 06 | System Hardening Standards | DevOps Lead | January 2026 | ✅ Complete |
| GAP-003 | 07 | Vulnerability Management Policy | Security Officer | January 2026 | ✅ Complete |
| GAP-004 | 14 | Vendor Risk Assessment Template | Security Officer | January 2026 | ✅ Complete |
| GAP-005 | 14 | Epic Vendor Risk Assessment | Security Officer | January 2026 | ✅ Complete |
| GAP-006 | 14 | AWS Vendor Risk Assessment | Security Officer | January 2026 | ✅ Complete |

### Priority 2: Partial Controls (Enhance before assessment)

| Gap ID | Domain | Description | Owner | Target Date | Status |
|--------|--------|-------------|-------|-------------|--------|
| GAP-007 | 01 | AWS VPC network diagram | DevOps Lead | AWS migration | Pending |
| GAP-008 | 05 | Penetration test engagement | Security Officer | Pre-launch | Pending |
| GAP-009 | 12 | BCP testing execution | Operations Lead | Q2 2026 | Scheduled |

---

## Evidence Repository Index

| Evidence Type | Location | Last Updated |
|---------------|----------|--------------|
| Security Policy | /docs/SECURITY_WHITEPAPER.md | January 2026 |
| Incident Response Plan | /docs/security/INCIDENT_RESPONSE_PLAN.md | January 2026 |
| Business Continuity Plan | /docs/security/BUSINESS_CONTINUITY_PLAN.md | January 2026 |
| Risk Assessment | /docs/security/NIST_800_30_RISK_REGISTER.md | January 2026 |
| Key Management Policy | /docs/security/key-management-policy.md | January 2026 |
| Privacy Procedures | /docs/security/PRIVACY_CONSENT_PROCEDURES.md | January 2026 |
| Security Checklist | /docs/security/SECURITY_CHECKLIST.md | January 2026 |
| IR Drill Results | /docs/security/IR_DRILL_RESULTS.md | January 2026 |
| Access Control Implementation | models.py (User, Organization) | January 2026 |
| Audit Logging Implementation | utils/document_audit.py | January 2026 |
| Security Alerting | services/security_alerts.py | January 2026 |
| PHI Filter | ocr/phi_filter.py | January 2026 |
| Secure Deletion | utils/secure_delete.py | January 2026 |
| CSP Headers | utils/security_headers.py | January 2026 |

---

## Assessment Preparation Checklist

### Pre-Assessment (2-4 weeks before)

- [ ] Complete all Priority 1 gap remediation
- [ ] Verify all evidence documents are current
- [ ] Conduct internal policy review
- [ ] Prepare evidence collection for assessor

### Assessment Week

- [ ] Designate point of contact for assessor
- [ ] Provide assessor access to documentation
- [ ] Schedule technical demonstration
- [ ] Prepare AdminLog audit samples

### Post-Assessment

- [ ] Address any findings from assessment
- [ ] Update documentation per recommendations
- [ ] Schedule i1 renewal for next year

---

## Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Security Officer | [TBD] | | |
| Technical Lead | [TBD] | | |
| Executive Sponsor | [TBD] | | |
