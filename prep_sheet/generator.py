from datetime import datetime, timedelta
from models import Patient, MedicalDocument, PatientScreening, PatientCondition, ChecklistSettings
from prep_sheet.filters import PrepSheetFilters
import logging

class PrepSheetGenerator:
    """Generates medical preparation sheets for patient visits"""
    
    def __init__(self):
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient):
        """Generate comprehensive prep sheet for patient"""
        try:
            # Get checklist settings for data cutoffs
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
            
            prep_data = {
                'patient_info': self._get_patient_info(patient),
                'summary': self._get_patient_summary(patient),
                'medical_data': self._get_medical_data(patient, settings),
                'quality_checklist': self._get_quality_checklist(patient),
                'enhanced_data': self._get_enhanced_medical_data(patient, settings),
                'generation_info': {
                    'generated_at': datetime.utcnow(),
                    'generated_by': 'HealthPrep System',
                    'data_cutoff_settings': {
                        'labs': f"{settings.labs_cutoff_months} months",
                        'imaging': f"{settings.imaging_cutoff_months} months",
                        'consults': f"{settings.consults_cutoff_months} months",
                        'hospital': f"{settings.hospital_cutoff_months} months"
                    }
                }
            }
            
            return prep_data
            
        except Exception as e:
            logging.error(f"Error generating prep sheet for patient {patient.id}: {str(e)}")
            raise
    
    def _get_patient_info(self, patient):
        """Get patient header information"""
        return {
            'name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth,
            'age': patient.age,
            'gender': patient.gender,
            'phone': patient.phone,
            'email': patient.email,
            'address': patient.address,
            'prep_date': datetime.utcnow().date()
        }
    
    def _get_patient_summary(self, patient):
        """Get patient summary with recent visits and conditions"""
        # Get recent documents (last 30 days) as proxy for visits
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        recent_documents = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.created_at >= recent_cutoff
        ).order_by(MedicalDocument.created_at.desc()).limit(5).all()
        
        # Get active conditions
        active_conditions = PatientCondition.query.filter(
            PatientCondition.patient_id == patient.id,
            PatientCondition.status == 'active'
        ).order_by(PatientCondition.diagnosis_date.desc()).all()
        
        return {
            'recent_activity': [
                {
                    'date': doc.created_at.date(),
                    'type': doc.document_type or 'Document',
                    'description': doc.filename
                }
                for doc in recent_documents
            ],
            'active_conditions': [
                {
                    'name': condition.condition_name,
                    'icd10_code': condition.icd10_code,
                    'diagnosis_date': condition.diagnosis_date,
                    'status': condition.status
                }
                for condition in active_conditions
            ]
        }
    
    def _get_medical_data(self, patient, settings):
        """Get filtered medical data by category"""
        medical_data = {}
        
        # Calculate cutoff dates
        cutoff_dates = {
            'labs': datetime.utcnow() - timedelta(days=30 * settings.labs_cutoff_months),
            'imaging': datetime.utcnow() - timedelta(days=30 * settings.imaging_cutoff_months),
            'consults': datetime.utcnow() - timedelta(days=30 * settings.consults_cutoff_months),
            'hospital': datetime.utcnow() - timedelta(days=30 * settings.hospital_cutoff_months)
        }
        
        # Get documents by type within cutoff periods
        for doc_type, cutoff_date in cutoff_dates.items():
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type == doc_type,
                MedicalDocument.created_at >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            medical_data[doc_type] = [
                {
                    'id': doc.id,
                    'filename': doc.filename,
                    'date': doc.document_date or doc.created_at.date(),
                    'confidence': doc.ocr_confidence,
                    'confidence_level': doc.confidence_level,
                    'has_ocr': bool(doc.ocr_text)
                }
                for doc in documents
            ]
        
        return medical_data
    
    def _get_quality_checklist(self, patient):
        """Get screening quality checklist"""
        screenings = PatientScreening.query.filter(
            PatientScreening.patient_id == patient.id
        ).join(PatientScreening.screening_type).all()
        
        checklist_items = []
        
        for screening in screenings:
            # Get matched documents
            matched_docs = []
            if screening.matched_documents:
                doc_ids = screening.matched_documents
                documents = MedicalDocument.query.filter(
                    MedicalDocument.id.in_(doc_ids)
                ).all()
                
                matched_docs = [
                    {
                        'id': doc.id,
                        'filename': doc.filename,
                        'date': doc.document_date or doc.created_at.date(),
                        'confidence_level': doc.confidence_level
                    }
                    for doc in documents
                ]
            
            checklist_items.append({
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed_date,
                'next_due': screening.next_due_date,
                'frequency': f"{screening.screening_type.frequency_value} {screening.screening_type.frequency_unit}",
                'matched_documents': matched_docs
            })
        
        return {
            'items': checklist_items,
            'summary': {
                'total': len(checklist_items),
                'due': len([item for item in checklist_items if item['status'] == 'due']),
                'due_soon': len([item for item in checklist_items if item['status'] == 'due_soon']),
                'complete': len([item for item in checklist_items if item['status'] == 'complete'])
            }
        }
    
    def _get_enhanced_medical_data(self, patient, settings):
        """Get enhanced medical data with document integration"""
        enhanced_data = {}
        
        # For each document type, get both structured data and documents
        document_types = ['labs', 'imaging', 'consults', 'hospital']
        
        for doc_type in document_types:
            cutoff_months = getattr(settings, f"{doc_type}_cutoff_months")
            cutoff_date = datetime.utcnow() - timedelta(days=30 * cutoff_months)
            
            # Get documents
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type == doc_type,
                MedicalDocument.created_at >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            # Filter documents by screening relevance
            relevant_docs = self.filters.filter_documents_by_relevance(documents, patient)
            
            enhanced_data[doc_type] = {
                'documents': [
                    {
                        'id': doc.id,
                        'filename': doc.filename,
                        'date': doc.document_date or doc.created_at.date(),
                        'confidence_level': doc.confidence_level,
                        'ocr_available': bool(doc.ocr_text),
                        'relevance_score': doc.relevance_score if hasattr(doc, 'relevance_score') else 1.0
                    }
                    for doc in relevant_docs
                ],
                'cutoff_period': f"Last {cutoff_months} months",
                'total_documents': len(documents),
                'relevant_documents': len(relevant_docs)
            }
        
        return enhanced_data
    
    def generate_batch_prep_sheets(self, patient_ids):
        """Generate prep sheets for multiple patients"""
        results = {
            'success': [],
            'errors': [],
            'total_processed': 0
        }
        
        for patient_id in patient_ids:
            try:
                patient = Patient.query.get(patient_id)
                if not patient:
                    results['errors'].append(f"Patient {patient_id} not found")
                    continue
                
                prep_data = self.generate_prep_sheet(patient)
                results['success'].append({
                    'patient_id': patient_id,
                    'patient_name': patient.full_name,
                    'prep_data': prep_data
                })
                
            except Exception as e:
                results['errors'].append(f"Error processing patient {patient_id}: {str(e)}")
            
            results['total_processed'] += 1
        
        return results
