"""
Frequency and cutoff filtering logic for prep sheets
Handles data filtering based on time periods and screening frequencies
"""
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from models import Document, Screening, ScreeningType, ChecklistSettings

class PrepSheetFilters:
    """Handles filtering logic for prep sheet data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def apply_document_filters(self, documents: List[Document], cutoff_months: int) -> List[Document]:
        """Filter documents based on cutoff period"""
        try:
            if not documents or cutoff_months <= 0:
                return documents
            
            cutoff_date = datetime.utcnow() - relativedelta(months=cutoff_months)
            
            filtered_docs = [doc for doc in documents if doc.date_created >= cutoff_date]
            
            self.logger.debug(f"Filtered {len(documents)} documents to {len(filtered_docs)} within {cutoff_months} months")
            
            return filtered_docs
            
        except Exception as e:
            self.logger.error(f"Error applying document filters: {str(e)}")
            return documents
    
    def apply_screening_frequency_filter(self, screening: Screening, documents: List[Document]) -> List[Document]:
        """Filter documents based on screening frequency requirements"""
        try:
            if not screening.screening_type or not documents:
                return documents
            
            screening_type = screening.screening_type
            
            # Calculate the screening cycle cutoff date
            cutoff_date = self._calculate_screening_cutoff_date(screening_type)
            
            if not cutoff_date:
                return documents  # No filtering if no frequency defined
            
            # Filter documents to only show those from the current screening cycle
            filtered_docs = [doc for doc in documents if doc.date_created >= cutoff_date]
            
            self.logger.debug(f"Applied frequency filter for {screening_type.name}: {len(documents)} -> {len(filtered_docs)} documents")
            
            return filtered_docs
            
        except Exception as e:
            self.logger.error(f"Error applying screening frequency filter: {str(e)}")
            return documents
    
    def _calculate_screening_cutoff_date(self, screening_type: ScreeningType) -> Optional[datetime]:
        """Calculate cutoff date based on screening frequency"""
        try:
            now = datetime.utcnow()
            
            if screening_type.frequency_years:
                return now - relativedelta(years=screening_type.frequency_years)
            elif screening_type.frequency_months:
                return now - relativedelta(months=screening_type.frequency_months)
            else:
                # Default to 1 year if no frequency specified
                return now - relativedelta(years=1)
                
        except Exception as e:
            self.logger.error(f"Error calculating screening cutoff date: {str(e)}")
            return None
    
    def filter_relevant_documents(self, patient_id: int, document_type: str, cutoff_months: int) -> List[Dict[str, Any]]:
        """Get relevant documents for a patient filtered by type and cutoff"""
        try:
            cutoff_date = datetime.utcnow() - relativedelta(months=cutoff_months)
            
            documents = Document.query.filter(
                Document.patient_id == patient_id,
                Document.document_type == document_type,
                Document.date_created >= cutoff_date
            ).order_by(Document.date_created.desc()).all()
            
            # Convert to dict format for template use
            doc_list = []
            for doc in documents:
                doc_list.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "date_created": doc.date_created,
                    "date_formatted": doc.date_created.strftime("%m/%d/%Y"),
                    "ocr_confidence": doc.ocr_confidence or 0,
                    "confidence_class": self._get_confidence_class(doc.ocr_confidence),
                    "has_text": bool(doc.ocr_text),
                    "text_preview": self._get_text_preview(doc.ocr_text),
                    "document_type": doc.document_type
                })
            
            return doc_list
            
        except Exception as e:
            self.logger.error(f"Error filtering relevant documents: {str(e)}")
            return []
    
    def get_screening_documents_in_cycle(self, screening_id: int) -> List[Dict[str, Any]]:
        """Get documents relevant to a screening within its current cycle"""
        try:
            screening = Screening.query.get(screening_id)
            if not screening:
                return []
            
            # Get matched documents
            matched_docs = []
            if screening.matched_documents:
                try:
                    import json
                    doc_ids = json.loads(screening.matched_documents)
                    matched_docs = Document.query.filter(Document.id.in_(doc_ids)).all()
                except:
                    pass
            
            # Apply frequency filtering
            filtered_docs = self.apply_screening_frequency_filter(screening, matched_docs)
            
            # Convert to dict format
            doc_list = []
            for doc in filtered_docs:
                doc_list.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "date_created": doc.date_created,
                    "date_formatted": doc.date_created.strftime("%m/%d/%Y"),
                    "ocr_confidence": doc.ocr_confidence or 0,
                    "confidence_class": self._get_confidence_class(doc.ocr_confidence),
                    "relevancy_score": self._calculate_relevancy_score(doc, screening.screening_type),
                    "is_recent": self._is_recent_document(doc, 30)  # Recent if within 30 days
                })
            
            # Sort by relevancy and recency
            doc_list.sort(key=lambda x: (x["relevancy_score"], x["is_recent"]), reverse=True)
            
            return doc_list
            
        except Exception as e:
            self.logger.error(f"Error getting screening documents in cycle: {str(e)}")
            return []
    
    def apply_prep_sheet_cutoffs(self, patient_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Apply all prep sheet cutoffs and return filtered medical data"""
        try:
            # Get settings
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()  # Use defaults
            
            filtered_data = {}
            
            # Apply cutoffs for each data type
            data_types = {
                'labs': settings.labs_cutoff_months,
                'imaging': settings.imaging_cutoff_months,
                'consults': settings.consults_cutoff_months,
                'hospital': settings.hospital_cutoff_months
            }
            
            for doc_type, cutoff_months in data_types.items():
                filtered_data[doc_type] = self.filter_relevant_documents(
                    patient_id, doc_type, cutoff_months
                )
            
            return filtered_data
            
        except Exception as e:
            self.logger.error(f"Error applying prep sheet cutoffs: {str(e)}")
            return {}
    
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
    
    def _get_text_preview(self, ocr_text: Optional[str], max_length: int = 150) -> str:
        """Get preview of OCR text"""
        if not ocr_text:
            return "No text available"
        
        if len(ocr_text) <= max_length:
            return ocr_text
        
        return ocr_text[:max_length] + "..."
    
    def _calculate_relevancy_score(self, document: Document, screening_type: ScreeningType) -> float:
        """Calculate document relevancy score for a screening type"""
        try:
            score = 0.0
            
            # Score based on keyword matching
            if screening_type.keywords and document.ocr_text:
                keywords = screening_type.keywords.lower().split('\n')
                text_lower = document.ocr_text.lower()
                
                matched_keywords = sum(1 for kw in keywords if kw.strip() in text_lower)
                if keywords:
                    score += (matched_keywords / len(keywords)) * 0.5
            
            # Score based on filename matching
            if screening_type.keywords and document.filename:
                keywords = screening_type.keywords.lower().split('\n')
                filename_lower = document.filename.lower()
                
                matched_in_filename = sum(1 for kw in keywords if kw.strip() in filename_lower)
                if keywords:
                    score += (matched_in_filename / len(keywords)) * 0.3
            
            # Score based on OCR confidence
            if document.ocr_confidence:
                score += (document.ocr_confidence / 100) * 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating relevancy score: {str(e)}")
            return 0.0
    
    def _is_recent_document(self, document: Document, days_threshold: int = 30) -> bool:
        """Check if document is recent"""
        try:
            threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
            return document.date_created >= threshold_date
        except:
            return False
    
    def get_filter_summary(self, patient_id: int) -> Dict[str, Any]:
        """Get summary of applied filters for a patient"""
        try:
            settings = ChecklistSettings.query.first()
            if not settings:
                settings = ChecklistSettings()
            
            # Count documents in each category
            total_counts = {}
            filtered_counts = {}
            
            data_types = {
                'labs': settings.labs_cutoff_months,
                'imaging': settings.imaging_cutoff_months,
                'consults': settings.consults_cutoff_months,
                'hospital': settings.hospital_cutoff_months
            }
            
            for doc_type, cutoff_months in data_types.items():
                # Total documents
                total_counts[doc_type] = Document.query.filter(
                    Document.patient_id == patient_id,
                    Document.document_type == doc_type
                ).count()
                
                # Filtered documents
                cutoff_date = datetime.utcnow() - relativedelta(months=cutoff_months)
                filtered_counts[doc_type] = Document.query.filter(
                    Document.patient_id == patient_id,
                    Document.document_type == doc_type,
                    Document.date_created >= cutoff_date
                ).count()
            
            return {
                "settings": {
                    "labs_cutoff_months": settings.labs_cutoff_months,
                    "imaging_cutoff_months": settings.imaging_cutoff_months,
                    "consults_cutoff_months": settings.consults_cutoff_months,
                    "hospital_cutoff_months": settings.hospital_cutoff_months
                },
                "document_counts": {
                    "total": total_counts,
                    "filtered": filtered_counts,
                    "reduction": {
                        doc_type: total_counts[doc_type] - filtered_counts[doc_type]
                        for doc_type in data_types.keys()
                    }
                },
                "total_reduction": sum(total_counts.values()) - sum(filtered_counts.values())
            }
            
        except Exception as e:
            self.logger.error(f"Error getting filter summary: {str(e)}")
            return {"error": str(e)}
