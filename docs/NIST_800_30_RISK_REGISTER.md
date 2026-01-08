# NIST 800-30 Risk Assessment Register

## Overview

This document provides a formal risk register for HealthPrep following NIST Special Publication 800-30 guidelines. It enumerates threat sources, threat events, vulnerabilities, and risk treatments for the healthcare data processing system.

**Assessment Date**: January 2026  
**Assessment Scope**: HealthPrep application, Epic FHIR integration, AWS deployment infrastructure  
**Assessment Methodology**: NIST SP 800-30 Rev. 1

## Asset Inventory

| Asset | Description | Data Classification | Criticality |
|-------|-------------|---------------------|-------------|
| Patient Demographics | Names, DOB, gender | PHI | High |
| Medical Documents | Lab results, imaging reports | PHI | High |
| Screening Results | Eligibility determinations | PHI | High |
| User Credentials | Passwords, tokens | Confidential | High |
| Epic OAuth Tokens | EMR access credentials | Confidential | Critical |
| Audit Logs | Access and processing records | Internal | High |
| Application Code | Business logic | Proprietary | Medium |

## Threat Source Identification

### Adversarial Threats

| ID | Threat Source | Capability | Intent | Targeting |
|----|---------------|------------|--------|-----------|
| ADV-1 | External Hackers | Medium-High | Financial/Data theft | Opportunistic |
| ADV-2 | Insider Threats | High | Data theft/sabotage | Targeted |
| ADV-3 | Competitors | Low-Medium | IP theft | Targeted |
| ADV-4 | Nation-State Actors | Very High | Espionage | Targeted |

### Non-Adversarial Threats

| ID | Threat Source | Description |
|----|---------------|-------------|
| NAD-1 | System Failures | Hardware/software malfunctions |
| NAD-2 | Natural Disasters | Fire, flood, earthquake |
| NAD-3 | Human Error | Misconfigurations, accidental deletions |
| NAD-4 | Supply Chain | Third-party vulnerabilities |

## Threat Event Catalog

### Authentication & Access Control

| ID | Threat Event | Threat Source | Likelihood | Impact | Risk Level |
|----|--------------|---------------|------------|--------|------------|
| TE-01 | Credential Stuffing Attack | ADV-1 | High | High | High |
| TE-02 | Brute Force Password Attack | ADV-1 | High | High | High |
| TE-03 | Session Hijacking | ADV-1 | Medium | High | Medium |
| TE-04 | Privilege Escalation | ADV-2 | Low | Critical | Medium |
| TE-05 | Unauthorized IDOR Access | ADV-1 | Medium | High | Medium |

### Data Protection

| ID | Threat Event | Threat Source | Likelihood | Impact | Risk Level |
|----|--------------|---------------|------------|--------|------------|
| TE-06 | PHI Exfiltration | ADV-1/2 | Medium | Critical | High |
| TE-07 | Database Breach | ADV-1 | Low | Critical | Medium |
| TE-08 | PHI Filter Bypass | ADV-1 | Low | High | Low |
| TE-09 | Encryption Key Compromise | ADV-4 | Very Low | Critical | Low |
| TE-10 | Temp File PHI Exposure | NAD-3 | Low | High | Low |

### Application Security

| ID | Threat Event | Threat Source | Likelihood | Impact | Risk Level |
|----|--------------|---------------|------------|--------|------------|
| TE-11 | Cross-Site Scripting (XSS) | ADV-1 | Medium | Medium | Medium |
| TE-12 | SQL Injection | ADV-1 | Low | Critical | Low |
| TE-13 | CSRF Attack | ADV-1 | Low | Medium | Low |
| TE-14 | Dependency Vulnerability | NAD-4 | Medium | High | Medium |

### Third-Party Integration

| ID | Threat Event | Threat Source | Likelihood | Impact | Risk Level |
|----|--------------|---------------|------------|--------|------------|
| TE-15 | Epic OAuth Token Theft | ADV-1 | Low | Critical | Medium |
| TE-16 | Epic API Abuse | ADV-2 | Low | High | Low |
| TE-17 | OCR Library Exploit | NAD-4 | Very Low | Medium | Very Low |
| TE-18 | PDF Parser Vulnerability | NAD-4 | Low | Medium | Low |

### Infrastructure

