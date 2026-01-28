# Vendor Risk Assessments

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Security Team | Initial release |

**Classification**: Internal Use Only  
**Review Frequency**: Annual or when vendor relationships change  
**Next Review**: January 2027  
**HITRUST CSF Alignment**: Domain 14.a (Third Party Assurance)

---

## 1. Purpose

This document provides vendor risk assessments for all third-party service providers that process, store, or transmit HealthPrep data or PHI. It ensures compliance with HIPAA requirements for Business Associate oversight and HITRUST CSF controls for third-party assurance.

---

## 2. Scope

Covered vendors:
- AWS (Infrastructure and database hosting)
- Epic Systems (FHIR EMR integration)
- Stripe (Payment processing)
- Resend (Transactional email)
- Replit (Development environment)

---

## 3. Vendor Risk Assessment Framework

### 3.1 Risk Categories

| Category | Weight | Description |
|----------|--------|-------------|
| Data Access | 30% | Level of access to PHI or sensitive data |
| Security Posture | 25% | Security certifications and controls |
| Business Continuity | 15% | Redundancy and disaster recovery |
| Contractual | 15% | BAA, SLA, liability coverage |
| Reputation | 15% | Industry standing, breach history |

### 3.2 Risk Scoring

| Score | Level | Description |
|-------|-------|-------------|
| 1-2 | Low | Minimal risk, standard monitoring |
| 3-4 | Medium | Moderate risk, enhanced monitoring |
| 5-6 | High | Significant risk, additional controls required |
| 7+ | Critical | Unacceptable risk, remediation required |

---

## 4. Vendor Assessment: Amazon Web Services (AWS)

### 4.1 Vendor Profile

| Attribute | Details |
|-----------|---------|
| Vendor Name | Amazon Web Services, Inc. |
| Service Type | Cloud Infrastructure (IaaS/PaaS) |
| Data Classification | PHI (encrypted at rest and in transit) |
| Services Used | EC2, RDS, S3, Secrets Manager, CloudWatch |
| Contract Type | Enterprise Agreement |
| BAA Status | **Required** - AWS BAA |

### 4.2 Risk Assessment

| Category | Score | Justification |
|----------|-------|---------------|
| Data Access | 2 | PHI stored encrypted, AWS has no access to keys |
| Security Posture | 1 | SOC 2 Type II, HITRUST, ISO 27001, FedRAMP |
| Business Continuity | 1 | Multi-AZ, Multi-region options, 99.99% SLA |
| Contractual | 2 | BAA available, comprehensive SLA |
| Reputation | 1 | Market leader, no major healthcare breaches |
| **Overall Score** | **1.4 (Low)** | |

### 4.3 Security Certifications

- SOC 1/2/3 Type II
- ISO 27001, 27017, 27018
- HITRUST CSF Certified
- FedRAMP (High)
- HIPAA Eligible Services

### 4.4 Controls Verification

| Control | AWS Responsibility | HealthPrep Responsibility |
|---------|-------------------|---------------------------|
| Physical security | AWS data centers | N/A |
| Network security | VPC, Security Groups | Configuration |
| Encryption at rest | KMS service | Key management |
| Encryption in transit | TLS infrastructure | Enforcement |
| Access control | IAM service | Policy configuration |
| Audit logging | CloudTrail, CloudWatch | Enablement, monitoring |
| Backup | Automated backups | Configuration, testing |

### 4.5 Required Actions

| Action | Status | Due Date |
|--------|--------|----------|
| Execute BAA | **Pending** | Before production |
| Enable CloudTrail | Planned | AWS migration |
| Configure VPC | Planned | AWS migration |
| Enable encryption | Planned | AWS migration |

### 4.6 Ongoing Monitoring

- Annual SOC 2 report review
- Quarterly security bulletin review
- Real-time AWS Health Dashboard monitoring
- Annual BAA renewal verification

---

## 5. Vendor Assessment: Epic Systems

### 5.1 Vendor Profile

| Attribute | Details |
|-----------|---------|
| Vendor Name | Epic Systems Corporation |
| Service Type | FHIR API (EMR Integration) |
| Data Classification | PHI (read/write access) |
| Services Used | FHIR R4 API via SMART on FHIR |
| Contract Type | App Orchard Agreement |
| BAA Status | **Required** - Provider BAA covers Epic access |

### 5.2 Risk Assessment

