# HealthPrep Security Whitepaper
## HIPAA Compliance & Data Protection Summary

This document provides a comprehensive overview of HealthPrep's security architecture for practitioners, compliance officers, and prospective clients.

---

## Executive Summary

HealthPrep is designed with a **privacy-first architecture** that minimizes data breach risk through:

1. **PHI Redaction at Ingestion**: All document text is filtered for Protected Health Information before storage
2. **Minimal Data Storage**: We store screening-relevant data only, not complete medical records
3. **Epic Hyperspace Access Control**: Only authorized practitioners with Epic credentials can access source documents
4. **Organization-Scoped Isolation**: Complete data separation between healthcare organizations
5. **Comprehensive Audit Logging**: Every data access is logged for HIPAA compliance

---

## What We Store vs. What We Don't Store

### Data We Store (PHI-Filtered)

| Data Type | What's Stored | PHI Status |
|-----------|---------------|------------|
| **Document Text** | OCR-extracted text with PHI redacted | SSN, phone, addresses, names → `[REDACTED]` |
| **Patient Demographics** | Name, DOB, gender (required for screening eligibility) | Minimal identifiers for clinical use |
| **Screening Results** | Due dates, completion status, matched documents | No PHI - operational data only |
| **Document Metadata** | Structured type codes (LOINC), date | **No PHI** - derived from structured FHIR codes only |

### Data We DON'T Store

| Data Type | Why Not Stored |
|-----------|----------------|
| **Original Documents** | Accessed live from Epic when needed, never cached |
| **Social Security Numbers** | Redacted before storage |
| **Insurance Details** | Redacted - policy numbers, member IDs |
| **Full Addresses** | Redacted - street addresses, ZIP codes |
| **Complete Medical Records** | Only screening-relevant excerpts retained |
| **Free-Text Document Titles** | **Replaced with structured LOINC codes** - eliminates PHI leakage |
| **Patient Names in Metadata** | Replaced with structured identifiers - no name strings stored |

---

## PHI Redaction System

### How It Works

All text extracted from documents (whether via direct PDF text extraction or OCR) passes through our PHI filter before storage:

```
Document → Text Extraction → PHI Filter → Database Storage
              ↓
         [PyMuPDF or Tesseract OCR]
              ↓
         PHI Patterns Detected:
         • SSN: XXX-XX-XXXX → [SSN REDACTED]
         • Phone: (XXX) XXX-XXXX → [PHONE REDACTED]
         • MRN: MRN: XXXXXXX → [MRN REDACTED]
         • Addresses: Street addresses → [ADDRESS REDACTED]
         • Names: Patient: John Doe → [NAME REDACTED]
```

### PHI Categories Filtered

| Category | Pattern Examples | Redaction |
|----------|------------------|-----------|
| **SSN** | 123-45-6789, SSN: 123456789 | `[SSN REDACTED]` |
| **Phone Numbers** | (555) 123-4567, 555.123.4567 | `[PHONE REDACTED]` |
| **Medical Record Numbers** | MRN: 12345, Patient ID: 67890 | `[MRN REDACTED]` |
| **Insurance IDs** | Policy#: 12345, Member ID: ABC123 | `[INSURANCE REDACTED]` |
| **Addresses** | 123 Main Street, ZIP codes | `[ADDRESS REDACTED]` |
| **Names** | Patient: John Doe, Last, First | `[NAME REDACTED]` |

### Medical Terms Preserved

The filter specifically protects clinical data that looks like PHI but isn't:
- Blood pressure readings (120/80)
- Lab values (glucose: 95 mg/dL)
- A1C percentages (A1C: 6.5%)
- Vital signs (72 BPM, 98.6°F)

### Accuracy Assurance

1. **Regex-Based Detection**: Precise pattern matching for known PHI formats
2. **Idempotent Processing**: Already-redacted text is protected from double-redaction
3. **Admin Configuration**: Organization can enable/disable specific filter categories
4. **Audit Trail**: All filtering operations are logged

---

## Structured Document Metadata (PHI-Free by Design)

### The Problem with Free-Text Titles

Epic DocumentReference resources often contain patient names embedded in title/description fields:
- "Lab Results - John Smith"
- "SMITH, JANE - Discharge Summary"
- "Progress Note for Patient Mary-Jane Watson"

