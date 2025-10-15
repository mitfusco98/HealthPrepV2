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
- Role-based user management with comprehensive audit logging for HIPAA compliance
- Multi-tenancy foundation with organization-scoped data isolation
- Enhanced User model with organization relationships and security features
- Epic FHIR credentials management per organization
- Universal screening type naming system with fuzzy detection capabilities
- Enhanced create_preset_from_types with user-specific filtering and variant grouping
- Comprehensive database models for screening catalog management

### Port Conflict Resolution Strategy
The application implements a **hybrid port conflict resolution system** combining:

1. **Environment-Based Port Configuration**: Application respects `PORT` environment variable for flexible port assignment
2. **Dynamic Port Cleanup**: Smart process cleanup and automatic port detection
3. **Intelligent Fallback**: Automatic alternative port discovery when conflicts occur

**Usage Options:**
- **Standard Mode**: `python main.py` - Basic port handling with fallback
- **Smart Mode**: `USE_SMART_START=true python main.py` - Advanced conflict resolution
- **Production Preview**: `python smart_start.py prod` - Gunicorn on port 5001
- **Direct Smart Start**: `python smart_start.py dev` - Enhanced development server

**Port Configuration:**
- Development: Port 5000 (fallback to 5001-5009)
- Production Preview: Port 5001 (fallback to 5002-5100)
- Custom Port: Set `PORT` environment variable

### System Architecture

**Backend Structure:**
The backend is organized into modular components: `core/` for the main engine logic (screening orchestration, fuzzy matching, eligibility criteria, selective refresh management with criteria change detection), `emr/` for FHIR data ingestion, normalization, and synchronization, `ocr/` for document processing (Tesseract integration, quality scoring, PHI filtering), `prep_sheet/` for generation and rendering, `services/` for Epic FHIR service layer with token management, bidirectional data synchronization, and selective EMR sync with pre-flight checks, and `admin/` for dashboard tools and configuration. Key features include a robust user authentication system with Flask-Login, role-based access control, and HIPAA-compliant templates. A unified `PrepSheetSettings` model manages document cutoff periods. Clean URL structures are implemented for screening management, EMR synchronization, Epic FHIR OAuth2 authentication, and comprehensive user management with role-based access control supporting admin, MA, and nurse roles. Screening name autocomplete with fuzzy detection and alias support, medical conditions database with FHIR-compatible codes, and a tag-based keyword management system facilitate data entry and standardization. Enhanced data models integrate comprehensive FHIR data for Patient and FHIRDocument management. **Performance Optimizations (Oct 2025):** Enhanced status calculation using 30-day window for "due soon" detection, appointment-based prioritization integration with intelligent fallback, selective EMR sync with pre-flight checks to skip unchanged patients, and selective screening refresh with criteria change detection to avoid unnecessary reprocessing.

**Frontend Structure:**
The frontend reuses assets from V1, organized under `templates/`. It includes `base_user.html` and `base_admin.html` for distinct user and admin interfaces. Specific directories like `screening/`, `admin/`, `auth/`, and `error/` house templates for various functionalities. The UI is Bootstrap-based, responsive, and supports a dark theme.

