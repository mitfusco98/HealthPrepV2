"""
OCR quality monitoring and confidence scoring
Provides dashboard and statistics for OCR processing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import func, desc

from models import MedicalDocument, OCRProcessingStats
from app import db

logger = logging.getLogger(__name__)

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.quality_thresholds = {
            'high': 80,
            'medium': 60,
            'low': 0
        }
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive OCR dashboard statistics"""
        try:
            # Basic processing stats
            basic_stats = self._get_basic_stats()
            
            # Quality distribution
            quality_dist = self._get_quality_distribution()
            
            # Recent activity (last 7 days)
            recent_activity = self._get_recent_activity()
            
            # Performance metrics
            performance = self._get_performance_metrics()
            
            # Document queue status
            queue_status = self._get_queue_status()
            
            return {
                'basic_stats': basic_stats,
                'quality_distribution': quality_dist,
                'recent_activity': recent_activity,
                'performance': performance,
                'queue_status': queue_status,
                'last_updated': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return {
                'error': str(e),
                'last_updated': datetime.now()
            }
    
    def _get_basic_stats(self) -> Dict[str, Any]:
        """Get basic OCR processing statistics"""
        total_docs = db.session.query(MedicalDocument).count()
        processed_docs = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_text.isnot(None)
        ).count()
        
        # Average confidence
        avg_confidence_result = db.session.query(
            func.avg(MedicalDocument.ocr_confidence)
        ).filter(
            MedicalDocument.ocr_confidence.isnot(None)
        ).scalar()
        
        avg_confidence = round(avg_confidence_result or 0, 1)
        
        processing_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'pending_documents': total_docs - processed_docs,
            'avg_confidence': avg_confidence,
            'processing_rate': round(processing_rate, 1)
        }
    
    def _get_quality_distribution(self) -> Dict[str, Any]:
        """Get distribution of documents by quality level"""
        high_quality = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_confidence >= self.quality_thresholds['high']
        ).count()
        
        medium_quality = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_confidence >= self.quality_thresholds['medium'],
            MedicalDocument.ocr_confidence < self.quality_thresholds['high']
        ).count()
        
        low_quality = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_confidence < self.quality_thresholds['medium'],
            MedicalDocument.ocr_confidence.isnot(None)
        ).count()
        
        total_with_confidence = high_quality + medium_quality + low_quality
        
        return {
            'high_quality': {
                'count': high_quality,
                'percentage': round((high_quality / total_with_confidence * 100) if total_with_confidence > 0 else 0, 1)
            },
            'medium_quality': {
                'count': medium_quality,
                'percentage': round((medium_quality / total_with_confidence * 100) if total_with_confidence > 0 else 0, 1)
            },
            'low_quality': {
                'count': low_quality,
                'percentage': round((low_quality / total_with_confidence * 100) if total_with_confidence > 0 else 0, 1)
            },
            'total_assessed': total_with_confidence
        }
    
    def _get_recent_activity(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent OCR processing activity"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_docs = db.session.query(MedicalDocument).filter(
            MedicalDocument.processed_at >= cutoff_date
        ).order_by(desc(MedicalDocument.processed_at)).limit(20).all()
        
        activity = []
        for doc in recent_docs:
            activity.append({
                'id': doc.id,
                'filename': doc.filename,
                'patient_name': doc.patient.name if doc.patient else 'Unknown',
                'confidence': round(doc.ocr_confidence or 0, 1),
                'processed_at': doc.processed_at,
                'quality_level': self._get_quality_level(doc.ocr_confidence)
            })
        
        return activity
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get OCR performance metrics"""
        # Get processing stats
        stats = OCRProcessingStats.query.first()
        
        if not stats:
            return {
                'avg_processing_time': 0.0,
                'success_rate': 0.0,
                'throughput_per_hour': 0.0
            }
        
        # Calculate success rate
        total_attempts = stats.documents_processed
        successful_processing = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_text.isnot(None)
        ).count()
        
        success_rate = (successful_processing / total_attempts * 100) if total_attempts > 0 else 0
        
        # Estimate throughput (documents per hour based on avg processing time)
        throughput = (3600 / stats.processing_time_avg) if stats.processing_time_avg > 0 else 0
        
        return {
            'avg_processing_time': round(stats.processing_time_avg or 0, 2),
            'success_rate': round(success_rate, 1),
            'throughput_per_hour': round(throughput, 1)
        }
    
    def _get_queue_status(self) -> Dict[str, Any]:
        """Get current processing queue status"""
        pending_count = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_text.is_(None),
            MedicalDocument.processed_at.is_(None)
        ).count()
        
        processing_count = db.session.query(MedicalDocument).filter(
            MedicalDocument.processed_at.is_(None),
            MedicalDocument.date_uploaded >= datetime.now() - timedelta(hours=1)
        ).count()
        
        return {
            'pending_processing': pending_count,
            'currently_processing': processing_count,
            'queue_status': 'Normal' if pending_count < 50 else 'High Volume'
        }
    
    def _get_quality_level(self, confidence: float) -> str:
        """Get quality level string for confidence score"""
        if confidence is None:
            return 'Unknown'
        elif confidence >= self.quality_thresholds['high']:
            return 'High'
        elif confidence >= self.quality_thresholds['medium']:
            return 'Medium'
        else:
            return 'Low'
    
    def get_low_quality_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get documents with low OCR quality for review"""
        low_quality_docs = db.session.query(MedicalDocument).filter(
            MedicalDocument.ocr_confidence < self.quality_thresholds['medium'],
            MedicalDocument.ocr_confidence.isnot(None)
        ).order_by(MedicalDocument.ocr_confidence).limit(limit).all()
        
        results = []
        for doc in low_quality_docs:
            results.append({
                'id': doc.id,
                'filename': doc.filename,
                'patient_name': doc.patient.name if doc.patient else 'Unknown',
                'confidence': round(doc.ocr_confidence, 1),
                'document_type': doc.document_type,
                'processed_at': doc.processed_at,
                'needs_review': True
            })
        
        return results
    
    def get_processing_trends(self, days: int = 30) -> Dict[str, List]:
        """Get OCR processing trends over time"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get daily processing counts and average confidence
        daily_stats = db.session.query(
            func.date(MedicalDocument.processed_at).label('date'),
            func.count(MedicalDocument.id).label('count'),
            func.avg(MedicalDocument.ocr_confidence).label('avg_confidence')
        ).filter(
            MedicalDocument.processed_at >= cutoff_date
        ).group_by(
            func.date(MedicalDocument.processed_at)
        ).order_by('date').all()
        
        dates = []
        counts = []
        confidences = []
        
        for stat in daily_stats:
            dates.append(stat.date.strftime('%Y-%m-%d'))
            counts.append(stat.count)
            confidences.append(round(stat.avg_confidence or 0, 1))
        
        return {
            'dates': dates,
            'daily_counts': counts,
            'daily_avg_confidence': confidences
        }
    
    def get_document_type_analysis(self) -> Dict[str, Any]:
        """Analyze OCR performance by document type"""
        type_stats = db.session.query(
            MedicalDocument.document_type,
            func.count(MedicalDocument.id).label('count'),
            func.avg(MedicalDocument.ocr_confidence).label('avg_confidence')
        ).filter(
            MedicalDocument.ocr_confidence.isnot(None)
        ).group_by(
            MedicalDocument.document_type
        ).all()
        
        results = {}
        for stat in type_stats:
            results[stat.document_type] = {
                'document_count': stat.count,
                'avg_confidence': round(stat.avg_confidence or 0, 1),
                'quality_level': self._get_quality_level(stat.avg_confidence)
            }
        
        return results
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive OCR quality report"""
        report_data = {
            'generated_at': datetime.now(),
            'summary': self._get_basic_stats(),
            'quality_distribution': self._get_quality_distribution(),
            'performance_metrics': self._get_performance_metrics(),
            'document_type_analysis': self.get_document_type_analysis(),
            'processing_trends': self.get_processing_trends(),
            'recommendations': self._get_quality_recommendations()
        }
        
        return report_data
    
    def _get_quality_recommendations(self) -> List[str]:
        """Get recommendations for improving OCR quality"""
        recommendations = []
        
        # Get current stats
        quality_dist = self._get_quality_distribution()
        low_quality_pct = quality_dist['low_quality']['percentage']
        
        if low_quality_pct > 20:
            recommendations.append("High percentage of low-quality OCR results. Consider reviewing document scanning quality.")
        
        if quality_dist['total_assessed'] < 100:
            recommendations.append("Limited OCR data available. Process more documents for better analysis.")
        
        # Check document type performance
        type_analysis = self.get_document_type_analysis()
        for doc_type, stats in type_analysis.items():
            if stats['avg_confidence'] < 60:
                recommendations.append(f"Poor OCR performance for {doc_type} documents. Consider type-specific optimization.")
        
        if not recommendations:
            recommendations.append("OCR performance is within acceptable ranges. Continue monitoring.")
        
        return recommendations
