"""
Assembles content into prep sheet format with medical data integration
"""
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from app import db
from models import Patient, Screening, Document, Appointment, PatientCondition, PrepSheetSettings
from .filters import PrepSheetFilters
from ocr.phi_filter import PHIFilter
import logging
import os

class PrepSheetGenerator:
    """Generates comprehensive prep sheets for patient visits"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
        self.phi_filter = PHIFilter()
        self.console_output_enabled = os.environ.get('PREP_SHEET_CONSOLE_OUTPUT', 'false').lower() == 'true'
    
    def _redact_phi(self, text):
        """Redact PHI from text using centralized PHI filter"""
        if not text:
            return text
        return self.phi_filter.filter_text(str(text))
    
    def _redact_mrn(self, mrn):
        """Redact MRN for console display - show only last 4 chars"""
        if not mrn:
            return '[REDACTED]'
        mrn_str = str(mrn)
        if len(mrn_str) <= 4:
            return '****'
        return f"****{mrn_str[-4:]}"
    
    def _output_prep_sheet_verbose(self, patient, medical_data, quality_checklist_data, verbose_mode=False):
        """
        Output verbose prep sheet details to console for individual generation.
        PHI is redacted for safe logging.
        
        Args:
            patient: Patient object
            medical_data: Medical data dict with document matches
            quality_checklist_data: Screening checklist data
            verbose_mode: If True, output verbose details (individual generation).
                          If False, skip output (bulk generation mode).
        """
        if not self.console_output_enabled or not verbose_mode:
            return
        
        # Use print for direct console output that won't be filtered by log levels
        print("\n" + "="*80)
        print("PREP SHEET GENERATION - VERBOSE OUTPUT")
        print("="*80)
        print(f"Patient MRN: {self._redact_mrn(patient.mrn)}")
        print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)
        
        # Medical Data Sections
        print("\n[MEDICAL DATA SECTIONS]")
        
        # Labs
        labs = medical_data.get('lab_results', [])
        cutoffs = medical_data.get('cutoff_dates', {})
        print(f"\n  LABS (cutoff: {cutoffs.get('labs', 'N/A')}):")
        if labs:
            for doc in labs:
                doc_date = getattr(doc, 'document_date', None)
                doc_title = self._redact_phi(getattr(doc, 'title', getattr(doc, 'search_title', 'Unknown')))
                doc_type = getattr(doc, 'document_type', getattr(doc, 'document_type_display', 'Unknown'))
                print(f"    - [{doc_date}] {doc_title} (type: {doc_type})")
        else:
            print("    No lab documents found within cutoff")
        
        # Imaging
        imaging = medical_data.get('imaging_studies', [])
        print(f"\n  IMAGING (cutoff: {cutoffs.get('imaging', 'N/A')}):")
        if imaging:
            for doc in imaging:
                doc_date = getattr(doc, 'document_date', None)
                doc_title = self._redact_phi(getattr(doc, 'title', getattr(doc, 'search_title', 'Unknown')))
                doc_type = getattr(doc, 'document_type', getattr(doc, 'document_type_display', 'Unknown'))
                print(f"    - [{doc_date}] {doc_title} (type: {doc_type})")
        else:
            print("    No imaging documents found within cutoff")
        
        # Consults
        consults = medical_data.get('specialist_consults', [])
        print(f"\n  CONSULTS (cutoff: {cutoffs.get('consults', 'N/A')}):")
        if consults:
            for doc in consults:
                doc_date = getattr(doc, 'document_date', None)
                doc_title = self._redact_phi(getattr(doc, 'title', getattr(doc, 'search_title', 'Unknown')))
                doc_type = getattr(doc, 'document_type', getattr(doc, 'document_type_display', 'Unknown'))
                print(f"    - [{doc_date}] {doc_title} (type: {doc_type})")
        else:
            print("    No consult documents found within cutoff")
        
        # Hospital
        hospital = medical_data.get('hospital_stays', [])
        print(f"\n  HOSPITAL RECORDS (cutoff: {cutoffs.get('hospital', 'N/A')}):")
        if hospital:
            for doc in hospital:
                doc_date = getattr(doc, 'document_date', None)
                doc_title = self._redact_phi(getattr(doc, 'title', getattr(doc, 'search_title', 'Unknown')))
                doc_type = getattr(doc, 'document_type', getattr(doc, 'document_type_display', 'Unknown'))
                print(f"    - [{doc_date}] {doc_title} (type: {doc_type})")
        else:
            print("    No hospital documents found within cutoff")
        
        # Quality Checklist / Screenings
        print("\n[SCREENING QUALITY CHECKLIST]")
        summary = quality_checklist_data.get('summary', {})
        print(f"  Total: {summary.get('total', 0)} | Due: {summary.get('due', 0)} | Due Soon: {summary.get('due_soon', 0)} | Complete: {summary.get('complete', 0)}")
        
        items = quality_checklist_data.get('items', [])
        for item in items:
            # Apply PHI filter to screening name as it could contain patient-derived data
            screening_name = self._redact_phi(item.get('screening_name', 'Unknown'))
            status = item.get('status', 'unknown')
            frequency = item.get('frequency', 'N/A')
            last_completed = item.get('last_completed')
            matched_docs = item.get('matched_documents', [])
            
            last_completed_str = last_completed.strftime('%Y-%m-%d') if last_completed else 'Never'
            print(f"\n  {screening_name} [{status.upper()}]")
            print(f"    Frequency: {frequency} | Last: {last_completed_str}")
            print(f"    Matched Documents: {len(matched_docs)}")
            if matched_docs:
                for doc in matched_docs[:5]:  # Limit to first 5
                    doc_date = getattr(doc, 'document_date', None)
                    doc_title = self._redact_phi(getattr(doc, 'title', getattr(doc, 'search_title', 'Unknown')))
                    print(f"      - [{doc_date}] {doc_title}")
                if len(matched_docs) > 5:
                    print(f"      ... and {len(matched_docs) - 5} more")
        
        print("\n" + "="*80)
        print("END PREP SHEET OUTPUT")
        print("="*80 + "\n")
    
    def generate_prep_sheet(self, patient_id, appointment_id=None, verbose_console=True):
        """
        Generate complete prep sheet for a patient
        
        Args:
            patient_id: Patient ID
            appointment_id: Optional appointment ID
            verbose_console: If True, output verbose details to console (individual generation).
                            If False, skip verbose output (for bulk generation).
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {'success': False, 'error': f'Patient {patient_id} not found'}
        
        try:
            # Get appointment if specified
            appointment = None
            if appointment_id:
                appointment = Appointment.query.get(appointment_id)
            
            # Generate all sections
            quality_checklist_data = self._generate_quality_checklist(patient_id)
            summary_data = self._generate_summary(patient_id)
            medical_data = self._generate_medical_data(patient_id)
            enhanced_data = self._generate_enhanced_data(patient_id)
            
            # Create prep sheet object-like structure for template
            prep_sheet = {
                'generated_at': datetime.now(),
                'appointment_date': appointment.appointment_date if appointment else None,
                'documents_processed': summary_data.get('total_documents', 0),
                'screenings_included': quality_checklist_data['summary']['total'],
                'generation_time_seconds': 0.5,  # Mock timing for now
                'content': {
                    'summary': summary_data,
                    'medical_data': medical_data,
                    'quality_checklist': quality_checklist_data['items'],
                    'enhanced_data': {
                        'checklist_items': [
                            'Obtain vital signs (weight, height, BP, temp)',
                            'Review current medications and allergies',
                            'Verify insurance and contact information',
                            'Review screening recommendations',
                            'Review recent lab/imaging results',
                            'Update care plan and next steps'
                        ],
                        **enhanced_data
                    }
                }
            }
            
            prep_data = {
                'patient': patient,
                'appointment': appointment,
                'prep_sheet': prep_sheet
            }
            
            # Output verbose console details if enabled (individual generation mode only)
            self._output_prep_sheet_verbose(patient, medical_data, quality_checklist_data, verbose_mode=verbose_console)
            
            self.logger.info(f"Generated prep sheet for patient {patient.mrn}")
            return {'success': True, 'data': prep_data}
            
        except Exception as e:
            self.logger.error(f"Error generating prep sheet: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_last_visit(self, patient_id):
        """Get patient's most recent visit information"""
        last_appointment = Appointment.query.filter_by(
            patient_id=patient_id,
            status='completed'
        ).order_by(Appointment.appointment_date.desc()).first()
        
        return {
            'date': last_appointment.appointment_date if last_appointment else None,
            'provider': last_appointment.provider if last_appointment else None,
            'type': last_appointment.appointment_type if last_appointment else None
        }
    
    def _generate_summary(self, patient_id):
        """Generate patient summary section"""
        # Recent appointments
        recent_appointments = Appointment.query.filter_by(
            patient_id=patient_id
        ).order_by(Appointment.appointment_date.desc()).limit(5).all()
        
        # Active conditions
        active_conditions = PatientCondition.query.filter_by(
            patient_id=patient_id,
            is_active=True
        ).order_by(PatientCondition.diagnosis_date.desc()).all()
        
        return {
            'recent_appointments': recent_appointments,
            'active_conditions': active_conditions,
            'total_documents': Document.query.filter_by(patient_id=patient_id).count(),
            'pending_screenings': Screening.query.filter_by(
                patient_id=patient_id,
                status='due'
            ).count()
        }
    
    def _generate_medical_data(self, patient_id):
        """
        Generate recent medical data sections using prep sheet settings
        
        This applies the broad medical data cutoffs configured in /screening/settings
        which control how far back to look for data in each category (labs, imaging, consults, hospital)
        """
        # Get patient's organization for settings lookup
        patient = Patient.query.get(patient_id)
        if not patient or not patient.org_id:
            self.logger.error(f"Patient {patient_id} not found or missing org_id")
            return {}
        
        settings = self._get_prep_settings(patient.org_id)
        
        # Calculate cutoff dates for each data type using prep sheet settings
        lab_cutoff = self._calculate_cutoff_date(settings.labs_cutoff_months, patient_id)
        imaging_cutoff = self._calculate_cutoff_date(settings.imaging_cutoff_months, patient_id)
        consults_cutoff = self._calculate_cutoff_date(settings.consults_cutoff_months, patient_id)
        hospital_cutoff = self._calculate_cutoff_date(settings.hospital_cutoff_months, patient_id)
        
        # Get keyword filters for consults and hospital records
        consults_keywords = settings.get_consults_keywords_list()
        hospital_keywords = settings.get_hospital_keywords_list()
        
        medical_data = {
            'lab_results': self._get_documents_by_type(patient_id, 'lab', lab_cutoff),
            'imaging_studies': self._get_documents_by_type(patient_id, 'imaging', imaging_cutoff),
            'specialist_consults': self._get_documents_by_type(patient_id, 'consult', consults_cutoff, keywords=consults_keywords),
            'hospital_stays': self._get_documents_by_type(patient_id, 'hospital', hospital_cutoff, keywords=hospital_keywords)
        }
        
        # Add structured data where available
        medical_data['structured_labs'] = self._get_structured_lab_data(patient_id, lab_cutoff)
        medical_data['cutoff_dates'] = {
            'labs': lab_cutoff,
            'imaging': imaging_cutoff,
            'consults': consults_cutoff,
            'hospital': hospital_cutoff
        }
        
        self.logger.info(f"Applied prep sheet data cutoffs: labs={settings.labs_cutoff_months}m, imaging={settings.imaging_cutoff_months}m, consults={settings.consults_cutoff_months}m, hospital={settings.hospital_cutoff_months}m")
        
        return medical_data
    
    def _generate_quality_checklist(self, patient_id):
        """Generate screening quality checklist"""
        # Exclude 'superseded' screenings - these are obsolete variant screenings
        # that were replaced by more specific variants (e.g., general -> PCOS variant)
        screenings = Screening.query.filter_by(patient_id=patient_id).filter(
            Screening.status != 'superseded'
        ).join(
            Screening.screening_type
        ).all()
        
        checklist_items = []
        
        for screening in screenings:
            # Get matching documents
            matching_docs = self._get_screening_documents(screening)
            
            item = {
                'screening': screening,
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed,
                'frequency': screening.screening_type.frequency_display,
                'matched_documents': matching_docs,
                'status_badge_class': self._get_status_badge_class(screening.status)
            }
            
            checklist_items.append(item)
        
        # Sort by priority (complete and due_soon first, then due, then others)
        priority_order = {'complete': 0, 'due_soon': 1, 'due': 2, 'overdue': 3}
        checklist_items.sort(key=lambda x: priority_order.get(x['status'], 99))
        
        return {
            'items': checklist_items,
            'summary': {
                'total': len(checklist_items),
                'due': len([i for i in checklist_items if i['status'] == 'due']),
                'due_soon': len([i for i in checklist_items if i['status'] == 'due_soon']),
                'complete': len([i for i in checklist_items if i['status'] == 'complete'])
            }
        }
    
    def _generate_enhanced_data(self, patient_id):
        """Generate enhanced medical data with document integration"""
        patient = Patient.query.get(patient_id)
        org_id = patient.org_id if patient else None
        
        settings = self._get_prep_settings(org_id)
        
        # Get keyword filters for consults and hospital records
        consults_keywords = settings.get_consults_keywords_list()
        hospital_keywords = settings.get_hospital_keywords_list()
        
        # Get data from each helper (they now include is_fallback)
        labs_data = self._get_enhanced_lab_data(patient_id, settings.labs_cutoff_months)
        imaging_data = self._get_enhanced_imaging_data(patient_id, settings.imaging_cutoff_months)
        consults_data = self._get_enhanced_consult_data(patient_id, settings.consults_cutoff_months, keywords=consults_keywords)
        hospital_data = self._get_enhanced_hospital_data(patient_id, settings.hospital_cutoff_months, keywords=hospital_keywords)
        
        # Build list of categories using fallback (with user-friendly names)
        category_name_map = {
            'labs': 'Labs',
            'imaging': 'Imaging', 
            'consults': 'Consults',
            'hospital': 'Hospital Records'
        }
        
        encounter_fallback_categories = []
        if labs_data.get('is_fallback'):
            encounter_fallback_categories.append(category_name_map['labs'])
        if imaging_data.get('is_fallback'):
            encounter_fallback_categories.append(category_name_map['imaging'])
        if consults_data.get('is_fallback'):
            encounter_fallback_categories.append(category_name_map['consults'])
        if hospital_data.get('is_fallback'):
            encounter_fallback_categories.append(category_name_map['hospital'])
        
        encounter_fallback_used = len(encounter_fallback_categories) > 0
        
        enhanced_data = {
            'laboratories': labs_data,
            'imaging': imaging_data,
            'consults': consults_data,
            'hospital_visits': hospital_data,
            'encounter_fallback_used': encounter_fallback_used,
            'encounter_fallback_categories': encounter_fallback_categories
        }
        
        return enhanced_data
    
    def _get_documents_by_type(self, patient_id, doc_type, cutoff_date, keywords=None):
        """
        Get documents of specific type after cutoff date.
        
        Now queries both Document and FHIRDocument models using PrepSheetFilters
        for unified document retrieval with LOINC-based category mapping.
        
        Args:
            patient_id: Patient ID
            doc_type: Document type (lab, imaging, consult, hospital)
            cutoff_date: Date cutoff for document filtering
            keywords: Optional list of keywords to filter documents by content/title
            
        Returns:
            List of document objects (Document or FHIRDocument) matching criteria
        """
        documents = self.filters._get_documents_for_category(
            patient_id, 
            doc_type, 
            cutoff_date, 
            keywords
        )
        
        self.logger.debug(f"Retrieved {len(documents)} documents for {doc_type} category (cutoff: {cutoff_date})")
        
        return documents
    
    def _get_structured_lab_data(self, patient_id, cutoff_date):
        """Get structured lab data (would integrate with FHIR observations)"""
        # This would pull from FHIR Observation resources in a real implementation
        # For now, return filtered document-based lab results
        lab_docs = self._get_documents_by_type(patient_id, 'lab', cutoff_date)
        
        structured_labs = []
        for doc in lab_docs:
            if doc.ocr_text:
                # Extract common lab values using regex
                lab_values = self._extract_lab_values(doc.ocr_text)
                if lab_values:
                    structured_labs.append({
                        'document': doc,
                        'values': lab_values
                    })
        
        return structured_labs
    
    def _extract_lab_values(self, text):
        """Extract structured lab values from OCR text"""
        import re
        
        lab_patterns = {
            'glucose': r'glucose[:\s]*(\d+\.?\d*)\s*(mg/dL)?',
            'a1c': r'(?:A1C|HbA1c)[:\s]*(\d+\.?\d*)\s*%?',
            'cholesterol': r'cholesterol[:\s]*(\d+\.?\d*)\s*(mg/dL)?',
            'triglycerides': r'triglycerides[:\s]*(\d+\.?\d*)\s*(mg/dL)?',
            'hdl': r'HDL[:\s]*(\d+\.?\d*)\s*(mg/dL)?',
            'ldl': r'LDL[:\s]*(\d+\.?\d*)\s*(mg/dL)?'
        }
        
        extracted_values = {}
        
        for lab_name, pattern in lab_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 else 'mg/dL'
                extracted_values[lab_name] = {
                    'value': value,
                    'unit': unit or 'mg/dL'
                }
                break  # Take first match
        
        return extracted_values
    
    def _get_screening_documents(self, screening):
        """Get documents that match a screening within frequency period"""
        # Use filters to get relevant documents based on keywords and frequency from last completed date
        relevant_docs = self.filters.get_relevant_documents(
            screening.patient_id, 
            screening.screening_type.name,
            screening.last_completed
        )
        
        # Return document objects directly for template compatibility
        return relevant_docs
    
    def _get_enhanced_lab_data(self, patient_id, cutoff_months):
        """Get enhanced lab data with filtering based on prep sheet settings"""
        cutoff_date, is_fallback = self._calculate_cutoff_date(cutoff_months, patient_id, return_fallback_info=True)
        lab_docs = self._get_documents_by_type(patient_id, 'lab', cutoff_date)
        
        if is_fallback:
            cutoff_description = "Last 6 months (no prior encounter)"
        elif cutoff_months == 0:
            cutoff_description = "To Last Encounter"
        else:
            cutoff_description = f"Last {cutoff_months} months"
        
        return {
            'documents': lab_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(lab_docs),
            'most_recent': lab_docs[0] if lab_docs else None,
            'is_fallback': is_fallback
        }
    
    def _get_enhanced_imaging_data(self, patient_id, cutoff_months):
        """Get enhanced imaging data with filtering based on prep sheet settings"""
        cutoff_date, is_fallback = self._calculate_cutoff_date(cutoff_months, patient_id, return_fallback_info=True)
        imaging_docs = self._get_documents_by_type(patient_id, 'imaging', cutoff_date)
        
        if is_fallback:
            cutoff_description = "Last 6 months (no prior encounter)"
        elif cutoff_months == 0:
            cutoff_description = "To Last Encounter"
        else:
            cutoff_description = f"Last {cutoff_months} months"
        
        return {
            'documents': imaging_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(imaging_docs),
            'most_recent': imaging_docs[0] if imaging_docs else None,
            'is_fallback': is_fallback
        }
    
    def _get_enhanced_consult_data(self, patient_id, cutoff_months, keywords=None):
        """Get enhanced consult data with filtering based on prep sheet settings"""
        cutoff_date, is_fallback = self._calculate_cutoff_date(cutoff_months, patient_id, return_fallback_info=True)
        consult_docs = self._get_documents_by_type(patient_id, 'consult', cutoff_date, keywords=keywords)
        
        if is_fallback:
            cutoff_description = "Last 6 months (no prior encounter)"
        elif cutoff_months == 0:
            cutoff_description = "To Last Encounter"
        else:
            cutoff_description = f"Last {cutoff_months} months"
        
        return {
            'documents': consult_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(consult_docs),
            'most_recent': consult_docs[0] if consult_docs else None,
            'is_fallback': is_fallback
        }
    
    def _get_enhanced_hospital_data(self, patient_id, cutoff_months, keywords=None):
        """Get enhanced hospital data with filtering based on prep sheet settings"""
        cutoff_date, is_fallback = self._calculate_cutoff_date(cutoff_months, patient_id, return_fallback_info=True)
        hospital_docs = self._get_documents_by_type(patient_id, 'hospital', cutoff_date, keywords=keywords)
        
        if is_fallback:
            cutoff_description = "Last 6 months (no prior encounter)"
        elif cutoff_months == 0:
            cutoff_description = "To Last Encounter"
        else:
            cutoff_description = f"Last {cutoff_months} months"
        
        return {
            'documents': hospital_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(hospital_docs),
            'most_recent': hospital_docs[0] if hospital_docs else None,
            'is_fallback': is_fallback
        }
    
    def _calculate_cutoff_date(self, months, patient_id=None, return_fallback_info=False):
        """
        Calculate cutoff date based on prep sheet settings
        
        If months = 0, use "To Last Encounter" logic (most recent completed visit before today)
        Otherwise, use months from today
        
        Args:
            months: Number of months for cutoff (0 = To Last Encounter)
            patient_id: Patient ID for encounter lookup
            return_fallback_info: If True, returns (date, is_fallback) tuple
        
        Returns:
            date or (date, is_fallback) tuple if return_fallback_info=True
        """
        is_fallback = False
        
        if months == 0:
            # "To Last Encounter" mode - find most recent completed encounter before today
            if patient_id:
                patient = Patient.query.get(patient_id)
                if patient and patient.last_completed_encounter_at:
                    encounter_date = patient.last_completed_encounter_at
                    self.logger.info(f"Using last_completed_encounter_at ({encounter_date}) for patient {patient_id}")
                    cutoff = encounter_date.date() if hasattr(encounter_date, 'date') else encounter_date
                    return (cutoff, False) if return_fallback_info else cutoff
            
            # Fallback to 6 months if no encounters found
            self.logger.warning(f"No completed encounters found for patient {patient_id}, using 6-month fallback")
            is_fallback = True
            cutoff = date.today() - relativedelta(months=6)
        else:
            # Standard months-based cutoff
            cutoff = date.today() - relativedelta(months=months)
        
        return (cutoff, is_fallback) if return_fallback_info else cutoff
    
    def _get_prep_settings(self, org_id=None):
        """Get prep sheet settings for organization"""
        if org_id:
            settings = PrepSheetSettings.query.filter_by(org_id=org_id).first()
            if not settings:
                # Create default settings for this organization
                settings = PrepSheetSettings(org_id=org_id)
                db.session.add(settings)
                db.session.commit()
                self.logger.info(f"Created default PrepSheetSettings for org_id={org_id}")
            return settings
        else:
            # Legacy fallback: get first settings or create default without org_id
            settings = PrepSheetSettings.query.first()
            if not settings:
                settings = PrepSheetSettings()
                db.session.add(settings)
                db.session.commit()
                self.logger.info("Created default PrepSheetSettings (no org_id)")
            return settings
    
    def _get_status_badge_class(self, status):
        """Get CSS class for status badge"""
        status_classes = {
            'due': 'badge-danger',
            'due_soon': 'badge-warning',
            'complete': 'badge-success'
        }
        return status_classes.get(status, 'badge-secondary')
    
    def _get_confidence_class(self, confidence):
        """Get CSS class for confidence level"""
        if confidence is None:
            return 'confidence-unknown'
        elif confidence >= 0.8:
            return 'confidence-high'
        elif confidence >= 0.6:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def generate_quick_prep(self, patient_id):
        """Generate a quick prep sheet with essential information only"""
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        
        # Get only critical screenings (due/due soon)
        critical_screenings = Screening.query.filter_by(
            patient_id=patient_id
        ).filter(Screening.status.in_(['due', 'due_soon'])).all()
        
        # Get recent documents (last 30 days)
        recent_cutoff = date.today() - timedelta(days=30)
        recent_docs = Document.query.filter_by(
            patient_id=patient_id
        ).filter(Document.document_date >= recent_cutoff).limit(10).all()
        
        return {
            'patient': patient,
            'generated_at': datetime.now(),
            'type': 'quick_prep',
            'critical_screenings': critical_screenings,
            'recent_documents': recent_docs,
            'active_conditions': PatientCondition.query.filter_by(
                patient_id=patient_id,
                is_active=True
            ).limit(5).all()
        }
