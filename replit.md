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

### System Architecture

**Backend Structure:**
The backend is organized into modular components: `core/` for the main engine logic (screening orchestration, fuzzy matching, eligibility criteria, selective refresh management), `emr/` for FHIR data ingestion, normalization, and synchronization with selective refresh integration, `ocr/` for document processing (Tesseract integration, quality scoring, PHI filtering), `prep_sheet/` for generation and rendering, and `admin/` for dashboard tools and configuration. Key features include a robust user authentication system with Flask-Login, role-based access control, and HIPAA-compliant templates. A unified `PrepSheetSettings` model manages document cutoff periods. Clean URL structures are implemented for screening management (`/screening/list`, `/screening/types`, `/screening/settings`), EMR synchronization (`/emr/dashboard`, `/emr/settings`, `/emr/webhook/fhir`), and **comprehensive user management (`/admin/users`, `/admin/users/create`, `/admin/users/<id>/edit`, `/admin/users/<id>/delete`, `/admin/users/<id>/toggle-status`) with role-based access control supporting admin, MA, and nurse roles**. Screening name autocomplete with fuzzy detection and alias support, medical conditions database with FHIR-compatible codes, and a tag-based keyword management system facilitate data entry and standardization. **✅ COMPLETE: Enhanced User model with organization linkage, role field, activity tracking, session management, and comprehensive audit logging for HIPAA compliance with full multi-tenancy support. Organization model implemented with Epic FHIR configuration, EpicCredentials storage, and data isolation across all core models (Patient, Screening, Document, ScreeningType).**

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

### External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database with HIPAA-compliant encryption.
- **Tesseract OCR:** For document processing and text extraction.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.