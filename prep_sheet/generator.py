"""
Prep sheet generation and rendering
Assembles patient data into formatted prep sheets
"""

import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Any, Optional
from jinja2 import Template

from models import Patient, Screening, MedicalDocument, PatientCondition, ChecklistSettings
from prep_sheet.filters import PrepSheetFilters
from app import db

logger = logging.getLogger(__name__)

class PrepSheetGenerator:
    """Generates formatted prep sheets for patient visits"""
    
    def __init__(self):
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id: int, custom_settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate a complete prep sheet for a patient
        """
        try:
            # Get patient data
            patient = Patient.query.get(patient_id)
            if not patient:
                return {'error': 'Patient not found'}
            
            # Get settings
            settings = self._get_prep_sheet_settings(custom_settings)
            
            # Gather all prep sheet data
            prep_data = {
                'patient_header': self._generate_patient_header(patient),
                'patient_summary': self._generate_patient_summary(patient, settings),
                'medical_data': self._generate_medical_data(patient, settings),
                'quality_checklist': self._generate_quality_checklist(patient, settings),
                'enhanced_data': self._generate_enhanced_data(patient, settings),
                'generated_at': datetime.now(),
                'settings': settings
            }
            
            return {
                'success': True,
                'patient_id': patient_id,
                'prep_data': prep_data
            }
            
        except Exception as e:
            logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
            return {'error': str(e)}
    
    def _generate_patient_header(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient header information"""
        age = None
        if patient.date_of_birth:
            today = date.today()
            age = today.year - patient.date_of_birth.year
            if today < date(today.year, patient.date_of_birth.month, patient.date_of_birth.day):
                age -= 1
        
        # Get last visit (most recent document date as proxy)
        last_visit = None
        latest_doc = MedicalDocument.query.filter_by(patient_id=patient.id)\
            .filter(MedicalDocument.date_created.isnot(None))\
            .order_by(MedicalDocument.date_created.desc()).first()
        if latest_doc:
            last_visit = latest_doc.date_created
        
        return {
            'name': patient.name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth,
            'age': age,
            'gender': self._format_gender(patient.gender),
            'prep_date': date.today(),
            'last_visit': last_visit
        }
    
    def _generate_patient_summary(self, patient: Patient, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate patient summary section"""
        # Get recent appointments (using documents as proxy for visits)
        recent_visits = MedicalDocument.query.filter_by(patient_id=patient.id)\
            .filter(MedicalDocument.date_created >= self.filters.get_cutoff_date(12, 'months'))\
            .order_by(MedicalDocument.date_created.desc()).limit(5).all()
        
        visit_history = []
        for doc in recent_visits:
            visit_history.append({
                'date': doc.date_created,
                'type': doc.document_type.title(),
                'description': doc.filename or 'Medical Visit'
            })
        
        # Get active conditions
        active_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).order_by(PatientCondition.onset_date.desc()).all()
        
        conditions_list = []
        for condition in active_conditions:
            conditions_list.append({
                'name': condition.condition_name,
                'onset_date': condition.onset_date,
                'code': condition.condition_code
            })
        
        return {
            'recent_visits': visit_history,
            'active_conditions': conditions_list,
            'total_visits_period': len(recent_visits),
            'total_active_conditions': len(conditions_list)
        }
    
    def _generate_medical_data(self, patient: Patient, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recent medical data sections"""
        cutoff_dates = {
            'lab': self.filters.get_cutoff_date(settings.get('lab_cutoff_months', 12), 'months'),
            'imaging': self.filters.get_cutoff_date(settings.get('imaging_cutoff_months', 24), 'months'),
            'consult': self.filters.get_cutoff_date(settings.get('consult_cutoff_months', 12), 'months'),
            'hospital': self.filters.get_cutoff_date(settings.get('hospital_cutoff_months', 24), 'months')
        }
        
        medical_data = {}
        
        for data_type, cutoff_date in cutoff_dates.items():
            documents = MedicalDocument.query.filter_by(
                patient_id=patient.id,
                document_type=data_type
            ).filter(
                MedicalDocument.date_created >= cutoff_date
            ).order_by(MedicalDocument.date_created.desc()).all()
            
            formatted_docs = []
            for doc in documents:
                formatted_docs.append({
                    'id': doc.id,
                    'filename': doc.filename,
                    'date': doc.date_created,
                    'confidence': doc.ocr_confidence,
                    'has_ocr': doc.ocr_text is not None,
                    'summary': self._generate_document_summary(doc)
                })
            
            medical_data[data_type] = {
                'documents': formatted_docs,
                'count': len(formatted_docs),
                'cutoff_date': cutoff_date,
                'period_months': settings.get(f'{data_type}_cutoff_months', 12)
            }
        
        return medical_data
    
    def _generate_quality_checklist(self, patient: Patient, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quality checklist section with screening status"""
        screenings = Screening.query.filter_by(patient_id=patient.id)\
            .join(Screening.screening_type)\
            .filter_by(is_active=True)\
            .order_by(Screening.status, Screening.next_due_date).all()
        
        screening_list = []
        status_counts = {'Due': 0, 'Due Soon': 0, 'Complete': 0}
        
        for screening in screenings:
            # Get matched documents
            matched_docs = []
            if screening.matched_documents:
                docs = MedicalDocument.query.filter(
                    MedicalDocument.id.in_(screening.matched_documents)
                ).all()
                
                for doc in docs:
                    matched_docs.append({
                        'id': doc.id,
                        'filename': doc.filename,
                        'date': doc.date_created,
                        'confidence': doc.ocr_confidence
                    })
            
            screening_item = {
                'id': screening.id,
                'name': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed_date,
                'next_due': screening.next_due_date,
                'frequency': self._format_frequency(screening.screening_type),
                'matched_documents': matched_docs,
                'overdue_days': self._calculate_overdue_days(screening.next_due_date)
            }
            
            screening_list.append(screening_item)
            status_counts[screening.status] = status_counts.get(screening.status, 0) + 1
        
        return {
            'screenings': screening_list,
            'status_summary': status_counts,
            'total_screenings': len(screening_list),
            'compliance_rate': self._calculate_compliance_rate(status_counts)
        }
    
    def _generate_enhanced_data(self, patient: Patient, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate enhanced medical data with document integration"""
        # This section shows documents filtered by current screening cycles
        enhanced_data = {}
        
        # Get all active screenings
        screenings = Screening.query.filter_by(patient_id=patient.id)\
            .join(Screening.screening_type)\
            .filter_by(is_active=True).all()
        
        # Group documents by screening relevance
        for screening in screenings:
            if not screening.matched_documents:
                continue
            
            relevant_docs = MedicalDocument.query.filter(
                MedicalDocument.id.in_(screening.matched_documents)
            ).filter(
                self.filters.is_document_current(screening.screening_type)
            ).all()
            
            if relevant_docs:
                if screening.screening_type.name not in enhanced_data:
                    enhanced_data[screening.screening_type.name] = []
                
                for doc in relevant_docs:
                    enhanced_data[screening.screening_type.name].append({
                        'id': doc.id,
                        'filename': doc.filename,
                        'date': doc.date_created,
                        'type': doc.document_type,
                        'confidence': doc.ocr_confidence,
                        'is_recent': self.filters.is_document_recent(doc, 6)
                    })
        
        return enhanced_data
    
    def _get_prep_sheet_settings(self, custom_settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get prep sheet generation settings"""
        # Get default settings from database
        db_settings = ChecklistSettings.query.first()
        
        default_settings = {
            'lab_cutoff_months': 12,
            'imaging_cutoff_months': 24,
            'consult_cutoff_months': 12,
            'hospital_cutoff_months': 24,
            'default_items': []
        }
        
        if db_settings:
            default_settings.update({
                'lab_cutoff_months': db_settings.lab_cutoff_months,
                'imaging_cutoff_months': db_settings.imaging_cutoff_months,
                'consult_cutoff_months': db_settings.consult_cutoff_months,
                'hospital_cutoff_months': db_settings.hospital_cutoff_months,
                'default_items': db_settings.default_items or []
            })
        
        # Override with custom settings if provided
        if custom_settings:
            default_settings.update(custom_settings)
        
        return default_settings
    
    def _format_gender(self, gender: str) -> str:
        """Format gender for display"""
        if not gender:
            return 'Unknown'
        
        gender_map = {
            'M': 'Male',
            'F': 'Female',
            'O': 'Other'
        }
        
        return gender_map.get(gender.upper(), gender)
    
    def _format_frequency(self, screening_type) -> str:
        """Format screening frequency for display"""
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return 'As needed'
        
        unit = screening_type.frequency_unit
        number = screening_type.frequency_number
        
        if number == 1:
            return f"Every {unit[:-1]}"  # Remove 's' from plural
        else:
            return f"Every {number} {unit}"
    
    def _calculate_overdue_days(self, next_due_date: Optional[date]) -> Optional[int]:
        """Calculate how many days a screening is overdue"""
        if not next_due_date:
            return None
        
        today = date.today()
        if next_due_date < today:
            return (today - next_due_date).days
        
        return None
    
    def _calculate_compliance_rate(self, status_counts: Dict[str, int]) -> float:
        """Calculate overall compliance rate"""
        total = sum(status_counts.values())
        if total == 0:
            return 0.0
        
        compliant = status_counts.get('Complete', 0)
        return round((compliant / total) * 100, 1)
    
    def _generate_document_summary(self, document: MedicalDocument) -> str:
        """Generate a brief summary of document content"""
        if document.ocr_text:
            # Extract first meaningful sentence or important info
            text = document.ocr_text.strip()
            sentences = text.split('.')[:2]  # First two sentences
            summary = '. '.join(sentences)
            
            if len(summary) > 150:
                summary = summary[:147] + '...'
            
            return summary
        
        return f"{document.document_type.title()} document from {document.date_created}"
    
    def export_prep_sheet_pdf(self, patient_id: int) -> bytes:
        """Export prep sheet as PDF (placeholder for future implementation)"""
        # This would integrate with a PDF generation library like ReportLab
        prep_data = self.generate_prep_sheet(patient_id)
        
        if not prep_data.get('success'):
            raise ValueError("Failed to generate prep sheet data")
        
        # For now, return empty bytes - PDF generation would be implemented here
        logger.warning("PDF export not yet implemented")
        return b''
    
    def get_prep_sheet_template_data(self, patient_id: int) -> Dict[str, Any]:
        """Get template-ready data for prep sheet rendering"""
        prep_data = self.generate_prep_sheet(patient_id)
        
        if not prep_data.get('success'):
            return {'error': prep_data.get('error', 'Unknown error')}
        
        return prep_data['prep_data']
