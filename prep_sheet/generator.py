"""
Prep sheet generation and rendering engine
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from app import db
from models import Patient, Screening, MedicalDocument, PatientCondition, ChecklistSettings
from emr.models import PrepSheetData, PatientInfo, ScreeningResult, DocumentInfo, ConditionInfo
from core.engine import screening_engine
from prep_sheet.filters import PrepSheetFilters

logger = logging.getLogger(__name__)

class PrepSheetGenerator:
    """Generates comprehensive prep sheets for patient visits"""
    
    def __init__(self):
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id: int) -> Dict[str, Any]:
        """
        Generate complete prep sheet for a patient
        """
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                logger.error(f"Patient {patient_id} not found")
                return {
                    'success': False,
                    'error': 'Patient not found'
                }
            
            logger.info(f"Generating prep sheet for patient {patient.full_name} (ID: {patient_id})")
            
            # Get checklist settings for data cutoffs
            settings = self._get_checklist_settings()
            
            # Build prep sheet data
            prep_data = PrepSheetData()
            prep_data.patient = self._build_patient_info(patient)
            prep_data.prep_date = date.today()
            
            # Get recent medical data
            prep_data.recent_labs = self._get_recent_labs(patient, settings)
            prep_data.recent_imaging = self._get_recent_imaging(patient, settings)
            prep_data.recent_consults = self._get_recent_consults(patient, settings)
            prep_data.recent_hospital_stays = self._get_recent_hospital_stays(patient, settings)
            
            # Get screening checklist
            prep_data.screenings = self._get_screening_checklist(patient)
            
            # Get active conditions
            prep_data.active_conditions = self._get_active_conditions(patient)
            
            # Get document summaries
            prep_data.lab_documents = self._get_lab_documents(patient, settings)
            prep_data.imaging_documents = self._get_imaging_documents(patient, settings)
            prep_data.consult_documents = self._get_consult_documents(patient, settings)
            prep_data.hospital_documents = self._get_hospital_documents(patient, settings)
            
            return {
                'success': True,
                'prep_data': prep_data,
                'patient_id': patient_id,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_patient_info(self, patient: Patient) -> PatientInfo:
        """Build patient information section"""
        return PatientInfo(
            mrn=patient.mrn,
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            phone=patient.phone,
            email=patient.email
        )
    
    def _get_screening_checklist(self, patient: Patient) -> List[ScreeningResult]:
        """Get screening checklist for patient"""
        try:
            # Run screening engine for this patient
            screening_results = screening_engine.process_patient_screenings(patient.id)
            
            checklist = []
            for result in screening_results:
                screening_result = ScreeningResult(
                    screening_id=result.get('screening_id'),
                    patient_name=patient.full_name,
                    screening_type=result.get('screening_type', ''),
                    status=result.get('status', 'Due'),
                    last_completed_date=result.get('last_completed_date'),
                    next_due_date=result.get('next_due_date'),
                    frequency=result.get('frequency', ''),
                    matched_documents=[
                        self._convert_to_document_info(doc) 
                        for doc in result.get('matched_documents', [])
                    ],
                    eligibility_met=result.get('eligibility_met', True)
                )
                checklist.append(screening_result)
            
            # Sort by urgency (Due first, then Due Soon, then Complete)
            status_priority = {'Due': 0, 'Due Soon': 1, 'Complete': 2}
            checklist.sort(key=lambda x: status_priority.get(x.status, 3))
            
            return checklist
            
        except Exception as e:
            logger.error(f"Error getting screening checklist for patient {patient.id}: {str(e)}")
            return []
    
    def _get_recent_labs(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get recent lab results"""
        cutoff_date = self.filters.calculate_cutoff_date(settings.labs_cutoff_months)
        
        lab_documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'lab',
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).limit(10).all()
        
        return [self._convert_to_document_info(doc) for doc in lab_documents]
    
    def _get_recent_imaging(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get recent imaging studies"""
        cutoff_date = self.filters.calculate_cutoff_date(settings.imaging_cutoff_months)
        
        imaging_documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'imaging',
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).limit(10).all()
        
        return [self._convert_to_document_info(doc) for doc in imaging_documents]
    
    def _get_recent_consults(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get recent consultant reports"""
        cutoff_date = self.filters.calculate_cutoff_date(settings.consults_cutoff_months)
        
        consult_documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'consult',
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).limit(10).all()
        
        return [self._convert_to_document_info(doc) for doc in consult_documents]
    
    def _get_recent_hospital_stays(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get recent hospital stays"""
        cutoff_date = self.filters.calculate_cutoff_date(settings.hospital_cutoff_months)
        
        hospital_documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == 'hospital',
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).limit(5).all()
        
        return [self._convert_to_document_info(doc) for doc in hospital_documents]
    
    def _get_active_conditions(self, patient: Patient) -> List[ConditionInfo]:
        """Get active medical conditions"""
        conditions = PatientCondition.query.filter(
            PatientCondition.patient_id == patient.id,
            PatientCondition.is_active == True
        ).order_by(PatientCondition.diagnosis_date.desc()).all()
        
        condition_list = []
        for condition in conditions:
            condition_info = ConditionInfo(
                condition_code=condition.condition_code,
                condition_name=condition.condition_name,
                diagnosis_date=condition.diagnosis_date,
                is_active=condition.is_active
            )
            condition_list.append(condition_info)
        
        return condition_list
    
    def _get_lab_documents(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get lab documents with filtering"""
        return self._get_documents_by_type(patient, 'lab', settings.labs_cutoff_months)
    
    def _get_imaging_documents(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get imaging documents with filtering"""
        return self._get_documents_by_type(patient, 'imaging', settings.imaging_cutoff_months)
    
    def _get_consult_documents(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get consult documents with filtering"""
        return self._get_documents_by_type(patient, 'consult', settings.consults_cutoff_months)
    
    def _get_hospital_documents(self, patient: Patient, settings: ChecklistSettings) -> List[DocumentInfo]:
        """Get hospital documents with filtering"""
        return self._get_documents_by_type(patient, 'hospital', settings.hospital_cutoff_months)
    
    def _get_documents_by_type(self, patient: Patient, doc_type: str, cutoff_months: int) -> List[DocumentInfo]:
        """Get documents by type with date filtering"""
        cutoff_date = self.filters.calculate_cutoff_date(cutoff_months)
        
        documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == doc_type,
            MedicalDocument.document_date >= cutoff_date
        ).order_by(MedicalDocument.document_date.desc()).all()
        
        return [self._convert_to_document_info(doc) for doc in documents]
    
    def _convert_to_document_info(self, document: MedicalDocument) -> DocumentInfo:
        """Convert MedicalDocument to DocumentInfo"""
        return DocumentInfo(
            fhir_id=str(document.id),
            filename=document.filename,
            document_type=document.document_type or 'other',
            document_date=document.document_date,
            description=document.ocr_text[:100] + '...' if document.ocr_text and len(document.ocr_text) > 100 else document.ocr_text or '',
            file_path=document.file_path or '',
            ocr_text=document.ocr_text or '',
            ocr_confidence=document.ocr_confidence or 0.0,
            phi_filtered=document.phi_filtered or False
        )
    
    def _get_checklist_settings(self) -> ChecklistSettings:
        """Get current checklist settings"""
        settings = ChecklistSettings.query.first()
        if not settings:
            # Create default settings
            settings = ChecklistSettings(
                labs_cutoff_months=12,
                imaging_cutoff_months=24,
                consults_cutoff_months=12,
                hospital_cutoff_months=12,
                show_confidence_indicators=True,
                phi_filtering_enabled=True
            )
            db.session.add(settings)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating default checklist settings: {str(e)}")
        
        return settings
    
    def generate_summary_stats(self, prep_data: PrepSheetData) -> Dict[str, Any]:
        """Generate summary statistics for prep sheet"""
        try:
            total_documents = (
                len(prep_data.lab_documents) +
                len(prep_data.imaging_documents) +
                len(prep_data.consult_documents) +
                len(prep_data.hospital_documents)
            )
            
            # Count screenings by status
            screening_stats = {
                'due': len([s for s in prep_data.screenings if s.status == 'Due']),
                'due_soon': len([s for s in prep_data.screenings if s.status == 'Due Soon']),
                'complete': len([s for s in prep_data.screenings if s.status == 'Complete']),
                'total': len(prep_data.screenings)
            }
            
            # Calculate average OCR confidence
            all_docs = (prep_data.lab_documents + prep_data.imaging_documents + 
                       prep_data.consult_documents + prep_data.hospital_documents)
            
            if all_docs:
                confidences = [doc.ocr_confidence for doc in all_docs if doc.ocr_confidence > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            else:
                avg_confidence = 0.0
            
            return {
                'total_documents': total_documents,
                'total_conditions': len(prep_data.active_conditions),
                'screening_stats': screening_stats,
                'avg_ocr_confidence': avg_confidence,
                'data_quality_score': self._calculate_data_quality_score(prep_data)
            }
            
        except Exception as e:
            logger.error(f"Error generating summary stats: {str(e)}")
            return {
                'total_documents': 0,
                'total_conditions': 0,
                'screening_stats': {'due': 0, 'due_soon': 0, 'complete': 0, 'total': 0},
                'avg_ocr_confidence': 0.0,
                'data_quality_score': 0.0
            }
    
    def _calculate_data_quality_score(self, prep_data: PrepSheetData) -> float:
        """Calculate overall data quality score"""
        try:
            score_factors = []
            
            # OCR confidence factor
            all_docs = (prep_data.lab_documents + prep_data.imaging_documents + 
                       prep_data.consult_documents + prep_data.hospital_documents)
            
            if all_docs:
                confidences = [doc.ocr_confidence for doc in all_docs if doc.ocr_confidence > 0]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                    score_factors.append(avg_confidence / 100.0)
            
            # Data completeness factor
            completeness_score = 0.0
            if prep_data.patient.date_of_birth:
                completeness_score += 0.25
            if prep_data.patient.phone:
                completeness_score += 0.25
            if len(prep_data.active_conditions) > 0:
                completeness_score += 0.25
            if len(all_docs) > 0:
                completeness_score += 0.25
            
            score_factors.append(completeness_score)
            
            # Screening coverage factor
            if prep_data.screenings:
                complete_screenings = len([s for s in prep_data.screenings if s.status == 'Complete'])
                coverage_score = complete_screenings / len(prep_data.screenings)
                score_factors.append(coverage_score)
            
            return sum(score_factors) / len(score_factors) if score_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating data quality score: {str(e)}")
            return 0.0
    
    def export_prep_sheet_data(self, prep_data: PrepSheetData) -> Dict[str, Any]:
        """Export prep sheet data for external use"""
        try:
            return {
                'patient': {
                    'name': prep_data.patient.full_name,
                    'mrn': prep_data.patient.mrn,
                    'age': prep_data.patient.age,
                    'gender': prep_data.patient.gender
                },
                'prep_date': prep_data.prep_date.isoformat() if prep_data.prep_date else None,
                'screenings': [
                    {
                        'type': s.screening_type,
                        'status': s.status,
                        'last_completed': s.last_completed_date.isoformat() if s.last_completed_date else None,
                        'next_due': s.next_due_date.isoformat() if s.next_due_date else None
                    }
                    for s in prep_data.screenings
                ],
                'conditions': [
                    {
                        'name': c.condition_name,
                        'code': c.condition_code,
                        'diagnosis_date': c.diagnosis_date.isoformat() if c.diagnosis_date else None
                    }
                    for c in prep_data.active_conditions
                ],
                'document_summary': {
                    'labs': len(prep_data.lab_documents),
                    'imaging': len(prep_data.imaging_documents),
                    'consults': len(prep_data.consult_documents),
                    'hospital': len(prep_data.hospital_documents)
                }
            }
            
        except Exception as e:
            logger.error(f"Error exporting prep sheet data: {str(e)}")
            return {}

# Global prep sheet generator instance
prep_sheet_generator = PrepSheetGenerator()
