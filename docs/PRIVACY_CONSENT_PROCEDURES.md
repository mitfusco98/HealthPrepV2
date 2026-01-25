# HealthPrep Privacy and Consent Procedures

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Compliance | Initial release |

**Classification**: Internal Use Only
**Review Frequency**: Annual or when regulations change
**Next Review**: January 2027

---

## 1. Purpose

This document establishes procedures for handling patient data privacy and consent within HealthPrep, ensuring compliance with:
- HIPAA Privacy Rule (45 CFR 164.500-534)
- HIPAA Security Rule (45 CFR 164.302-318)
- HITRUST CSF privacy controls
- State privacy laws as applicable

---

## 2. Data Classification

### 2.1 Protected Health Information (PHI)

HealthPrep processes the following PHI categories:

| Category | Examples | Handling |
|----------|----------|----------|
| **Direct Identifiers** | Name, SSN, MRN, DOB | Encrypted at rest, redacted in logs |
| **Contact Information** | Address, phone, email | Encrypted at rest, redacted in logs |
| **Clinical Data** | Diagnoses, medications, labs | Displayed only to authorized users |
| **Financial Data** | Insurance, account numbers | Encrypted, limited access |
| **Documents** | Clinical notes, test results | OCR processed, PHI filtered |

### 2.2 PHI Sources

| Source | Data Flow | Consent Basis |
|--------|-----------|---------------|
| Epic FHIR API | Patient records, documents | Treatment (HIPAA TPO) |
| User upload | Clinical documents | Treatment (HIPAA TPO) |
| Manual entry | Demographics, notes | Treatment (HIPAA TPO) |

---

## 3. Consent Framework

### 3.1 HIPAA Treatment, Payment, Operations (TPO)

HealthPrep operates under HIPAA's Treatment, Payment, and Operations (TPO) exception, which permits use and disclosure of PHI for:

- **Treatment**: Coordinating and managing patient care, generating prep sheets for appointments
- **Operations**: Quality assessment, training, business management

**No additional patient consent required** for TPO activities when:
1. A valid Business Associate Agreement (BAA) is in place with the covered entity
2. Data access is limited to minimum necessary
3. Users are authorized healthcare personnel

### 3.2 Business Associate Agreements

HealthPrep maintains BAAs with:

| Party | Type | Status |
|-------|------|--------|
| Customer organizations | Covered Entity | Required before data access |
| AWS | Subcontractor BA | Active |
| Epic | Covered Entity | Via App Orchard agreement |

**BAA Requirements for Customers**:
- Must be signed before organization onboarding
- Defines permitted uses and disclosures
- Specifies breach notification requirements
- Annual review and renewal

### 3.3 Patient Rights

Patients retain the following rights under HIPAA:

| Right | HealthPrep Implementation |
|-------|--------------------------|
| Access to records | Via covered entity (Epic) |
| Amendment requests | Via covered entity |
| Accounting of disclosures | Audit logs available to covered entity |
| Restriction requests | Handled by covered entity |
| Breach notification | Via covered entity within 60 days |

---

## 4. Minimum Necessary Standard

### 4.1 Access Controls

HealthPrep enforces minimum necessary access through:

| Control | Implementation |
|---------|----------------|
| Role-based access | Users see only assigned patients/organizations |
| Organization isolation | Multi-tenant data segregation |
| Purpose limitation | Data used only for prep sheet generation |
| Audit logging | All PHI access logged with user, time, purpose |

### 4.2 Data Minimization

| Principle | Implementation |
|-----------|----------------|
| Collection | Only data needed for prep sheet generation |
| Retention | Per organization policy (default 7 years) |
| Display | Only relevant data shown in prep sheets |
| Export | Limited to authorized admin functions |

---

## 5. Data Processing Procedures

### 5.1 Epic FHIR Data Sync

**Consent Basis**: Treatment (via Epic OAuth consent screen)

**Procedure**:
1. Provider admin initiates Epic OAuth connection
2. Epic displays consent screen to authenticating user
3. User authorizes HealthPrep access to their organization's Epic data
4. HealthPrep syncs only authorized patient data
5. All access logged in audit trail

**User Responsibilities**:
- Only authorized Epic users can connect
- Epic MFA (Duo Push) required during authentication
- Connection limited to appropriate scope

### 5.2 Document Processing

**Procedure**:
1. Document received (via Epic or upload)
2. PHI filter applied to extracted text
3. Direct identifiers redacted with `[TYPE REDACTED]` markers
4. Processed document stored encrypted
5. Original preserved for minimum retention period

**PHI Categories Filtered**:
- SSN, MRN, Insurance IDs
- Phone numbers, emails, addresses
- Names (context-aware to preserve medical terms)
- Financial account numbers
- Government IDs