**Key Technical Implementations:**
- Database models for patients, screenings, documents, and conditions.
- User authentication and authorization with password hashing and role-based access.
- Centralized `PrepSheetSettings` for configurable prep sheet generation parameters.
- Screening list architecture aligning patient listings with screening statuses.
- Clean URL structure for improved navigation and maintainability.
- Comprehensive error handling.
- OCR processing framework with confidence scoring and configurable PHI filtering.
- Standardized screening names database with fuzzy detection and autocomplete.
- Medical conditions database with FHIR-compatible codes for trigger conditions.
- One-click medical terminology import system and tag-based keyword management.
- Enhanced `ScreeningType` architecture supporting gender/age/condition eligibility, fractional frequencies, and JSON storage for keywords and trigger conditions.
- Comprehensive prep sheet generation system with patient header, quality checklist, recent medical data sections, document relevancy filtering, interactive document links, color-coded badges, configurable time periods, and dynamic response to screening type changes.
- Variant grouping functionality ensuring screening variants display properly as grouped entities with status syncing.
- Dual filtering system for comprehensive prep sheet data control, including document relevancy filtering and medical data cutoffs.
- Selective refreshing system for EMR synchronization implementing intelligent change detection for screening criteria modifications, document additions/deletions, and patient updates, with targeted regeneration of only affected screenings for efficiency and FHIR R4 compatibility. **Critical Fix (Oct 2025)**: Enhanced refresh service to check BOTH local Documents and Epic FHIRDocuments, preventing data loss where refresh operations were overwriting EMR sync results by only checking local documents.
- Advanced fuzzy detection engine with semantic separator handling for filename matching, medical terminology equivalence mapping, keyword variation generation, and confidence-based matching with automatic keyword optimization. **Enhanced Medical Condition Matching (Oct 2025)**: Comprehensive medical condition normalizer with 100+ variants covering pneumonia types, asthma variations, heart disease, PCOS, bronchitis, diabetes types, and medical abbreviations (PCOS, MI, T2DM, CAD, CHF, COPD). Implements clinical modifier stripping (chronic, acute, severe, moderate, mild), severity extraction, spelling variant normalization (ovarian/ovary, ischaemic/ischemic), word boundary protection to prevent false positives (diabetes ≠ prediabetes), and word order flexibility (diabetes mellitus type 2 = type 2 diabetes = T2DM). Trigger conditions fully integrated across all workflows including EMR sync, screening refresh, and new screening type generation using EligibilityCriteria system.
- Multi-tenancy infrastructure with Organization model, data isolation via org_id across all models, organization-scoped queries, enhanced audit logging, Epic credentials per organization, user session management, and onboarding utilities.
- Preset management UI/UX consolidation with streamlined interface and consolidated approval workflows.
- Universal screening type system with comprehensive models enabling fuzzy detection, synonym management, and cross-organizational screening type standardization.
- Enhanced variant management with user-specific filtering, fuzzy name grouping, author tracking, comparison capabilities, and semantic separator handling.
- Root admin preset management system for direct preset promotion to universal availability, activation/deactivation controls, universal preset deletion, and HIPAA-compliant audit logging.
- Comprehensive root admin preset detail view showing detailed screening type information.
- Enhanced baseline screening coverage system addressing trigger condition gaps by enhancing specialty presets with general population baseline and condition-specific variants, ensuring appropriate care and proper variant system integration.
- Epic SMART on FHIR Integration with OAuth2 Authentication, implementing Epic's exact OAuth2 flow and query patterns, including token management with refresh tokens, session-based secure token storage, Epic credentials management per organization, and HIPAA-compliant authentication.
- Comprehensive Epic SMART on FHIR Architectural Adjustments, including enhanced Patient model with FHIR integration fields, FHIRDocument model for Epic DocumentReference management, `screening_fhir_documents` association table, Epic FHIR service layer with token management and automatic refresh, enhanced FHIR client with document operations, bidirectional Epic data synchronization, and writing results back to Epic as DocumentReference resources.
- Asynchronous Processing & Performance Architecture using RQ (Redis Queue) for batch operations supporting patient prep sheet generation, batch FHIR data synchronization, rate limiting, job status monitoring, background document processing, and Epic API rate limit compliance.
- Comprehensive PHI Filter Testing Interface at `/admin/dashboard/phi/test` featuring real-time PHI detection and redaction testing, side-by-side comparison, detailed detection analysis, quick test samples, batch testing capabilities, and HIPAA-compliant audit logging.
- Enhanced Multi-Tenancy & Configurability with production-ready multi-tenant support, organization-specific Epic FHIR endpoints, sandbox vs production configuration, per-organization Epic credentials and base URLs, rate limiting controls, batch size limits, async processing toggles, data isolation enforcement, and comprehensive tenant-scoped token and data storage.
- HIPAA-Compliant Audit Logging & Compliance with comprehensive audit logging system, PHI protection, configurable logging levels, FHIR operation tracking, API call logging, Epic document write tracking, async job audit trails, audit report generation, and secure session-based activity logging.
- Epic FHIR Blueprint Compliance Integration, including enhanced LOINC code mapping system, consolidated screening data structures, advanced unit conversion system, enhanced 401 unauthorized error handling with automatic token refresh retry, and Epic blueprint-compliant API wrapper functions.
- **Epic Prep Sheet Write-Back System (Oct 2025)**: Comprehensive document write-back functionality enabling manual prep sheet generation and Epic DocumentReference creation. Features include PDF generation with WeasyPrint preserving HTML hyperlinks, timestamp-based versioning in filename format (PrepSheet_{MRN}_{YYYYMMDD_HHMMSS}.pdf) and embedded content headers, base64-encoded PDF attachment with FHIR R4-compliant DocumentReference structure, automatic OAuth token refresh with connection error handling, individual prep sheet generation via prep sheet icon in matched documents column on /screening/list, bulk prep sheet generation button adjacent to appointment prioritization display using appointment window filtering, comprehensive audit logging for HIPAA compliance tracking all Epic writes, no local storage (Epic-only write-back), and manual generation only (user-triggered, no auto-generation). The system implements a living document concept where each generation creates a new timestamped version in Epic.

### External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database with HIPAA-compliant encryption.
- **Tesseract OCR:** For document processing and text extraction.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.