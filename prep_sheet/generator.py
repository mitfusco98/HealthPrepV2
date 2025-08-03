"""
Assembles content into prep sheet format
Generates comprehensive medical preparation sheets
"""
import logging
from datetime import datetime, timedelta
from app import db
from models import Patient, Screening, Document, ChecklistSettings, Condition, Appointment
from .filters import PrepSheetFilters

logger = logging.getLogger(__name__)

class PrepSheetGenerator:
    """Generates comprehensive prep sheets for patient visits"""
    
    def __init__(self):
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id, appointment_id=None):
        """Generate a complete prep sheet for a patient"""
        patient = Patient.query.get(patient_id)
        if not patient:
            raise ValueError(f"Patient with ID {patient_id} not found")
        
        # Get checklist settings for data cutoffs
        settings = ChecklistSettings.query.first()
        if not settings:
            settings = ChecklistSettings()
        
        # Generate each section of the prep sheet
        prep_data = {
            'patient': self.get_patient_header(patient),
            'summary': self.get_patient_summary(patient, appointment_id),
            'medical_data': self.get_medical_data(patient, settings),
            'quality_checklist': self.get_quality_checklist(patient),
            'enhanced_data': self.get_enhanced_medical_data(patient, settings),
            'generation_info': {
                'generated_at': datetime.utcnow(),
                'generated_by': 'HealthPrep System',
                'data_cutoff_months': {
                    'labs': settings.labs_cutoff_months,
                    'imaging': settings.imaging_cutoff_months,
                    'consults': settings.consults_cutoff_months,
                    'hospital': settings.hospital_cutoff_months
                }
            }
        }
        
        return prep_data
    
    def get_patient_header(self, patient):
        """Generate patient header information"""
        return {
            'name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth,
            'age': patient.age,
            'gender': patient.gender,
            'last_visit': patient.last_visit,
            'contact': {
                'phone': patient.phone,
                'email': patient.email,
                'address': patient.address
            }
        }
    
    def get_patient_summary(self, patient, appointment_id=None):
        """Generate patient summary section"""
        # Get upcoming/recent appointments
        appointments = Appointment.query.filter_by(patient_id=patient.id)\
                                      .order_by(Appointment.appointment_date.desc())\
                                      .limit(5).all()
        
        # Get active conditions
        active_conditions = Condition.query.filter_by(
            patient_id=patient.id,
            status='active'
        ).order_by(Condition.diagnosis_date.desc()).all()
        
        # Current appointment details
        current_appointment = None
        if appointment_id:
            current_appointment = Appointment.query.get(appointment_id)
        
        return {
            'current_appointment': {
                'date': current_appointment.appointment_date if current_appointment else None,
                'type': current_appointment.appointment_type if current_appointment else None,
                'provider': current_appointment.provider if current_appointment else None,
                'notes': current_appointment.notes if current_appointment else None
            },
            'recent_appointments': [
                {
                    'date': apt.appointment_date,
                    'type': apt.appointment_type,
                    'provider': apt.provider,
                    'status': apt.status
                }
                for apt in appointments
            ],
            'active_conditions': [
                {
                    'name': cond.condition_name,
                    'icd10_code': cond.icd10_code,
                    'diagnosis_date': cond.diagnosis_date,
                    'notes': cond.notes
                }
                for cond in active_conditions
            ]
        }
    
    def get_medical_data(self, patient, settings):
        """Generate medical data sections with filtering"""
        cutoff_dates = {
            'labs': datetime.utcnow() - timedelta(days=settings.labs_cutoff_months * 30),
            'imaging': datetime.utcnow() - timedelta(days=settings.imaging_cutoff_months * 30),
            'consults': datetime.utcnow() - timedelta(days=settings.consults_cutoff_months * 30),
            'hospital': datetime.utcnow() - timedelta(days=settings.hospital_cutoff_months * 30)
        }
        
        medical_data = {}
        
        # Get documents by type with date filtering
        for data_type, cutoff_date in cutoff_dates.items():
            documents = Document.query.filter_by(patient_id=patient.id)\
                                    .filter(Document.document_type == data_type)\
                                    .filter(Document.document_date >= cutoff_date)\
                                    .order_by(Document.document_date.desc()).all()
            
            medical_data[data_type] = [
                {
                    'id': doc.id,
                    'filename': doc.original_filename,
                    'document_date': doc.document_date,
                    'upload_date': doc.upload_date,
                    'confidence': doc.ocr_confidence,
                    'summary': self.extract_document_summary(doc)
                }
                for doc in documents
            ]
        
        return medical_data
    
    def get_quality_checklist(self, patient):
        """Generate quality checklist with screening status"""
        screenings = Screening.query.filter_by(patient_id=patient.id)\
                                  .join(Screening.screening_type)\
                                  .filter_by(status='active')\
                                  .order_by(Screening.status.desc()).all()
        
        checklist_items = []
        
        for screening in screenings:
            # Get matched documents for this screening
            matched_docs = []
            for screening_doc in screening.documents:
                doc = screening_doc.document
                matched_docs.append({
                    'id': doc.id,
                    'filename': doc.original_filename,
                    'document_date': doc.document_date,
                    'match_confidence': screening_doc.match_confidence,
                    'matched_keywords': screening_doc.matched_keywords
                })
            
            checklist_items.append({
                'screening_name': screening.screening_type.name,
                'description': screening.screening_type.description,
                'status': screening.status,
                'last_completed': screening.last_completed,
                'next_due': screening.next_due,
                'frequency': {
                    'value': screening.screening_type.frequency_value,
                    'unit': screening.screening_type.frequency_unit
                },
                'matched_documents': matched_docs,
                'urgency': self.calculate_urgency(screening)
            })
        
        # Sort by urgency and status
        checklist_items.sort(key=lambda x: (
            {'due': 0, 'due_soon': 1, 'complete': 2}[x['status']],
            x['urgency']
        ))
        
        return checklist_items
    
    def get_enhanced_medical_data(self, patient, settings):
        """Generate enhanced medical data with document integration"""
        enhanced_data = {}
        
        # Get all documents with filtering
        cutoff_dates = {
            'laboratories': datetime.utcnow() - timedelta(days=settings.labs_cutoff_months * 30),
            'imaging': datetime.utcnow() - timedelta(days=settings.imaging_cutoff_months * 30),
            'consults': datetime.utcnow() - timedelta(days=settings.consults_cutoff_months * 30),
            'hospital_visits': datetime.utcnow() - timedelta(days=settings.hospital_cutoff_months * 30)
        }
        
        for section, cutoff_date in cutoff_dates.items():
            documents = self.filters.filter_documents_by_relevancy(
                patient.id, section, cutoff_date
            )
            
            enhanced_data[section] = {
                'title': section.replace('_', ' ').title(),
                'cutoff_months': getattr(settings, f"{section.split('_')[0]}_cutoff_months", 12),
                'documents': [
                    {
                        'id': doc.id,
                        'filename': doc.original_filename,
                        'document_date': doc.document_date,
                        'document_type': doc.document_type,
                        'confidence': doc.ocr_confidence,
                        'confidence_class': self.get_confidence_class(doc.ocr_confidence),
                        'summary': self.extract_document_summary(doc),
                        'key_findings': self.extract_key_findings(doc, section)
                    }
                    for doc in documents
                ],
                'summary_stats': self.generate_section_stats(documents)
            }
        
        return enhanced_data
    
    def extract_document_summary(self, document):
        """Extract a brief summary from document OCR text"""
        if not document.ocr_text:
            return "No text available"
        
        # Simple extraction - first few meaningful lines
        lines = document.ocr_text.split('\n')
        meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 10]
        
        if meaningful_lines:
            summary = ' '.join(meaningful_lines[:3])
            return summary[:200] + '...' if len(summary) > 200 else summary
        
        return "Unable to extract summary"
    
    def extract_key_findings(self, document, section):
        """Extract key findings relevant to the section"""
        if not document.ocr_text:
            return []
        
        findings = []
        text = document.ocr_text.lower()
        
        # Section-specific keyword extraction
        if section == 'laboratories':
            lab_patterns = [
                r'glucose[:\s]+(\d+(?:\.\d+)?)',
                r'cholesterol[:\s]+(\d+)',
                r'a1c[:\s]+(\d+(?:\.\d+)?)',
                r'creatinine[:\s]+(\d+(?:\.\d+)?)',
                r'hemoglobin[:\s]+(\d+(?:\.\d+)?)'
            ]
            findings.extend(self.extract_patterns(text, lab_patterns))
        
        elif section == 'imaging':
            # Look for impression or findings sections
            if 'impression:' in text:
                impression_start = text.find('impression:')
                impression_text = text[impression_start:impression_start+200]
                findings.append(impression_text.strip())
        
        elif section == 'consults':
            # Look for recommendations or assessment
            if 'assessment:' in text:
                assessment_start = text.find('assessment:')
                assessment_text = text[assessment_start:assessment_start+200]
                findings.append(assessment_text.strip())
        
        return findings[:5]  # Limit to 5 key findings
    
    def extract_patterns(self, text, patterns):
        """Extract values matching specific patterns"""
        import re
        findings = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append(match.group(0))
        
        return findings
    
    def calculate_urgency(self, screening):
        """Calculate urgency score for screening (0-10, higher = more urgent)"""
        if screening.status == 'due':
            return 10
        elif screening.status == 'due_soon':
            if screening.next_due:
                days_until_due = (screening.next_due - datetime.utcnow()).days
                if days_until_due <= 7:
                    return 8
                elif days_until_due <= 30:
                    return 6
                else:
                    return 4
            return 6
        else:  # complete
            return 2
    
    def get_confidence_class(self, confidence):
        """Get CSS class for confidence level"""
        if confidence is None or confidence == 0:
            return 'confidence-unknown'
        elif confidence >= 0.8:
            return 'confidence-high'
        elif confidence >= 0.6:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def generate_section_stats(self, documents):
        """Generate statistics for a document section"""
        if not documents:
            return {
                'total_documents': 0,
                'avg_confidence': 0,
                'date_range': None
            }
        
        confidences = [doc.ocr_confidence for doc in documents if doc.ocr_confidence is not None]
        dates = [doc.document_date for doc in documents if doc.document_date is not None]
        
        stats = {
            'total_documents': len(documents),
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
            'date_range': {
                'earliest': min(dates) if dates else None,
                'latest': max(dates) if dates else None
            }
        }
        
        return stats
    
    def export_prep_sheet_data(self, prep_data, format='dict'):
        """Export prep sheet data in various formats"""
        if format == 'dict':
            return prep_data
        elif format == 'json':
            import json
            return json.dumps(prep_data, default=str, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
