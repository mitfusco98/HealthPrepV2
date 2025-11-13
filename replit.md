# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

## Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed for integration with FHIR-based EMRs like Epic. Its primary purpose is to parse patient documents and data, determine eligibility for medical screenings using customizable logic, and generate comprehensive prep sheets reflecting the patient's current care status. Key capabilities include an intelligent screening engine with fuzzy detection, dynamic status updates for compliance tracking, and robust prep sheet generation with enhanced medical data sections. The system also features advanced variant management, document relevancy filtering, interactive document links, and configurable time periods for medical data display, aiming to improve efficiency and compliance in healthcare preparation.

The system supports both self-service (Stripe billing, 14-day trial) and manual (enterprise sales, custom billing) organization creation, with a JSON API for marketing website integration to streamline client onboarding.

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

## System Architecture

### UI/UX Decisions
The frontend reuses V1 assets, structured with `base_user.html` and `base_admin.html` for distinct user and administrative interfaces. It is Bootstrap-based, responsive, and supports a dark theme.

### Technical Implementations
The backend is modular, with `core/` for screening logic, `emr/` for FHIR data, `ocr/` for document processing, `prep_sheet/` for generation, `services/` for Epic FHIR integration, and `admin/` for tools. Key features include a robust user authentication system with Flask-Login and role-based access control. The system employs clean URL structures, comprehensive error handling, and an OCR processing framework with confidence scoring and PHI filtering.

A standardized screening names database, medical conditions database (FHIR-compatible), and tag-based keyword management facilitate data entry. `ScreeningType` architecture supports gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords. Prep sheet generation includes patient header, quality checklist, recent medical data sections, interactive links, color-coded badges, and dynamic responses to screening type changes. Variant grouping ensures proper display and status syncing.

A dual filtering system controls prep sheet data, combining document relevancy and medical data cutoffs. A selective refreshing system for EMR synchronization uses intelligent change detection to efficiently update affected screenings. An advanced fuzzy detection engine handles semantic separator processing, terminology equivalence, and keyword variation. Medical condition normalization covers 100+ variants.

Multi-tenancy is supported with an `Organization` model, data isolation via `org_id`, organization-scoped queries, enhanced audit logging, and per-organization Epic credentials. Preset management is consolidated, and a universal screening type system allows for cross-organizational standardization. Enhanced variant management includes user-specific filtering and fuzzy name grouping. A root admin system manages universal presets, and an enhanced baseline screening coverage system addresses trigger condition gaps.

Epic SMART on FHIR integration uses OAuth2 authentication, including token management and session-based secure storage. Architectural adjustments include an enhanced `Patient` model, `FHIRDocument` model for DocumentReference management, and a dedicated FHIR service layer for bidirectional synchronization. Asynchronous processing via RQ (Redis Queue) handles batch operations, rate limiting, and background document processing. A PHI filter testing interface allows real-time detection and redaction testing.

The system features robust multi-tenancy with organization-specific Epic FHIR endpoints, sandbox/production configuration, and comprehensive tenant-scoped token and data storage. HIPAA-compliant audit logging tracks all FHIR operations and API calls. Epic blueprint compliance is ensured through LOINC code mapping, consolidated data structures, unit conversion, and enhanced 401 error handling.

A comprehensive Epic Prep Sheet Write-Back System allows manual PDF generation with WeasyPrint, timestamped versioning, base64-encoded PDF attachments in FHIR R4 DocumentReference format, and automatic OAuth token refresh. This system includes `epic_patient_id` validation, intelligent 401 retry logic, and ensures DocumentReference uses validated Epic patient IDs. It also features a living document concept where each generation creates a new timestamped version in Epic, and comprehensive audit logging. Organization-scoped `PrepSheetSettings` ensure independent configuration per tenant. An Epic Dry-Run Mode enables safe testing of Epic integration without live data transmission, logging FHIR DocumentReference structures with PHI-safe redaction.

User onboarding supports both self-service via Stripe setup mode (payment collected without starting trial, trial starts upon root admin approval) and manual creation by root admins for enterprise clients (no trial, immediate activation). A JSON API endpoint (`/api/signup`) facilitates external marketing website integration for self-service signups, handling organization creation, admin setup, and Stripe checkout URL provisioning. This API is CORS-enabled and CSRF-exempt.

### System Design Choices
- **Multi-tenancy:** Core design principle with `Organization` model for data isolation.
- **Microservices-oriented (conceptual):** Modular backend components for distinct functionalities.
- **Asynchronous processing:** RQ (Redis Queue) for background tasks.
- **Security:** HIPAA compliance, robust user authentication (Flask-Login), role-based access control, CSRF protection, comprehensive audit logging.
- **Extensibility:** Customizable screening logic, universal naming systems, variant management.

## External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database.
- **Tesseract OCR:** For document processing.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.
- **Stripe:** Payment processing.
- **Resend:** Transactional email service (requires RESEND_API_KEY and FROM_EMAIL environment variables).