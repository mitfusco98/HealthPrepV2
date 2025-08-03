"""
OCR quality and confidence scoring monitoring
Provides dashboards and analytics for OCR performance
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import Document
from .processor import OCRProcessor

logger = logging.getLogger(__name__)

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.processor = OCRProcessor()
    
    def get_processing_statistics(self, days=30):
        """Get comprehensive OCR processing statistics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Basic counts
        total_docs = Document.query.count()
        processed_docs = Document.query.filter_by(ocr_processed=True).count()
        recent_docs = Document.query.filter(Document.upload_date >= cutoff_date).count()
        recent_processed = Document.query.filter(
            Document.upload_date >= cutoff_date,
            Document.ocr_processed == True
        ).count()
        
        # Confidence distribution
        confidence_stats = self.get_confidence_distribution()
        
        # Processing time analysis
        processing_times = self.get_processing_time_stats(days)
        
        # Error analysis
        error_stats = self.get_error_statistics(days)
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'pending_documents': total_docs - processed_docs,
            'recent_documents': recent_docs,
            'recent_processed': recent_processed,
            'success_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'recent_success_rate': (recent_processed / recent_docs * 100) if recent_docs > 0 else 0,
            'confidence_distribution': confidence_stats,
            'processing_times': processing_times,
            'errors': error_stats
        }
    
    def get_confidence_distribution(self):
        """Get distribution of OCR confidence scores"""
        # Query confidence ranges
        high_confidence = Document.query.filter(
            Document.ocr_confidence >= 0.8,
            Document.ocr_processed == True
        ).count()
        
        medium_confidence = Document.query.filter(
            Document.ocr_confidence >= 0.6,
            Document.ocr_confidence < 0.8,
            Document.ocr_processed == True
        ).count()
        
        low_confidence = Document.query.filter(
            Document.ocr_confidence > 0,
            Document.ocr_confidence < 0.6,
            Document.ocr_processed == True
        ).count()
        
        failed_processing = Document.query.filter(
            Document.ocr_confidence == 0,
            Document.ocr_processed == True
        ).count()
        
        total_processed = high_confidence + medium_confidence + low_confidence + failed_processing
        
        return {
            'high': {
                'count': high_confidence,
                'percentage': (high_confidence / total_processed * 100) if total_processed > 0 else 0
            },
            'medium': {
                'count': medium_confidence,
                'percentage': (medium_confidence / total_processed * 100) if total_processed > 0 else 0
            },
            'low': {
                'count': low_confidence,
                'percentage': (low_confidence / total_processed * 100) if total_processed > 0 else 0
            },
            'failed': {
                'count': failed_processing,
                'percentage': (failed_processing / total_processed * 100) if total_processed > 0 else 0
            }
        }
    
    def get_processing_time_stats(self, days=7):
        """Get processing time statistics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get daily processing counts
        daily_stats = db.session.query(
            func.date(Document.upload_date).label('date'),
            func.count(Document.id).label('uploaded'),
            func.sum(func.cast(Document.ocr_processed, db.Integer)).label('processed')
        ).filter(
            Document.upload_date >= cutoff_date
        ).group_by(
            func.date(Document.upload_date)
        ).all()
        
        return [
            {
                'date': stat.date.isoformat(),
                'uploaded': stat.uploaded,
                'processed': stat.processed or 0,
                'processing_rate': (stat.processed / stat.uploaded * 100) if stat.uploaded > 0 else 0
            }
            for stat in daily_stats
        ]
    
    def get_error_statistics(self, days=30):
        """Get error statistics for OCR processing"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Documents with zero confidence (likely processing errors)
        failed_docs = Document.query.filter(
            Document.upload_date >= cutoff_date,
            Document.ocr_processed == True,
            Document.ocr_confidence == 0
        ).count()
        
        # Documents with very low confidence (potential quality issues)
        low_quality_docs = Document.query.filter(
            Document.upload_date >= cutoff_date,
            Document.ocr_processed == True,
            Document.ocr_confidence > 0,
            Document.ocr_confidence < 0.3
        ).count()
        
        # Unprocessed documents (potential stuck in queue)
        stuck_docs = Document.query.filter(
            Document.upload_date <= datetime.utcnow() - timedelta(hours=1),
            Document.ocr_processed == False
        ).count()
        
        return {
            'failed_processing': failed_docs,
            'low_quality': low_quality_docs,
            'stuck_in_queue': stuck_docs
        }
    
    def get_recent_activity(self, limit=20):
        """Get recent OCR processing activity"""
        recent_docs = Document.query.filter_by(ocr_processed=True)\
                                  .order_by(Document.upload_date.desc())\
                                  .limit(limit).all()
        
        activity = []
        for doc in recent_docs:
            activity.append({
                'id': doc.id,
                'filename': doc.original_filename,
                'upload_date': doc.upload_date,
                'confidence': doc.ocr_confidence,
                'confidence_class': self.get_confidence_class(doc.ocr_confidence),
                'patient_name': doc.patient.full_name if doc.patient else 'Unknown',
                'document_type': doc.document_type or 'Unknown'
            })
        
        return activity
    
    def get_confidence_class(self, confidence):
        """Get CSS class for confidence level"""
        if confidence is None or confidence == 0:
            return 'confidence-failed'
        elif confidence >= 0.8:
            return 'confidence-high'
        elif confidence >= 0.6:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def get_low_confidence_documents(self, threshold=0.6, limit=50):
        """Get documents with low confidence scores for review"""
        low_confidence_docs = Document.query.filter(
            Document.ocr_processed == True,
            Document.ocr_confidence < threshold,
            Document.ocr_confidence > 0
        ).order_by(Document.ocr_confidence.asc()).limit(limit).all()
        
        return [
            {
                'id': doc.id,
                'filename': doc.original_filename,
                'confidence': doc.ocr_confidence,
                'patient_name': doc.patient.full_name if doc.patient else 'Unknown',
                'upload_date': doc.upload_date,
                'text_preview': doc.ocr_text[:200] + '...' if doc.ocr_text else 'No text extracted'
            }
            for doc in low_confidence_docs
        ]
    
    def generate_quality_report(self, days=30):
        """Generate a comprehensive quality report"""
        stats = self.get_processing_statistics(days)
        low_confidence_docs = self.get_low_confidence_documents()
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'period_days': days,
            'summary': {
                'total_documents': stats['total_documents'],
                'success_rate': stats['success_rate'],
                'average_confidence': self.calculate_average_confidence(),
                'quality_score': self.calculate_quality_score(stats)
            },
            'confidence_distribution': stats['confidence_distribution'],
            'recommendations': self.generate_recommendations(stats),
            'low_confidence_documents': low_confidence_docs[:10]  # Top 10 for review
        }
        
        return report
    
    def calculate_average_confidence(self):
        """Calculate average confidence across all processed documents"""
        result = db.session.query(func.avg(Document.ocr_confidence)).filter(
            Document.ocr_processed == True,
            Document.ocr_confidence > 0
        ).scalar()
        
        return float(result) if result else 0.0
    
    def calculate_quality_score(self, stats):
        """Calculate overall OCR quality score (0-100)"""
        confidence_dist = stats['confidence_distribution']
        
        # Weighted score based on confidence distribution
        score = (
            confidence_dist['high']['percentage'] * 1.0 +
            confidence_dist['medium']['percentage'] * 0.7 +
            confidence_dist['low']['percentage'] * 0.3 +
            confidence_dist['failed']['percentage'] * 0.0
        )
        
        return round(score, 1)
    
    def generate_recommendations(self, stats):
        """Generate recommendations based on OCR statistics"""
        recommendations = []
        
        if stats['success_rate'] < 90:
            recommendations.append({
                'type': 'warning',
                'message': f"OCR success rate ({stats['success_rate']:.1f}%) is below recommended 90%",
                'action': "Review document upload quality and file formats"
            })
        
        if stats['confidence_distribution']['high']['percentage'] < 70:
            recommendations.append({
                'type': 'info',
                'message': f"Only {stats['confidence_distribution']['high']['percentage']:.1f}% of documents have high confidence",
                'action': "Consider improving document scan quality or OCR preprocessing"
            })
        
        if stats['confidence_distribution']['failed']['percentage'] > 5:
            recommendations.append({
                'type': 'error',
                'message': f"{stats['confidence_distribution']['failed']['percentage']:.1f}% of documents failed OCR processing",
                'action': "Check for unsupported file formats or corrupted documents"
            })
        
        if stats['errors']['stuck_in_queue'] > 0:
            recommendations.append({
                'type': 'warning',
                'message': f"{stats['errors']['stuck_in_queue']} documents appear stuck in processing queue",
                'action': "Check OCR processing service status"
            })
        
        return recommendations
