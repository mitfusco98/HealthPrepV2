# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

### Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed to integrate with FHIR-based EMRs (e.g., Epic). It parses incoming patient documents and data, determines eligibility for medical screenings based on customizable logic, and generates prep sheets reflecting the patient's care status. Its core capabilities include an intelligent screening engine with fuzzy detection, dynamic status updates for compliance tracking, comprehensive prep sheet generation with enhanced medical data sections, and administrative controls. The system features advanced variant management for screening types, document relevancy filtering, interactive document links, and configurable time periods for medical data display. The project provides a robust solution for healthcare preparation, improving efficiency and compliance.

### User Preferences
- Focus on healthcare compliance and FHIR integration
- Reuse existing template assets where possible
- Maintain separation between user and admin interfaces
- Prioritize screening engine accuracy and performance
- Implement document relevancy filtering using exact formulas: `cutoff_date = last_completed - relativedelta(years/months=frequency_number)`
- Use dual filtering systems: frequency-based for screening documents, settings-based for medical data categories
- Implement fuzzy detection for semantic keyword matching regardless of separator formatting (underscores, dashes, periods, spaces)
- Use advanced fuzzy matching to identify semantically equivalent terms for improved document-keyword matching accuracy
- **Role-based user management with comprehensive audit logging for HIPAA compliance**
- **✅ COMPLETE: Multi-tenancy foundation with organization-scoped data isolation**
- **✅ COMPLETE: Enhanced User model with organization relationships and security features**
- **✅ COMPLETE: Epic FHIR credentials management per organization**
- **✅ COMPLETE: Universal screening type naming system with fuzzy detection capabilities**
- **✅ COMPLETE: Enhanced create_preset_from_types with user-specific filtering and variant grouping**
- **✅ COMPLETE: Comprehensive database models for screening catalog management**

### System Architecture

**Backend Structure:**
The backend is organized into modular components: `core/` for the main engine logic (screening orchestration, fuzzy matching, eligibility criteria, selective refresh management), `emr/` for FHIR data ingestion, normalization, and synchronization with selective refresh integration, `ocr/` for document processing (Tesseract integration, quality scoring, PHI filtering), `prep_sheet/` for generation and rendering, `services/` for Epic FHIR service layer with comprehensive token management and bidirectional data synchronization, and `admin/` for dashboard tools and configuration. Key features include a robust user authentication system with Flask-Login, role-based access control, and HIPAA-compliant templates. A unified `PrepSheetSettings` model manages document cutoff periods. Clean URL structures are implemented for screening management (`/screening/list`, `/screening/types`, `/screening/settings`), EMR synchronization (`/emr/dashboard`, `/emr/settings`, `/emr/webhook/fhir`), Epic FHIR OAuth2 authentication (`/fhir/epic-authorize`, `/fhir/epic-callback`, `/fhir/epic-disconnect`), and **comprehensive user management (`/admin/users`, `/admin/users/create`, `/admin/users/<id>/edit`, `/admin/users/<id>/delete`, `/admin/users/<id>/toggle-status`) with role-based access control supporting admin, MA, and nurse roles**. Screening name autocomplete with fuzzy detection and alias support, medical conditions database with FHIR-compatible codes, and a tag-based keyword management system facilitate data entry and standardization. **✅ COMPLETE: Enhanced data models with comprehensive FHIR integration - Patient model with epic_patient_id, fhir_patient_resource, last_fhir_sync, fhir_version_id fields and FHIR sync methods; FHIRDocument model for Epic DocumentReference management with processing status tracking, content hash validation, and relevance scoring; screening_fhir_documents association table for document-screening relationships enabling comprehensive Epic document integration.**

**Frontend Structure:**
The frontend reuses assets from V1, organized under `templates/`. It includes `base_user.html` and `base_admin.html` for distinct user and admin interfaces. Specific directories like `screening/`, `admin/`, `auth/`, and `error/` house templates for various functionalities, ensuring a clear separation of concerns. The UI is Bootstrap-based, responsive, and supports a dark theme.

**Key Technical Implementations:**
- Database models for patients, screenings, documents, and conditions.
- User authentication and authorization with password hashing and role-based access.
- Centralized `PrepSheetSettings` for configurable prep sheet generation parameters.
- Screening list architecture aligned with design, consolidating patient listings with screening statuses.
- Clean URL structure for improved navigation and maintainability.
- Comprehensive error handling with dedicated templates.
- OCR processing framework with confidence scoring and configurable PHI filtering patterns.
- Standardized screening names database with fuzzy detection and autocomplete.
- Medical conditions database with FHIR-compatible codes for trigger conditions.
- One-click medical terminology import system and tag-based keyword management.
- Enhanced `ScreeningType` architecture supporting gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords and trigger conditions.
- **Comprehensive prep sheet generation system** with patient header, quality checklist, recent medical data sections, document relevancy filtering, interactive document links, color-coded badges, configurable time periods, and dynamic response to screening type changes.
- **Variant grouping functionality** ensuring screening variants display properly as grouped entities with status syncing across variants.
- **Dual filtering system for comprehensive prep sheet data control:**
  - **Document relevancy filtering** for screening matched documents using the formula: `cutoff_date = last_completed - relativedelta(years/months=frequency_number)`, showing only documents within the last frequency period from last completion
  - **Medical data cutoffs** via `/screening/settings` controlling broad medical data categories (laboratories, imaging, consults, hospital visits) displayed in prep sheet sections, with "To Last Appointment" mode support (cutoff = 0)
