# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

### Recent Changes (November 8, 2025)
**Stripe Billing Portal & Epic OAuth Validation:**
- **Stripe Billing Portal Fix**: Fixed broken Stripe billing links ("Update Payment", "Manage Billing") by creating `create_billing_portal_session()` method in StripeService and new `/admin/billing-portal` route that redirects to Stripe Customer Portal for billing management. Replaced 3 hardcoded test URLs in base_admin.html with proper `url_for('admin.billing_portal')` calls.
- **Epic OAuth Connection Validation**: Added `has_epic_oauth_connected` property to Organization model that checks `is_epic_connected` field (validates actual OAuth token from /admin/epic/registration exists, not just credentials entered). This is distinct from `has_epic_credentials` which only verifies credentials are configured.
- **Enhanced Root Admin Dashboard**: Updated pending organizations readiness status badges to show Epic OAuth connection status (green "Epic OAuth" badge when connected with valid token, gray "No OAuth" when not connected). Added prominent "READY FOR APPROVAL" badge combining all 3 readiness checks: payment info (stripe_customer_id), Epic OAuth connected (is_epic_connected=True), and live users (user_count with permanent passwords).

### Previous Changes (November 7, 2025)
**Critical Bug Fixes & Improvements:**
- **Audit Logging Fix**: Corrected all root admin log_admin_event calls to use `org_id=0` instead of falsy conditional logic that incorrectly logged to org_id=1. Affected functions: preset operations, organization management, user management, audit log export, security question reset.
- **Organization Model Properties**: Added `has_payment_info`, `has_epic_credentials`, and `live_user_count` properties for dashboard status indicators showing organization readiness.
- **Root Admin Dashboard**: Enhanced pending organizations table with visual status badges (Payment, Epic, Live Users) to quickly assess organization setup progress.
- **Organization Rejection**: Modified rejection workflow to automatically delete rejected organizations and cascade cleanup of all related data (users, audit logs, credentials).
- **Pre-Trial Configuration Access**: Removed subscription requirement from screening configuration routes (/list, /types, /settings, /type/add, /type/edit) to enable setup before trial activation, while keeping operational routes (/refresh, prep sheet generation) gated.
- **CSRF Security**: Added missing CSRF token to organization edit form in root admin interface.
- **Email Feature Flag**: Added RESEND_ENABLED environment variable to bypass email sending during testing (defaults to true for production).

### Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed for integration with FHIR-based EMRs like Epic. Its primary purpose is to parse patient documents and data, determine eligibility for medical screenings using customizable logic, and generate comprehensive prep sheets reflecting the patient's current care status. Key capabilities include an intelligent screening engine with fuzzy detection, dynamic status updates for compliance tracking, and robust prep sheet generation with enhanced medical data sections. The system also features advanced variant management, document relevancy filtering, interactive document links, and configurable time periods for medical data display, aiming to improve efficiency and compliance in healthcare preparation.

### User Preferences
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

### System Architecture

**UI/UX Decisions:**
The frontend reuses V1 assets, structured with `base_user.html` and `base_admin.html` for distinct user and administrative interfaces. It is Bootstrap-based, responsive, and supports a dark theme.

**Technical Implementations:**
The backend is modular, with `core/` for screening logic, `emr/` for FHIR data, `ocr/` for document processing, `prep_sheet/` for generation, `services/` for Epic FHIR integration, and `admin/` for tools. Key features include a robust user authentication system with Flask-Login and role-based access control (admin, MA, nurse roles), HIPAA-compliant templates, and a unified `PrepSheetSettings` model for document cutoff periods. The system employs clean URL structures, comprehensive error handling, and an OCR processing framework with confidence scoring and PHI filtering.

A standardized screening names database, medical conditions database (FHIR-compatible), and tag-based keyword management facilitate data entry. `ScreeningType` architecture supports gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords. Prep sheet generation includes patient header, quality checklist, recent medical data sections, interactive links, color-coded badges, and dynamic responses to screening type changes. Variant grouping ensures proper display and status syncing.

A dual filtering system controls prep sheet data, combining document relevancy and medical data cutoffs. A selective refreshing system for EMR synchronization uses intelligent change detection to efficiently update affected screenings. An advanced fuzzy detection engine handles semantic separator processing, terminology equivalence, and keyword variation. Medical condition normalization covers 100+ variants, including clinical modifier stripping, severity extraction, and spelling variant normalization.

Multi-tenancy is supported with an `Organization` model, data isolation via `org_id`, organization-scoped queries, enhanced audit logging, and per-organization Epic credentials. Preset management is consolidated, and a universal screening type system allows for cross-organizational standardization. Enhanced variant management includes user-specific filtering and fuzzy name grouping. A root admin system manages universal presets. An enhanced baseline screening coverage system addresses trigger condition gaps.

Epic SMART on FHIR integration uses OAuth2 authentication, including token management and session-based secure storage. Architectural adjustments include an enhanced `Patient` model, `FHIRDocument` model for DocumentReference management, and a dedicated FHIR service layer for bidirectional synchronization. Asynchronous processing via RQ (Redis Queue) handles batch operations, rate limiting, and background document processing. A PHI filter testing interface (`/admin/dashboard/phi/test`) allows real-time detection and redaction testing.

The system features robust multi-tenancy with organization-specific Epic FHIR endpoints, sandbox/production configuration, and comprehensive tenant-scoped token and data storage. HIPAA-compliant audit logging tracks all FHIR operations and API calls. Epic blueprint compliance is ensured through LOINC code mapping, consolidated data structures, unit conversion, and enhanced 401 error handling.

A comprehensive Epic Prep Sheet Write-Back System allows manual PDF generation with WeasyPrint, timestamped versioning, base64-encoded PDF attachments in FHIR R4 DocumentReference format, and automatic OAuth token refresh. This system includes `epic_patient_id` validation, intelligent 401 retry logic, and ensures DocumentReference uses validated Epic patient IDs. It also features a living document concept where each generation creates a new timestamped version in Epic, and comprehensive audit logging. Organization-scoped `PrepSheetSettings` ensure independent configuration per tenant. An Epic Dry-Run Mode enables safe testing of Epic integration without live data transmission, logging FHIR DocumentReference structures with PHI-safe redaction.

### External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database.
- **Tesseract OCR:** For document processing.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.
- **Stripe:** Payment processing ($100/month flat-rate subscription with 14-day trial)
- **Resend:** Transactional email service (not yet configured - needs RESEND_API_KEY and FROM_EMAIL environment variables)