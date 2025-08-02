"""
OCR quality monitoring and confidence scoring
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from app import db
from models import MedicalDocument

logger = logging.getLogger(__name__)

class OCRMonitor:
    """Monitors OCR processing quality and performance metrics"""
    
    def __init__(self):
        self.confidence_thresholds = {
            'high': 85.0,
            'medium': 60.0,
            'low': 30.0
        }
        self.quality_metrics = {}
    
    def record_processing_result(self, document_id: int, ocr_result: Dict[str, Any]) -> None:
        """Record OCR processing result for monitoring"""
        try:
            document = MedicalDocument.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found for OCR monitoring")
                return
            
            # Update document with OCR results
            document.ocr_text = ocr_result.get('text', '')
            document.ocr_confidence = ocr_result.get('confidence', 0.0)
            document.ocr_processed = ocr_result.get('success', False)
            
            # Log processing metrics
            self._log_processing_metrics(document_id, ocr_result)
            
            db.session.commit()
            logger.info(f"Recorded OCR result for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error recording OCR result for document {document_id}: {str(e)}")
            db.session.rollback()
    
    def _log_processing_metrics(self, document_id: int, ocr_result: Dict[str, Any]) -> None:
        """Log detailed processing metrics"""
        metrics = {
            'document_id': document_id,
            'timestamp': datetime.utcnow(),
            'success': ocr_result.get('success', False),
            'confidence': ocr_result.get('confidence', 0.0),
            'word_count': ocr_result.get('word_count', 0),
            'processing_time': ocr_result.get('processing_time', 0.0),
            'quality_score': ocr_result.get('quality_score', 0.0),
            'needs_review': ocr_result.get('needs_review', False)
        }
        
        # Store in memory for dashboard (in production, use Redis or database)
        if not hasattr(self, '_metrics_cache'):
            self._metrics_cache = []
        
        self._metrics_cache.append(metrics)
        
        # Keep only last 1000 entries
        if len(self._metrics_cache) > 1000:
            self._metrics_cache = self._metrics_cache[-1000:]
    
    def get_confidence_distribution(self, days: int = 7) -> Dict[str, int]:
        """Get distribution of confidence levels over specified days"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            documents = MedicalDocument.query.filter(
                MedicalDocument.upload_date >= since_date,
                MedicalDocument.ocr_processed == True
            ).all()
            
            distribution = {
                'high': 0,
                'medium': 0,
                'low': 0,
                'failed': 0
            }
            
            for doc in documents:
                confidence = doc.ocr_confidence or 0.0
                
                if confidence >= self.confidence_thresholds['high']:
                    distribution['high'] += 1
                elif confidence >= self.confidence_thresholds['medium']:
                    distribution['medium'] += 1
                elif confidence >= self.confidence_thresholds['low']:
                    distribution['low'] += 1
                else:
                    distribution['failed'] += 1
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting confidence distribution: {str(e)}")
            return {'high': 0, 'medium': 0, 'low': 0, 'failed': 0}
    
    def get_processing_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            documents = MedicalDocument.query.filter(
                MedicalDocument.upload_date >= since_date
            ).all()
            
            total_docs = len(documents)
            processed_docs = len([d for d in documents if d.ocr_processed])
            pending_docs = total_docs - processed_docs
            
            if processed_docs > 0:
                confidences = [d.ocr_confidence for d in documents if d.ocr_confidence is not None]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                # Get documents needing review (low confidence)
                low_confidence_docs = [
                    d for d in documents 
                    if d.ocr_confidence and d.ocr_confidence < self.confidence_thresholds['medium']
                ]
            else:
                avg_confidence = 0.0
                low_confidence_docs = []
            
            return {
                'total_documents': total_docs,
                'processed_documents': processed_docs,
                'pending_documents': pending_docs,
                'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0.0,
                'average_confidence': avg_confidence,
                'low_confidence_count': len(low_confidence_docs),
                'needs_review_count': len(low_confidence_docs),
                'confidence_distribution': self.get_confidence_distribution(days)
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {
                'total_documents': 0,
                'processed_documents': 0,
                'pending_documents': 0,
                'processing_rate': 0.0,
                'average_confidence': 0.0,
                'low_confidence_count': 0,
                'needs_review_count': 0,
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0, 'failed': 0}
            }
    
    def get_recent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent OCR processing activity"""
        try:
            recent_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed == True
            ).order_by(MedicalDocument.upload_date.desc()).limit(limit).all()
            
            activity = []
            for doc in recent_docs:
                confidence_level = self._get_confidence_level(doc.ocr_confidence or 0.0)
                
                activity.append({
                    'document_id': doc.id,
                    'filename': doc.filename,
                    'patient_id': doc.patient_id,
                    'upload_date': doc.upload_date,
                    'confidence': doc.ocr_confidence or 0.0,
                    'confidence_level': confidence_level,
                    'word_count': len(doc.ocr_text.split()) if doc.ocr_text else 0,
                    'document_type': doc.document_type or 'unknown'
                })
            
            return activity
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Determine confidence level category"""
        if confidence >= self.confidence_thresholds['high']:
            return 'high'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'medium'
        elif confidence >= self.confidence_thresholds['low']:
            return 'low'
        else:
            return 'failed'
    
    def get_documents_needing_review(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get documents that need manual review due to low confidence"""
        try:
            low_confidence_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed == True,
                MedicalDocument.ocr_confidence < self.confidence_thresholds['medium']
            ).order_by(MedicalDocument.upload_date.desc()).limit(limit).all()
            
            review_list = []
            for doc in low_confidence_docs:
                review_list.append({
                    'document_id': doc.id,
                    'filename': doc.filename,
                    'patient_id': doc.patient_id,
                    'upload_date': doc.upload_date,
                    'confidence': doc.ocr_confidence or 0.0,
                    'confidence_level': self._get_confidence_level(doc.ocr_confidence or 0.0),
                    'ocr_text_preview': (doc.ocr_text[:100] + '...') if doc.ocr_text and len(doc.ocr_text) > 100 else doc.ocr_text
                })
            
            return review_list
            
        except Exception as e:
            logger.error(f"Error getting documents needing review: {str(e)}")
            return []
    
    def get_processing_trends(self, days: int = 30) -> Dict[str, List]:
        """Get processing trends over time"""
        try:
            # Group documents by day
            since_date = datetime.utcnow() - timedelta(days=days)
            documents = MedicalDocument.query.filter(
                MedicalDocument.upload_date >= since_date,
                MedicalDocument.ocr_processed == True
            ).all()
            
            daily_stats = defaultdict(lambda: {
                'total': 0,
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
                'avg_confidence': 0.0
            })
            
            for doc in documents:
                day_key = doc.upload_date.strftime('%Y-%m-%d')
                confidence = doc.ocr_confidence or 0.0
                
                daily_stats[day_key]['total'] += 1
                
                if confidence >= self.confidence_thresholds['high']:
                    daily_stats[day_key]['high_confidence'] += 1
                elif confidence >= self.confidence_thresholds['medium']:
                    daily_stats[day_key]['medium_confidence'] += 1
                else:
                    daily_stats[day_key]['low_confidence'] += 1
            
            # Calculate average confidence per day
            for day_key in daily_stats:
                day_docs = [d for d in documents if d.upload_date.strftime('%Y-%m-%d') == day_key]
                confidences = [d.ocr_confidence for d in day_docs if d.ocr_confidence is not None]
                daily_stats[day_key]['avg_confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Convert to lists for charting
            dates = sorted(daily_stats.keys())
            return {
                'dates': dates,
                'total_processed': [daily_stats[d]['total'] for d in dates],
                'high_confidence': [daily_stats[d]['high_confidence'] for d in dates],
                'medium_confidence': [daily_stats[d]['medium_confidence'] for d in dates],
                'low_confidence': [daily_stats[d]['low_confidence'] for d in dates],
                'avg_confidence': [daily_stats[d]['avg_confidence'] for d in dates]
            }
            
        except Exception as e:
            logger.error(f"Error getting processing trends: {str(e)}")
            return {
                'dates': [],
                'total_processed': [],
                'high_confidence': [],
                'medium_confidence': [],
                'low_confidence': [],
                'avg_confidence': []
            }
    
    def generate_quality_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate comprehensive quality report"""
        try:
            stats = self.get_processing_statistics(days)
            distribution = self.get_confidence_distribution(days)
            recent_activity = self.get_recent_activity(10)
            review_queue = self.get_documents_needing_review(10)
            
            # Calculate quality score
            total_processed = stats['processed_documents']
            if total_processed > 0:
                high_quality_ratio = distribution['high'] / total_processed
                medium_quality_ratio = distribution['medium'] / total_processed
                quality_score = (high_quality_ratio * 100 + medium_quality_ratio * 70) / 1.7
            else:
                quality_score = 0.0
            
            return {
                'report_period_days': days,
                'generated_at': datetime.utcnow(),
                'overall_quality_score': quality_score,
                'processing_statistics': stats,
                'confidence_distribution': distribution,
                'recent_activity': recent_activity,
                'review_queue': review_queue,
                'recommendations': self._generate_recommendations(stats, distribution)
            }
            
        except Exception as e:
            logger.error(f"Error generating quality report: {str(e)}")
            return {}
    
    def _generate_recommendations(self, stats: Dict[str, Any], distribution: Dict[str, int]) -> List[str]:
        """Generate recommendations based on processing statistics"""
        recommendations = []
        
        try:
            total_processed = stats['processed_documents']
            avg_confidence = stats['average_confidence']
            
            if total_processed == 0:
                recommendations.append("No documents processed yet. Upload some documents to begin OCR analysis.")
                return recommendations
            
            if avg_confidence < 60:
                recommendations.append("Average confidence is low. Consider image quality improvements or document preprocessing.")
            
            if distribution['failed'] / total_processed > 0.2:
                recommendations.append("High failure rate detected. Check document formats and image quality.")
            
            if distribution['low'] / total_processed > 0.3:
                recommendations.append("Many documents have low confidence scores. Consider manual review process.")
            
            if stats['needs_review_count'] > 10:
                recommendations.append("Review queue is building up. Consider prioritizing manual document review.")
            
            if not recommendations:
                recommendations.append("OCR processing quality looks good. Continue monitoring for consistency.")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations.append("Unable to generate recommendations due to data processing error.")
        
        return recommendations

# Global OCR monitor instance
ocr_monitor = OCRMonitor()