| Category | Score | Justification |
|----------|-------|---------------|
| Data Access | 3 | Direct PHI access through FHIR API |
| Security Posture | 1 | Healthcare industry leader, HITRUST certified |
| Business Continuity | 2 | Provider-dependent, Epic highly available |
| Contractual | 2 | App Orchard terms, provider BAAs |
| Reputation | 1 | Dominant healthcare EMR, excellent track record |
| **Overall Score** | **1.8 (Low)** | |

### 5.3 Security Certifications

- HITRUST CSF Certified
- SOC 2 Type II
- Comprehensive healthcare security program
- Regular third-party penetration testing

### 5.4 Integration Controls

| Control | Implementation |
|---------|----------------|
| Authentication | OAuth 2.0 / SMART on FHIR |
| Authorization | Scope-limited tokens |
| Token management | Short-lived, rotated |
| Audit logging | AdminLog Epic sync events |
| Data validation | FHIR R4 schema validation |
| Error handling | PHI-safe logging |

### 5.5 Scope Restrictions

HealthPrep requests minimum necessary FHIR scopes:
- `patient/Patient.read`
- `patient/DocumentReference.read`
- `patient/DocumentReference.write`
- `patient/Observation.read`
- `launch/patient`
- `openid`, `fhirUser`

### 5.6 Required Actions

| Action | Status | Due Date |
|--------|--------|----------|
| App Orchard approval | Complete | - |
| Scope review | Complete | January 2026 |
| Provider BAA template | Complete | - |

### 5.7 Ongoing Monitoring

- Epic App Orchard compliance reviews
- Annual integration security assessment
- Token usage monitoring
- Error rate monitoring

---

## 6. Vendor Assessment: Stripe

### 6.1 Vendor Profile

| Attribute | Details |
|-----------|---------|
| Vendor Name | Stripe, Inc. |
| Service Type | Payment Processing |
| Data Classification | PCI (cardholder data), no PHI |
| Services Used | Stripe Payments, Stripe Billing |
| Contract Type | Standard Terms of Service |
| BAA Status | **Not Required** - No PHI processed |

### 6.2 Risk Assessment

| Category | Score | Justification |
|----------|-------|---------------|
| Data Access | 1 | No PHI access, PCI data only |
| Security Posture | 1 | PCI DSS Level 1, SOC 2 Type II |
| Business Continuity | 1 | 99.999% uptime, global redundancy |
| Contractual | 2 | Standard terms, comprehensive fraud protection |
| Reputation | 1 | Industry leader, no major breaches |
| **Overall Score** | **1.2 (Low)** | |

### 6.3 Security Certifications

- PCI DSS Level 1 Service Provider
- SOC 2 Type II
- ISO 27001

### 6.4 Integration Controls

| Control | Implementation |
|---------|----------------|
| API key storage | Replit Secrets / AWS Secrets Manager |
| Webhook verification | Signature validation |
| Card data handling | Stripe.js (no server-side exposure) |
| Audit logging | AdminLog payment events |

### 6.5 PCI Scope

HealthPrep integration qualifies for SAQ-A:
- Card data entered directly in Stripe.js
- No card data stored, processed, or transmitted by HealthPrep servers
- Stripe handles all PCI compliance requirements

### 6.6 Required Actions

| Action | Status | Due Date |
|--------|--------|----------|
| Webhook signature validation | Complete | - |
| API key in Secrets Manager | Complete | - |
| SAQ-A self-assessment | Pending | Before production |

### 6.7 Ongoing Monitoring

- Annual PCI compliance verification
- Monthly webhook failure review
- Transaction anomaly monitoring

---

## 7. Vendor Assessment: Resend

### 7.1 Vendor Profile

| Attribute | Details |
|-----------|---------|
| Vendor Name | Resend, Inc. |
| Service Type | Transactional Email |
| Data Classification | Business data (no PHI in emails) |
| Services Used | Email API |
| Contract Type | Standard Terms of Service |
| BAA Status | **Not Required** - No PHI in emails |

### 7.2 Risk Assessment

| Category | Score | Justification |
|----------|-------|---------------|
| Data Access | 1 | No PHI - emails contain only notifications |
| Security Posture | 2 | Standard security practices, SOC 2 in progress |
| Business Continuity | 2 | Standard uptime SLA |
| Contractual | 2 | Standard terms |
| Reputation | 2 | Newer company, growing adoption |
| **Overall Score** | **1.8 (Low)** | |

### 7.3 Email Content Policy

**PHI Prohibited in Emails**:
- Security alerts contain event type only, no patient data
- Notifications reference organization name only
- Password reset contains secure token only
- No diagnostic results or patient information

### 7.4 Integration Controls

