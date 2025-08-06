# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

### Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed to integrate with FHIR-based EMRs (e.g., Epic). It parses incoming patient documents and data, determines eligibility for medical screenings based on customizable logic, and generates prep sheets reflecting the patient's care status. Its core capabilities include an intelligent screening engine with fuzzy detection, dynamic status updates for compliance tracking, comprehensive prep sheet generation with enhanced medical data sections, and administrative controls. The system features advanced variant management for screening types, document relevancy filtering, interactive document links, and configurable time periods for medical data display. The project provides a robust solution for healthcare preparation, improving efficiency and compliance.

### User Preferences
- Focus on healthcare compliance and FHIR integration
- Reuse existing template assets where possible
- Maintain separation between user and admin interfaces
- Prioritize screening engine accuracy and performance

### System Architecture

**Backend Structure:**
The backend is organized into modular components: `core/` for the main engine logic (screening orchestration, fuzzy matching, eligibility criteria), `emr/` for FHIR data ingestion and normalization, `ocr/` for document processing (Tesseract integration, quality scoring, PHI filtering), `prep_sheet/` for generation and rendering, and `admin/` for dashboard tools and configuration. Key features include a robust user authentication system with Flask-Login, role-based access control, and HIPAA-compliant templates. A unified `PrepSheetSettings` model manages document cutoff periods. Clean URL structures are implemented for screening management (`/screening/list`, `/screening/types`, `/screening/settings`). Screening name autocomplete with fuzzy detection and alias support, medical conditions database with FHIR-compatible codes, and a tag-based keyword management system facilitate data entry and standardization.

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
- **Document relevancy filtering system** implementing the specified formula: `cutoff_date = last_completed - relativedelta(years/months=frequency_number)`, ensuring matched documents for screening types only show documents created after the cutoff date, filtering out documents older than one frequency cycle. Separate broad medical data cutoffs control prep sheet sections.

### External Dependencies
- **FHIR-based EMRs:** e.g., Epic (for real-time data integration)
- **FHIR R4:** For EMR compatibility and interoperability.
- **PostgreSQL:** Primary database with HIPAA-compliant encryption.
- **Tesseract OCR:** For document processing and text extraction.
- **Flask:** Python web framework.
- **Flask-Login:** For user authentication.
- **Werkzeug:** For password hashing.
- **Bootstrap:** For responsive UI design.