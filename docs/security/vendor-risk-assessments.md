# HealthPrep Third-Party Vendor Risk Assessments

**Document Purpose:** Formal risk assessments for critical third-party vendors supporting HealthPrep operations, required for HITRUST CSF compliance.

**Review Frequency:** Annual or upon vendor contract renewal/change

**Last Review:** February 2026

---

## 1. Vendor Risk Assessment Framework

### 1.1 Risk Categories

| Category | Description | Weight |
|----------|-------------|--------|
| Data Access | Level of access to PHI/sensitive data | High |
| Availability | Impact on HealthPrep operations if unavailable | High |
| Compliance | Vendor's own compliance certifications | Medium |
| Security Controls | Technical security measures | High |
| Financial Stability | Vendor viability and continuity | Medium |

### 1.2 Risk Ratings

| Rating | Score | Description |
|--------|-------|-------------|
| Low | 1-2 | Minimal risk, standard monitoring |
| Medium | 3 | Moderate risk, enhanced monitoring |
| High | 4-5 | Significant risk, active mitigation required |

---

## 2. Critical Vendor Assessments

### 2.1 Amazon Web Services (AWS)

**Vendor Type:** Infrastructure Provider  
**Services Used:** ECS Fargate, RDS PostgreSQL, S3, Secrets Manager, ECR, ALB  
**Contract Type:** Standard AWS Customer Agreement + BAA  
**Data Access Level:** High (hosts all PHI)

#### Compliance Certifications
| Certification | Status | Verification |
|---------------|--------|--------------|
| HITRUST CSF | Certified (v11.5.1, 177 services) | AWS Artifact |
| SOC 2 Type II | Current | AWS Artifact |
| ISO 27001 | Certified | AWS Artifact |
| HIPAA | BAA Available | AWS Artifact (pending execution) |
| FedRAMP | Authorized | AWS Artifact |

#### Risk Assessment
| Category | Rating | Justification |
|----------|--------|---------------|
| Data Access | High (5) | Hosts all PHI in RDS/S3 |
| Availability | High (5) | Critical infrastructure dependency |
| Compliance | Low (1) | Extensive certifications including HITRUST |
| Security Controls | Low (1) | Industry-leading security posture |
| Financial Stability | Low (1) | Fortune 500, stable financials |

**Overall Risk:** Low (mitigated by compliance certifications)

#### Mitigations in Place
- [ ] Business Associate Agreement (BAA) pending execution via AWS Artifact
- [x] Encryption at rest enabled (RDS, S3)
- [x] Encryption in transit (TLS 1.2+)
- [x] VPC isolation with security groups
- [x] IAM least-privilege access
- [x] CloudWatch monitoring and alerting

#### Contingency Plan
- Multi-AZ deployment for high availability
- RDS automated backups with 35-day retention
- Cross-region replication capability (recommended)
- See `/docs/BUSINESS_CONTINUITY_PLAN.md`

---

### 2.2 Epic Systems (FHIR API)

**Vendor Type:** Healthcare EMR Provider  
**Services Used:** FHIR R4 API (patient data, documents, appointments)  
**Contract Type:** App Orchard Partnership  
**Data Access Level:** High (source of PHI)

#### Compliance Certifications
| Certification | Status | Verification |
|---------------|--------|--------------|
| HITRUST CSF | Certified | Epic documentation |
| SOC 2 Type II | Current | Epic documentation |
| HIPAA | Compliant | Standard healthcare vendor |
| ONC Certified | Yes | CMS Certified EHR Technology |

#### Risk Assessment
| Category | Rating | Justification |
|----------|--------|---------------|
| Data Access | High (5) | Primary source of patient PHI |
| Availability | High (4) | Core functionality depends on Epic sync |
| Compliance | Low (1) | Healthcare-specific certifications |
| Security Controls | Low (1) | SMART on FHIR OAuth2, PKI-based auth |
| Financial Stability | Low (1) | Market leader in healthcare IT |

**Overall Risk:** Low (mitigated by healthcare-grade compliance)

#### Mitigations in Place
- [x] SMART on FHIR OAuth2 authentication
- [x] JWT-based backend service authorization
- [x] RSA key rotation policy (annual)
- [x] Dry-run mode for testing without PHI exposure
- [x] Graceful degradation when Epic unavailable

