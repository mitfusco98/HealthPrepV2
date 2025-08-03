"""
OCR quality monitoring and confidence scoring.
Provides monitoring dashboard and quality assessment for OCR processing.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from app import db
from models import MedicalDocument

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get comprehensive OCR quality metrics"""
        try:
            # Basic statistics
            total_docs = MedicalDocument.query.count()
            processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).count()
            
            if processed_docs == 0:
                return self._empty_metrics()
            
            # Confidence distribution
            confidence_data = db.session.query(MedicalDocument.ocr_confidence)\
                                      .filter(MedicalDocument.ocr_processed == True,
                                             MedicalDocument.ocr_confidence.isnot(None))\
                                      .all()
            
            confidences = [conf[0] for conf in confidence_data if conf[0] is not None]
            
            if not confidences:
                return self._empty_metrics()
            
            # Calculate statistics
            avg_confidence = statistics.mean(confidences)
            median_confidence = statistics.median(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
            
            # Confidence categories
            high_conf = len([c for c in confidences if c >= 0.8])
            medium_conf = len([c for c in confidences if 0.6 <= c < 0.8])
            low_conf = len([c for c in confidences if c < 0.6])
            
            # Processing success rate
            success_rate = (processed_docs / total_docs) * 100 if total_docs > 0 else 0
            
            # Recent processing trends
            trends = self._calculate_processing_trends()
            
            return {
                'overview': {
                    'total_documents': total_docs,
                    'processed_documents': processed_docs,
                    'pending_documents': total_docs - processed_docs,
                    'success_rate': round(success_rate, 2)
                },
                'confidence_metrics': {
                    'average': round(avg_confidence, 3),
                    'median': round(median_confidence, 3),
                    'minimum': round(min_confidence, 3),
                    'maximum': round(max_confidence, 3),
                    'distribution': {
                        'high': {'count': high_conf, 'percentage': round((high_conf / len(confidences)) * 100, 1)},
                        'medium': {'count': medium_conf, 'percentage': round((medium_conf / len(confidences)) * 100, 1)},
                        'low': {'count': low_conf, 'percentage': round((low_conf / len(confidences)) * 100, 1)}
                    }
                },
                'trends': trends,
                'quality_flags': self._identify_quality_flags(confidences)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating quality metrics: {str(e)}")
            return self._empty_metrics()
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            'overview': {
                'total_documents': 0,
                'processed_documents': 0,
                'pending_documents': 0,
                'success_rate': 0
            },
            'confidence_metrics': {
                'average': 0,
                'median': 0,
                'minimum': 0,
                'maximum': 0,
                'distribution': {
                    'high': {'count': 0, 'percentage': 0},
                    'medium': {'count': 0, 'percentage': 0},
                    'low': {'count': 0, 'percentage': 0}
                }
            },
            'trends': [],
            'quality_flags': []
        }
    
    def _calculate_processing_trends(self) -> List[Dict[str, Any]]:
        """Calculate processing trends over the last 7 days"""
        try:
            trends = []
            today = datetime.utcnow().date()
            
            for i in range(7):
                date = today - timedelta(days=i)
                start_datetime = datetime.combine(date, datetime.min.time())
                end_datetime = datetime.combine(date, datetime.max.time())
                
                # Count documents processed on this date
                processed_count = MedicalDocument.query.filter(
                    MedicalDocument.ocr_processed_at >= start_datetime,
                    MedicalDocument.ocr_processed_at <= end_datetime
                ).count()
                
                # Calculate average confidence for this date
                confidence_data = db.session.query(MedicalDocument.ocr_confidence)\
                                          .filter(MedicalDocument.ocr_processed_at >= start_datetime,
                                                 MedicalDocument.ocr_processed_at <= end_datetime,
                                                 MedicalDocument.ocr_confidence.isnot(None))\
                                          .all()
                
                confidences = [conf[0] for conf in confidence_data if conf[0] is not None]
                avg_confidence = statistics.mean(confidences) if confidences else 0
                
                trends.append({
                    'date': date.isoformat(),
                    'processed_count': processed_count,
                    'average_confidence': round(avg_confidence, 3)
                })
            
            return sorted(trends, key=lambda x: x['date'])
            
        except Exception as e:
            self.logger.error(f"Error calculating trends: {str(e)}")
            return []
    
    def _identify_quality_flags(self, confidences: List[float]) -> List[Dict[str, str]]:
        """Identify quality issues and flags"""
        flags = []
        
        if not confidences:
            return flags
        
        avg_confidence = statistics.mean(confidences)
        low_confidence_count = len([c for c in confidences if c < 0.5])
        low_confidence_rate = (low_confidence_count / len(confidences)) * 100
        
        # Flag: Low average confidence
        if avg_confidence < 0.7:
            flags.append({
                'type': 'warning',
                'message': f'Average confidence is low ({avg_confidence:.2f}). Consider reviewing OCR settings or document quality.'
            })
        
        # Flag: High rate of low confidence documents
        if low_confidence_rate > 20:
            flags.append({
                'type': 'error',
                'message': f'{low_confidence_rate:.1f}% of documents have very low confidence (<50%). Review document sources.'
            })
        
        # Flag: Wide confidence variation
        if len(confidences) > 1:
            confidence_std = statistics.stdev(confidences)
            if confidence_std > 0.3:
                flags.append({
                    'type': 'info',
                    'message': 'High variation in confidence scores detected. Document quality may be inconsistent.'
                })
        
        return flags
    
    def get_low_confidence_documents(self, threshold: float = 0.6, limit: int = 50) -> List[Dict[str, Any]]:
        """Get documents with confidence below threshold"""
        try:
            low_conf_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed == True,
                MedicalDocument.ocr_confidence < threshold
            ).order_by(MedicalDocument.ocr_confidence.asc()).limit(limit).all()
            
            result = []
            for doc in low_conf_docs:
                result.append({
                    'id': doc.id,
                    'filename': doc.filename,
                    'confidence': doc.ocr_confidence,
                    'document_type': doc.document_type,
                    'processed_at': doc.ocr_processed_at.isoformat() if doc.ocr_processed_at else None,
                    'patient_id': doc.patient_id,
                    'file_size': doc.file_size,
                    'text_preview': doc.ocr_text[:100] + '...' if doc.ocr_text and len(doc.ocr_text) > 100 else doc.ocr_text
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting low confidence documents: {str(e)}")
            return []
    
    def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get status of OCR processing queue"""
        try:
            pending_docs = MedicalDocument.query.filter_by(ocr_processed=False).all()
            
            # Group by document type
            type_counts = defaultdict(int)
            size_distribution = []
            
            for doc in pending_docs:
                type_counts[doc.document_type or 'unknown'] += 1
                if doc.file_size:
                    size_distribution.append(doc.file_size)
            
            # Calculate estimated processing time (rough estimate)
            avg_processing_time = 30  # seconds per document (rough estimate)
            estimated_time = len(pending_docs) * avg_processing_time
            
            return {
                'pending_count': len(pending_docs),
                'type_breakdown': dict(type_counts),
                'estimated_processing_time_seconds': estimated_time,
                'estimated_processing_time_minutes': round(estimated_time / 60, 1),
                'average_file_size': round(statistics.mean(size_distribution), 0) if size_distribution else 0,
                'oldest_pending': min([doc.upload_date for doc in pending_docs]).isoformat() if pending_docs else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            return {}
    
    def get_recent_activity(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent OCR processing activity"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            recent_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed_at >= cutoff_time,
                MedicalDocument.ocr_processed == True
            ).order_by(MedicalDocument.ocr_processed_at.desc()).limit(100).all()
            
            activity = []
            for doc in recent_docs:
                # Determine confidence level
                confidence_level = 'high'
                if doc.ocr_confidence < 0.8:
                    confidence_level = 'medium'
                if doc.ocr_confidence < 0.6:
                    confidence_level = 'low'
                
                activity.append({
                    'id': doc.id,
                    'filename': doc.filename,
                    'confidence': doc.ocr_confidence,
                    'confidence_level': confidence_level,
                    'processed_at': doc.ocr_processed_at.isoformat(),
                    'document_type': doc.document_type,
                    'patient_id': doc.patient_id,
                    'text_length': len(doc.ocr_text) if doc.ocr_text else 0
                })
            
            return activity
            
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive quality report"""
        try:
            metrics = self.get_quality_metrics()
            low_conf_docs = self.get_low_confidence_documents()
            queue_status = self.get_processing_queue_status()
            recent_activity = self.get_recent_activity()
            
            # Calculate recommendations
            recommendations = self._generate_recommendations(metrics)
            
            return {
                'report_generated': datetime.utcnow().isoformat(),
                'metrics': metrics,
                'low_confidence_documents': low_conf_docs,
                'queue_status': queue_status,
                'recent_activity': recent_activity[:10],  # Limit to last 10
                'recommendations': recommendations
            }
            
        except Exception as e:
            self.logger.error(f"Error generating quality report: {str(e)}")
            return {}
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics"""
        recommendations = []
        
        if not metrics.get('confidence_metrics'):
            return recommendations
        
        confidence_metrics = metrics['confidence_metrics']
        avg_confidence = confidence_metrics.get('average', 0)
        low_conf_percentage = confidence_metrics.get('distribution', {}).get('low', {}).get('percentage', 0)
        
        if avg_confidence < 0.6:
            recommendations.append("Consider improving document scan quality or adjusting OCR preprocessing settings.")
        
        if low_conf_percentage > 30:
            recommendations.append("High percentage of low-confidence documents detected. Review document sources and scanning procedures.")
        
        if avg_confidence > 0.9:
            recommendations.append("Excellent OCR performance! Current settings are working well.")
        
        if confidence_metrics.get('minimum', 0) < 0.3:
            recommendations.append("Some documents have very low confidence. Consider manual review of problematic files.")
        
        return recommendations