- **Selective refreshing system for EMR synchronization** implementing intelligent change detection for screening criteria modifications, document additions/deletions, and patient updates, with targeted regeneration of only affected screenings while preserving unchanged data for maximum efficiency and FHIR R4 compatibility
- **Advanced fuzzy detection engine** with semantic separator handling for filename matching regardless of formatting (underscores, dashes, periods, spaces), medical terminology equivalence mapping, keyword variation generation, and confidence-based matching with automatic keyword optimization and suggestion capabilities
- **✅ COMPLETE: Multi-tenancy infrastructure** with Organization model, data isolation via org_id across all models, organization-scoped queries, enhanced audit logging with HIPAA compliance, Epic credentials per organization, user session management with security features, and comprehensive onboarding utilities
- **✅ COMPLETE: Preset management UI/UX consolidation** with streamlined two-action interface across both `/admin/dashboard/presets` and `/admin/presets`, removing redundant download/import/create buttons and consolidating approval workflows for improved user experience
- **✅ COMPLETE: Universal screening type system** with comprehensive models (UniversalType, UniversalTypeAlias, ScreeningProtocol, ScreeningVariant, TypeSynonymGroup, TypeLabelAssociation) enabling fuzzy detection, synonym management, and cross-organizational screening type standardization
- **✅ COMPLETE: Enhanced variant management** with user-specific filtering in create_preset_from_types, fuzzy name grouping (0.8 exact match, 0.6 partial match thresholds), author tracking, comparison capabilities, and semantic separator handling for improved screening criteria discovery and reuse
- **✅ COMPLETE: Root admin preset management system** with dedicated /root-admin/presets page for direct preset promotion to universal availability, preset activation/deactivation controls, universal preset deletion capabilities, and HIPAA-compliant audit logging
- **✅ COMPLETE: Export request functionality removed** - all global preset management is now handled directly by root admin on /root-admin/presets without organization admin requests
- **✅ COMPLETE: Root admin preset detail view** - comprehensive /root-admin/presets/view/<id> page showing detailed screening type information including name, keywords, conditions, eligibility criteria, frequency, variants, and organization context for thorough preset evaluation before global promotion
- **✅ COMPLETE: Enhanced baseline screening coverage system** - comprehensive solution addressing trigger condition gaps by enhancing specialty presets with both general population baseline variants (no triggers) and condition-specific variants (with triggers) using standardized naming conventions, ensuring all patients receive appropriate care and proper variant system integration
- **✅ COMPLETE: Epic SMART on FHIR Integration with OAuth2 Authentication** - comprehensive FHIR integration implementing Epic's exact OAuth2 flow and query patterns, including Epic authorization endpoint (https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize), SMART on FHIR OAuth2 authentication with proper scopes (openid, fhirUser, patient/*.read, user/*.read), Epic's recommended data retrieval sequence (Patient → Condition → Observation → DocumentReference → Encounter), OAuth2 callback handling (/fhir/epic-callback), token management with refresh tokens, session-based secure token storage, Epic credentials management per organization, HIPAA-compliant authentication (no direct credential handling), and administrative interfaces for OAuth2 connection management (/fhir/epic-config, /fhir/epic-authorize)
- **✅ COMPLETE: Comprehensive Epic SMART on FHIR Architectural Adjustments** - full implementation of Epic's blueprint architectural patterns including enhanced Patient model with FHIR integration fields (epic_patient_id, fhir_patient_resource, last_fhir_sync, fhir_version_id), FHIRDocument model for Epic DocumentReference management with processing status tracking, screening_fhir_documents association table for document-screening relationships, Epic FHIR service layer with comprehensive token management and automatic refresh, enhanced FHIR client with document operations (get_document_content, create_document_reference, update_document_reference), bidirectional Epic data synchronization (sync_patient_from_epic, sync_patient_documents), and writing results back to Epic as DocumentReference resources with proper FHIR formatting and HIPAA-compliant audit logging
- **✅ COMPLETE: Asynchronous Processing & Performance Architecture** - comprehensive async processing system using RQ (Redis Queue) for batch operations supporting 500+ patient prep sheet generation, batch FHIR data synchronization with progress tracking, rate limiting and timeout management, job status monitoring with real-time updates, background document processing with OCR integration, and Epic API rate limit compliance with organizational controls
- **✅ COMPLETE: Enhanced Multi-Tenancy & Configurability** - production-ready multi-tenant support with organization-specific Epic FHIR endpoints, sandbox vs production configuration management, per-organization Epic credentials and base URLs (open.epic.com integration ready), rate limiting controls per tenant, batch size limits and async processing toggles, data isolation enforcement across all FHIR operations, and comprehensive tenant-scoped token and data storage
- **✅ COMPLETE: HIPAA-Compliant Audit Logging & Compliance** - comprehensive audit logging system with PHI protection, configurable logging levels (minimal/standard/detailed), FHIR operation tracking with patient identifier hashing, API call logging for rate limit enforcement, Epic document write tracking, async job audit trails, audit report generation for compliance reviews, and secure session-based activity logging with IP and user agent tracking

### External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database with HIPAA-compliant encryption.
- **Tesseract OCR:** For document processing and text extraction.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.