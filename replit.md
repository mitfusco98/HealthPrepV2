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
- Basic Flask app structure with authentication
- Error handling templates

### 🔄 In Progress  
- Core screening engine with fuzzy detection
- OCR processing with PHI filtering
- FHIR client integration
- Admin dashboard components
- Reusable template assets migration

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

## Recent Changes
- 2025-02-02: Initial project setup with models and Flask structure
- 2025-02-02: Created comprehensive database schema for healthcare data
- 2025-02-02: Planned reusable asset migration from V1 project

## Technical Requirements
- Python 3.11+ with Flask framework
- PostgreSQL database with HIPAA-compliant encryption
- Tesseract OCR for document processing
- FHIR R4 compatibility for EMR integration
- Bootstrap-based responsive UI with dark theme