Traditional regex-based filtering cannot reliably distinguish patient names from medical terms (e.g., surnames like "Bone", "Head", "Health" match anatomical keywords).

### Our Solution: Structured Code-Based Titles

Instead of storing and filtering free-text titles, HealthPrep uses a **deterministic approach**:

1. **Extract FHIR Type Codes**: Use `DocumentReference.type.coding` (LOINC codes)
2. **Map to Controlled Vocabulary**: 300+ LOINC codes → safe display names
3. **Discard Free Text**: Never store raw description/title fields

```
Epic FHIR Response:
{
  "type": {
    "coding": [{"code": "11506-3", "system": "http://loinc.org"}]
  },
  "description": "Progress Note - John Smith"  // <- IGNORED (contains PHI)
}

HealthPrep Storage:
{
  "title": "Progress Note",           // <- Derived from LOINC code 11506-3
  "document_type_code": "11506-3",    // <- Structured identifier
  "fhir_document_reference": {...}    // <- All free-text fields redacted
}
```

### Security Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **No Patient Names in Titles** | Titles derived only from structured codes |
| **Deterministic Protection** | No heuristics, no regex edge cases |
| **Searchable Metadata** | LOINC codes enable standardized queries |
| **Compliance Verification** | Easily auditable - check for non-code titles |

### FHIR Resource Sanitization

When storing the full FHIR DocumentReference JSON:

| Field Type | Treatment |
|------------|-----------|
| `name`, `address`, `telecom` | Removed entirely |
| `title`, `description`, `display` | Redacted to `[REDACTED]` |
| `identifier.value` | Redacted while keeping `identifier.type` |
| `type.coding`, `category` | Preserved (structured codes) |
| `attachment.data` | Removed (binary content) |

---

## Data Breach Scenario Analysis

### Scenario 1: Database Breach

**If an attacker gains access to our database:**

| Risk | Mitigation |
|------|------------|
| Patient names visible | Names stored for clinical workflow only - no SSN, addresses, or financial data |
| Document text exposed | All text is PHI-redacted before storage - no SSN, phone, addresses, names |
| Document metadata exposed | **No PHI** - titles derived from LOINC codes, not free-text |
| FHIR resources exposed | All free-text fields (title, description, display) redacted to `[REDACTED]` |
| Screening data visible | Contains due dates and status only - no clinical details |
| No access to Epic | Database contains no Epic credentials - cannot reach source records |

**Impact Assessment**: LOW - Attacker gets de-identified operational data. Document metadata contains only structured codes, not patient-identifying information.

### Scenario 2: Session Hijacking

**If an attacker hijacks a user session:**

| Risk | Mitigation |
|------|------------|
| Access patient list | Limited to organization's patients only |
| View prep sheets | Contains screening due dates, redacted document excerpts |
| Cannot access Epic | Epic OAuth tokens require practitioner credentials |
| Audit logged | Session activity recorded with IP, user agent |

**Impact Assessment**: MEDIUM - Limited to same access as legitimate user, but audit trail enables detection.

### Scenario 3: Epic Credential Compromise

**If Epic SMART on FHIR credentials are compromised:**

| Risk | Mitigation |
|------|------------|
| Access source documents | Requires valid Epic session AND HealthPrep authorization |
| Credentials stored encrypted | OAuth tokens refreshed regularly, stored securely |
| Per-organization isolation | Compromised org cannot access other organizations |

**Impact Assessment**: Handled by Epic's security model - HealthPrep enforces separation.

---

## Access Control Architecture

### User Roles

| Role | Epic Access | Patient Access | Admin Access |
|------|-------------|----------------|--------------|
| **Root Admin** | None | None (system only) | Full system |
| **Org Admin** | Configured per org | Own org's patients | Own org settings |
| **Provider** | Full (with Epic credentials) | Own patients | None |
| **Staff** | View only | Assigned patients | None |

### Epic Hyperspace Integration

- **OAuth 2.0 SMART on FHIR**: Industry-standard secure authentication
- **Practitioner Resource Required**: Only users with Epic practitioner credentials can access documents
- **Session-Based Tokens**: Epic tokens stored in encrypted session, not database
- **Automatic Token Refresh**: Expired tokens refreshed seamlessly