### 5.3 Prep Sheet Generation

**Procedure**:
1. User requests prep sheet for specific patient
2. Access authorization verified
3. Relevant data aggregated from patient record
4. Screening eligibility calculated
5. Prep sheet generated and displayed
6. Access logged in audit trail

---

## 6. Third-Party Data Sharing

### 6.1 Permitted Disclosures

| Recipient | Purpose | Legal Basis |
|-----------|---------|-------------|
| Epic (write-back) | Treatment documentation | TPO |
| AWS infrastructure | Hosting, processing | BAA |
| No marketing use | N/A | Prohibited |
| No sale of data | N/A | Prohibited |

### 6.2 Prohibited Uses

The following are explicitly prohibited:
- Sale of PHI to any party
- Marketing communications without explicit consent
- Research use without IRB approval and consent
- Sharing with unauthorized third parties
- Retention beyond legal requirements

---

## 7. Breach Response

### 7.1 Breach Definition

A breach occurs when unsecured PHI is accessed, acquired, used, or disclosed in violation of HIPAA.

### 7.2 Notification Timeline

| Notification | Deadline | Responsibility |
|--------------|----------|----------------|
| To covered entity | Without unreasonable delay, max 60 days | HealthPrep (as BA) |
| To patients | Within 60 days of discovery | Covered entity |
| To HHS | Within 60 days (500+) or annual (under 500) | Covered entity |
| To media | Within 60 days (500+ in jurisdiction) | Covered entity |

### 7.3 Documentation

All breach investigations must document:
- Date of discovery
- Nature and extent of PHI involved
- Unauthorized recipient(s) if known
- Risk assessment factors
- Mitigation actions taken
- Corrective measures implemented

See [INCIDENT_RESPONSE_PLAN.md](./INCIDENT_RESPONSE_PLAN.md) for full procedures.

---

## 8. Training Requirements

### 8.1 Required Training

| Audience | Training | Frequency |
|----------|----------|-----------|
| All employees | HIPAA Privacy & Security Basics | Annual |
| Developers | Secure Coding for Healthcare | Annual |
| Support staff | PHI Handling Procedures | Annual |
| Administrators | Access Management, Audit Review | Annual |

### 8.2 Training Documentation

- [ ] Training completion tracked in HR system
- [ ] Certificates retained for 7 years
- [ ] New hire training within 30 days of start

---

## 9. Audit and Compliance

### 9.1 Internal Audits

| Audit Type | Frequency | Owner |
|------------|-----------|-------|
| Access log review | Monthly | Security Lead |
| Permission audit | Quarterly | Operations Lead |
| Privacy control assessment | Annual | Compliance Officer |

### 9.2 Compliance Reporting

**Metrics Tracked**:
- PHI access volume by user
- Filter success/failure rates
- Breach incidents (target: 0)
- Training completion rates

---

## 10. Contact Information

| Role | Responsibility | Contact |
|------|----------------|---------|
| Privacy Officer | Privacy compliance, patient rights | [TBD] |
| Security Officer | Technical safeguards, breach response | [TBD] |
| Legal Counsel | Regulatory guidance, BAA review | [TBD] |

---

## Appendix A: Consent Flow Diagrams

### Epic OAuth Consent Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  1. Provider Admin clicks "Connect to Epic"                       │
│                     ↓                                             │
│  2. Redirect to Epic login page                                   │
│                     ↓                                             │
│  3. Epic MFA (Duo Push) verification                              │
│                     ↓                                             │
│  4. Epic consent screen: "Allow HealthPrep to access..."          │
│     - Patient demographics                                        │
│     - Clinical documents                                          │
│     - Screening data                                              │
│                     ↓                                             │
│  5. User clicks "Allow"                                           │
│                     ↓                                             │
│  6. Redirect to HealthPrep with authorization code                │
│                     ↓                                             │
│  7. HealthPrep exchanges code for access token                    │
│                     ↓                                             │
│  8. Data sync begins (logged, PHI-filtered)                       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Patient Data Access Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  1. User logs in to HealthPrep                                    │
│                     ↓                                             │
│  2. MFA verification (security questions for admins)              │
│                     ↓                                             │
│  3. User selects patient                                          │
│                     ↓                                             │
│  4. Access authorization check:                                   │
│     - Is user in same organization as patient?                    │
│     - Is user role permitted to view?                             │
│     - Is patient assigned to user (if applicable)?                │
│                     ↓                                             │
│  5. If authorized: Display patient data                           │
│     If denied: Redirect with "Access Denied"                      │
│                     ↓                                             │
│  6. Log access: user_id, patient_id, timestamp, action            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```
