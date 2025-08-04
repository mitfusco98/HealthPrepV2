import logging
from datetime import datetime, timedelta
from collections import defaultdict
from models import MedicalDocument, AdminLog
from app import db

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.confidence_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.0
        }
    
    def get_processing_statistics(self):
        """Get comprehensive OCR processing statistics"""
        # Basic counts
        total_docs = MedicalDocument.query.count()
        processed_docs = MedicalDocument.query.filter(MedicalDocument.ocr_text.isnot(None)).count()
        pending_docs = total_docs - processed_docs
        
        # Confidence distribution
        confidence_stats = self._get_confidence_distribution()
        
        # Recent processing activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_docs = MedicalDocument.query.filter(
            MedicalDocument.created_at >= week_ago
        ).all()
        
        recent_stats = self._analyze_recent_processing(recent_docs)
        
        # Quality alerts
        quality_alerts = self._get_quality_alerts()
        
        return {
            'overview': {
                'total_documents': total_docs,
                'processed_documents': processed_docs,
                'pending_processing': pending_docs,
                'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0
            },
            'confidence_distribution': confidence_stats,
            'recent_activity': recent_stats,
            'quality_alerts': quality_alerts
        }
    
    def _get_confidence_distribution(self):
        """Get distribution of documents by confidence level"""
        high_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_confidence >= self.confidence_thresholds['high']
        ).count()
        
        medium_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_confidence >= self.confidence_thresholds['medium'],
            MedicalDocument.ocr_confidence < self.confidence_thresholds['high']
        ).count()
        
        low_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_confidence < self.confidence_thresholds['medium'],
            MedicalDocument.ocr_confidence.isnot(None)
        ).count()
        
        return {
            'high': high_confidence,
            'medium': medium_confidence,
            'low': low_confidence
        }
    
    def _analyze_recent_processing(self, recent_docs):
        """Analyze recent processing activity"""
        if not recent_docs:
            return {
                'documents_processed': 0,
                'average_confidence': 0.0,
                'daily_breakdown': []
            }
        
        # Calculate daily breakdown
        daily_counts = defaultdict(int)
        daily_confidence = defaultdict(list)
        
        for doc in recent_docs:
            if doc.ocr_text:  # Only processed documents
                day = doc.created_at.date()
                daily_counts[day] += 1
                if doc.ocr_confidence:
                    daily_confidence[day].append(doc.ocr_confidence)
        
        # Create daily breakdown
        daily_breakdown = []
        for day in sorted(daily_counts.keys()):
            avg_conf = sum(daily_confidence[day]) / len(daily_confidence[day]) if daily_confidence[day] else 0.0
            daily_breakdown.append({
                'date': day.isoformat(),
                'documents': daily_counts[day],
                'average_confidence': round(avg_conf, 3)
            })
        
        # Overall stats
        processed_recent = [doc for doc in recent_docs if doc.ocr_text]
        confidences = [doc.ocr_confidence for doc in processed_recent if doc.ocr_confidence]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            'documents_processed': len(processed_recent),
            'average_confidence': round(avg_confidence, 3),
            'daily_breakdown': daily_breakdown
        }
    
    def _get_quality_alerts(self):
        """Get quality-related alerts"""
        alerts = []
        
        # Check for low confidence documents
        low_conf_count = MedicalDocument.query.filter(
            MedicalDocument.ocr_confidence < self.confidence_thresholds['medium'],
            MedicalDocument.ocr_confidence.isnot(None)
        ).count()
        
        if low_conf_count > 10:
            alerts.append({
                'type': 'warning',
                'message': f'{low_conf_count} documents have low OCR confidence (<60%)',
                'action': 'Review document quality and OCR settings'
            })
        
        # Check for documents without OCR processing
        unprocessed_count = MedicalDocument.query.filter(
            MedicalDocument.ocr_text.is_(None)
        ).count()
        
        if unprocessed_count > 0:
            alerts.append({
                'type': 'info',
                'message': f'{unprocessed_count} documents pending OCR processing',
                'action': 'OCR processing will complete automatically'
            })
        
        # Check for old documents without processing
        week_ago = datetime.utcnow() - timedelta(days=7)
        old_unprocessed = MedicalDocument.query.filter(
            MedicalDocument.created_at < week_ago,
            MedicalDocument.ocr_text.is_(None)
        ).count()
        
        if old_unprocessed > 0:
            alerts.append({
                'type': 'error',
                'message': f'{old_unprocessed} documents older than 1 week are still unprocessed',
                'action': 'Check OCR processing system'
            })
        
        return alerts
    
    def log_processing_event(self, document, event_type, details=None):
        """Log OCR processing events"""
        try:
            log_entry = AdminLog(
                action=f'OCR_{event_type}',
                description=f'Document {document.id}: {details or event_type}',
                ip_address='system'
            )
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Failed to log OCR event: {str(e)}")
    
    def get_confidence_color_class(self, confidence):
        """Get CSS class for confidence level"""
        if confidence is None:
            return 'confidence-unknown'
        elif confidence >= self.confidence_thresholds['high']:
            return 'confidence-high'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def get_recent_documents(self, limit=10):
        """Get recently processed documents with confidence indicators"""
        recent_docs = MedicalDocument.query.filter(
            MedicalDocument.ocr_text.isnot(None)
        ).order_by(MedicalDocument.created_at.desc()).limit(limit).all()
        
        # Add confidence indicators
        for doc in recent_docs:
            doc.confidence_class = self.get_confidence_color_class(doc.ocr_confidence)
            doc.confidence_label = self._get_confidence_label(doc.ocr_confidence)
        
        return recent_docs
    
    def _get_confidence_label(self, confidence):
        """Get human-readable confidence label"""
        if confidence is None:
            return 'Unknown'
        elif confidence >= self.confidence_thresholds['high']:
            return 'High'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'Medium'
        else:
            return 'Low'
