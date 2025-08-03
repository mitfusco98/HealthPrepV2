"""
Prep sheet generation and assembly module.
Creates comprehensive patient preparation sheets with medical data integration.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from app import db
from models import Patient, MedicalDocument, Screening, ScreeningType, ChecklistSettings, Appointment
from prep_sheet.filters import PrepSheetFilters

class PrepSheetGenerator:
    """Main prep sheet generator"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id: int) -> Dict[str, Any]:
        """Generate complete prep sheet for a patient"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get checklist settings for cutoffs
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
                db.session.add(settings)
                db.session.commit()
            
            # Generate each section of the prep sheet
            prep_data = {
                'patient_header': self._generate_patient_header(patient),
                'summary': self._generate_patient_summary(patient),
                'medical_data': self._generate_medical_data(patient, settings),
                'quality_checklist': self._generate_quality_checklist(patient),
                'enhanced_data': self._generate_enhanced_data(patient, settings),
                'generation_info': {
                    'generated_at': datetime.utcnow().isoformat(),
                    'generated_by': 'HealthPrep System',
                    'settings_used': {
                        'cutoff_labs': settings.cutoff_labs,
                        'cutoff_imaging': settings.cutoff_imaging,
                        'cutoff_consults': settings.cutoff_consults,
                        'cutoff_hospital': settings.cutoff_hospital
                    }
                }
            }
            
            self.logger.info(f"Generated prep sheet for patient {patient_id}")
            return prep_data
            
        except Exception as e:
            self.logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
            raise
    
    def _generate_patient_header(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient header information"""
        # Calculate age
        age = None
        if patient.date_of_birth:
            today = date.today()
            age = today.year - patient.date_of_birth.year
            if (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day):
                age -= 1
        
        # Get last visit
        last_appointment = Appointment.query.filter_by(patient_id=patient.id)\
                                          .filter(Appointment.appointment_date <= datetime.utcnow())\
                                          .order_by(Appointment.appointment_date.desc())\
                                          .first()
        
        return {
            'name': f"{patient.first_name} {patient.last_name}",
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            'age': age,
            'gender': patient.gender,
            'last_visit': last_appointment.appointment_date.isoformat() if last_appointment else None,
            'prep_date': datetime.utcnow().isoformat(),
            'contact_info': {
                'phone': patient.phone,
                'email': patient.email,
                'address': patient.address
            }
        }
    
    def _generate_patient_summary(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient summary section"""
        # Get recent appointments
        recent_appointments = Appointment.query.filter_by(patient_id=patient.id)\
                                             .order_by(Appointment.appointment_date.desc())\
                                             .limit(5).all()
        
        appointments_data = []
        for apt in recent_appointments:
            appointments_data.append({
                'date': apt.appointment_date.isoformat(),
                'type': apt.appointment_type,
                'provider': apt.provider,
                'status': apt.status,
                'notes': apt.notes
            })
        
        # Get active conditions (this would be enhanced with actual condition tracking)
        # For now, we'll extract from document analysis
        active_conditions = self._extract_conditions_from_documents(patient.id)
        
        return {
            'recent_appointments': appointments_data,
            'active_conditions': active_conditions,
            'total_documents': len(patient.documents),
            'total_screenings': len(patient.screenings)
        }
    
    def _generate_medical_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate medical data sections with cutoff filtering"""
        cutoff_dates = {
            'labs': datetime.utcnow() - relativedelta(months=settings.cutoff_labs),
            'imaging': datetime.utcnow() - relativedelta(months=settings.cutoff_imaging),
            'consults': datetime.utcnow() - relativedelta(months=settings.cutoff_consults),
            'hospital': datetime.utcnow() - relativedelta(months=settings.cutoff_hospital)
        }
        
        # Get documents by type within cutoff periods
        lab_docs = self.filters.filter_documents_by_type_and_date(
            patient.id, 'lab', cutoff_dates['labs'].date()
        )
        
        imaging_docs = self.filters.filter_documents_by_type_and_date(
            patient.id, 'imaging', cutoff_dates['imaging'].date()
        )
        
        consult_docs = self.filters.filter_documents_by_type_and_date(
            patient.id, 'consult', cutoff_dates['consults'].date()
        )
        
        hospital_docs = self.filters.filter_documents_by_type_and_date(
            patient.id, 'hospital', cutoff_dates['hospital'].date()
        )
        
        return {
            'labs': {
                'cutoff_months': settings.cutoff_labs,
                'cutoff_date': cutoff_dates['labs'].date().isoformat(),
                'documents': [self._format_document_summary(doc) for doc in lab_docs],
                'count': len(lab_docs)
            },
            'imaging': {
                'cutoff_months': settings.cutoff_imaging,
                'cutoff_date': cutoff_dates['imaging'].date().isoformat(),
                'documents': [self._format_document_summary(doc) for doc in imaging_docs],
                'count': len(imaging_docs)
            },
            'consults': {
                'cutoff_months': settings.cutoff_consults,
                'cutoff_date': cutoff_dates['consults'].date().isoformat(),
                'documents': [self._format_document_summary(doc) for doc in consult_docs],
                'count': len(consult_docs)
            },
            'hospital': {
                'cutoff_months': settings.cutoff_hospital,
                'cutoff_date': cutoff_dates['hospital'].date().isoformat(),
                'documents': [self._format_document_summary(doc) for doc in hospital_docs],
                'count': len(hospital_docs)
            }
        }
    
    def _generate_quality_checklist(self, patient: Patient) -> Dict[str, Any]:
        """Generate quality checklist section with screening status"""
        screenings = Screening.query.filter_by(patient_id=patient.id)\
                                  .join(ScreeningType)\
                                  .filter(ScreeningType.is_active == True)\
                                  .order_by(ScreeningType.name).all()
        
        checklist_items = []
        status_counts = {'Complete': 0, 'Due': 0, 'Due Soon': 0}
        
        for screening in screenings:
            # Get matched documents
            matched_docs = []
            if screening.matched_documents:
                try:
                    doc_ids = eval(screening.matched_documents)  # Parse JSON
                    matched_docs = MedicalDocument.query.filter(
                        MedicalDocument.id.in_(doc_ids)
                    ).all()
                except:
                    pass
            
            # Calculate frequency description
            freq_desc = self._get_frequency_description(screening.screening_type)
            
            checklist_item = {
                'screening_name': screening.screening_type.name,
                'status': screening.status,
                'last_completed_date': screening.last_completed_date.isoformat() if screening.last_completed_date else None,
                'next_due_date': screening.next_due_date.isoformat() if screening.next_due_date else None,
                'frequency': freq_desc,
                'matched_documents': [self._format_document_link(doc) for doc in matched_docs],
                'document_count': len(matched_docs)
            }
            
            checklist_items.append(checklist_item)
            status_counts[screening.status] = status_counts.get(screening.status, 0) + 1
        
        return {
            'items': checklist_items,
            'summary': {
                'total_screenings': len(checklist_items),
                'complete': status_counts.get('Complete', 0),
                'due': status_counts.get('Due', 0),
                'due_soon': status_counts.get('Due Soon', 0)
            }
        }
    
    def _generate_enhanced_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate enhanced medical data with document integration"""
        # This section provides filtered, clickable documents per medical category
        cutoff_date = datetime.utcnow() - relativedelta(months=12)  # Default 12 months
        
        recent_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_date >= cutoff_date.date()
        ).order_by(MedicalDocument.document_date.desc()).all()
        
        # Group documents by type
        docs_by_type = {
            'laboratories': [],
            'imaging': [],
            'consults': [],
            'hospital_visits': []
        }
        
        for doc in recent_docs:
            doc_data = self._format_enhanced_document(doc)
            
            if doc.document_type == 'lab':
                docs_by_type['laboratories'].append(doc_data)
            elif doc.document_type == 'imaging':
                docs_by_type['imaging'].append(doc_data)
            elif doc.document_type == 'consult':
                docs_by_type['consults'].append(doc_data)
            elif doc.document_type == 'hospital':
                docs_by_type['hospital_visits'].append(doc_data)
        
        return {
            'timeframe': '12 months',
            'cutoff_date': cutoff_date.date().isoformat(),
            'laboratories': docs_by_type['laboratories'],
            'imaging': docs_by_type['imaging'],
            'consults': docs_by_type['consults'],
            'hospital_visits': docs_by_type['hospital_visits'],
            'total_documents': len(recent_docs)
        }
    
    def _format_document_summary(self, doc: MedicalDocument) -> Dict[str, Any]:
        """Format document for summary display"""
        return {
            'id': doc.id,
            'filename': doc.filename,
            'date': doc.document_date.isoformat() if doc.document_date else None,
            'type': doc.document_type,
            'size': doc.file_size,
            'ocr_confidence': doc.ocr_confidence,
            'text_preview': doc.ocr_text[:100] + '...' if doc.ocr_text and len(doc.ocr_text) > 100 else doc.ocr_text
        }
    
    def _format_document_link(self, doc: MedicalDocument) -> Dict[str, Any]:
        """Format document for clickable link display"""
        # Determine confidence level for styling
        confidence_level = 'high'
        if doc.ocr_confidence and doc.ocr_confidence < 0.8:
            confidence_level = 'medium'
        if doc.ocr_confidence and doc.ocr_confidence < 0.6:
            confidence_level = 'low'
        
        return {
            'id': doc.id,
            'filename': doc.filename,
            'date': doc.document_date.isoformat() if doc.document_date else None,
            'confidence_level': confidence_level,
            'confidence_score': doc.ocr_confidence,
            'url': f'/document/{doc.id}'  # URL to view document
        }
    
    def _format_enhanced_document(self, doc: MedicalDocument) -> Dict[str, Any]:
        """Format document for enhanced data display"""
        return {
            'id': doc.id,
            'filename': doc.filename,
            'date': doc.document_date.isoformat() if doc.document_date else None,
            'type': doc.document_type,
            'confidence_level': self._get_confidence_level(doc.ocr_confidence),
            'has_text': bool(doc.ocr_text),
            'text_length': len(doc.ocr_text) if doc.ocr_text else 0,
            'url': f'/document/{doc.id}',
            'downloadable': bool(doc.file_path)
        }
    
    def _get_confidence_level(self, confidence: Optional[float]) -> str:
        """Get confidence level description"""
        if not confidence:
            return 'unknown'
        
        if confidence >= 0.8:
            return 'high'
        elif confidence >= 0.6:
            return 'medium'
        else:
            return 'low'
    
    def _get_frequency_description(self, screening_type: ScreeningType) -> str:
        """Get human-readable frequency description"""
        if not screening_type.frequency_number or not screening_type.frequency_unit:
            return "Frequency not specified"
        
        number = screening_type.frequency_number
        unit = screening_type.frequency_unit
        
        if number == 1:
            unit_name = "year" if unit == "years" else "month"
            return f"Every {unit_name}"
        else:
            return f"Every {number} {unit}"
    
    def _extract_conditions_from_documents(self, patient_id: int) -> List[Dict[str, Any]]:
        """Extract medical conditions from document analysis"""
        # This is a simplified implementation
        # In practice, this would use NLP or structured data extraction
        
        conditions = []
        
        # Common condition keywords to look for in documents
        condition_keywords = {
            'diabetes': ['diabetes', 'diabetic', 'dm', 'diabetes mellitus'],
            'hypertension': ['hypertension', 'htn', 'high blood pressure'],
            'hyperlipidemia': ['hyperlipidemia', 'high cholesterol', 'dyslipidemia'],
            'copd': ['copd', 'chronic obstructive pulmonary disease'],
            'cad': ['coronary artery disease', 'cad', 'heart disease']
        }
        
        # Get recent documents
        recent_docs = MedicalDocument.query.filter_by(patient_id=patient_id)\
                                         .filter(MedicalDocument.ocr_text.isnot(None))\
                                         .order_by(MedicalDocument.document_date.desc())\
                                         .limit(50).all()
        
        found_conditions = set()
        
        for doc in recent_docs:
            if doc.ocr_text:
                text_lower = doc.ocr_text.lower()
                for condition, keywords in condition_keywords.items():
                    for keyword in keywords:
                        if keyword in text_lower and condition not in found_conditions:
                            conditions.append({
                                'name': condition.title(),
                                'source_document': doc.filename,
                                'source_date': doc.document_date.isoformat() if doc.document_date else None
                            })
                            found_conditions.add(condition)
                            break
        
        return conditions[:10]  # Limit to 10 conditions
    
    def generate_screening_summary(self, patient_id: int) -> Dict[str, Any]:
        """Generate focused screening summary"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            screenings = Screening.query.filter_by(patient_id=patient_id)\
                                      .join(ScreeningType)\
                                      .filter(ScreeningType.is_active == True).all()
            
            summary = {
                'patient_info': {
                    'name': f"{patient.first_name} {patient.last_name}",
                    'mrn': patient.mrn
                },
                'screening_overview': {
                    'total': len(screenings),
                    'complete': len([s for s in screenings if s.status == 'Complete']),
                    'due': len([s for s in screenings if s.status == 'Due']),
                    'due_soon': len([s for s in screenings if s.status == 'Due Soon'])
                },
                'urgent_screenings': [
                    {
                        'name': s.screening_type.name,
                        'status': s.status,
                        'last_completed': s.last_completed_date.isoformat() if s.last_completed_date else None,
                        'next_due': s.next_due_date.isoformat() if s.next_due_date else None
                    }
                    for s in screenings if s.status == 'Due'
                ]
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating screening summary for patient {patient_id}: {str(e)}")
            raise
