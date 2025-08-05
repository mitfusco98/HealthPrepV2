# Health-Prep v2 - HIPAA-Compliant Healthcare Preparation System

## Project Overview
Health-Prep v2 is a real-time medical preparation sheet generation engine designed to integrate with FHIR-based EMRs (e.g., Epic). It parses incoming patient documents and data, determines eligibility for medical screenings based on customizable logic, and generates prep sheets reflecting the patient's care status.

## Core Objectives
- **Intelligent Screening Engine**: Analyzes user-defined screening types with fuzzy detection for equivalent terms
- **Document Processing**: OCR system with quality scoring and HIPAA-compliant PHI filtering
- **Dynamic Status Updates**: Real-time compliance tracking (Complete, Due, Due Soon) based on frequency and last screening dates
- **Comprehensive Prep Sheets**: Include patient headers, medical summaries, quality checklists, and filtered clinical data
- **Administrative Controls**: User management, activity logging, and screening preset management
- **FHIR Integration**: SMART on FHIR workflows for EMR compatibility

## Project Architecture

### Backend Structure
```
├── core/                      # Core engine logic
│   ├── engine.py              # Screening engine orchestration
│   ├── matcher.py             # Fuzzy keyword + document matching
│   ├── criteria.py            # Screening eligibility and frequency logic
│   └── variants.py            # Handles screening type variants
├── emr/                       # FHIR data ingestion and normalization
│   ├── fhir_client.py         # SMART on FHIR API client
│   ├── parser.py              # Converts FHIR bundles to internal model
│   └── models.py              # Internal representations of EMR data
├── ocr/                       # OCR + document processing
│   ├── processor.py           # Tesseract integration and text cleanup
│   ├── monitor.py             # Quality/confidence scoring
│   └── phi_filter.py          # Regex-based PHI redaction
├── prep_sheet/               # Prep sheet generation and rendering
│   ├── generator.py           # Assembles content into prep sheet format
│   ├── filters.py             # Frequency and cutoff filtering logic
│   └── templates/             # HTML/JSON templates
├── admin/                     # Admin dashboard tools
│   ├── logs.py                # Admin log management
│   ├── analytics.py           # Hours saved, compliance gaps closed
│   └── config.py              # Admin configurations and presets
```

### Frontend Structure (Reusable Assets from V1)
```
templates/
├── base_user.html              # Renamed from base_demo.html
├── base_admin.html             # For admin interface
├── screening/
│   ├── list.html               # Extracted from screening_list.html
│   ├── types.html
│   └── checklist_settings.html
├── admin/
│   ├── dashboard.html
│   ├── ocr_dashboard.html
│   └── logs.html
├── auth/
│   └── login.html
└── error/
    └── [400.html, 401.html, 403.html, 404.html, 500.html]
```

## Key Features Implementation Status

### ✅ Completed
- Database models for patients, screenings, documents, conditions
- **User Authentication System** (January 2025)
  - Flask-Login integration with session-based authentication
  - Login, logout, and registration routes in `/auth` blueprint
  - User registration with duplicate checking and validation
  - Password hashing with Werkzeug security
  - Role-based access control (admin/user roles)
  - HIPAA-compliant login and registration templates
  - Authentication redirects to `/home` after login
  - Default admin and test users created
- **Prep Sheet Settings System** (January 2025)
  - Replaced redundant ChecklistSettings with unified PrepSheetSettings model
  - PrepSheetSettings for document cutoff periods (labs, imaging, consults, hospital)
  - Admin route `/admin/settings/prep-sheet` for configuration management
  - PrepSheetSettingsForm with validation and number range constraints
  - HIPAA-compliant admin template for prep sheet settings
  - Integration with prep sheet generation pipeline
- **Screening List Architecture Alignment** (January 2025)
  - Removed conflicting `/patients` route and templates per design intent
  - Redirected patient list functionality to `/screening/list` as specified in design
  - Patient listings with screening statuses now properly consolidated on screening list
  - Removed redundant patient_routes.py module causing cascading errors
  - Maintained individual patient detail and prep sheet functionality
  - DocumentUploadForm and PatientForm retained for document management workflow
- **Clean URL Structure Implementation** (January 2025)
  - Restructured screening management to use clean URL structure
  - `/screening/list` - Main screening list with patient statuses
  - `/screening/types` - Screening types management interface  
  - `/screening/settings` - Prep sheet configuration settings
  - Updated templates with proper navigation between tabs using links instead of JavaScript tabs
  - All routes properly authenticated and functioning with 302 redirects
- Error handling templates
- Admin dashboard structure (logs, analytics, PHI settings)
- OCR processing framework with confidence scoring
- PHI filtering system with configurable patterns

### 🔄 In Progress  
- Core screening engine with fuzzy detection
- FHIR client integration
- Template asset organization and modularization

### ✅ Recently Completed
- **Enhanced Screening Types Architecture** (January 2025)
  - Aligned model fields with design intent for gender/age/condition eligibility
  - Added `description` field for better screening documentation
  - Enhanced `eligible_genders` field with clear 'M', 'F', 'both' options 
  - Updated `frequency_years` to support fractional frequencies (0.25 for quarterly, etc.)
  - Implemented proper JSON storage for keywords and trigger conditions
  - Created comprehensive add/edit forms with examples and guidance
  - Added proper field validation and help text aligned with healthcare requirements
  - Implemented full CRUD operations for screening type management

### ⚠️ Current Issues
- Some LSP diagnostics in routes (model attribute references need cleanup)
- Incomplete screening engine implementation  
- FHIR integration not yet started

### 📋 Planned
- Screening type variants and presets
- Batch automation for 500+ patients
- Multi-tenant architecture
- Performance optimization (10s prep generation)
- HIPAA compliance features (audit logs, encryption)

## User Preferences
- Focus on healthcare compliance and FHIR integration
- Reuse existing template assets where possible
- Maintain separation between user and admin interfaces
- Prioritize screening engine accuracy and performance

## Design Document Adherence

### Aligned with TDD/Design Intent:
- ✅ Database schema matches healthcare data requirements
- ✅ Admin dashboard follows specified structure
- ✅ OCR processing with HIPAA-compliant PHI filtering
- ✅ Screening status tracking (Complete, Due, Due Soon)
- ✅ Multi-tenant ready architecture

### Needs Alignment:
- ⚠️ FHIR integration (core requirement not yet implemented)
- ⚠️ Fuzzy detection for screening types
- ⚠️ Screening type variants system
- ⚠️ Batch automation for 500+ patients
- ⚠️ Performance targets (10s prep generation)

## Recent Changes
- 2025-01-04: Implemented clean URL structure for screening management (/screening/list, /screening/types, /screening/settings)
- 2025-01-04: Updated navigation templates to use proper links instead of JavaScript tabs
- 2025-01-04: Fixed indentation errors in screening routes and verified all routes working with authentication
- 2025-01-04: Replaced ChecklistSettings with PrepSheetSettings system aligned with design intent
- 2025-01-04: Removed conflicting /patients route, redirected to /screening/list per design requirements
- 2025-01-04: Cleaned up redundant patient_routes module causing cascading errors
- 2025-01-04: Consolidated patient listings with screening information on single screening list view
- 2025-02-02: Initial project setup with models and Flask structure
- 2025-02-02: Created comprehensive database schema for healthcare data

## Technical Requirements
- Python 3.11+ with Flask framework
- PostgreSQL database with HIPAA-compliant encryption
- Tesseract OCR for document processing
- FHIR R4 compatibility for EMR integration
- Bootstrap-based responsive UI with dark theme