"""
Assembles content into prep sheet format with medical data filtering
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dateutil.relativedelta import relativedelta
from models import Patient, Screening, MedicalDocument, Condition, Appointment, ChecklistSettings
from .filters import PrepSheetFilters

logger = logging.getLogger(__name__)

class PrepSheetGenerator:
    """Generates comprehensive preparation sheets for patient visits"""
    
    def __init__(self):
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient: Patient, appointment_date: datetime = None) -> Dict[str, Any]:
        """
        Generate a complete preparation sheet for a patient
        """
        logger.info(f"Generating prep sheet for patient {patient.mrn}")
        
        if not appointment_date:
            appointment_date = datetime.utcnow()
        
        # Get current checklist settings for filtering
        settings = ChecklistSettings.get_current()
        
        # Build prep sheet data
        prep_data = {
            'patient_header': self._generate_patient_header(patient, appointment_date),
            'patient_summary': self._generate_patient_summary(patient),
            'medical_data': self._generate_medical_data(patient, settings),
            'quality_checklist': self._generate_quality_checklist(patient),
            'enhanced_data': self._generate_enhanced_medical_data(patient, settings),
            'generation_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'generated_for_date': appointment_date.isoformat(),
                'settings_applied': {
                    'lab_cutoff_months': settings.lab_cutoff_months,
                    'imaging_cutoff_months': settings.imaging_cutoff_months,
                    'consult_cutoff_months': settings.consult_cutoff_months,
                    'hospital_cutoff_months': settings.hospital_cutoff_months
                }
            }
        }
        
        logger.info(f"Prep sheet generated for patient {patient.mrn}")
        return prep_data
    
    def _generate_patient_header(self, patient: Patient, appointment_date: datetime) -> Dict[str, Any]:
        """Generate patient header information"""
        
        # Get last visit
        last_appointment = Appointment.query.filter_by(patient_id=patient.id)\
            .filter(Appointment.appointment_date < appointment_date)\
            .order_by(Appointment.appointment_date.desc()).first()
        
        return {
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth.strftime('%m/%d/%Y'),
            'age': patient.age,
            'gender': patient.gender,
            'phone': patient.phone,
            'email': patient.email,
            'address': patient.address,
            'prep_date': appointment_date.strftime('%m/%d/%Y'),
            'last_visit': {
                'date': last_appointment.appointment_date.strftime('%m/%d/%Y') if last_appointment else 'No previous visits',
                'type': last_appointment.appointment_type if last_appointment else None,
                'provider': last_appointment.provider if last_appointment else None
            }
        }
    
    def _generate_patient_summary(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient summary with recent visits and conditions"""
        
        # Recent appointments (last 6 months)
        six_months_ago = datetime.utcnow() - relativedelta(months=6)
        recent_appointments = Appointment.query.filter_by(patient_id=patient.id)\
            .filter(Appointment.appointment_date >= six_months_ago)\
            .order_by(Appointment.appointment_date.desc()).limit(5).all()
        
        # Active conditions
        active_conditions = Condition.query.filter_by(patient_id=patient.id, status='active')\
            .order_by(Condition.onset_date.desc().nullslast()).all()
        
        # Format appointments
        appointment_list = []
        for appointment in recent_appointments:
            appointment_list.append({
                'date': appointment.appointment_date.strftime('%m/%d/%Y'),
                'type': appointment.appointment_type,
                'provider': appointment.provider,
                'status': appointment.status,
                'notes': appointment.notes
            })
        
        # Format conditions
        condition_list = []
        for condition in active_conditions:
            condition_list.append({
                'name': condition.condition_name,
                'icd10_code': condition.icd10_code,
                'onset_date': condition.onset_date.strftime('%m/%d/%Y') if condition.onset_date else 'Unknown',
                'status': condition.status
            })
        
        return {
            'recent_appointments': appointment_list,
            'active_conditions': condition_list,
            'appointment_count': len(appointment_list),
            'condition_count': len(condition_list)
        }
    
    def _generate_medical_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate filtered medical data sections"""
        
        # Calculate cutoff dates
        now = datetime.utcnow()
        lab_cutoff = now - relativedelta(months=settings.lab_cutoff_months)
        imaging_cutoff = now - relativedelta(months=settings.imaging_cutoff_months)
        consult_cutoff = now - relativedelta(months=settings.consult_cutoff_months)
        hospital_cutoff = now - relativedelta(months=settings.hospital_cutoff_months)
        
        # Get documents by type with cutoff filtering
        lab_docs = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='lab').all(),
            lab_cutoff.date()
        )
        
        imaging_docs = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='imaging').all(),
            imaging_cutoff.date()
        )
        
        consult_docs = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='consult').all(),
            consult_cutoff.date()
        )
        
        hospital_docs = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='hospital').all(),
            hospital_cutoff.date()
        )
        
        return {
            'recent_lab_results': self._format_medical_documents(lab_docs, 'lab'),
            'recent_imaging_studies': self._format_medical_documents(imaging_docs, 'imaging'),
            'recent_specialist_consults': self._format_medical_documents(consult_docs, 'consult'),
            'recent_hospital_stays': self._format_medical_documents(hospital_docs, 'hospital'),
            'data_periods': {
                'lab_period': f'Last {settings.lab_cutoff_months} months',
                'imaging_period': f'Last {settings.imaging_cutoff_months} months',
                'consult_period': f'Last {settings.consult_cutoff_months} months',
                'hospital_period': f'Last {settings.hospital_cutoff_months} months'
            }
        }
    
    def _generate_quality_checklist(self, patient: Patient) -> Dict[str, Any]:
        """Generate quality checklist with screening statuses"""
        
        # Get all screenings for patient
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        # Format screening data
        screening_list = []
        for screening in screenings:
            # Get matched documents for this screening
            matched_docs = []
            if screening.matched_documents_list:
                docs = MedicalDocument.query.filter(
                    MedicalDocument.id.in_(screening.matched_documents_list)
                ).all()
                
                for doc in docs:
                    matched_docs.append({
                        'id': doc.id,
                        'filename': doc.filename,
                        'document_date': doc.document_date.strftime('%m/%d/%Y') if doc.document_date else 'Unknown',
                        'document_type': doc.document_type,
                        'confidence': doc.ocr_confidence,
                        'url': f'/document/{doc.id}'  # URL for viewing document
                    })
            
            screening_info = {
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'last_completed_date': screening.last_completed_date.strftime('%m/%d/%Y') if screening.last_completed_date else 'N/A',
                'frequency': f"{screening.screening_type.frequency_number} {screening.screening_type.frequency_unit}",
                'next_due_date': screening.next_due_date.strftime('%m/%d/%Y') if screening.next_due_date else 'N/A',
                'matched_documents': matched_docs,
                'screening_id': screening.id
            }
            
            screening_list.append(screening_info)
        
        # Calculate summary statistics
        status_counts = {'Complete': 0, 'Due': 0, 'Due Soon': 0}
        for screening in screening_list:
            status = screening['status']
            if status in status_counts:
                status_counts[status] += 1
        
        return {
            'screenings': screening_list,
            'summary': {
                'total_screenings': len(screening_list),
                'complete': status_counts['Complete'],
                'due': status_counts['Due'],
                'due_soon': status_counts['Due Soon'],
                'completion_rate': round(status_counts['Complete'] / len(screening_list) * 100, 1) if screening_list else 0
            }
        }
    
    def _generate_enhanced_medical_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate enhanced medical data with document integration"""
        
        # This provides clickable document links organized by medical data type
        # Filter documents based on screening frequency cycles
        
        enhanced_data = {
            'laboratories': self._get_enhanced_lab_data(patient, settings),
            'imaging': self._get_enhanced_imaging_data(patient, settings),
            'consults': self._get_enhanced_consult_data(patient, settings),
            'hospital_visits': self._get_enhanced_hospital_data(patient, settings)
        }
        
        return enhanced_data
    
    def _get_enhanced_lab_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Get enhanced laboratory data with document links"""
        
        cutoff_date = datetime.utcnow() - relativedelta(months=settings.lab_cutoff_months)
        
        lab_documents = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='lab').all(),
            cutoff_date.date()
        )
        
        # Group by common lab types
        lab_groups = {
            'chemistry': [],
            'hematology': [],
            'lipids': [],
            'diabetes': [],
            'other': []
        }
        
        for doc in lab_documents:
            # Categorize based on filename/content
            filename_lower = doc.filename.lower()
            if any(term in filename_lower for term in ['chem', 'basic', 'comprehensive']):
                lab_groups['chemistry'].append(doc)
            elif any(term in filename_lower for term in ['cbc', 'hemoglobin', 'hematocrit']):
                lab_groups['hematology'].append(doc)
            elif any(term in filename_lower for term in ['lipid', 'cholesterol', 'hdl', 'ldl']):
                lab_groups['lipids'].append(doc)
            elif any(term in filename_lower for term in ['a1c', 'glucose', 'diabetes']):
                lab_groups['diabetes'].append(doc)
            else:
                lab_groups['other'].append(doc)
        
        # Format for display
        formatted_groups = {}
        for group_name, docs in lab_groups.items():
            if docs:  # Only include groups with documents
                formatted_groups[group_name] = self._format_medical_documents(docs, 'lab')
        
        return {
            'grouped_labs': formatted_groups,
            'total_count': len(lab_documents),
            'period': f'Last {settings.lab_cutoff_months} months'
        }
    
    def _get_enhanced_imaging_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Get enhanced imaging data with document links"""
        
        cutoff_date = datetime.utcnow() - relativedelta(months=settings.imaging_cutoff_months)
        
        imaging_documents = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='imaging').all(),
            cutoff_date.date()
        )
        
        return {
            'imaging_studies': self._format_medical_documents(imaging_documents, 'imaging'),
            'total_count': len(imaging_documents),
            'period': f'Last {settings.imaging_cutoff_months} months'
        }
    
    def _get_enhanced_consult_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Get enhanced consultation data with document links"""
        
        cutoff_date = datetime.utcnow() - relativedelta(months=settings.consult_cutoff_months)
        
        consult_documents = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='consult').all(),
            cutoff_date.date()
        )
        
        return {
            'specialist_consults': self._format_medical_documents(consult_documents, 'consult'),
            'total_count': len(consult_documents),
            'period': f'Last {settings.consult_cutoff_months} months'
        }
    
    def _get_enhanced_hospital_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Get enhanced hospital data with document links"""
        
        cutoff_date = datetime.utcnow() - relativedelta(months=settings.hospital_cutoff_months)
        
        hospital_documents = self.filters.filter_documents_by_date(
            patient.documents.filter_by(document_type='hospital').all(),
            cutoff_date.date()
        )
        
        return {
            'hospital_records': self._format_medical_documents(hospital_documents, 'hospital'),
            'total_count': len(hospital_documents),
            'period': f'Last {settings.hospital_cutoff_months} months'
        }
    
    def _format_medical_documents(self, documents: List[MedicalDocument], doc_type: str) -> List[Dict[str, Any]]:
        """Format medical documents for display"""
        
        formatted_docs = []
        
        for doc in documents:
            doc_info = {
                'id': doc.id,
                'filename': doc.filename,
                'document_date': doc.document_date.strftime('%m/%d/%Y') if doc.document_date else 'Unknown',
                'upload_date': doc.upload_date.strftime('%m/%d/%Y'),
                'document_type': doc.document_type,
                'ocr_confidence': doc.ocr_confidence,
                'confidence_level': self._get_confidence_level(doc.ocr_confidence),
                'url': f'/document/{doc.id}',
                'has_ocr': doc.ocr_processed,
                'text_preview': self._get_text_preview(doc.ocr_text) if doc.ocr_text else None
            }
            
            formatted_docs.append(doc_info)
        
        # Sort by document date (most recent first)
        formatted_docs.sort(key=lambda x: x['document_date'], reverse=True)
        
        return formatted_docs
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level for OCR quality"""
        if not confidence:
            return 'unknown'
        elif confidence >= 0.85:
            return 'high'
        elif confidence >= 0.70:
            return 'medium'
        else:
            return 'low'
    
    def _get_text_preview(self, text: str, max_length: int = 150) -> str:
        """Get a preview of document text"""
        if not text:
            return ""
        
        # Clean up text and get preview
        cleaned_text = ' '.join(text.split())  # Remove extra whitespace
        
        if len(cleaned_text) <= max_length:
            return cleaned_text
        else:
            return cleaned_text[:max_length] + "..."
    
    def generate_batch_prep_sheets(self, patient_ids: List[int], appointment_date: datetime = None) -> Dict[str, Any]:
        """
        Generate prep sheets for multiple patients in batch
        """
        logger.info(f"Generating batch prep sheets for {len(patient_ids)} patients")
        
        if not appointment_date:
            appointment_date = datetime.utcnow()
        
        results = {
            'prep_sheets': [],
            'successful': 0,
            'failed': 0,
            'errors': [],
            'generated_at': datetime.utcnow().isoformat()
        }
        
        for patient_id in patient_ids:
            try:
                patient = Patient.query.get(patient_id)
                if not patient:
                    results['errors'].append(f"Patient ID {patient_id} not found")
                    results['failed'] += 1
                    continue
                
                prep_sheet = self.generate_prep_sheet(patient, appointment_date)
                prep_sheet['patient_id'] = patient_id
                
                results['prep_sheets'].append(prep_sheet)
                results['successful'] += 1
                
            except Exception as e:
                logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
                results['errors'].append(f"Patient ID {patient_id}: {str(e)}")
                results['failed'] += 1
        
        logger.info(f"Batch prep sheet generation complete: {results['successful']} successful, {results['failed']} failed")
        return results

