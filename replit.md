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

## System Architecture

### UI/UX Decisions
The frontend reuses V1 assets, structured with `base_user.html` and `base_admin.html` for distinct user and administrative interfaces. It is Bootstrap-based, responsive, and supports a dark theme.

### Technical Implementations
The backend is modular, with dedicated components for screening logic, EMR integration, OCR, prep sheet generation, Epic FHIR services, and administrative tools. Key features include user authentication with Flask-Login, role-based access control, clean URL structures, and comprehensive error handling. An OCR processing framework includes confidence scoring and PHI filtering. The system utilizes standardized screening names, a medical conditions database (FHIR-compatible), and tag-based keyword management. `ScreeningType` architecture supports gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords. Prep sheet generation includes dynamic content, interactive links, color-coded badges, and variant grouping for proper display. A dual filtering system controls prep sheet data using document relevancy and medical data cutoffs. Selective refreshing of EMR data uses intelligent change detection. An advanced fuzzy detection engine handles semantic processing and keyword variations, with medical condition normalization.

Multi-tenancy is supported by an `Organization` model, ensuring data isolation via `org_id`, organization-scoped queries, enhanced audit logging, and per-organization Epic credentials. Preset management is consolidated, and a universal screening type system allows cross-organizational standardization. Enhanced variant management includes user-specific filtering and fuzzy name grouping.

Epic SMART on FHIR integration uses OAuth2 for authentication, token management, and session-based secure storage. It includes an enhanced `Patient` model, `FHIRDocument` model for DocumentReference management, and a dedicated FHIR service layer for bidirectional synchronization. Asynchronous processing via RQ (Redis Queue) handles batch operations, rate limiting, and background document processing. A PHI filter testing interface allows real-time detection and redaction testing. The system ensures Epic blueprint compliance through LOINC code mapping, consolidated data structures, and unit conversion. A comprehensive Epic Prep Sheet Write-Back System allows manual PDF generation with WeasyPrint, timestamped versioning, base64-encoded PDF attachments in FHIR R4 DocumentReference format, and automatic OAuth token refresh, including a living document concept. Organization-scoped `PrepSheetSettings` provide independent configuration per tenant. An Epic Dry-Run Mode enables safe testing without live data transmission.

User onboarding supports both self-service via Stripe setup mode and manual creation by root admins. A JSON API endpoint (`/api/signup`) facilitates external marketing website integration for self-service signups, handling organization creation, admin setup, and Stripe checkout URL provisioning. The application uses a unified `billing_state` property on the `Organization` model for consistent access control and integrates with Stripe webhooks for subscription lifecycle management.

### System Design Choices
- **Multi-tenancy:** Core design principle with `Organization` model for data isolation.
- **Microservices-oriented (conceptual):** Modular backend components for distinct functionalities.
- **Asynchronous processing:** RQ (Redis Queue) for background tasks.
- **Security:** HIPAA compliance, robust user authentication (Flask-Login), role-based access control, CSRF protection, comprehensive audit logging, secure deletion of original files, and PHI filtering at multiple layers. Account recovery, OAuth, EMR, document, and session security are hardened with rate limiting, secure tokens, isolation, and audit trails.
- **Extensibility:** Customizable screening logic, universal naming systems, variant management.
- **OCR Processing Optimizations:** Cascading text extraction strategy prioritizing PyMuPDF, then hybrid processing, and finally Tesseract OCR for efficiency. Supports various file and image formats. Parallelized via ThreadPoolExecutor with configurable OCR_MAX_WORKERS (auto-detects CPU cores). Response-time circuit breaker with OCR_TIMEOUT_SECONDS (default 10s) ensures synchronous batch calls return within SLA. Timeout sentinel value (-1.0 confidence) distinguishes true timeouts from low-confidence OCR results, preserving legitimate text. Unified document processing: both manual Document and FHIRDocument types use identical timeout handling, PHI filtering, and parallelization via `process_fhir_documents_batch()`. Thread-safe PHI filtering uses `PHIFilter.get_settings_snapshot()` to preload settings before batch operations, avoiding cross-thread session issues. For production PHI workloads requiring true task cancellation, use RQ async processing (services/async_processing.py) with job_timeout.
- **Document Matching Optimization:** Keyword pre-filtering with medical suffix stem matching (gram/graphy, scopy/scope) skips non-matching screenings before expensive fuzzy matching.
- **Queue Depth Alerting:** PerformanceMonitor.get_queue_metrics() triggers warnings when pending jobs exceed threshold (default 50), alerting operators to SLA risks.
- **Performance:** Performance monitoring via a singleton `PerformanceMonitor` and API endpoints for real-time metrics and reports. Benchmarking scripts (scripts/benchmark_processing.py) analyze throughput and scaling efficiency.
- **Reliability:** Deterministic eligibility calculations, idempotent PHI redaction, match explanation audit trails, and atomic refresh operations using per-patient savepoints.
- **Selective Refresh Optimization:** ScreeningType includes `criteria_signature` (SHA-256 hash of keywords/eligibility/frequency) and `criteria_last_changed_at` timestamp, auto-updated via SQLAlchemy event listeners. Patient model includes `documents_last_evaluated_at` with `needs_document_evaluation(criteria_changed_at)` for skip logic. Document/FHIRDocument models include `content_hash` and `last_processed_at` for unchanged document detection. These optimizations reduce redundant processing when criteria haven't changed.
- **Verified Secure Deletion:** All OCR temp files use `secure_temp_directory()` with 3-pass overwrite before deletion. Preprocessed images tracked via `cleanup_temp_files()` method. HIPAA-compliant PHI disposal with audit logging via `utils/secure_delete.py`.
- **Deterministic PHI Metadata Protection:** Document titles derived exclusively from structured FHIR type codes (LOINC) via `utils/document_types.py`, eliminating PHI leakage from free-text metadata. Free-text title/description/display fields in stored FHIR JSON are redacted to `[REDACTED]`. This provides deterministic HIPAA compliance without relying on regex/NLP name detection.

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
- **Resend:** Transactional email service.