| ID | Threat Event | Threat Source | Likelihood | Impact | Risk Level |
|----|--------------|---------------|------------|--------|------------|
| TE-19 | AWS Misconfiguration | NAD-3 | Medium | High | Medium |
| TE-20 | DDoS Attack | ADV-1 | Medium | Medium | Medium |
| TE-21 | Data Center Failure | NAD-2 | Very Low | High | Low |

## Risk Treatment Plans

### TE-01: Credential Stuffing Attack

**Current Controls:**
- IP-based rate limiting (5 attempts per minute)
- Account lockout after 5 failed attempts
- PBKDF2 password hashing

**Additional Mitigations:**
- Brute force detection alerts (implemented)
- CAPTCHA for repeated failures (planned)
- Breach password detection (planned)

**Residual Risk:** Medium

---

### TE-02: Brute Force Password Attack

**Current Controls:**
- Rate limiting per IP
- Account lockout mechanism
- Email alerts on lockout

**Additional Mitigations:**
- Progressive delay on failures
- IP reputation checking (planned)

**Residual Risk:** Low

---

### TE-05: Unauthorized IDOR Access

**Current Controls:**
- org_id filtering on all queries
- @require_organization_access decorator
- IDOR vulnerability fixes applied

**Additional Mitigations:**
- Automated IDOR testing in CI/CD (planned)

**Residual Risk:** Low

---

### TE-06: PHI Exfiltration

**Current Controls:**
- PHI redaction pipeline
- Minimal data storage
- Audit logging of all PHI access
- Role-based access control

**Additional Mitigations:**
- Data loss prevention monitoring (planned)
- Anomaly detection for bulk access (planned)

**Residual Risk:** Medium

---

### TE-08: PHI Filter Bypass

**Current Controls:**
- Regex-based filtering with multiple patterns
- Idempotent filtering (no double-redaction)
- Medical term whitelisting

**Additional Mitigations:**
- PHI filter failure alerts (implemented)
- Periodic filter effectiveness review

**Residual Risk:** Very Low

---

### TE-10: Temp File PHI Exposure

**Current Controls:**
- Secure 3-pass overwrite deletion
- Unique random filenames
- Automatic cleanup on startup
- Audit logging of file disposal

**Additional Mitigations:**
- RAM disk for temp files (planned)

**Residual Risk:** Very Low

---

### TE-11: Cross-Site Scripting (XSS)

**Current Controls:**
- Jinja2 auto-escaping
- Content Security Policy headers
- Sanitized tojsonpretty filter (fixed)

**Additional Mitigations:**
- Remove 'unsafe-inline' from CSP (planned)
- CSP nonces for inline scripts (planned)

**Residual Risk:** Low

---

### TE-14: Dependency Vulnerability

**Current Controls:**
- Pinned dependency versions
- Open-source library selection

**Additional Mitigations:**
- Automated dependency scanning (planned)
- Regular update schedule

**Residual Risk:** Medium

---

### TE-15: Epic OAuth Token Theft

**Current Controls:**
- AES-256 encryption of stored tokens
- Session-based token storage for interactive use
- Token refresh with short expiry
- Per-provider credential isolation

**Additional Mitigations:**
- Token rotation policy
- Access pattern monitoring (planned)

**Residual Risk:** Low

---

### TE-17: OCR Library Exploit (PyMuPDF/Tesseract)

**Current Controls:**
- Local-only processing (no network calls)
- Open-source auditable code
- Timeout circuit breakers
- Resource limits

**Additional Mitigations:**
- Container sandboxing in production
- Regular library updates

**Residual Risk:** Very Low

---

### TE-19: AWS Misconfiguration

**Current Controls:**
- Infrastructure as code (planned)
- Security group documentation
- VPC private subnets for DB/Redis

**Additional Mitigations:**
- AWS Config rules for compliance
- Automated security audits

**Residual Risk:** Medium

## Risk Acceptance Statement

The following residual risks have been reviewed and accepted by management:

| Risk ID | Description | Residual Risk | Acceptance Rationale |
|---------|-------------|---------------|---------------------|
| TE-06 | PHI Exfiltration | Medium | Multiple layers of protection in place; monitoring planned |
| TE-14 | Dependency Vulnerability | Medium | Acceptable with regular update schedule |
| TE-19 | AWS Misconfiguration | Medium | Will be addressed during AWS deployment phase |

## Review Schedule

- **Quarterly**: Review threat landscape and update likelihood assessments
- **Annually**: Full risk assessment review
- **Event-Driven**: Re-assess after security incidents or major changes

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Security Team | Initial risk register |
