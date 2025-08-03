"""
Assembles content into prep sheet format
Generates comprehensive medical preparation sheets for patient visits
"""

from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, or_
from app import db
from models import Patient, Screening, MedicalDocument, Visit, Condition, ChecklistSettings
from prep_sheet.filters import PrepSheetFilters
import logging

class PrepSheetGenerator:
    """Generates comprehensive prep sheets for patient visits"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient):
        """Generate a complete prep sheet for a patient"""
        try:
            self.logger.info(f"Generating prep sheet for patient {patient.mrn}")
            
            # Get checklist settings
            settings = ChecklistSettings.query.filter_by(is_active=True).first()
            if not settings:
                settings = self._get_default_settings()
            
            prep_data = {
                'patient': self._get_patient_header(patient),
                'summary': self._get_patient_summary(patient),
                'medical_data': self._get_medical_data(patient, settings),
                'quality_checklist': self._get_quality_checklist(patient),
                'generation_info': {
                    'generated_at': datetime.utcnow(),
                    'settings_used': settings.name if settings else 'Default',
                    'total_screenings': Screening.query.filter_by(patient_id=patient.id).count(),
                    'total_documents': MedicalDocument.query.filter_by(patient_id=patient.id).count()
                }
            }
            
            self.logger.info(f"Successfully generated prep sheet for patient {patient.mrn}")
            return prep_data
            
        except Exception as e:
            self.logger.error(f"Error generating prep sheet for patient {patient.mrn}: {str(e)}")
            raise
    
    def _get_patient_header(self, patient):
        """Generate patient header information"""
        # Get last visit
        last_visit = Visit.query.filter_by(patient_id=patient.id).order_by(Visit.visit_date.desc()).first()
        
        return {
            'name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth,
            'age': patient.age,
            'gender': patient.gender,
            'phone': patient.phone,
            'email': patient.email,
            'address': patient.address,
            'primary_physician': patient.primary_physician,
            'last_visit_date': last_visit.visit_date if last_visit else None,
            'prep_date': date.today()
        }
    
    def _get_patient_summary(self, patient):
        """Generate patient summary section"""
        # Recent visits
        recent_visits = Visit.query.filter_by(patient_id=patient.id).order_by(
            Visit.visit_date.desc()
        ).limit(5).all()
        
        # Active conditions
        active_conditions = Condition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).order_by(Condition.diagnosis_date.desc()).all()
        
        return {
            'recent_visits': [
                {
                    'date': visit.visit_date,
                    'type': visit.visit_type,
                    'provider': visit.provider,
                    'chief_complaint': visit.chief_complaint,
                    'diagnosis': visit.diagnosis
                }
                for visit in recent_visits
            ],
            'active_conditions': [
                {
                    'name': condition.condition_name,
                    'diagnosis_date': condition.diagnosis_date,
                    'icd10_code': condition.icd10_code,
                    'status': condition.status,
                    'severity': condition.severity
                }
                for condition in active_conditions
            ]
        }
    
    def _get_medical_data(self, patient, settings):
        """Get filtered medical data based on cutoff settings"""
        # Calculate cutoff dates
        cutoff_dates = {
            'labs': date.today() - relativedelta(months=settings.lab_cutoff_months),
            'imaging': date.today() - relativedelta(months=settings.imaging_cutoff_months),
            'consults': date.today() - relativedelta(months=settings.consult_cutoff_months),
            'hospital': date.today() - relativedelta(months=settings.hospital_cutoff_months)
        }
        
        medical_data = {}
        
        # Get documents by type within cutoff periods
        for doc_type, cutoff_date in cutoff_dates.items():
            documents = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.patient_id == patient.id,
                    MedicalDocument.document_type == doc_type.rstrip('s'),  # Remove 's' from plural
                    MedicalDocument.document_date >= cutoff_date,
                    MedicalDocument.is_processed == True
                )
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            medical_data[doc_type] = [
                {
                    'id': doc.id,
                    'filename': doc.filename,
                    'document_date': doc.document_date,
                    'document_type': doc.document_type,
                    'content_summary': doc.content_summary,
                    'ocr_confidence': doc.ocr_confidence,
                    'keywords_matched': doc.keywords_matched or []
                }
                for doc in documents
            ]
        
        return medical_data
    
    def _get_quality_checklist(self, patient):
        """Generate quality checklist with screening information"""
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        checklist_items = []
        
        for screening in screenings:
            # Get matched documents for this screening
            matched_docs = []
            if screening.matched_documents:
                doc_ids = screening.matched_documents
                matched_docs = MedicalDocument.query.filter(
                    MedicalDocument.id.in_(doc_ids)
                ).order_by(MedicalDocument.document_date.desc()).all()
            
            # Determine status color and priority
            status_info = self._get_status_info(screening.status)
            
            checklist_item = {
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'status_color': status_info['color'],
                'priority': status_info['priority'],
                'last_completed_date': screening.last_completed_date,
                'next_due_date': screening.next_due_date,
                'frequency': self._format_frequency(screening.screening_type),
                'matched_documents': [
                    {
                        'id': doc.id,
                        'filename': doc.filename,
                        'document_date': doc.document_date,
                        'confidence': doc.ocr_confidence,
                        'confidence_level': self._get_confidence_level(doc.ocr_confidence)
                    }
                    for doc in matched_docs
                ],
                'recommendations': self._get_screening_recommendations(screening)
            }
            
            checklist_items.append(checklist_item)
        
        # Sort by priority and status
        checklist_items.sort(key=lambda x: (x['priority'], x['screening_name']))
        
        return {
            'items': checklist_items,
            'summary': self._get_checklist_summary(checklist_items)
        }
    
    def _get_status_info(self, status):
        """Get status color and priority for screening status"""
        status_mapping = {
            'Overdue': {'color': 'danger', 'priority': 1},
            'Due': {'color': 'warning', 'priority': 2},
            'Due Soon': {'color': 'info', 'priority': 3},
            'Complete': {'color': 'success', 'priority': 4}
        }
        
        return status_mapping.get(status, {'color': 'secondary', 'priority': 5})
    
    def _format_frequency(self, screening_type):
        """Format screening frequency for display"""
        frequency_parts = []
        
        if screening_type.frequency_years:
            frequency_parts.append(f"{screening_type.frequency_years} year{'s' if screening_type.frequency_years > 1 else ''}")
        
        if screening_type.frequency_months:
            frequency_parts.append(f"{screening_type.frequency_months} month{'s' if screening_type.frequency_months > 1 else ''}")
        
        return ' '.join(frequency_parts) if frequency_parts else 'Not specified'
    
    def _get_confidence_level(self, confidence):
        """Get confidence level category"""
        if confidence is None:
            return 'unknown'
        elif confidence >= 80:
            return 'high'
        elif confidence >= 60:
            return 'medium'
        else:
            return 'low'
    
    def _get_screening_recommendations(self, screening):
        """Get recommendations for a screening based on its status"""
        recommendations = []
        
        if screening.status == 'Overdue':
            recommendations.append('Schedule immediately - screening is overdue')
            recommendations.append('Review with patient during visit')
        elif screening.status == 'Due':
            recommendations.append('Schedule screening appointment')
            recommendations.append('Discuss importance with patient')
        elif screening.status == 'Due Soon':
            recommendations.append('Consider scheduling in next 30 days')
            recommendations.append('Mention upcoming need to patient')
        elif screening.status == 'Complete':
            if screening.next_due_date:
                recommendations.append(f'Next screening due: {screening.next_due_date.strftime("%m/%d/%Y")}')
        
        # Add specific recommendations based on screening type
        screening_specific = self._get_screening_specific_recommendations(screening)
        recommendations.extend(screening_specific)
        
        return recommendations
    
    def _get_screening_specific_recommendations(self, screening):
        """Get screening-type specific recommendations"""
        screening_name = screening.screening_type.name.lower()
        recommendations = []
        
        if 'mammogram' in screening_name:
            recommendations.append('Coordinate with radiology department')
            recommendations.append('Provide prep instructions if needed')
        elif 'colonoscopy' in screening_name:
            recommendations.append('Provide bowel prep instructions')
            recommendations.append('Schedule pre-procedure consultation')
        elif 'pap' in screening_name:
            recommendations.append('Schedule with appropriate provider')
            recommendations.append('Ensure patient preparation guidelines')
        elif 'a1c' in screening_name and screening.status in ['Due', 'Overdue']:
            recommendations.append('Can be done at this visit if lab available')
            recommendations.append('Review diabetes management')
        
        return recommendations
    
    def _get_checklist_summary(self, checklist_items):
        """Generate summary statistics for the checklist"""
        total_items = len(checklist_items)
        status_counts = {}
        
        for item in checklist_items:
            status = item['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        overdue_count = status_counts.get('Overdue', 0)
        due_count = status_counts.get('Due', 0)
        due_soon_count = status_counts.get('Due Soon', 0)
        complete_count = status_counts.get('Complete', 0)
        
        # Calculate compliance rate
        compliant_count = complete_count + due_soon_count
        compliance_rate = (compliant_count / total_items * 100) if total_items > 0 else 0
        
        return {
            'total_screenings': total_items,
            'overdue': overdue_count,
            'due': due_count,
            'due_soon': due_soon_count,
            'complete': complete_count,
            'compliance_rate': round(compliance_rate, 1),
            'needs_attention': overdue_count + due_count,
            'priority_actions': overdue_count > 0 or due_count > 0
        }
    
    def _get_default_settings(self):
        """Get default checklist settings"""
        from models import ChecklistSettings
        
        default_settings = ChecklistSettings(
            name='Default Settings',
            lab_cutoff_months=12,
            imaging_cutoff_months=24,
            consult_cutoff_months=12,
            hospital_cutoff_months=24
        )
        
        return default_settings
    
    def generate_batch_prep_sheets(self, patient_ids):
        """Generate prep sheets for multiple patients"""
        try:
            prep_sheets = {}
            success_count = 0
            error_count = 0
            
            for patient_id in patient_ids:
                try:
                    patient = Patient.query.get(patient_id)
                    if patient:
                        prep_data = self.generate_prep_sheet(patient)
                        prep_sheets[patient_id] = prep_data
                        success_count += 1
                    else:
                        prep_sheets[patient_id] = {'error': 'Patient not found'}
                        error_count += 1
                except Exception as e:
                    prep_sheets[patient_id] = {'error': str(e)}
                    error_count += 1
            
            self.logger.info(f"Batch prep sheet generation completed: {success_count} success, {error_count} errors")
            
            return {
                'prep_sheets': prep_sheets,
                'summary': {
                    'total_requested': len(patient_ids),
                    'successful': success_count,
                    'errors': error_count,
                    'generated_at': datetime.utcnow()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in batch prep sheet generation: {str(e)}")
            raise
    
    def export_prep_sheet_pdf(self, patient_id):
        """Export prep sheet as PDF (placeholder for future implementation)"""
        # This would integrate with a PDF generation library like ReportLab
        # For now, return the data that would be used for PDF generation
        
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        
        prep_data = self.generate_prep_sheet(patient)
        
        return {
            'format': 'pdf_data',
            'patient_mrn': patient.mrn,
            'prep_data': prep_data,
            'export_timestamp': datetime.utcnow(),
            'note': 'PDF generation would be implemented here'
        }