---

## Secure File Handling

### Temporary File Management (HIPAA Compliant)

All temporary files created during document processing:

1. **Registered on Creation**: Files tracked in secure registry
2. **3-Pass Overwrite Deletion**: Random data written 3x before unlink
3. **Crash Recovery**: Orphaned files cleaned on application restart
4. **Audit Logged**: All secure deletions recorded

### Document Upload Workflow

```
Upload → Virus Scan → Temp Storage → OCR/Extract → PHI Filter → Database
                          ↓
                    Secure Delete (3-pass)
```

---

## Audit Logging

### What Gets Logged

| Event Type | Details Captured |
|------------|------------------|
| **User Login** | Timestamp, IP, user agent, success/failure |
| **Patient Access** | Which patient, what data viewed, by whom |
| **Document Access** | Document ID, access type, user |
| **Admin Actions** | Settings changes, user management |
| **Data Export** | What was exported, by whom, when |
| **PHI Filtering** | Documents processed, patterns matched |

### Log Retention

- Development: 90 days
- Production: Per organization retention policy (typically 6 years for HIPAA)

---

## Frequently Asked Questions

### Q: How do we verify documents are properly disposed of?

**A:** All temporary files containing PHI are:
1. Tracked in a secure registry upon creation
2. Deleted using 3-pass random data overwrite
3. Verified as deleted before removing from registry
4. If deletion fails, file remains in registry and generates HIPAA ALERT
5. On application restart, any orphaned files are securely deleted

Audit logs record every secure deletion with hashed file paths.

### Q: What happens if the system crashes during processing?

**A:** Crash recovery is automatic:
1. All temp files are registered before processing
2. On startup, the registry is scanned
3. Any orphaned files are securely deleted
4. HIPAA ALERT logged if any files couldn't be deleted
5. Failed deletions remain in registry for future retry

### Q: What patient data is stored in your database?

**A:** We store:
- **Patient name, DOB, gender**: Required for screening eligibility calculations
- **MRN**: For matching with Epic records
- **Screening results**: Due dates, completion status
- **PHI-filtered document text**: With SSN, addresses, phones, etc. redacted

We do NOT store:
- Original documents (accessed live from Epic)
- SSN, insurance details, full addresses
- Epic credentials or passwords

### Q: Who can access patient data?

**A:** Access is controlled by:
1. **Role-based permissions**: Providers see their patients, staff see assigned patients
2. **Organization isolation**: Each healthcare organization's data is completely separate
3. **Epic authentication**: Document access requires valid Epic practitioner credentials
4. **Audit logging**: Every access is logged with user, timestamp, IP address

### Q: What if someone gains unauthorized database access?

**A:** The impact is minimized because:
1. All document text is PHI-redacted before storage
2. No SSN, insurance IDs, addresses, or phone numbers are stored
3. Epic credentials are session-based, not in the database
4. Patient names are the only identifiable data (required for clinical workflow)
5. Screening data contains due dates only, not clinical details

### Q: How accurate is the PHI redaction?

**A:** Our PHI filter uses:
1. **Precise regex patterns** for known PHI formats (SSN, phone, etc.)
2. **Context-aware detection** for MRN, insurance IDs
3. **Medical term preservation** to avoid corrupting clinical data
4. **Idempotent processing** to prevent double-redaction
5. **Admin-configurable categories** per organization
6. **Continuous pattern updates** as new PHI formats are identified

### Q: Can you access our Epic system without our knowledge?

**A:** No. Epic access requires:
1. Valid OAuth tokens from Epic's authentication
2. User must have Practitioner resource in Epic
3. All access is logged in both Epic and HealthPrep
4. Tokens expire and require re-authentication
5. Organization admins control Epic integration settings

---

## Compliance Certifications

- **HIPAA Compliant**: Business Associate Agreement available
- **SOC 2 Type II**: (If applicable - update as certified)
- **Epic App Orchard**: Certified integration partner

---

## Contact

For security questions or to report vulnerabilities:
- Email: security@healthprep.com
- For urgent security issues: Contact your organization administrator

---

*Last Updated: January 2026*
*Version: 1.0*
