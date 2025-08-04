"""
Prep sheet generation engine that assembles patient data into formatted preparation sheets.
Includes medical data filtering, screening summaries, and template rendering.
"""

import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Any
import json

from app import db
from models import (Patient, MedicalDocument, Screening, ScreeningType, 
                   PatientCondition, ChecklistSettings)
from .filters import PrepSheetFilters
from core.engine import ScreeningEngine

class PrepSheetGenerator:
    """Generates comprehensive preparation sheets for patient visits."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
        self.screening_engine = ScreeningEngine()
    
    def generate_prep_sheet(self, patient: Patient) -> Dict[str, Any]:
        """Generate complete prep sheet data for a patient."""
        
        try:
            self.logger.info(f"Generating prep sheet for patient {patient.id} - {patient.full_name}")
            
            # Get cutoff settings
            cutoff_settings = self._get_cutoff_settings()
            
            # Generate all sections
            prep_data = {
                'patient_header': self._generate_patient_header(patient),
                'patient_summary': self._generate_patient_summary(patient),
                'medical_data': self._generate_medical_data_sections(patient, cutoff_settings),
                'quality_checklist': self._generate_quality_checklist(patient),
                'enhanced_medical_data': self._generate_enhanced_medical_data(patient, cutoff_settings),
                'generation_metadata': self._generate_metadata()
            }
            
            self.logger.info(f"Successfully generated prep sheet for patient {patient.id}")
            return prep_data
            
        except Exception as e:
            self.logger.error(f"Error generating prep sheet for patient {patient.id}: {e}")
            raise Exception(f"Prep sheet generation failed: {str(e)}")
    
    def _generate_patient_header(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient header information."""
        
        return {
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'date_of_birth': patient.date_of_birth.strftime('%m/%d/%Y'),
            'age': patient.age,
            'gender': 'Male' if patient.gender == 'M' else 'Female',
            'last_visit': patient.last_visit.strftime('%m/%d/%Y %I:%M %p') if patient.last_visit else 'No previous visits',
            'prep_date': datetime.now().strftime('%m/%d/%Y %I:%M %p'),
            'prep_date_full': datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')
        }
    
    def _generate_patient_summary(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient summary with recent visits and active conditions."""
        
        # Get recent visit history (simulated - would come from EMR)
        recent_visits = self._get_recent_visit_history(patient)
        
        # Get active conditions
        active_conditions = PatientCondition.query.filter_by(
            patient_id=patient.id,
            is_active=True
        ).order_by(PatientCondition.diagnosis_date.desc()).all()
        
        return {
            'recent_visits': recent_visits,
            'active_conditions': [{
                'condition_name': condition.condition_name,
                'diagnosis_date': condition.diagnosis_date.strftime('%m/%d/%Y') if condition.diagnosis_date else 'Unknown',
                'duration': self._calculate_condition_duration(condition.diagnosis_date) if condition.diagnosis_date else 'Unknown duration'
            } for condition in active_conditions[:10]],  # Limit to 10 most recent
            'total_active_conditions': len(active_conditions)
        }
    
    def _generate_medical_data_sections(self, patient: Patient, cutoff_settings: ChecklistSettings) -> Dict[str, List]:
        """Generate medical data sections with filtering."""
        
        # Calculate cutoff dates
        cutoff_dates = {
            'labs': date.today() - relativedelta(months=cutoff_settings.labs_cutoff_months),
            'imaging': date.today() - relativedelta(months=cutoff_settings.imaging_cutoff_months),
            'consults': date.today() - relativedelta(months=cutoff_settings.consults_cutoff_months),
            'hospital': date.today() - relativedelta(months=cutoff_settings.hospital_cutoff_months)
        }
        
        medical_data = {}
        
        # Get filtered documents by type
        for doc_type, cutoff_date in cutoff_dates.items():
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type == doc_type,
                MedicalDocument.document_date >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            medical_data[f'recent_{doc_type}'] = [{
                'id': doc.id,
                'filename': doc.filename,
                'document_date': doc.document_date.strftime('%m/%d/%Y'),
                'document_type': doc.document_type.title(),
                'content_preview': self._generate_content_preview(doc),
                'confidence_score': round(doc.confidence_score * 100, 1) if doc.confidence_score else 0,
                'confidence_class': self._get_confidence_css_class(doc.confidence_score),
                'days_ago': (date.today() - doc.document_date).days
            } for doc in documents[:20]]  # Limit to 20 most recent per type
        
        return medical_data
    
    def _generate_quality_checklist(self, patient: Patient) -> Dict[str, Any]:
        """Generate quality checklist with screening statuses."""
        
        # Get patient screenings
        screenings = Screening.query.filter_by(patient_id=patient.id).all()
        
        screening_items = []
        status_summary = {'Complete': 0, 'Due': 0, 'Due Soon': 0, 'Overdue': 0}
        
        for screening in screenings:
            # Get matched documents for this screening
            matched_docs = self._get_screening_matched_documents(screening)
            
            screening_item = {
                'screening_name': screening.screening_type.name,
                'last_completed_date': screening.last_completed_date.strftime('%m/%d/%Y') if screening.last_completed_date else 'Never',
                'frequency': f"Every {screening.screening_type.frequency_value} {screening.screening_type.frequency_unit}",
                'status': screening.status,
                'status_class': self._get_status_css_class(screening.status),
                'next_due_date': screening.next_due_date.strftime('%m/%d/%Y') if screening.next_due_date else 'N/A',
                'matched_documents': matched_docs,
                'days_since_last': (date.today() - screening.last_completed_date).days if screening.last_completed_date else None,
                'urgency_score': self._calculate_urgency_score(screening)
            }
            
            screening_items.append(screening_item)
            status_summary[screening.status] = status_summary.get(screening.status, 0) + 1
        
        # Sort by urgency score (highest first)
        screening_items.sort(key=lambda x: x['urgency_score'], reverse=True)
        
        return {
            'screening_items': screening_items,
            'status_summary': status_summary,
            'total_screenings': len(screening_items),
            'completion_rate': (status_summary['Complete'] / max(len(screening_items), 1)) * 100,
            'urgent_items': [item for item in screening_items if item['status'] in ['Due', 'Overdue']]
        }
    
    def _generate_enhanced_medical_data(self, patient: Patient, cutoff_settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate enhanced medical data with document integration and relevancy filtering."""
        
        enhanced_data = {}
        
        # Define data categories with their cutoff periods
        categories = {
            'laboratories': {
                'cutoff_months': cutoff_settings.labs_cutoff_months,
                'document_types': ['lab'],
                'title': 'Laboratory Results'
            },
            'imaging': {
                'cutoff_months': cutoff_settings.imaging_cutoff_months,
                'document_types': ['imaging'],
                'title': 'Imaging Studies'
            },
            'consults': {
                'cutoff_months': cutoff_settings.consults_cutoff_months,
                'document_types': ['consult'],
                'title': 'Specialist Consultations'
            },
            'hospital_visits': {
                'cutoff_months': cutoff_settings.hospital_cutoff_months,
                'document_types': ['hospital'],
                'title': 'Hospital Encounters'
            }
        }
        
        for category, config in categories.items():
            cutoff_date = date.today() - relativedelta(months=config['cutoff_months'])
            
            # Get relevant documents
            documents = MedicalDocument.query.filter(
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type.in_(config['document_types']),
                MedicalDocument.document_date >= cutoff_date
            ).order_by(MedicalDocument.document_date.desc()).all()
            
            # Process documents with relevancy filtering
            processed_docs = []
            for doc in documents:
                # Apply relevancy filtering based on current screening cycle
                if self.filters.is_document_relevant_for_current_cycle(doc, patient):
                    processed_docs.append({
                        'id': doc.id,
                        'title': doc.filename,
                        'date': doc.document_date.strftime('%m/%d/%Y'),
                        'type': doc.document_type.title(),
                        'content_summary': self._generate_content_summary(doc),
                        'confidence_score': round(doc.confidence_score * 100, 1) if doc.confidence_score else 0,
                        'confidence_class': self._get_confidence_css_class(doc.confidence_score),
                        'relevancy_score': self.filters.calculate_document_relevancy(doc, patient),
                        'clickable_link': f"/documents/{doc.id}/view",
                        'days_ago': (date.today() - doc.document_date).days
                    })
            
            # Sort by relevancy and date
            processed_docs.sort(key=lambda x: (x['relevancy_score'], -x['days_ago']), reverse=True)
            
            enhanced_data[category] = {
                'title': config['title'],
                'cutoff_period': f"Last {config['cutoff_months']} months",
                'documents': processed_docs[:15],  # Limit to 15 most relevant
                'total_available': len(documents),
                'showing_count': len(processed_docs[:15])
            }
        
        return enhanced_data
    
    def _get_screening_matched_documents(self, screening: Screening) -> List[Dict]:
        """Get documents matched to a specific screening."""
        
        from models import ScreeningDocumentMatch
        
        matches = ScreeningDocumentMatch.query.filter_by(screening_id=screening.id).all()
        
        matched_docs = []
        for match in matches:
            doc = match.document
            matched_docs.append({
                'id': doc.id,
                'filename': doc.filename,
                'document_date': doc.document_date.strftime('%m/%d/%Y'),
                'match_confidence': round(match.match_confidence * 100, 1) if match.match_confidence else 0,
                'confidence_class': self._get_confidence_css_class(match.match_confidence),
                'clickable_link': f"/documents/{doc.id}/view",
                'matched_keywords': json.loads(match.matched_keywords) if match.matched_keywords else []
            })
        
        return matched_docs[:5]  # Limit to 5 most relevant documents
    
    def _get_recent_visit_history(self, patient: Patient) -> List[Dict]:
        """Get recent visit history (simulated - would integrate with EMR)."""
        
        # This would typically integrate with EMR encounter data
        # For now, we'll derive from document dates as a proxy
        
        recent_docs = MedicalDocument.query.filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_date >= date.today() - relativedelta(months=12)
        ).order_by(MedicalDocument.document_date.desc()).limit(10).all()
        
        # Group by date to simulate visits
        visit_dates = {}
        for doc in recent_docs:
            doc_date = doc.document_date
            if doc_date not in visit_dates:
                visit_dates[doc_date] = []
            visit_dates[doc_date].append(doc)
        
        visits = []
        for visit_date, docs in list(visit_dates.items())[:5]:  # Last 5 visit dates
            visits.append({
                'visit_date': visit_date.strftime('%m/%d/%Y'),
                'days_ago': (date.today() - visit_date).days,
                'document_count': len(docs),
                'visit_type': self._infer_visit_type(docs),
                'primary_documents': [doc.filename for doc in docs[:3]]
            })
        
        return visits
    
    def _infer_visit_type(self, documents: List[MedicalDocument]) -> str:
        """Infer visit type from document types."""
        
        doc_types = [doc.document_type for doc in documents]
        
        if 'hospital' in doc_types:
            return 'Hospital Visit'
        elif 'consult' in doc_types:
            return 'Specialist Consultation'
        elif 'imaging' in doc_types:
            return 'Imaging/Diagnostic'
        elif 'lab' in doc_types:
            return 'Laboratory/Routine'
        else:
            return 'General Visit'
    
    def _calculate_condition_duration(self, diagnosis_date: date) -> str:
        """Calculate human-readable duration since diagnosis."""
        
        if not diagnosis_date:
            return "Unknown duration"
        
        today = date.today()
        delta = today - diagnosis_date
        
        years = delta.days // 365
        months = (delta.days % 365) // 30
        
        if years > 0:
            if months > 0:
                return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
            else:
                return f"{years} year{'s' if years != 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"
    
    def _calculate_urgency_score(self, screening: Screening) -> int:
        """Calculate urgency score for screening prioritization."""
        
        if screening.status == 'Overdue':
            return 100
        elif screening.status == 'Due':
            return 80
        elif screening.status == 'Due Soon':
            return 60
        else:  # Complete
            return 20
    
    def _generate_content_preview(self, document: MedicalDocument) -> str:
        """Generate a short preview of document content."""
        
        if not document.content:
            return "No content available"
        
        # Clean up content and create preview
        content = document.content.strip()
        
        # Remove multiple whitespace and newlines
        import re
        content = re.sub(r'\s+', ' ', content)
        
        # Create preview (first 150 characters)
        if len(content) > 150:
            preview = content[:147] + "..."
        else:
            preview = content
        
        return preview
    
    def _generate_content_summary(self, document: MedicalDocument) -> str:
        """Generate a more detailed content summary."""
        
        if not document.content:
            return "Document content not available"
        
        content = document.content.strip()
        
        # Extract key information based on document type
        if document.document_type == 'lab':
            return self._extract_lab_summary(content)
        elif document.document_type == 'imaging':
            return self._extract_imaging_summary(content)
        elif document.document_type == 'consult':
            return self._extract_consult_summary(content)
        else:
            # Generic summary
            import re
            content = re.sub(r'\s+', ' ', content)
            return content[:200] + "..." if len(content) > 200 else content
    
    def _extract_lab_summary(self, content: str) -> str:
        """Extract key information from lab results."""
        
        # Look for common lab patterns
        import re
        
        # Find numeric results
        numeric_results = re.findall(r'([A-Za-z0-9\s]+):\s*(\d+\.?\d*)\s*([a-zA-Z/]+)?', content)
        
        if numeric_results:
            summary_parts = []
            for test_name, value, unit in numeric_results[:3]:  # First 3 results
                unit_str = f" {unit}" if unit else ""
                summary_parts.append(f"{test_name.strip()}: {value}{unit_str}")
            return "; ".join(summary_parts)
        
        # Fallback to content preview
        return content[:150] + "..." if len(content) > 150 else content
    
    def _extract_imaging_summary(self, content: str) -> str:
        """Extract key information from imaging reports."""
        
        # Look for impression or findings sections
        import re
        
        impression_match = re.search(r'impression[:\s]*(.*?)(?=\n|$)', content, re.IGNORECASE | re.DOTALL)
        if impression_match:
            impression = impression_match.group(1).strip()
            return impression[:200] + "..." if len(impression) > 200 else impression
        
        findings_match = re.search(r'findings[:\s]*(.*?)(?=impression|$)', content, re.IGNORECASE | re.DOTALL)
        if findings_match:
            findings = findings_match.group(1).strip()
            return findings[:200] + "..." if len(findings) > 200 else findings
        
        # Fallback
        return content[:150] + "..." if len(content) > 150 else content
    
    def _extract_consult_summary(self, content: str) -> str:
        """Extract key information from consultation notes."""
        
        # Look for assessment or plan sections
        import re
        
        assessment_match = re.search(r'assessment[:\s]*(.*?)(?=plan|$)', content, re.IGNORECASE | re.DOTALL)
        if assessment_match:
            assessment = assessment_match.group(1).strip()
            return assessment[:200] + "..." if len(assessment) > 200 else assessment
        
        plan_match = re.search(r'plan[:\s]*(.*?)(?=\n|$)', content, re.IGNORECASE | re.DOTALL)
        if plan_match:
            plan = plan_match.group(1).strip()
            return plan[:200] + "..." if len(plan) > 200 else plan
        
        # Fallback
        return content[:150] + "..." if len(content) > 150 else content
    
    def _get_confidence_css_class(self, confidence_score: Optional[float]) -> str:
        """Get CSS class for confidence score display."""
        
        if confidence_score is None:
            return 'confidence-unknown'
        
        confidence_pct = confidence_score * 100 if confidence_score <= 1 else confidence_score
        
        if confidence_pct >= 80:
            return 'confidence-high'
        elif confidence_pct >= 60:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def _get_status_css_class(self, status: str) -> str:
        """Get CSS class for screening status display."""
        
        status_classes = {
            'Complete': 'status-complete',
            'Due Soon': 'status-due-soon',
            'Due': 'status-due',
            'Overdue': 'status-overdue'
        }
        
        return status_classes.get(status, 'status-unknown')
    
    def _get_cutoff_settings(self) -> ChecklistSettings:
        """Get current cutoff settings or create defaults."""
        
        settings = ChecklistSettings.query.first()
        
        if not settings:
            settings = ChecklistSettings(
                labs_cutoff_months=12,
                imaging_cutoff_months=24,
                consults_cutoff_months=12,
                hospital_cutoff_months=36
            )
            db.session.add(settings)
            db.session.commit()
        
        return settings
    
    def _generate_metadata(self) -> Dict[str, Any]:
        """Generate prep sheet metadata."""
        
        return {
            'generated_at': datetime.now().isoformat(),
            'generated_by': 'HealthPrep System',
            'version': '2.0',
            'generation_time_ms': None,  # Would be calculated in actual implementation
            'data_sources': ['EMR Documents', 'Screening Engine', 'Patient Conditions'],
            'filters_applied': ['PHI Filtering', 'Date Cutoffs', 'Relevancy Scoring']
        }
