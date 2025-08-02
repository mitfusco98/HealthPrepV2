"""
Assembles content into prep sheet format
"""
import json
import logging
from datetime import datetime, date, timedelta
from models import Patient, Screening, MedicalDocument, ScreeningType
from prep_sheet.filters import apply_cutoff_filters
from app import db

class PrepSheetGenerator:
    
    def generate_for_patient(self, patient, settings):
        """Generate comprehensive prep sheet data for a patient"""
        try:
            prep_data = {
                'patient_info': self._get_patient_info(patient),
                'screening_checklist': self._get_screening_checklist(patient),
                'medical_data': self._get_medical_data(patient, settings),
                'visit_summary': self._get_visit_summary(patient),
                'generated_date': datetime.utcnow().isoformat()
            }
            
            return json.dumps(prep_data, indent=2)
            
        except Exception as e:
            logging.error(f"Error generating prep sheet for patient {patient.id}: {e}")
            return json.dumps({'error': str(e)})
    
    def _get_patient_info(self, patient):
        """Get patient header information"""
        return {
            'name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth.isoformat(),
            'age': patient.age,
            'gender': patient.gender,
            'last_visit': self._get_last_visit_date(patient)
        }
    
    def _get_screening_checklist(self, patient):
        """Get screening status checklist"""
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        checklist = []
        for screening in screenings:
            if screening.screening_type.is_active:
                # Get matched documents
                matched_docs = []
                if screening.matched_documents:
                    try:
                        doc_ids = json.loads(screening.matched_documents)
                        matched_docs = MedicalDocument.query.filter(
                            MedicalDocument.id.in_(doc_ids)
                        ).all()
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                checklist_item = {
                    'screening_name': screening.screening_type.name,
                    'status': screening.status,
                    'last_completed': screening.last_completed_date.isoformat() if screening.last_completed_date else None,
                    'frequency': f"Every {screening.screening_type.frequency_value} {screening.screening_type.frequency_unit}",
                    'matched_documents': [
                        {
                            'id': doc.id,
                            'filename': doc.filename,
                            'date': doc.upload_date.strftime('%Y-%m-%d'),
                            'confidence': doc.ocr_confidence or 0.0
                        }
                        for doc in matched_docs
                    ]
                }
                checklist.append(checklist_item)
        
        return sorted(checklist, key=lambda x: x['screening_name'])
    
    def _get_medical_data(self, patient, settings):
        """Get recent medical data organized by type"""
        medical_data = {
            'laboratories': self._get_lab_data(patient, settings.lab_cutoff_months),
            'imaging': self._get_imaging_data(patient, settings.imaging_cutoff_months),
            'consults': self._get_consult_data(patient, settings.consult_cutoff_months),
            'hospital_visits': self._get_hospital_data(patient, settings.hospital_cutoff_months)
        }
        
        return medical_data
    
    def _get_lab_data(self, patient, cutoff_months):
        """Get laboratory data within cutoff period"""
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        lab_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'lab',
            MedicalDocument.upload_date >= cutoff_date
        ).order_by(MedicalDocument.upload_date.desc()).all()
        
        return [
            {
                'id': doc.id,
                'filename': doc.filename,
                'date': doc.upload_date.strftime('%Y-%m-%d'),
                'confidence': doc.ocr_confidence or 0.0,
                'preview': self._get_text_preview(doc.ocr_text)
            }
            for doc in lab_docs
        ]
    
    def _get_imaging_data(self, patient, cutoff_months):
        """Get imaging data within cutoff period"""
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        imaging_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'imaging',
            MedicalDocument.upload_date >= cutoff_date
        ).order_by(MedicalDocument.upload_date.desc()).all()
        
        return [
            {
                'id': doc.id,
                'filename': doc.filename,
                'date': doc.upload_date.strftime('%Y-%m-%d'),
                'confidence': doc.ocr_confidence or 0.0,
                'preview': self._get_text_preview(doc.ocr_text)
            }
            for doc in imaging_docs
        ]
    
    def _get_consult_data(self, patient, cutoff_months):
        """Get consultation data within cutoff period"""
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        consult_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'consult',
            MedicalDocument.upload_date >= cutoff_date
        ).order_by(MedicalDocument.upload_date.desc()).all()
        
        return [
            {
                'id': doc.id,
                'filename': doc.filename,
                'date': doc.upload_date.strftime('%Y-%m-%d'),
                'confidence': doc.ocr_confidence or 0.0,
                'preview': self._get_text_preview(doc.ocr_text)
            }
            for doc in consult_docs
        ]
    
    def _get_hospital_data(self, patient, cutoff_months):
        """Get hospital visit data within cutoff period"""
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        hospital_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'hospital',
            MedicalDocument.upload_date >= cutoff_date
        ).order_by(MedicalDocument.upload_date.desc()).all()
        
        return [
            {
                'id': doc.id,
                'filename': doc.filename,
                'date': doc.upload_date.strftime('%Y-%m-%d'),
                'confidence': doc.ocr_confidence or 0.0,
                'preview': self._get_text_preview(doc.ocr_text)
            }
            for doc in hospital_docs
        ]
    
    def _get_visit_summary(self, patient):
        """Get recent visit summary"""
        # This would integrate with appointment system
        # For now, return basic info
        return {
            'upcoming_appointments': [],
            'recent_visits': [],
            'active_conditions': []
        }
    
    def _get_last_visit_date(self, patient):
        """Get patient's last visit date"""
        # This would come from appointment/visit system
        # For now, return None
        return None
    
    def _get_text_preview(self, text, max_length=200):
        """Get preview of OCR text"""
        if not text:
            return ""
        
        preview = text.strip()
        if len(preview) > max_length:
            preview = preview[:max_length] + "..."
        
        return preview
    
    def generate_summary_stats(self, patient):
        """Generate summary statistics for prep sheet"""
        try:
            total_screenings = Screening.query.filter_by(patient_id=patient.id).count()
            due_screenings = Screening.query.filter_by(
                patient_id=patient.id, 
                status='Due'
            ).count()
            complete_screenings = Screening.query.filter_by(
                patient_id=patient.id,
                status='Complete'
            ).count()
            
            total_documents = MedicalDocument.query.filter_by(patient_id=patient.id).count()
            
            return {
                'total_screenings': total_screenings,
                'due_screenings': due_screenings,
                'complete_screenings': complete_screenings,
                'compliance_rate': (complete_screenings / total_screenings * 100) if total_screenings > 0 else 0,
                'total_documents': total_documents
            }
            
        except Exception as e:
            logging.error(f"Error generating summary stats: {e}")
            return {}
