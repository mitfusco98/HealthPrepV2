"""
Frequency and cutoff filtering logic for prep sheets
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

def apply_cutoff_filters(documents, cutoff_months):
    """Filter documents based on cutoff period"""
    if not documents or cutoff_months is None:
        return documents
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_months * 30)
        
        filtered_docs = [
            doc for doc in documents 
            if doc.upload_date >= cutoff_date
        ]
        
        return filtered_docs
        
    except Exception as e:
        logging.error(f"Error applying cutoff filters: {e}")
        return documents

def apply_frequency_filters(documents, screening_type, last_completed_date):
    """Filter documents based on screening frequency"""
    if not documents or not screening_type or not last_completed_date:
        return documents
    
    try:
        # Calculate cutoff date based on frequency
        if screening_type.frequency_unit == 'years':
            cutoff_date = last_completed_date - relativedelta(years=screening_type.frequency_value)
        elif screening_type.frequency_unit == 'months':
            cutoff_date = last_completed_date - relativedelta(months=screening_type.frequency_value)
        else:  # days
            cutoff_date = last_completed_date - timedelta(days=screening_type.frequency_value)
        
        # Convert to datetime if needed
        if hasattr(cutoff_date, 'date'):
            cutoff_datetime = datetime.combine(cutoff_date, datetime.min.time())
        else:
            cutoff_datetime = datetime.combine(cutoff_date, datetime.min.time())
        
        # Filter documents after cutoff
        filtered_docs = [
            doc for doc in documents
            if doc.upload_date > cutoff_datetime
        ]
        
        return filtered_docs
        
    except Exception as e:
        logging.error(f"Error applying frequency filters: {e}")
        return documents

def get_relevant_documents(patient, screening_type, cutoff_months):
    """Get documents relevant to a specific screening within cutoff period"""
    from models import MedicalDocument
    from core.matcher import FuzzyMatcher
    import json
    
    try:
        # Get all patient documents within cutoff
        all_docs = MedicalDocument.query.filter_by(patient_id=patient.id).all()
        cutoff_filtered = apply_cutoff_filters(all_docs, cutoff_months)
        
        # Apply keyword matching
        matcher = FuzzyMatcher()
        keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
        
        relevant_docs = []
        for doc in cutoff_filtered:
            # Check filename matching
            if matcher.matches_keywords(doc.filename, keywords):
                relevant_docs.append(doc)
            # Check OCR text matching
            elif doc.ocr_text and matcher.matches_keywords(doc.ocr_text, keywords):
                relevant_docs.append(doc)
        
        return relevant_docs
        
    except Exception as e:
        logging.error(f"Error getting relevant documents: {e}")
        return []

def calculate_document_relevancy_score(document, screening_type):
    """Calculate how relevant a document is to a screening type"""
    from core.matcher import FuzzyMatcher
    import json
    
    try:
        matcher = FuzzyMatcher()
        keywords = json.loads(screening_type.keywords) if screening_type.keywords else []
        
        if not keywords:
            return 0.0
        
        # Calculate filename relevancy
        filename_score = 0.0
        for keyword in keywords:
            confidence = matcher.get_match_confidence(document.filename, keyword)
            filename_score = max(filename_score, confidence)
        
        # Calculate content relevancy
        content_score = 0.0
        if document.ocr_text:
            for keyword in keywords:
                confidence = matcher.get_match_confidence(document.ocr_text, keyword)
                content_score = max(content_score, confidence)
        
        # Weight filename and content scores
        # Filename match is weighted higher for medical documents
        total_score = (filename_score * 0.7) + (content_score * 0.3)
        
        return min(total_score, 1.0)
        
    except Exception as e:
        logging.error(f"Error calculating document relevancy: {e}")
        return 0.0

def filter_by_confidence_threshold(documents, min_confidence=0.5):
    """Filter documents by OCR confidence threshold"""
    try:
        return [
            doc for doc in documents
            if (doc.ocr_confidence or 0.0) >= min_confidence
        ]
    except Exception as e:
        logging.error(f"Error filtering by confidence: {e}")
        return documents

def sort_documents_by_relevancy(documents, screening_type):
    """Sort documents by relevancy to screening type"""
    try:
        # Calculate scores and sort
        doc_scores = []
        for doc in documents:
            score = calculate_document_relevancy_score(doc, screening_type)
            doc_scores.append((doc, score))
        
        # Sort by score (descending) then by date (descending)
        doc_scores.sort(key=lambda x: (x[1], x[0].upload_date), reverse=True)
        
        return [doc for doc, score in doc_scores]
        
    except Exception as e:
        logging.error(f"Error sorting documents: {e}")
        return documents
