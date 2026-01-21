"""
Frequency and cutoff filtering logic for prep sheets
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from app import db
from models import Document, FHIRDocument, Screening, ScreeningType
from utils.document_types import get_prep_sheet_category
import logging

class PrepSheetFilters:
    """Handles filtering of medical data for prep sheets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def filter_documents_by_frequency(self, documents, screening_type, last_completed_date=None):
        """
        Filter documents to only show those within the last frequency period
        
        Formula implementation:
        - cutoff_date = last_completed - relativedelta(years/months=frequency_number)  
        - Only show documents created after the cutoff date
        - Documents older than one frequency cycle are filtered out
        """
        if not screening_type.frequency_value or not screening_type.frequency_unit:
            return documents
        
        # Calculate cutoff date using the specified formula
        cutoff_date = self._calculate_frequency_cutoff_from_last_completed(
            screening_type.frequency_value,
            screening_type.frequency_unit,
            last_completed_date
        )
        
        # Filter: only show documents created after the cutoff date
        filtered_docs = []
        for doc in documents:
            if hasattr(doc, 'document_date') and doc.document_date:
                # Convert document_date to date if it's datetime
                doc_date = doc.document_date.date() if hasattr(doc.document_date, 'date') else doc.document_date
                
                # Only include documents newer than cutoff (within last frequency period)
                if doc_date >= cutoff_date:
                    filtered_docs.append(doc)
        
        return filtered_docs
    
    def apply_data_cutoffs(self, patient_id, cutoff_settings):
        """Apply data cutoffs to all document types (both Document and FHIRDocument)"""
        filtered_data = {}
        
        document_types = ['lab', 'imaging', 'consult', 'hospital']
        
        for doc_type in document_types:
            cutoff_months = getattr(cutoff_settings, f"{doc_type}_cutoff_months", 12)
            cutoff_date = self._calculate_cutoff_date(cutoff_months)
            
            all_docs = self._get_documents_for_category(patient_id, doc_type, cutoff_date)
            
            filtered_data[f"{doc_type}_documents"] = all_docs
            filtered_data[f"{doc_type}_cutoff_date"] = cutoff_date
            filtered_data[f"{doc_type}_count"] = len(all_docs)
        
        return filtered_data
    
    def _get_documents_for_category(self, patient_id, category, cutoff_date, keywords=None):
        """
        Get documents (both Document and FHIRDocument) for a category with date filtering.
        
        Args:
            patient_id: Patient ID
            category: Document category (lab, imaging, consult, hospital)
            cutoff_date: Only include documents on or after this date
            keywords: Optional list of keywords to filter by
            
        Returns:
            List of document-like objects (unified interface for templates)
        """
        all_docs = []
        
        manual_docs = Document.query.filter_by(
            patient_id=patient_id,
            document_type=category
        ).filter(
            Document.document_date.isnot(None),
            Document.document_date >= cutoff_date
        ).order_by(Document.document_date.desc()).all()
        all_docs.extend(manual_docs)
        
        fhir_docs_query = FHIRDocument.query.filter_by(patient_id=patient_id).filter(
            FHIRDocument.document_date.isnot(None),
            FHIRDocument.document_date >= cutoff_date
        ).order_by(FHIRDocument.document_date.desc()).all()
        
        for fhir_doc in fhir_docs_query:
            doc_category = get_prep_sheet_category(
                fhir_doc.document_type_code, 
                fhir_doc.document_type_display
            )
            if doc_category == category:
                all_docs.append(fhir_doc)
        
        if keywords and len(keywords) > 0:
            all_docs = self._apply_keyword_filter(all_docs, keywords)
        
        all_docs.sort(key=lambda d: d.document_date if d.document_date else date.min, reverse=True)
        
        return all_docs
    
    def _apply_keyword_filter(self, documents, keywords):
        """Apply keyword filtering to a list of documents (Document or FHIRDocument)"""
        if not keywords:
            return documents
        
        keywords_lower = [k.lower() for k in keywords]
        filtered_docs = []
        
        for doc in documents:
            if hasattr(doc, 'search_title'):
                search_text = ' '.join([
                    (doc.search_title or '').lower(),
                    (doc.ocr_text or '').lower()
                ])
            else:
                search_text = ' '.join([
                    (getattr(doc, 'title', '') or '').lower(),
                    (getattr(doc, 'description', '') or '').lower(),
                    (getattr(doc, 'filename', '') or '').lower(),
                    (doc.ocr_text or '').lower()
                ])
            
            if any(kw in search_text for kw in keywords_lower):
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def filter_screening_documents(self, screening_id):
        """Filter documents for a specific screening based on its frequency from last completed date"""
        screening = Screening.query.get(screening_id)
        if not screening:
            return []
        
        patient_docs = self._get_all_patient_documents(screening.patient_id)
        
        filtered_docs = self.filter_documents_by_frequency(
            patient_docs, 
            screening.screening_type,
            screening.last_completed
        )
        
        return filtered_docs
    
    def get_relevant_documents(self, patient_id, screening_type_name, last_completed_date=None):
        """Get documents relevant to a specific screening type"""
        screening_type = ScreeningType.query.filter_by(name=screening_type_name).first()
        if not screening_type:
            return []
        
        all_docs = self._get_all_patient_documents(patient_id)
        
        frequency_filtered = self.filter_documents_by_frequency(
            all_docs, 
            screening_type, 
            last_completed_date
        )
        
        keyword_filtered = self._filter_by_keywords(frequency_filtered, screening_type)
        
        return keyword_filtered
    
    def _get_all_patient_documents(self, patient_id):
        """Get all documents (Document + FHIRDocument) for a patient"""
        all_docs = []
        
        manual_docs = Document.query.filter_by(patient_id=patient_id).all()
        all_docs.extend(manual_docs)
        
        fhir_docs = FHIRDocument.query.filter_by(patient_id=patient_id).all()
        all_docs.extend(fhir_docs)
        
        return all_docs
    
    def _filter_by_keywords(self, documents, screening_type):
        """Filter documents by screening type keywords (supports both Document and FHIRDocument)"""
        if not screening_type.keywords_list:
            return documents
        
        keywords = [k.lower() for k in screening_type.keywords_list]
        relevant_docs = []
        
        for doc in documents:
            if hasattr(doc, 'search_title'):
                search_text = ' '.join([
                    (doc.search_title or '').lower(),
                    (doc.ocr_text or '').lower()
                ])
            else:
                search_text = ' '.join([
                    (getattr(doc, 'title', '') or '').lower(),
                    (getattr(doc, 'description', '') or '').lower(),
                    (getattr(doc, 'filename', '') or '').lower(),
                    (doc.ocr_text or '').lower()
                ])
            
            for keyword in keywords:
                if keyword in search_text:
                    relevant_docs.append(doc)
                    break
        
        return relevant_docs
    
    def _calculate_frequency_cutoff(self, frequency_value, frequency_unit):
        """Calculate cutoff date based on frequency from today"""
        today = date.today()
        
        if frequency_unit == 'years':
            cutoff_date = today - relativedelta(years=frequency_value)
        elif frequency_unit == 'months':
            cutoff_date = today - relativedelta(months=frequency_value)
        else:
            # Default to years
            cutoff_date = today - relativedelta(years=frequency_value)
        
        return cutoff_date
    
    def _calculate_frequency_cutoff_from_last_completed(self, frequency_value, frequency_unit, last_completed_date):
        """
        Calculate cutoff date for document relevancy based on screening frequency
        Formula: cutoff_date = last_completed - relativedelta(years/months=frequency_number)
        Only show documents created after the cutoff date
        """
        # If no last completed date, use today as reference and go back one frequency period
        if not last_completed_date:
            return self._calculate_frequency_cutoff(frequency_value, frequency_unit)
        
        # Convert to date if it's a datetime
        if hasattr(last_completed_date, 'date'):
            reference_date = last_completed_date.date()
        else:
            reference_date = last_completed_date
        
        # Calculate cutoff date: last_completed - frequency_period
        # This shows documents within the last frequency cycle from last completed
        if frequency_unit == 'years':
            cutoff_date = reference_date - relativedelta(years=frequency_value)
        elif frequency_unit == 'months':
            cutoff_date = reference_date - relativedelta(months=frequency_value)
        else:
            # Default to years if unit is unclear
            cutoff_date = reference_date - relativedelta(years=frequency_value)
        
        return cutoff_date
    
    def _calculate_cutoff_date(self, months):
        """Calculate cutoff date based on months"""
        return date.today() - relativedelta(months=months)
    
    def get_document_relevancy_score(self, document, screening_type):
        """Calculate relevancy score for a document to a screening type (supports Document and FHIRDocument)"""
        if not document.ocr_text:
            return 0.0
        
        score = 0.0
        
        if hasattr(document, 'search_title'):
            search_text = f"{document.search_title or ''} {document.ocr_text}".lower()
        else:
            search_text = f"{getattr(document, 'filename', '') or ''} {document.ocr_text}".lower()
        
        keywords = screening_type.keywords_list if screening_type.keywords_list else []
        for keyword in keywords:
            if keyword.lower() in search_text:
                score += 0.3
        
        type_scores = {
            ('lab', 'a1c'): 0.4,
            ('lab', 'cholesterol'): 0.4,
            ('lab', 'glucose'): 0.4,
            ('imaging', 'mammogram'): 0.4,
            ('imaging', 'dxa'): 0.4,
            ('imaging', 'dexa'): 0.4,
            ('consult', 'cardiology'): 0.4,
            ('consult', 'oncology'): 0.4
        }
        
        doc_category = None
        if hasattr(document, 'document_type_code'):
            doc_category = get_prep_sheet_category(document.document_type_code, document.document_type_display)
        elif hasattr(document, 'document_type'):
            doc_category = document.document_type
        
        if doc_category:
            for (doc_type, screening_term), points in type_scores.items():
                if (doc_category == doc_type and 
                    screening_term in screening_type.name.lower()):
                    score += points
        
        # Recency bonus (more recent = higher score)
        if document.document_date:
            days_ago = (date.today() - document.document_date).days
            if days_ago <= 30:
                score += 0.2
            elif days_ago <= 90:
                score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def apply_smart_filtering(self, patient_id, screening_context=None):
        """Apply intelligent filtering based on patient context"""
        # Get patient conditions to inform filtering
        from models import PatientCondition
        
        patient_conditions = PatientCondition.query.filter_by(
            patient_id=patient_id,
            is_active=True
        ).all()
        
        condition_names = [c.condition_name.lower() for c in patient_conditions]
        
        # Adjust filtering based on conditions
        smart_filters = {}
        
        # Diabetic patients - show more frequent lab monitoring
        if any('diabetes' in cond for cond in condition_names):
            smart_filters['lab_priority'] = True
            smart_filters['a1c_frequency'] = 'quarterly'
        
        # Heart disease - prioritize cardiac studies
        if any('heart' in cond or 'cardiac' in cond for cond in condition_names):
            smart_filters['cardiac_priority'] = True
            smart_filters['echo_frequency'] = 'annual'
        
        # Cancer history - prioritize screening studies
        if any('cancer' in cond for cond in condition_names):
            smart_filters['cancer_screening_priority'] = True
            smart_filters['imaging_frequency'] = 'frequent'
        
        return smart_filters
    
    def get_filtered_document_summary(self, patient_id, cutoff_settings):
        """Get summary of filtered documents"""
        filtered_data = self.apply_data_cutoffs(patient_id, cutoff_settings)
        
        summary = {
            'total_documents': 0,
            'by_type': {},
            'most_recent_by_type': {},
            'cutoff_dates': {}
        }
        
        for doc_type in ['lab', 'imaging', 'consult', 'hospital']:
            docs = filtered_data.get(f"{doc_type}_documents", [])
            count = len(docs)
            
            summary['total_documents'] += count
            summary['by_type'][doc_type] = count
            summary['most_recent_by_type'][doc_type] = docs[0] if docs else None
            summary['cutoff_dates'][doc_type] = filtered_data.get(f"{doc_type}_cutoff_date")
        
        return summary
    
    def export_filter_config(self, cutoff_settings):
        """Export current filter configuration"""
        config = {
            'filter_version': '1.0',
            'cutoff_settings': {
                'labs_cutoff_months': cutoff_settings.labs_cutoff_months,
                'imaging_cutoff_months': cutoff_settings.imaging_cutoff_months,
                'consults_cutoff_months': cutoff_settings.consults_cutoff_months,
                'hospital_cutoff_months': cutoff_settings.hospital_cutoff_months
            },
            'frequency_based_filtering': True,
            'smart_filtering_enabled': True,
            'last_updated': cutoff_settings.updated_at.isoformat() if cutoff_settings.updated_at else None
        }
        
        return config
