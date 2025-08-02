"""
Prep sheet generation and rendering
Assembles medical data into comprehensive preparation sheets
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from models import Patient, Screening, Document, Condition, ChecklistSettings, db
from prep_sheet.filters import PrepSheetFilters

class PrepSheetGenerator:
    """Generates comprehensive medical preparation sheets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filters = PrepSheetFilters()
    
    def generate_prep_sheet(self, patient_id: int) -> Dict[str, Any]:
        """Generate a complete preparation sheet for a patient"""
        try:
            patient = Patient.query.get(patient_id)
            if not patient:
                return {"error": "Patient not found"}
            
            # Get checklist settings for data cutoffs
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()  # Use defaults
            
            prep_sheet = {
                "patient_header": self._generate_patient_header(patient),
                "patient_summary": self._generate_patient_summary(patient),
                "medical_data": self._generate_medical_data(patient, settings),
                "quality_checklist": self._generate_quality_checklist(patient),
                "enhanced_data": self._generate_enhanced_data(patient, settings),
                "generated_at": datetime.utcnow().isoformat(),
                "settings_used": {
                    "labs_cutoff_months": settings.labs_cutoff_months,
                    "imaging_cutoff_months": settings.imaging_cutoff_months,
                    "consults_cutoff_months": settings.consults_cutoff_months,
                    "hospital_cutoff_months": settings.hospital_cutoff_months
                }
            }
            
            return prep_sheet
            
        except Exception as e:
            self.logger.error(f"Error generating prep sheet for patient {patient_id}: {str(e)}")
            return {"error": str(e)}
    
    def _generate_patient_header(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient header information"""
        try:
            # Calculate last visit date
            last_visit = None
            visit_documents = Document.query.filter_by(
                patient_id=patient.id,
                document_type='consult'
            ).order_by(Document.date_created.desc()).first()
            
            if visit_documents:
                last_visit = visit_documents.date_created
            
            return {
                "name": patient.full_name,
                "mrn": patient.mrn,
                "date_of_birth": patient.date_of_birth.strftime("%m/%d/%Y") if patient.date_of_birth else "N/A",
                "age": patient.age,
                "gender": patient.gender,
                "last_visit": last_visit.strftime("%m/%d/%Y") if last_visit else "N/A",
                "prep_date": datetime.utcnow().strftime("%m/%d/%Y"),
                "contact_info": {
                    "phone": patient.phone or "N/A",
                    "email": patient.email or "N/A",
                    "address": patient.address or "N/A"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating patient header: {str(e)}")
            return {"error": str(e)}
    
    def _generate_patient_summary(self, patient: Patient) -> Dict[str, Any]:
        """Generate patient summary section"""
        try:
            # Recent appointments/visits
            recent_visits = Document.query.filter_by(
                patient_id=patient.id,
                document_type='consult'
            ).filter(
                Document.date_created >= datetime.utcnow() - timedelta(days=90)
            ).order_by(Document.date_created.desc()).limit(5).all()
            
            # Active conditions
            active_conditions = Condition.query.filter_by(
                patient_id=patient.id,
                is_active=True
            ).order_by(Condition.diagnosis_date.desc()).all()
            
            return {
                "recent_visits": [
                    {
                        "date": visit.date_created.strftime("%m/%d/%Y"),
                        "type": "Consultation",
                        "document": visit.filename
                    } for visit in recent_visits
                ],
                "active_conditions": [
                    {
                        "condition": condition.condition_name,
                        "icd_code": condition.icd_code or "N/A",
                        "diagnosis_date": condition.diagnosis_date.strftime("%m/%d/%Y") if condition.diagnosis_date else "N/A",
                        "notes": condition.notes or ""
                    } for condition in active_conditions
                ],
                "total_active_conditions": len(active_conditions)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating patient summary: {str(e)}")
            return {"error": str(e)}
    
    def _generate_medical_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate recent medical data sections"""
        try:
            medical_data = {}
            
            # Recent lab results
            labs_cutoff = datetime.utcnow() - timedelta(days=30 * settings.labs_cutoff_months)
            recent_labs = Document.query.filter(
                Document.patient_id == patient.id,
                Document.document_type == 'lab',
                Document.date_created >= labs_cutoff
            ).order_by(Document.date_created.desc()).limit(10).all()
            
            medical_data["labs"] = [
                {
                    "test_name": self._extract_test_name(lab.filename),
                    "date": lab.date_created.strftime("%m/%d/%Y"),
                    "results": self._extract_lab_results(lab.ocr_text) if lab.ocr_text else "See document",
                    "document_id": lab.id,
                    "filename": lab.filename
                } for lab in recent_labs
            ]
            
            # Recent imaging studies
            imaging_cutoff = datetime.utcnow() - timedelta(days=30 * settings.imaging_cutoff_months)
            recent_imaging = Document.query.filter(
                Document.patient_id == patient.id,
                Document.document_type == 'imaging',
                Document.date_created >= imaging_cutoff
            ).order_by(Document.date_created.desc()).limit(10).all()
            
            medical_data["imaging"] = [
                {
                    "study_type": self._extract_study_type(img.filename),
                    "date": img.date_created.strftime("%m/%d/%Y"),
                    "body_site": self._extract_body_site(img.ocr_text) if img.ocr_text else "N/A",
                    "impression": self._extract_impression(img.ocr_text) if img.ocr_text else "See document",
                    "document_id": img.id,
                    "filename": img.filename
                } for img in recent_imaging
            ]
            
            # Recent specialist consults
            consults_cutoff = datetime.utcnow() - timedelta(days=30 * settings.consults_cutoff_months)
            recent_consults = Document.query.filter(
                Document.patient_id == patient.id,
                Document.document_type == 'consult',
                Document.date_created >= consults_cutoff
            ).order_by(Document.date_created.desc()).limit(10).all()
            
            medical_data["consults"] = [
                {
                    "specialty": self._extract_specialty(consult.filename),
                    "date": consult.date_created.strftime("%m/%d/%Y"),
                    "specialist": self._extract_specialist(consult.ocr_text) if consult.ocr_text else "N/A",
                    "recommendations": self._extract_recommendations(consult.ocr_text) if consult.ocr_text else "See document",
                    "document_id": consult.id,
                    "filename": consult.filename
                } for consult in recent_consults
            ]
            
            # Recent hospital stays
            hospital_cutoff = datetime.utcnow() - timedelta(days=30 * settings.hospital_cutoff_months)
            recent_hospital = Document.query.filter(
                Document.patient_id == patient.id,
                Document.document_type == 'hospital',
                Document.date_created >= hospital_cutoff
            ).order_by(Document.date_created.desc()).limit(10).all()
            
            medical_data["hospital_stays"] = [
                {
                    "hospital": self._extract_hospital_name(hosp.filename),
                    "admission_date": hosp.date_created.strftime("%m/%d/%Y"),
                    "discharge_date": self._extract_discharge_date(hosp.ocr_text) if hosp.ocr_text else "N/A",
                    "diagnosis": self._extract_hospital_diagnosis(hosp.ocr_text) if hosp.ocr_text else "See document",
                    "document_id": hosp.id,
                    "filename": hosp.filename
                } for hosp in recent_hospital
            ]
            
            return medical_data
            
        except Exception as e:
            self.logger.error(f"Error generating medical data: {str(e)}")
            return {"error": str(e)}
    
    def _generate_quality_checklist(self, patient: Patient) -> Dict[str, Any]:
        """Generate quality checklist with screening statuses"""
        try:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            
            checklist_items = []
            for screening in screenings:
                # Get matched documents for this screening
                matched_docs = []
                if screening.matched_documents:
                    try:
                        import json
                        doc_ids = json.loads(screening.matched_documents)
                        matched_docs = Document.query.filter(Document.id.in_(doc_ids)).all()
                    except:
                        pass
                
                checklist_items.append({
                    "screening_name": screening.screening_type.name,
                    "status": screening.status,
                    "last_completed": screening.last_completed_date.strftime("%m/%d/%Y") if screening.last_completed_date else "N/A",
                    "frequency": self._format_frequency(screening.screening_type),
                    "next_due": screening.next_due_date.strftime("%m/%d/%Y") if screening.next_due_date else "N/A",
                    "matched_documents": [
                        {
                            "id": doc.id,
                            "filename": doc.filename,
                            "date": doc.date_created.strftime("%m/%d/%Y"),
                            "confidence": doc.ocr_confidence or 0
                        } for doc in matched_docs
                    ],
                    "status_badge_class": self._get_status_badge_class(screening.status)
                })
            
            # Sort by status priority (due first, then due_soon, then complete)
            status_priority = {"due": 1, "due_soon": 2, "complete": 3}
            checklist_items.sort(key=lambda x: status_priority.get(x["status"], 4))
            
            return {
                "screenings": checklist_items,
                "total_screenings": len(checklist_items),
                "due_count": len([s for s in checklist_items if s["status"] == "due"]),
                "due_soon_count": len([s for s in checklist_items if s["status"] == "due_soon"]),
                "complete_count": len([s for s in checklist_items if s["status"] == "complete"])
            }
            
        except Exception as e:
            self.logger.error(f"Error generating quality checklist: {str(e)}")
            return {"error": str(e)}
    
    def _generate_enhanced_data(self, patient: Patient, settings: ChecklistSettings) -> Dict[str, Any]:
        """Generate enhanced medical data with document integration"""
        try:
            enhanced_data = {}
            
            # Get all documents within cutoff periods
            cutoff_dates = {
                'labs': datetime.utcnow() - timedelta(days=30 * settings.labs_cutoff_months),
                'imaging': datetime.utcnow() - timedelta(days=30 * settings.imaging_cutoff_months),
                'consults': datetime.utcnow() - timedelta(days=30 * settings.consults_cutoff_months),
                'hospital': datetime.utcnow() - timedelta(days=30 * settings.hospital_cutoff_months)
            }
            
            for doc_type, cutoff_date in cutoff_dates.items():
                documents = Document.query.filter(
                    Document.patient_id == patient.id,
                    Document.document_type == doc_type,
                    Document.date_created >= cutoff_date
                ).order_by(Document.date_created.desc()).all()
                
                enhanced_data[doc_type] = [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "date": doc.date_created.strftime("%m/%d/%Y"),
                        "confidence": doc.ocr_confidence or 0,
                        "confidence_class": self._get_confidence_class(doc.ocr_confidence),
                        "has_text": bool(doc.ocr_text),
                        "text_preview": doc.ocr_text[:200] + "..." if doc.ocr_text and len(doc.ocr_text) > 200 else doc.ocr_text or "",
                        "relevancy_score": self._calculate_document_relevancy(doc)
                    } for doc in documents
                ]
            
            return enhanced_data
            
        except Exception as e:
            self.logger.error(f"Error generating enhanced data: {str(e)}")
            return {"error": str(e)}
    
    def _extract_test_name(self, filename: str) -> str:
        """Extract test name from lab document filename"""
        # Simple extraction - in production, this would be more sophisticated
        if 'cbc' in filename.lower():
            return "Complete Blood Count"
        elif 'cmp' in filename.lower():
            return "Comprehensive Metabolic Panel"
        elif 'lipid' in filename.lower():
            return "Lipid Panel"
        elif 'a1c' in filename.lower():
            return "Hemoglobin A1C"
        else:
            return filename.replace('.pdf', '').replace('_', ' ').title()
    
    def _extract_lab_results(self, ocr_text: str) -> str:
        """Extract key lab results from OCR text"""
        if not ocr_text:
            return "See document"
        
        # Look for common lab values
        import re
        results = []
        
        # Glucose
        glucose_match = re.search(r'glucose[:\s]*(\d{2,4})\s*(?:mg/dl)?', ocr_text, re.IGNORECASE)
        if glucose_match:
            results.append(f"Glucose: {glucose_match.group(1)} mg/dL")
        
        # A1C
        a1c_match = re.search(r'a1c[:\s]*(\d+\.\d+)%?', ocr_text, re.IGNORECASE)
        if a1c_match:
            results.append(f"A1C: {a1c_match.group(1)}%")
        
        # Cholesterol
        chol_match = re.search(r'cholesterol[:\s]*(\d{2,4})\s*(?:mg/dl)?', ocr_text, re.IGNORECASE)
        if chol_match:
            results.append(f"Cholesterol: {chol_match.group(1)} mg/dL")
        
        return "; ".join(results) if results else "See document for details"
    
    def _extract_study_type(self, filename: str) -> str:
        """Extract imaging study type from filename"""
        filename_lower = filename.lower()
        if 'mammogram' in filename_lower or 'mammo' in filename_lower:
            return "Mammogram"
        elif 'ct' in filename_lower:
            return "CT Scan"
        elif 'mri' in filename_lower:
            return "MRI"
        elif 'xray' in filename_lower or 'x-ray' in filename_lower:
            return "X-Ray"
        elif 'ultrasound' in filename_lower:
            return "Ultrasound"
        else:
            return filename.replace('.pdf', '').replace('_', ' ').title()
    
    def _extract_body_site(self, ocr_text: str) -> str:
        """Extract body site from imaging report"""
        if not ocr_text:
            return "N/A"
        
        # Look for common body sites
        import re
        sites = ['chest', 'abdomen', 'pelvis', 'head', 'brain', 'spine', 'extremity', 'breast']
        
        for site in sites:
            if re.search(rf'\b{site}\b', ocr_text, re.IGNORECASE):
                return site.title()
        
        return "N/A"
    
    def _extract_impression(self, ocr_text: str) -> str:
        """Extract impression from imaging report"""
        if not ocr_text:
            return "See document"
        
        # Look for impression section
        import re
        impression_match = re.search(r'impression[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)', ocr_text, re.IGNORECASE | re.DOTALL)
        
        if impression_match:
            impression = impression_match.group(1).strip()
            return impression[:200] + "..." if len(impression) > 200 else impression
        
        return "See document for impression"
    
    def _extract_specialty(self, filename: str) -> str:
        """Extract medical specialty from consult filename"""
        filename_lower = filename.lower()
        specialties = {
            'cardio': 'Cardiology',
            'neuro': 'Neurology',
            'ortho': 'Orthopedics',
            'derm': 'Dermatology',
            'endo': 'Endocrinology',
            'gastro': 'Gastroenterology',
            'pulm': 'Pulmonology',
            'oncol': 'Oncology'
        }
        
        for key, specialty in specialties.items():
            if key in filename_lower:
                return specialty
        
        return "General Medicine"
    
    def _extract_specialist(self, ocr_text: str) -> str:
        """Extract specialist name from consult report"""
        if not ocr_text:
            return "N/A"
        
        # Look for doctor names
        import re
        doctor_match = re.search(r'dr\.?\s+([a-z]+\s+[a-z]+)', ocr_text, re.IGNORECASE)
        
        if doctor_match:
            return f"Dr. {doctor_match.group(1).title()}"
        
        return "See document"
    
    def _extract_recommendations(self, ocr_text: str) -> str:
        """Extract recommendations from consult report"""
        if not ocr_text:
            return "See document"
        
        # Look for recommendations section
        import re
        rec_match = re.search(r'recommend(?:ation)?s?[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)', ocr_text, re.IGNORECASE | re.DOTALL)
        
        if rec_match:
            recommendations = rec_match.group(1).strip()
            return recommendations[:200] + "..." if len(recommendations) > 200 else recommendations
        
        return "See document for recommendations"
    
    def _extract_hospital_name(self, filename: str) -> str:
        """Extract hospital name from filename"""
        # Simple extraction - would be more sophisticated in production
        return filename.replace('.pdf', '').replace('_', ' ').title()
    
    def _extract_discharge_date(self, ocr_text: str) -> str:
        """Extract discharge date from hospital document"""
        if not ocr_text:
            return "N/A"
        
        import re
        date_match = re.search(r'discharge(?:d?).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', ocr_text, re.IGNORECASE)
        
        if date_match:
            return date_match.group(1)
        
        return "N/A"
    
    def _extract_hospital_diagnosis(self, ocr_text: str) -> str:
        """Extract primary diagnosis from hospital document"""
        if not ocr_text:
            return "See document"
        
        import re
        diag_match = re.search(r'(?:primary\s+)?diagnos[ie]s[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)', ocr_text, re.IGNORECASE | re.DOTALL)
        
        if diag_match:
            diagnosis = diag_match.group(1).strip()
            return diagnosis[:200] + "..." if len(diagnosis) > 200 else diagnosis
        
        return "See document for diagnosis"
    
    def _format_frequency(self, screening_type) -> str:
        """Format screening frequency for display"""
        if screening_type.frequency_years:
            years = screening_type.frequency_years
            return f"Every {years} year{'s' if years > 1 else ''}"
        elif screening_type.frequency_months:
            months = screening_type.frequency_months
            if months == 12:
                return "Annually"
            elif months == 6:
                return "Every 6 months"
            elif months == 3:
                return "Quarterly"
            else:
                return f"Every {months} months"
        else:
            return "As needed"
    
    def _get_status_badge_class(self, status: str) -> str:
        """Get Bootstrap badge class for screening status"""
        status_classes = {
            "due": "badge bg-danger",
            "due_soon": "badge bg-warning text-dark",
            "complete": "badge bg-success"
        }
        return status_classes.get(status, "badge bg-secondary")
    
    def _get_confidence_class(self, confidence: Optional[float]) -> str:
        """Get CSS class for OCR confidence level"""
        if not confidence:
            return "confidence-low"
        
        if confidence >= 80:
            return "confidence-high"
        elif confidence >= 60:
            return "confidence-medium"
        else:
            return "confidence-low"
    
    def _calculate_document_relevancy(self, document: Document) -> float:
        """Calculate document relevancy score for prep sheet"""
        score = 0.5  # Base score
        
        # Boost score for recent documents
        days_old = (datetime.utcnow() - document.date_created).days
        if days_old <= 30:
            score += 0.3
        elif days_old <= 90:
            score += 0.2
        elif days_old <= 180:
            score += 0.1
        
        # Boost score for high OCR confidence
        if document.ocr_confidence:
            score += (document.ocr_confidence / 100) * 0.2
        
        # Boost score for documents with text content
        if document.ocr_text and len(document.ocr_text) > 100:
            score += 0.1
        
        return min(score, 1.0)