#### Contingency Plan
- Cached patient data for read-only access during outages
- Queue-based sync retry for transient failures
- Manual data entry fallback for critical situations

---

### 2.3 Stripe

**Vendor Type:** Payment Processor  
**Services Used:** Subscription billing, payment processing  
**Contract Type:** Standard Stripe Services Agreement  
**Data Access Level:** Medium (payment data, no PHI)

#### Compliance Certifications
| Certification | Status | Verification |
|---------------|--------|--------------|
| PCI DSS Level 1 | Certified | Stripe documentation |
| SOC 2 Type II | Current | Stripe documentation |
| ISO 27001 | Certified | Stripe documentation |
| GDPR | Compliant | Stripe DPA available |

#### Risk Assessment
| Category | Rating | Justification |
|----------|--------|---------------|
| Data Access | Medium (3) | Payment data only, no PHI |
| Availability | Medium (3) | Billing disruption, not clinical |
| Compliance | Low (1) | PCI DSS Level 1 certified |
| Security Controls | Low (1) | Industry-leading payment security |
| Financial Stability | Low (1) | Public company, strong financials |

**Overall Risk:** Low

#### Mitigations in Place
- [x] Stripe handles all payment card data (PCI scope reduction)
- [x] Webhook signature verification
- [x] API key stored in AWS Secrets Manager
- [x] No PHI transmitted to Stripe

#### Contingency Plan
- Grace period for billing failures
- Manual invoicing capability if needed
- Transaction reconciliation on recovery

---

### 2.4 Resend

**Vendor Type:** Email Service Provider  
**Services Used:** Transactional email delivery  
**Contract Type:** Standard Terms of Service  
**Data Access Level:** Low (email addresses, no PHI in email body)

#### Compliance Certifications
| Certification | Status | Verification |
|---------------|--------|--------------|
| SOC 2 Type II | Current | Resend documentation |
| GDPR | Compliant | Resend DPA available |

#### Risk Assessment
| Category | Rating | Justification |
|----------|--------|---------------|
| Data Access | Low (2) | Email addresses only, PHI-free content |
| Availability | Low (2) | Email alerts are non-critical |
| Compliance | Medium (3) | SOC 2 certified, no healthcare-specific |
| Security Controls | Low (2) | TLS encryption, API key auth |
| Financial Stability | Medium (3) | Startup, monitor viability |

**Overall Risk:** Low

#### Mitigations in Place
- [x] No PHI included in email content
- [x] Email templates reviewed for PHI-free content
- [x] API key stored in AWS Secrets Manager
- [x] TLS encryption for email transmission

#### Contingency Plan
- Email queue with retry logic
- Alternative email provider (e.g., SendGrid, AWS SES) pre-evaluated
- Critical alerts can be logged without email delivery

---

## 3. Vendor Monitoring

### 3.1 Ongoing Monitoring Activities

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Review vendor security advisories | Monthly | Security Lead |
| Verify compliance certifications | Annually | Compliance |
| Review vendor financial stability | Annually | Operations |
| Test contingency plans | Per BCP schedule | Operations |

### 3.2 Vendor Incident Response

If a vendor reports a security incident:
1. Assess impact on HealthPrep data
2. Document in incident log
3. Notify affected organizations if PHI involved
4. Review and update mitigations
5. Consider vendor relationship continuity

---

## 4. New Vendor Onboarding Checklist

Before engaging a new vendor with data access:

- [ ] Request and verify compliance certifications
- [ ] Review security questionnaire or SOC 2 report
- [ ] Execute BAA if PHI access required
- [ ] Conduct risk assessment using framework above
- [ ] Document in this vendor registry
- [ ] Establish monitoring schedule
- [ ] Define contingency plan

---

## 5. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | February 2026 | HealthPrep Security | Initial vendor risk assessments |

---

## 6. References

| Document | Location |
|----------|----------|
| Business Continuity Plan | `/docs/BUSINESS_CONTINUITY_PLAN.md` |
| Incident Response Plan | `/docs/INCIDENT_RESPONSE_PLAN.md` |
| HITRUST Shared Responsibility Matrix | `/docs/security/hitrust-shared-responsibility-matrix.md` |
| Key Management Policy | `/docs/security/key-management-policy.md` |