| Control | Implementation |
|---------|----------------|
| API key storage | Replit Secrets / AWS Secrets Manager |
| Email content | PHI-free templates only |
| Rate limiting | Per Resend plan limits |
| Audit logging | AdminLog email events |

### 7.5 Required Actions

| Action | Status | Due Date |
|--------|--------|----------|
| Email template review | Complete | - |
| API key in secrets | Complete | - |
| Delivery monitoring | Implemented | - |

### 7.6 Ongoing Monitoring

- Email delivery rate monitoring
- Bounce rate tracking
- Annual vendor review

---

## 8. Vendor Assessment: Replit (Development)

### 8.1 Vendor Profile

| Attribute | Details |
|-----------|---------|
| Vendor Name | Replit, Inc. |
| Service Type | Development Environment / Hosting |
| Data Classification | Development/test data only, no production PHI |
| Services Used | Workspace, Deployments, Secrets, Database |
| Contract Type | Terms of Service |
| BAA Status | **N/A** - Development environment only |

### 8.2 Risk Assessment

| Category | Score | Justification |
|----------|-------|---------------|
| Data Access | 2 | Development only, no production PHI |
| Security Posture | 2 | SOC 2 Type II certified |
| Business Continuity | 2 | Standard uptime |
| Contractual | 2 | Standard terms |
| Reputation | 2 | Established developer platform |
| **Overall Score** | **2.0 (Low)** | |

### 8.3 Security Controls

| Control | Implementation |
|---------|----------------|
| Secret storage | Replit Secrets (encrypted) |
| Access control | Replit account authentication |
| Code isolation | Container-based workspaces |
| Network | HTTPS only |

### 8.4 Scope Limitations

- **Development and staging only**
- **No production PHI**
- Production migrating to AWS

### 8.5 Required Actions

| Action | Status | Due Date |
|--------|--------|----------|
| Migrate production to AWS | Planned | Q1 2026 |
| Maintain for development | Ongoing | - |

---

## 9. Vendor Risk Summary

| Vendor | Risk Level | BAA Required | Status | Review Due |
|--------|------------|--------------|--------|------------|
| AWS | Low (1.4) | Yes | Pending | January 2027 |
| Epic | Low (1.8) | Provider BAA | Complete | January 2027 |
| Stripe | Low (1.2) | No | N/A | January 2027 |
| Resend | Low (1.8) | No | N/A | January 2027 |
| Replit | Low (2.0) | No (dev only) | N/A | January 2027 |

---

## 10. New Vendor Onboarding Process

### 10.1 Pre-Engagement

1. **Identify need** - Document business requirement
2. **Security review** - Complete vendor questionnaire
3. **Risk assessment** - Score per framework
4. **Certification review** - Verify SOC 2, HITRUST, etc.
5. **Contract review** - BAA if PHI access, SLA review

### 10.2 Vendor Security Questionnaire

Required for any vendor with system access:

| Category | Questions |
|----------|-----------|
| Security governance | Policies, CISO, training |
| Access control | Authentication, authorization |
| Data protection | Encryption, retention |
| Incident response | Plan, notification |
| Business continuity | Backups, DR |
| Compliance | Certifications, audits |
| Subprocessors | Fourth-party risks |

### 10.3 Approval Requirements

| Vendor Risk | Approval Authority |
|-------------|-------------------|
| Low | DevOps Lead |
| Medium | Security Officer |
| High | Management + Security Officer |
| Critical | Not approved without remediation |

---

## 11. Ongoing Vendor Management

### 11.1 Annual Review

All vendors reviewed annually for:
- Security posture changes
- Certification renewals
- Incident history
- Contract terms
- Continued necessity

### 11.2 Event-Based Review

Immediate review triggered by:
- Vendor security breach
- Certification lapse
- Major service changes
- Contract renewal
- Regulatory changes

### 11.3 Documentation Requirements

| Document | Retention |
|----------|-----------|
| Risk assessments | 7 years |
| Vendor questionnaires | 7 years |
| BAAs | Duration + 7 years |
| Certification evidence | 3 years |
| Review records | 7 years |

---

## 12. References

| Document | Location |
|----------|----------|
| HIPAA Business Associate Requirements | 45 CFR 164.502(e) |
| HITRUST Third Party Assurance | Domain 14 |
| Provider Agreement Template | /docs/legal/provider_agreement.md |
| Incident Response Plan | /docs/security/INCIDENT_RESPONSE_PLAN.md |

---

## Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Security Officer | [TBD] | | |
| Legal Counsel | [TBD] | | |
| Technical Lead | [TBD] | | |
