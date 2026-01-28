# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

## Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed for integration with FHIR-based EMRs. Its primary purpose is to parse patient data, determine eligibility for medical screenings using customizable logic, and generate comprehensive, dynamic prep sheets. The system aims to enhance efficiency and compliance in healthcare preparation through an intelligent screening engine, dynamic status updates, advanced variant management, and robust document processing capabilities. It supports both self-service and enterprise client onboarding with a JSON API for marketing website integration. The project prioritizes HIPAA compliance, FHIR interoperability, and providing a scalable, multi-tenant solution for healthcare providers.

## User Preferences
- Focus on healthcare compliance and FHIR integration
- Reuse existing template assets where possible
- Maintain separation between user and admin interfaces
- Prioritize screening engine accuracy and performance
- Implement document relevancy filtering using exact formulas: `cutoff_date = last_completed - relativedelta(years/months=frequency_number)`
- Use dual filtering systems: frequency-based for screening documents, settings-based for medical data categories
- Implement fuzzy detection for semantic keyword matching regardless of separator formatting (underscores, dashes, periods, spaces)
- Use advanced fuzzy matching to identify semantically equivalent terms for improved document-keyword matching accuracy
- Role-based user management with comprehensive audit logging for HIPAA compliance
- Multi-tenancy foundation with organization-scoped data isolation and tenant-specific settings
- Enhanced User model with organization relationships and security features
- Epic FHIR credentials management per organization
- Universal screening type naming system with fuzzy detection capabilities
- Enhanced create_preset_from_types with user-specific filtering and variant grouping
- Comprehensive database models for screening catalog management
- Dry-run mode for Epic integration testing with PHI-safe logging
- Console output for prep sheet feedback: Set `PREP_SHEET_CONSOLE_OUTPUT=true` to enable; verbose mode for individual generation (full sections), quiet mode for bulk (one-line summaries); PHI redacted

## System Architecture
The system features a modular backend with dedicated components for screening logic, EMR integration, OCR, prep sheet generation, and administrative tools. The UI is Bootstrap-based, responsive, and reuses V1 assets with distinct user and admin interfaces.

Key technical aspects include:
- **EMR Integration:** Epic SMART on FHIR integration uses OAuth2 for authentication and supports bidirectional synchronization. It includes logic for environment detection (sandbox vs. production) to determine output format (plain text vs. PDF). All EMR ingestion is routed through `services/comprehensive_emr_sync.py` which uses atomic upserts and PostgreSQL `on_conflict_do_update()`. Prep sheets written back to Epic include specific FHIR identifiers and author displays to prevent circular data flow.
- **Multi-tenancy:** Implemented via an `Organization` model ensuring data isolation, organization-scoped queries, audit logging, and per-organization Epic credentials.
- **Screening Engine:** Supports gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords. Includes deterministic variant selection based on `base_name`, trigger matches, and specificity score, with soft-archiving for obsolete variants.
- **Prep Sheet Generation:** Dynamic content, interactive links, color-coded badges, and variant grouping. Dual filtering controls data relevancy and medical data cutoffs. A daily limit and `relatesTo` with `code: "replaces"` manages living documents.
- **Document Processing (OCR):** A cascading text extraction strategy prioritizes PyMuPDF, then hybrid processing, and finally Tesseract OCR. It supports various formats, parallelization via `ThreadPoolExecutor`, and includes a response-time circuit breaker (`OCR_TIMEOUT_SECONDS`). `MAX_DOCUMENT_PAGES` limits processing costs. **Cost Optimization (v2):** Lazy page rendering using `fitz.get_pixmap()` only renders pages that need OCR (embedded text <50 chars), eliminating pdf2image dependency for most documents. PHI filter uses pre-compiled regex patterns at class level and early-exit detection for already-redacted content, reducing compute by 40-60%.
- **Security & Compliance:** HIPAA compliant with robust authentication (Flask-Login), role-based access control, CSRF protection, comprehensive audit logging, secure deletion with 3-pass overwrite, and multi-layered PHI filtering. PHI metadata protection ensures document titles are LOINC-derived and free of PHI. Enhanced PHI filter includes financial, government, provider IDs, and context-aware patterns. CSP hardened with nonce-based script execution for HITRUST i2 compliance; mode auto-detected via FHIR URL (sandbox=relaxed, production=strict nonces). **Security Lockout System (v2.2):** Dual user status system distinguishes between admin-triggered deactivation (`is_active_user`) and system-triggered security lockouts (`security_locked`). Security lockouts trigger via multiple conditions: (1) 5 failed login attempts, (2) concurrent session detection from different IPs, (3) password spray detection (3+ distinct usernames from same IP in 15 min). Unusual hours logins (outside 6 AM - 5 PM in org timezone) generate alerts without lockout (production-only feature). Concurrent session and password spray detection are universal (all environments). IPBlocklist and UserSession models track IP-based threats and active sessions. Org admins can no longer activate/deactivate users; this is root admin only. Role escalation prevention blocks nurses/MAs from being promoted to admin - they must be deleted and re-registered.
- **Asynchronous Processing:** RQ (Redis Queue) handles batch prep sheet generation and background document processing.
- **Performance & Reliability:** Features selective refresh optimizations using `criteria_signature` and content hashing to reduce redundant processing. Deterministic eligibility calculations and match explanation audit trails ensure reliability.
- **User Onboarding:** Supports self-service via Stripe and manual creation by root admins. A JSON API facilitates external marketing website integration.
- **Key Management:** A documented policy covers rotation schedules, migration mapping to AWS Secrets Manager, dual-key rotation for PHI re-encryption, and container secret injection patterns.
- **Timezone-Aware Dormancy Rollover:** `Organization` model includes IANA timezone for local midnight cutoff for appointment-based prioritization.
- **HITRUST i1 Compliance:** Complete documentation suite covering all 19 domains with gap analysis, training policy, hardening standards, vulnerability management, and vendor risk assessments.

## External Dependencies
- **FHIR-based EMRs:** e.g., Epic
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database.
- **Tesseract OCR:** For document processing.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.
- **Stripe:** Payment processing.
- **Resend:** Transactional email service.