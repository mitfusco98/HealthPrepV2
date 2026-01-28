# HealthPrep Legal Documentation Suite

**Version:** 1.0  
**Last Updated:** {{EFFECTIVE_DATE}}  
**HITRUST Control Reference:** 19.d, 19.e (Third Party Agreements)

---

## Purpose

This directory contains the legal documentation suite for HealthPrep, prepared for HITRUST i1 certification submission. These documents establish the contractual framework for HIPAA compliance, data protection, and service delivery.

---

## Document Inventory

| Document | File | Description | HITRUST Control |
|----------|------|-------------|-----------------|
| Terms of Service | [terms_of_service.md](./terms_of_service.md) | General terms governing platform use | 19.d |
| Business Associate Agreement | [business_associate_agreement.md](./business_associate_agreement.md) | HIPAA BAA for PHI handling | 19.e, 06.c |
| Standalone Provider Agreement | [standalone_provider_agreement.md](./standalone_provider_agreement.md) | 12-month service agreement for individual providers | 19.d |
| Multi-Provider Agreement | [multi_provider_agreement.md](./multi_provider_agreement.md) | Enterprise agreement for healthcare organizations | 19.d |
| Order Form | [order_form.md](./order_form.md) | Pricing and subscription details template | 19.d |

---

## Template Variables

All documents use template variables (denoted by `{{VARIABLE_NAME}}`) that should be replaced with actual values when generating final agreements. Key variables include:

### Common Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{EFFECTIVE_DATE}}` | Document effective date | January 15, 2026 |
| `{{AGREEMENT_DATE}}` | Date agreement is signed | January 15, 2026 |

### Provider/Organization Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{PROVIDER_NAME}}` | Legal name of provider | Albany Medical Associates |
| `{{ORGANIZATION_NAME}}` | Legal name of organization | Capital Region Health System |
| `{{COVERED_ENTITY_NAME}}` | HIPAA covered entity name | Albany Medical Center |

### Payment Variables (Adjustable)

| Variable | Description | Default |
|----------|-------------|---------|
| `{{SUBSCRIPTION_FEE_MONTHLY}}` | Monthly per-provider fee | $300.00 |
| `{{SUBSCRIPTION_FEE_PER_PROVIDER}}` | Same as above (multi-provider) | $300.00 |
| `{{BILLING_FREQUENCY}}` | Invoice frequency | Monthly |
| `{{PAYMENT_DUE_DAYS}}` | Days until payment due | 30 |
| `{{LATE_PAYMENT_RATE}}` | Weekly late fee rate | 1% |
| `{{SUSPENSION_GRACE_DAYS}}` | Days before suspension | 15 |
| `{{VOLUME_DISCOUNT_THRESHOLD}}` | Providers needed for discount | 10 |
| `{{VOLUME_DISCOUNT_RATE}}` | Discount percentage | 10% |

---

## HITRUST i1 Compliance Mapping

### Control 19.d - Addressing Security in Third Party Agreements

**Evidence:** Terms of Service, Standalone Provider Agreement, Multi-Provider Agreement

These documents address:
- Security responsibilities of each party
- Compliance requirements (HIPAA, HITECH)
- Acceptable use policies
- Incident reporting obligations
- Termination conditions

### Control 19.e - Addressing Security in Supplier Agreements

**Evidence:** Business Associate Agreement

This document addresses:
- PHI handling requirements
- Minimum necessary standard
- Breach notification (48-hour requirement)
- Safeguard requirements (administrative, technical, physical)
- Audit rights
- Subcontractor requirements
- Return/destruction of PHI

### Control 06.c - Data Protection in Third Party Agreements

**Evidence:** Business Associate Agreement, Terms of Service

These documents address:
- Data minimization
- De-identification standards
- Encryption requirements
- Access controls
- Audit logging

---

## Document Generation Workflow

1. **Select appropriate agreement template** based on customer type:
   - Individual provider → Standalone Provider Agreement + Order Form
   - Healthcare organization → Multi-Provider Agreement
   - All customers → Terms of Service + BAA

2. **Replace template variables** with customer-specific values

3. **Adjust payment terms** as needed using the payment variable table

4. **Generate PDF** from markdown for signature

5. **Execute agreement** and store in document management system

---

## Version Control

All legal documents are maintained in version control with the following practices:

- Major revisions increment the version number (e.g., 1.0 → 2.0)
- Minor revisions use sub-versions (e.g., 1.0 → 1.1)
- All changes are tracked in the Document Control table within each document
- Legal review is required before any version update

---

## Review Schedule

| Document | Review Frequency | Last Review | Next Review |
|----------|------------------|-------------|-------------|
| Terms of Service | Annual | {{EFFECTIVE_DATE}} | +12 months |
| Business Associate Agreement | Annual | {{EFFECTIVE_DATE}} | +12 months |
| Standalone Provider Agreement | Annual | {{EFFECTIVE_DATE}} | +12 months |
| Multi-Provider Agreement | Annual | {{EFFECTIVE_DATE}} | +12 months |
| Order Form | As needed | {{EFFECTIVE_DATE}} | As needed |

---

## Contact

For questions regarding these legal documents, contact:

**Fusco Digital Solutions LLC**  
418 Broadway St, Albany, NY 12207  
Email: legal@fuscodigital.com

---

*This documentation is maintained as part of HealthPrep's HITRUST i1 certification program.*
