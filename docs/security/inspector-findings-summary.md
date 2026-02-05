# AWS Inspector Findings Summary

**Document Purpose:** Centralized summary of AWS Inspector vulnerability findings for HITRUST i1 certification evidence. This document provides point-in-time snapshots of container image security posture with 100% CVE accountability.

**Related Documents:**
- `/docs/security/vulnerability-remediation-log.md` - Detailed CVE analysis and remediation tracking
- `/docs/HITRUST_READINESS.md` - HITRUST readiness checklist
- `/docs/security/hitrust-shared-responsibility-matrix.md` - AWS vs HealthPrep control mapping

---

## Current Findings Summary

**Scan Date:** 2026-02-04  
**Scan Source:** AWS Inspector v2 (us-east-2)  
**Image Scanned:** `healthprep:3dd1245f3f2ad5d38599ce3afc074b002d60d312` (latest)  
**Platform:** Debian 13 (Trixie) / Python 3.11-slim  
**Total Active Findings:** 2

### Findings Overview

| Severity | CVE ID | Package | CVSS Score | Fix Available | Status |
|----------|--------|---------|------------|---------------|--------|
| Medium | CVE-2026-25210 | expat 2.7.1 | 6.9 | No | Accepted Risk |
| Informational | CVE-2025-7709 | sqlite3 | N/A | No | Accepted Risk |

---

## CVE-2026-25210 - expat (libexpat1)

### Finding Details

| Field | Value |
|-------|-------|
| **Finding ARN** | `arn:aws:inspector2:us-east-2:179678238031:finding/764b48f83aa4bdc693496b415628ecaf` |
| **AWS Account** | 179678238031 |
| **Type** | PACKAGE_VULNERABILITY |
| **Severity** | MEDIUM |
| **CVSS 3.1 Score** | 6.9 |
| **CVSS Vector** | CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:L |
| **EPSS Score** | 0.00005 (0.005% - Very Low) |
| **Exploit Available** | NO |
| **Fix Available** | NO |

### Vulnerability Description

In libexpat before 2.7.4, the `doContent` function does not properly determine the buffer size `bufSize` because there is no integer overflow check for tag buffer reallocation.

### Affected Resource

| Field | Value |
|-------|-------|
| **Resource Type** | AWS_ECR_CONTAINER_IMAGE |
| **Repository** | healthprep |
| **Image Tags** | `3dd1245f3f2ad5d38599ce3afc074b002d60d312`, `latest` |
| **Architecture** | amd64 |
| **Platform** | DEBIAN_13 |
| **Pushed At** | 2026-02-03T22:54:28.563Z |

### Package Details

| Field | Value |
|-------|-------|
| **Package Name** | expat |
| **Installed Version** | 2.7.1-2 |
| **Fixed Version** | NotAvailable |
| **Package Manager** | OS (Debian) |
| **Source** | DEBIAN_CVE |
| **Vendor Severity** | not yet assigned |

### Risk Acceptance Rationale

1. **Low EPSS Score:** 0.005% probability of exploitation in the wild
2. **No Exploit Available:** No known public exploits
3. **Local Attack Vector:** Requires local access (AV:L), not network-exploitable
4. **High Attack Complexity:** Requires specific conditions (AC:H)
5. **No Upstream Fix:** Debian has not released a patched version
6. **HealthPrep Context:** XML parsing limited to trusted FHIR resources from Epic endpoints

### References

- [Debian Security Tracker](https://security-tracker.debian.org/tracker/CVE-2026-25210)
- [Debian Bug Report #1126697](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1126697)

---

## CVE-2025-7709 - sqlite3

### Finding Details

| Field | Value |
|-------|-------|
| **Severity** | INFORMATIONAL |
| **Package** | sqlite3 |
| **Type** | PACKAGE_VULNERABILITY |
| **Fix Available** | NO |

### Risk Acceptance Rationale

1. **Informational Severity:** Lowest severity classification
2. **No Upstream Fix:** Awaiting vendor patch
3. **HealthPrep Context:** SQLite not used for primary data storage (PostgreSQL is primary database)

---

## Compensating Controls

All accepted-risk vulnerabilities are mitigated by the following controls:

| Control | Description | Evidence |
|---------|-------------|----------|
| **Network Isolation** | Application runs in private VPC subnet | AWS VPC configuration |
| **ALB TLS Termination** | TLS 1.2+ enforced at load balancer | ALB listener configuration |
| **WAF Protection** | AWS WAF with managed rule sets | WAF web ACL |
| **Input Validation** | FHIR resources validated against R4 schemas | `services/fhir_parser.py` |
| **Non-Root Container** | Application runs as `healthprep` user | `Dockerfile` (USER directive) |
| **Container Scanning** | AWS Inspector continuous scanning | This document |
| **Rapid Patching SLA** | Critical: 24h, High: 7d, Medium: 30d | `/docs/security/vulnerability-remediation-log.md` |

---

## CVE Accountability Summary

### By Remediation Status

| Status | Count | CVE IDs |
|--------|-------|---------|
| Remediated | 2 | CVE-2026-24049 (wheel), CVE-2026-23949 (jaraco.context) |
| Accepted Risk | 8 | CVE-2026-25210 (expat), CVE-2025-7709 (sqlite3), CVE-2025-69419, CVE-2025-69421, CVE-2026-22795, CVE-2025-69418, CVE-2025-11187 (OpenSSL cluster) |
| **Total** | **10** | **100% Tracked** |

### Current Active Findings

| Metric | Value |
|--------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 0 |
| Informational | 1 |
| **Total Active** | **2** |

---

## Evidence Export Attempts

### Export Status

AWS Inspector S3 export functionality encountered persistent 403 errors despite correct IAM and KMS configuration. Manual evidence collection used instead.

| Report ID | Date | Status | Error |
|-----------|------|--------|-------|
| c9912d8e-4e94-4c7e-b4ad-62013b6d88e9 | 2026-02-04 | FAILED | INVALID_PERMISSIONS (S3 403) |
| e769b213-4bd7-4c49-bb78-d2974f59c912 | 2026-02-04 | FAILED | INVALID_PERMISSIONS (S3 403) |
| c100570d-6dc3-4444-9f61-41f88e70623b | 2026-02-04 | FAILED | INVALID_PERMISSIONS (S3 403) |
| e43ae630-5b47-4e8f-a871-a377e2bc1e8f | 2026-02-04 | FAILED | INVALID_PERMISSIONS (S3 403) |

**Note:** This is a known AWS Inspector limitation with customer-managed KMS keys. Evidence collected via console screenshots and JSON exports instead.

### Manual Evidence Collection

Evidence collected on 2026-02-04:
- AWS Inspector console screenshot showing 2 active findings
- JSON export of CVE-2026-25210 finding details
- CLI verification of finding status

---

## Monitoring Schedule

| Action | Frequency | Owner | Method |
|--------|-----------|-------|--------|
| Review AWS Inspector findings | Daily | Mitchell Fusillo | AWS Console / CLI |
| Check Debian security tracker | Weekly | Mitchell Fusillo | https://security-tracker.debian.org |
| Update this summary | After each remediation | Mitchell Fusillo | Manual update |
| HITRUST evidence refresh | Monthly | Mitchell Fusillo | Export findings snapshot |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-04 | Mitchell Fusillo | Initial Inspector findings summary for HITRUST evidence |
