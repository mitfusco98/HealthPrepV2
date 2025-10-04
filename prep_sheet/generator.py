"""
Assembles content into prep sheet format with medical data integration
"""
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from app import db
from models import Patient, Screening, Document, Appointment, PatientCondition, PrepSheetSettings
from .filters import PrepSheetFilters
import logging

class PrepSheetGenerator:
    """Generates comprehensive prep sheets for patient visits"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id, appointment_id=None):
        """Generate complete prep sheet for a patient"""
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
        settings = self._get_prep_settings()
        
        # Calculate cutoff dates for each data type using prep sheet settings
        lab_cutoff = self._calculate_cutoff_date(settings.labs_cutoff_months, patient_id)
        imaging_cutoff = self._calculate_cutoff_date(settings.imaging_cutoff_months, patient_id)
        consults_cutoff = self._calculate_cutoff_date(settings.consults_cutoff_months, patient_id)
        hospital_cutoff = self._calculate_cutoff_date(settings.hospital_cutoff_months, patient_id)
        
        medical_data = {
            'lab_results': self._get_documents_by_type(patient_id, 'lab', lab_cutoff),
            'imaging_studies': self._get_documents_by_type(patient_id, 'imaging', imaging_cutoff),
            'specialist_consults': self._get_documents_by_type(patient_id, 'consult', consults_cutoff),
            'hospital_stays': self._get_documents_by_type(patient_id, 'hospital', hospital_cutoff)
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
        screenings = Screening.query.filter_by(patient_id=patient_id).join(
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
                'last_completed': screening.last_completed_date,
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
        settings = self._get_prep_settings()
        
        enhanced_data = {
            'laboratories': self._get_enhanced_lab_data(patient_id, settings.labs_cutoff_months),
            'imaging': self._get_enhanced_imaging_data(patient_id, settings.imaging_cutoff_months),
            'consults': self._get_enhanced_consult_data(patient_id, settings.consults_cutoff_months),
            'hospital_visits': self._get_enhanced_hospital_data(patient_id, settings.hospital_cutoff_months)
        }
        
        return enhanced_data
    
    def _get_documents_by_type(self, patient_id, doc_type, cutoff_date):
        """Get documents of specific type after cutoff date"""
        return Document.query.filter_by(
            patient_id=patient_id,
            document_type=doc_type
        ).filter(
            Document.document_date >= cutoff_date
        ).order_by(Document.document_date.desc()).all()
    
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
            screening.last_completed_date
        )
        
        # Return document objects directly for template compatibility
        return relevant_docs
    
    def _get_enhanced_lab_data(self, patient_id, cutoff_months):
        """Get enhanced lab data with filtering based on prep sheet settings"""
        cutoff_date = self._calculate_cutoff_date(cutoff_months, patient_id)
        lab_docs = self._get_documents_by_type(patient_id, 'lab', cutoff_date)
        
        cutoff_description = "To Last Appointment" if cutoff_months == 0 else f"Last {cutoff_months} months"
        
        return {
            'documents': lab_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(lab_docs),
            'most_recent': lab_docs[0] if lab_docs else None
        }
    
    def _get_enhanced_imaging_data(self, patient_id, cutoff_months):
        """Get enhanced imaging data with filtering based on prep sheet settings"""
        cutoff_date = self._calculate_cutoff_date(cutoff_months, patient_id)
        imaging_docs = self._get_documents_by_type(patient_id, 'imaging', cutoff_date)
        
        cutoff_description = "To Last Appointment" if cutoff_months == 0 else f"Last {cutoff_months} months"
        
        return {
            'documents': imaging_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(imaging_docs),
            'most_recent': imaging_docs[0] if imaging_docs else None
        }
    
    def _get_enhanced_consult_data(self, patient_id, cutoff_months):
        """Get enhanced consult data with filtering based on prep sheet settings"""
        cutoff_date = self._calculate_cutoff_date(cutoff_months, patient_id)
        consult_docs = self._get_documents_by_type(patient_id, 'consult', cutoff_date)
        
        cutoff_description = "To Last Appointment" if cutoff_months == 0 else f"Last {cutoff_months} months"
        
        return {
            'documents': consult_docs,
            'cutoff_period': cutoff_description,
            'document_count': len(consult_docs),
            'most_recent': consult_docs[0] if consult_docs else None
        }
    
    def _get_enhanced_hospital_data(self, patient_id, cutoff_months):
        """Get enhanced hospital data with filtering based on prep sheet settings"""
        cutoff_date = self._calculate_cutoff_date(cutoff_months, patient_id)
        hospital_docs = self._get_documents_by_type(patient_id, 'hospital', cutoff_date)
        
        cutoff_description = "To Last Appointment" if cutoff_months == 0 else f"Last {cutoff_months} months"
        
        return {
            'documents': hospital_docs,
            'cutoff_period': f"Last {cutoff_months} months",
            'document_count': len(hospital_docs),
            'most_recent': hospital_docs[0] if hospital_docs else None
        }
    
    def _calculate_cutoff_date(self, months, patient_id=None):
        """
        Calculate cutoff date based on prep sheet settings
        
        If months = 0, use "To Last Appointment" logic
        Otherwise, use months from today
        """
        if months == 0:
            # "To Last Appointment" mode - find most recent completed appointment
            if patient_id:
                last_appointment = Appointment.query.filter_by(
                    patient_id=patient_id,
                    status='completed'
                ).order_by(Appointment.appointment_date.desc()).first()
                
                if last_appointment:
                    return last_appointment.appointment_date.date() if hasattr(last_appointment.appointment_date, 'date') else last_appointment.appointment_date
            
            # Fallback to 6 months if no appointments found
            self.logger.warning(f"No completed appointments found for patient {patient_id}, using 6-month fallback")
            return date.today() - relativedelta(months=6)
        else:
            # Standard months-based cutoff
            return date.today() - relativedelta(months=months)
    
    def _get_prep_settings(self):
        """Get prep sheet settings"""
        settings = PrepSheetSettings.query.first()
        if not settings:
            settings = PrepSheetSettings()
            db.session.add(settings)
            db.session.commit()
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
