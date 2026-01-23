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

### UI/UX Decisions
The frontend reuses V1 assets, structured with `base_user.html` and `base_admin.html` for distinct user and administrative interfaces. It is Bootstrap-based, responsive, and supports a dark theme.

### Technical Implementations
The backend is modular, with dedicated components for screening logic, EMR integration, OCR, prep sheet generation, Epic FHIR services, and administrative tools. Key features include user authentication with Flask-Login, role-based access control, clean URL structures, and comprehensive error handling. An OCR processing framework includes confidence scoring and PHI filtering. The system utilizes standardized screening names, a medical conditions database (FHIR-compatible), and tag-based keyword management. `ScreeningType` architecture supports gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords. Prep sheet generation includes dynamic content, interactive links, color-coded badges, and variant grouping for proper display. A dual filtering system controls prep sheet data using document relevancy and medical data cutoffs. Selective refreshing of EMR data uses intelligent change detection. An advanced fuzzy detection engine handles semantic processing and keyword variations, with medical condition normalization.

Multi-tenancy is supported by an `Organization` model, ensuring data isolation via `org_id`, organization-scoped queries, enhanced audit logging, and per-organization Epic credentials. Preset management is consolidated, and a universal screening type system allows cross-organizational standardization. Enhanced variant management includes user-specific filtering and fuzzy name grouping.

Epic SMART on FHIR integration uses OAuth2 for authentication, token management, and session-based secure storage. It includes an enhanced `Patient` model, `FHIRDocument` model for DocumentReference management, and a dedicated FHIR service layer for bidirectional synchronization. **Epic environment detection for writeback uses FHIR URL pattern as authoritative source**: sandbox URLs (containing `fhir.epic.com/interconnect-fhir-oauth`) → plain text output; production URLs → PDF output. This runtime detection in `_detect_sandbox_from_fhir_url()` overrides the stored `epic_environment` field to prevent format mismatches when credentials change. **`services/comprehensive_emr_sync.py` is the sole authoritative EMR ingestion path** - it provides atomic upserts with SELECT FOR UPDATE row locking and PostgreSQL `on_conflict_do_update()` for duplicate key safety during document synchronization. When prep sheets are written back to Epic, they include a FHIR identifier (`urn:healthprep:document`) and author display (`HealthPrep System`). During EMR sync, `_is_healthprep_generated_document()` detects these markers and skips them to prevent circular data flow. `FHIRDocument._check_healthprep_identifier()` also sets `is_healthprep_generated=True` on any such documents that are processed. Asynchronous processing via RQ (Redis Queue) handles batch prep sheet generation and background document processing. A PHI filter testing interface allows real-time detection and redaction testing. The system ensures Epic blueprint compliance through LOINC code mapping, consolidated data structures, and unit conversion. A comprehensive Epic Prep Sheet Write-Back System allows manual PDF generation with WeasyPrint, timestamped versioning, base64-encoded PDF attachments in FHIR R4 DocumentReference format, and automatic OAuth token refresh, including a living document concept. Organization-scoped `PrepSheetSettings` provide independent configuration per tenant. An Epic Dry-Run Mode enables safe testing without live data transmission. Epic FHIR client includes OperationOutcome parsing for detailed error messages, sandbox limitation detection, and structured error responses.

User onboarding supports both self-service via Stripe setup mode and manual creation by root admins. A JSON API endpoint (`/api/signup`) facilitates external marketing website integration for self-service signups, handling organization creation, admin setup, and Stripe checkout URL provisioning. The application uses a unified `billing_state` property on the `Organization` model for consistent access control and integrates with Stripe webhooks for subscription lifecycle management.

