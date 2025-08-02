"""
OCR quality monitoring and confidence scoring
Provides monitoring dashboard and processing statistics
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from models import MedicalDocument, AdminLog
from app import db

logger = logging.getLogger(__name__)

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.confidence_ranges = {
            'high': (80, 100),
            'medium': (60, 79),
            'low': (40, 59),
            'very_low': (0, 39)
        }
    
    def get_processing_statistics(self, days: int = 7) -> Dict:
        """
        Get OCR processing statistics for the specified period
        
        Args:
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get documents processed in the time period
            documents = MedicalDocument.query.filter(
                MedicalDocument.processed_at >= cutoff_date,
                MedicalDocument.ocr_confidence.isnot(None)
            ).all()
            
            if not documents:
                return self._get_empty_stats()
            
            # Calculate statistics
            total_docs = len(documents)
            confidence_scores = [doc.ocr_confidence for doc in documents if doc.ocr_confidence is not None]
            
            if not confidence_scores:
                return self._get_empty_stats()
            
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            
            # Group by confidence ranges
            confidence_distribution = self._calculate_confidence_distribution(confidence_scores)
            
            # Calculate processing trends
            daily_stats = self._calculate_daily_stats(documents)
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(documents)
            
            return {
                'period_days': days,
                'total_documents': total_docs,
                'average_confidence': round(avg_confidence, 2),
                'confidence_distribution': confidence_distribution,
                'daily_statistics': daily_stats,
                'quality_metrics': quality_metrics,
                'last_updated': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting OCR statistics: {str(e)}")
            return self._get_empty_stats()
    
    def get_low_confidence_documents(self, threshold: float = 60.0, limit: int = 50) -> List[Dict]:
        """
        Get documents with low OCR confidence scores
        
        Args:
            threshold: Confidence threshold below which documents are considered low quality
            limit: Maximum number of documents to return
            
        Returns:
            List of low confidence documents with details
        """
        try:
            documents = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence < threshold,
                MedicalDocument.ocr_confidence.isnot(None)
            ).order_by(MedicalDocument.ocr_confidence.asc()).limit(limit).all()
            
            low_confidence_docs = []
            
            for doc in documents:
                doc_info = {
                    'id': doc.id,
                    'filename': doc.filename,
                    'patient_id': doc.patient_id,
                    'patient_name': doc.patient.name if doc.patient else 'Unknown',
                    'confidence': doc.ocr_confidence,
                    'confidence_level': self._get_confidence_level(doc.ocr_confidence),
                    'document_type': doc.document_type,
                    'processed_at': doc.processed_at,
                    'content_length': len(doc.content or ''),
                    'needs_review': doc.ocr_confidence < 40.0
                }
                low_confidence_docs.append(doc_info)
            
            return low_confidence_docs
            
        except Exception as e:
            logger.error(f"Error getting low confidence documents: {str(e)}")
            return []
    
    def get_processing_queue_status(self) -> Dict:
        """
        Get current OCR processing queue status
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            # Documents uploaded but not yet processed
            pending_docs = MedicalDocument.query.filter(
                MedicalDocument.processed_at.is_(None),
                MedicalDocument.content.is_(None)
            ).count()
            
            # Documents processed today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            processed_today = MedicalDocument.query.filter(
                MedicalDocument.processed_at >= today_start
            ).count()
            
            # Recent processing activity (last hour)
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            processed_last_hour = MedicalDocument.query.filter(
                MedicalDocument.processed_at >= hour_ago
            ).count()
            
            # Calculate average processing time (if available)
            recent_docs = MedicalDocument.query.filter(
                MedicalDocument.processed_at >= datetime.utcnow() - timedelta(days=1)
            ).limit(100).all()
            
            avg_processing_time = self._calculate_average_processing_time(recent_docs)
            
            return {
                'pending_documents': pending_docs,
                'processed_today': processed_today,
                'processed_last_hour': processed_last_hour,
                'average_processing_time_seconds': avg_processing_time,
                'queue_healthy': pending_docs < 100,  # Arbitrary threshold
                'last_updated': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue status: {str(e)}")
            return {
                'pending_documents': 0,
                'processed_today': 0,
                'processed_last_hour': 0,
                'average_processing_time_seconds': None,
                'queue_healthy': True,
                'error': str(e),
                'last_updated': datetime.utcnow()
            }
    
    def log_processing_event(self, document_id: int, event_type: str, details: Dict = None):
        """
        Log OCR processing events for monitoring
        
        Args:
            document_id: Document ID
            event_type: Type of event (started, completed, failed, etc.)
            details: Additional event details
        """
        try:
            log_entry = AdminLog(
                action=f"OCR_{event_type.upper()}",
                details=f"Document ID: {document_id}" + (f", Details: {details}" if details else ""),
                timestamp=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error logging OCR event: {str(e)}")
    
    def get_confidence_color_class(self, confidence: float) -> str:
        """
        Get CSS class for confidence-based color coding
        
        Args:
            confidence: Confidence score (0-100)
            
        Returns:
            CSS class name
        """
        if confidence >= 80:
            return 'confidence-high'
        elif confidence >= 60:
            return 'confidence-medium'
        else:
            return 'confidence-low'
    
    def _get_empty_stats(self) -> Dict:
        """Return empty statistics structure"""
        return {
            'total_documents': 0,
            'average_confidence': 0.0,
            'confidence_distribution': {level: 0 for level in self.confidence_ranges.keys()},
            'daily_statistics': [],
            'quality_metrics': {
                'high_quality_percentage': 0.0,
                'needs_review_percentage': 0.0,
                'average_content_length': 0
            },
            'last_updated': datetime.utcnow()
        }
    
    def _calculate_confidence_distribution(self, confidence_scores: List[float]) -> Dict[str, int]:
        """Calculate distribution of confidence scores"""
        distribution = {level: 0 for level in self.confidence_ranges.keys()}
        
        for score in confidence_scores:
            level = self._get_confidence_level(score)
            distribution[level] += 1
        
        return distribution
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level name for a score"""
        for level, (min_score, max_score) in self.confidence_ranges.items():
            if min_score <= confidence <= max_score:
                return level
        return 'very_low'
    
    def _calculate_daily_stats(self, documents: List[MedicalDocument]) -> List[Dict]:
        """Calculate daily processing statistics"""
        daily_stats = defaultdict(lambda: {'count': 0, 'avg_confidence': 0.0, 'confidences': []})
        
        for doc in documents:
            if doc.processed_at and doc.ocr_confidence is not None:
                day_key = doc.processed_at.date().isoformat()
                daily_stats[day_key]['count'] += 1
                daily_stats[day_key]['confidences'].append(doc.ocr_confidence)
        
        # Calculate averages
        result = []
        for day, stats in daily_stats.items():
            if stats['confidences']:
                avg_confidence = sum(stats['confidences']) / len(stats['confidences'])
                result.append({
                    'date': day,
                    'document_count': stats['count'],
                    'average_confidence': round(avg_confidence, 2)
                })
        
        return sorted(result, key=lambda x: x['date'])
    
    def _calculate_quality_metrics(self, documents: List[MedicalDocument]) -> Dict:
        """Calculate quality metrics"""
        if not documents:
            return {
                'high_quality_percentage': 0.0,
                'needs_review_percentage': 0.0,
                'average_content_length': 0
            }
        
        high_quality_count = sum(1 for doc in documents if doc.ocr_confidence and doc.ocr_confidence >= 80)
        needs_review_count = sum(1 for doc in documents if doc.ocr_confidence and doc.ocr_confidence < 40)
        
        content_lengths = [len(doc.content or '') for doc in documents]
        avg_content_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0
        
        total_count = len(documents)
        
        return {
            'high_quality_percentage': round((high_quality_count / total_count) * 100, 2),
            'needs_review_percentage': round((needs_review_count / total_count) * 100, 2),
            'average_content_length': round(avg_content_length)
        }
    
    def _calculate_average_processing_time(self, documents: List[MedicalDocument]) -> Optional[float]:
        """Calculate average processing time if timestamps are available"""
        # This would require additional timestamp fields in the model
        # For now, return None as we don't have processing start times
        return None
    
    def generate_quality_report(self, days: int = 30) -> Dict:
        """
        Generate comprehensive OCR quality report
        
        Args:
            days: Number of days to include in report
            
        Returns:
            Detailed quality report
        """
        try:
            stats = self.get_processing_statistics(days)
            low_confidence_docs = self.get_low_confidence_documents(limit=10)
            queue_status = self.get_processing_queue_status()
            
            # Calculate trends
            if len(stats['daily_statistics']) >= 2:
                recent_avg = stats['daily_statistics'][-1]['average_confidence']
                previous_avg = stats['daily_statistics'][-2]['average_confidence']
                confidence_trend = recent_avg - previous_avg
            else:
                confidence_trend = 0.0
            
            return {
                'report_period_days': days,
                'generation_time': datetime.utcnow(),
                'overall_statistics': stats,
                'low_confidence_documents': low_confidence_docs,
                'queue_status': queue_status,
                'confidence_trend': round(confidence_trend, 2),
                'recommendations': self._generate_recommendations(stats, low_confidence_docs)
            }
            
        except Exception as e:
            logger.error(f"Error generating quality report: {str(e)}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, stats: Dict, low_confidence_docs: List[Dict]) -> List[str]:
        """Generate recommendations based on OCR quality analysis"""
        recommendations = []
        
        if stats['average_confidence'] < 70:
            recommendations.append("Overall OCR confidence is below recommended threshold. Consider reviewing document quality and OCR settings.")
        
        high_quality_pct = stats['quality_metrics']['high_quality_percentage']
        if high_quality_pct < 60:
            recommendations.append(f"Only {high_quality_pct}% of documents are high quality. Consider document preprocessing improvements.")
        
        needs_review_pct = stats['quality_metrics']['needs_review_percentage']
        if needs_review_pct > 20:
            recommendations.append(f"{needs_review_pct}% of documents need manual review. Consider quality control measures.")
        
        if len(low_confidence_docs) > 25:
            recommendations.append("High number of low-confidence documents detected. Review document sources and scanning quality.")
        
        if not recommendations:
            recommendations.append("OCR quality metrics are within acceptable ranges.")
        
        return recommendations