### System Design Choices
- **Multi-tenancy:** Core design principle with `Organization` model for data isolation.
- **Microservices-oriented (conceptual):** Modular backend components for distinct functionalities.
- **Asynchronous processing:** RQ (Redis Queue) for background tasks.
- **Security:** HIPAA compliance, robust user authentication (Flask-Login), role-based access control, CSRF protection, comprehensive audit logging, secure deletion of original files, and PHI filtering at multiple layers. Account recovery, OAuth, EMR, document, and session security are hardened with rate limiting, secure tokens, isolation, and audit trails. Security alerting via Resend for account lockouts, brute force detection, and PHI filter failures. Epic OAuth token refresh includes circuit breaker to prevent infinite retry loops when credentials are revoked. Enhanced PHI filter includes financial IDs, government IDs, provider IDs, PHI-bearing URLs, and context-aware patterns. Production security hardening includes environment-based CORS, enforced encryption key, PostgreSQL requirement, Redis-backed rate limiting, configurable CSP, and dedicated security audit scripts.
- **Extensibility:** Customizable screening logic, universal naming systems, variant management.
- **Deterministic Variant Selection:** Screening types are grouped by `base_name`. For each family, one variant is selected per patient using deterministic sorting based on trigger matches, specificity score, and ID. Obsolete variant screenings are soft-archived and filtered from the UI. `_archive_other_variant_screenings()` automatically removes non-completed screenings for other variants when a more specific variant is created, preserving completed/historical records with HIPAA-compliant audit logging.
- **Ralph Loop Self-Optimization:** 57 tests in `ralph_loop.py` ensure screening engine determinism, error-free operation, condition normalization, variant deduplication, and performance benchmarks. The loop validates: eligibility calculations (<3s for 100 calls), fuzzy detection (<15s for 10 calls), document matcher initialization (<2s), specific_screening_types filtering for targeted refresh, completed screening preservation during variant archiving, DocumentProcessor/PrepSheetGenerator initialization (<3s), PHI filter performance (<3s/100 iterations), criteria signature computation (<1s/100 calls), screening list query with eager loading (<2s for 50 items), HealthPrep document exclusion from admin views, and EMR sync detection of HealthPrep-generated documents (PrepSheet_ filename pattern).
- **HITRUST CSF Readiness:** Documented in `docs/HITRUST_READINESS.md`. Controls mapped across 10 HITRUST domains with evidence locations. Epic MFA justification documents why 2FA is sufficient within an already-authenticated EMR context. Remediation plan phases: Pre-Launch (CSP hardening, pen test, data flow), AWS Migration (architecture diagram, BCP, BAA), Ongoing (key rotation, training).
- **Living Document Prep Sheets:** Daily limit of 10 prep sheet generations per patient prevents record clutter. New prep sheets include FHIR `relatesTo` with `code: "replaces"` to supersede previous versions. Patient model tracks `prep_sheet_count_today`, `prep_sheet_count_date`, and `last_prep_sheet_epic_id`. FHIRDocument tracks `is_superseded` for local records. Appointment window capped at 20 days to control processing scope.
- **OCR Processing Optimizations:** Cascading text extraction strategy prioritizing PyMuPDF, then hybrid processing, and finally Tesseract OCR. Supports various file and image formats. Parallelized via ThreadPoolExecutor with configurable `OCR_MAX_WORKERS`. Response-time circuit breaker with `OCR_TIMEOUT_SECONDS` ensures synchronous batch calls return within SLA. Unified document processing for manual and FHIRDocument types with identical timeout handling, PHI filtering, and parallelization. Thread-safe PHI filtering uses `PHIFilter.get_settings_snapshot()` to preload settings.
- **Document Matching Optimization:** Keyword pre-filtering with medical suffix stem matching skips non-matching screenings before expensive fuzzy matching.
- **Queue Depth Alerting:** `PerformanceMonitor.get_queue_metrics()` triggers warnings when pending jobs exceed a threshold.
- **Performance:** Performance monitoring via a singleton `PerformanceMonitor` and API endpoints for real-time metrics and reports. Benchmarking scripts analyze throughput and scaling efficiency.
- **Reliability:** Deterministic eligibility calculations, idempotent PHI redaction, match explanation audit trails, and atomic refresh operations using per-patient savepoints. Document processing events logged with org/patient/user context.
- **Selective Refresh Optimization:** `ScreeningType` includes `criteria_signature` and `criteria_last_changed_at` timestamp. Patient model includes `documents_last_evaluated_at` with `needs_document_evaluation()` for skip logic. Document/FHIRDocument models include `content_hash` and `last_processed_at` for unchanged document detection. These optimizations reduce redundant processing.
- **Verified Secure Deletion:** All OCR temp files use `secure_temp_directory()` with 3-pass overwrite before deletion. Preprocessed images tracked via `cleanup_temp_files()` method. HIPAA-compliant PHI disposal with audit logging.
- **Deterministic PHI Metadata Protection:** Document titles derived exclusively from structured FHIR type codes (LOINC), eliminating PHI leakage from free-text metadata. Free-text title/description/display fields in stored FHIR JSON are redacted.
- **Dual-Title Architecture:** `FHIRDocument` stores two title fields: `title` (LOINC-derived, PHI-free for UI display) and `search_title` (PHI-filtered, preserves medical keywords for screening matching).
- **AWS Backup/Recovery Architecture:** Designed for deterministic recovery with minimal data storage. Essential data backed up via RDS PITR and S3. Regenerable data reconstructed from Epic sync. Recovery preserves admin and screening functionality.
- **Key Management Policy:** Documented in `docs/security/key-management-policy.md`. Covers rotation schedules, Replit → AWS Secrets Manager migration mapping, ENCRYPTION_KEY dual-key rotation for PHI re-encryption, HITRUST 10.g alignment, and container secret injection patterns (ECS/EKS). Infrastructure-agnostic policy with platform-specific procedures.
- **Timezone-Aware Dormancy Rollover:** Organization model includes IANA timezone field. Dormancy cutoff uses local midnight for clean day-boundary transitions when appointment-based prioritization is enabled. Rolling 14-day window used for other configurations.

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