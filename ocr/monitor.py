"""
Quality/confidence scoring and monitoring for OCR processing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import func
from models import MedicalDocument, db

logger = logging.getLogger(__name__)

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        # Quality thresholds
        self.confidence_thresholds = {
            'high': 0.85,
            'medium': 0.70,
            'low': 0.50
        }
        
        # Performance monitoring settings
        self.monitoring_window_days = 7
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get comprehensive OCR quality metrics"""
        
        # Basic processing statistics
        total_docs = MedicalDocument.query.count()
        processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).count()
        pending_docs = total_docs - processed_docs
        
        # Confidence distribution
        confidence_stats = self._get_confidence_distribution()
        
        # Recent processing activity
        recent_activity = self._get_recent_activity()
        
        # Quality alerts
        quality_alerts = self._get_quality_alerts()
        
        return {
            'overview': {
                'total_documents': total_docs,
                'processed_documents': processed_docs,
                'pending_documents': pending_docs,
                'processing_rate': round((processed_docs / total_docs * 100), 2) if total_docs > 0 else 0
            },
            'confidence_distribution': confidence_stats,
            'recent_activity': recent_activity,
            'quality_alerts': quality_alerts,
            'last_updated': datetime.utcnow().isoformat()
        }
    
    def _get_confidence_distribution(self) -> Dict[str, Any]:
        """Get distribution of confidence scores"""
        
        # Count documents by confidence ranges
        high_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed == True,
            MedicalDocument.ocr_confidence >= self.confidence_thresholds['high']
        ).count()
        
        medium_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed == True,
            MedicalDocument.ocr_confidence >= self.confidence_thresholds['medium'],
            MedicalDocument.ocr_confidence < self.confidence_thresholds['high']
        ).count()
        
        low_confidence = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed == True,
            MedicalDocument.ocr_confidence < self.confidence_thresholds['medium']
        ).count()
        
        # Average confidence
        avg_confidence = db.session.query(func.avg(MedicalDocument.ocr_confidence)).\
            filter(MedicalDocument.ocr_processed == True).scalar() or 0.0
        
        # Median confidence
        median_result = db.session.query(MedicalDocument.ocr_confidence).\
            filter(MedicalDocument.ocr_processed == True).\
            order_by(MedicalDocument.ocr_confidence).\
            offset(high_confidence + medium_confidence + low_confidence // 2).\
            limit(1).first()
        
        median_confidence = median_result[0] if median_result else 0.0
        
        return {
            'high_confidence': {
                'count': high_confidence,
                'threshold': self.confidence_thresholds['high'],
                'description': f'≥{self.confidence_thresholds["high"]*100:.0f}%'
            },
            'medium_confidence': {
                'count': medium_confidence,
                'threshold': self.confidence_thresholds['medium'],
                'description': f'{self.confidence_thresholds["medium"]*100:.0f}%-{self.confidence_thresholds["high"]*100:.0f}%'
            },
            'low_confidence': {
                'count': low_confidence,
                'threshold': self.confidence_thresholds['low'],
                'description': f'<{self.confidence_thresholds["medium"]*100:.0f}%'
            },
            'statistics': {
                'average_confidence': round(avg_confidence, 3),
                'median_confidence': round(median_confidence, 3)
            }
        }
    
    def _get_recent_activity(self) -> Dict[str, Any]:
        """Get recent OCR processing activity"""
        
        # Last 7 days of activity
        week_ago = datetime.utcnow() - timedelta(days=self.monitoring_window_days)
        
        recent_docs = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed_at >= week_ago
        ).order_by(MedicalDocument.ocr_processed_at.desc()).limit(50).all()
        
        # Group by day
        daily_stats = {}
        for doc in recent_docs:
            if doc.ocr_processed_at:
                day_key = doc.ocr_processed_at.strftime('%Y-%m-%d')
                if day_key not in daily_stats:
                    daily_stats[day_key] = {
                        'count': 0,
                        'avg_confidence': 0,
                        'confidences': []
                    }
                daily_stats[day_key]['count'] += 1
                daily_stats[day_key]['confidences'].append(doc.ocr_confidence or 0)
        
        # Calculate averages
        for day_data in daily_stats.values():
            if day_data['confidences']:
                day_data['avg_confidence'] = sum(day_data['confidences']) / len(day_data['confidences'])
            del day_data['confidences']  # Remove raw data
        
        # Recent processing details
        recent_details = []
        for doc in recent_docs[:10]:  # Last 10 processed
            recent_details.append({
                'document_id': doc.id,
                'filename': doc.filename,
                'confidence': doc.ocr_confidence,
                'processed_at': doc.ocr_processed_at.isoformat() if doc.ocr_processed_at else None,
                'confidence_level': self._get_confidence_level(doc.ocr_confidence or 0)
            })
        
        return {
            'daily_statistics': daily_stats,
            'recent_documents': recent_details,
            'total_this_week': len(recent_docs)
        }
    
    def _get_quality_alerts(self) -> List[Dict[str, Any]]:
        """Get quality alerts that need attention"""
        alerts = []
        
        # Low confidence documents
        low_confidence_docs = MedicalDocument.query.filter(
            MedicalDocument.ocr_processed == True,
            MedicalDocument.ocr_confidence < self.confidence_thresholds['low']
        ).count()
        
        if low_confidence_docs > 0:
            alerts.append({
                'type': 'low_confidence',
                'severity': 'warning',
                'count': low_confidence_docs,
                'message': f'{low_confidence_docs} documents with very low OCR confidence (<{self.confidence_thresholds["low"]*100:.0f}%)',
                'action': 'Review and consider manual verification'
            })
        
        # Large backlog
        pending_docs = MedicalDocument.query.filter_by(ocr_processed=False).count()
        if pending_docs > 50:
            alerts.append({
                'type': 'large_backlog',
                'severity': 'info',
                'count': pending_docs,
                'message': f'{pending_docs} documents pending OCR processing',
                'action': 'Consider batch processing or increasing processing capacity'
            })
        
        # Recent processing failures (documents uploaded but not processed within 24 hours)
        day_ago = datetime.utcnow() - timedelta(days=1)
        stale_docs = MedicalDocument.query.filter(
            MedicalDocument.upload_date < day_ago,
            MedicalDocument.ocr_processed == False
        ).count()
        
        if stale_docs > 0:
            alerts.append({
                'type': 'stale_documents',
                'severity': 'warning',
                'count': stale_docs,
                'message': f'{stale_docs} documents uploaded over 24 hours ago but not yet processed',
                'action': 'Check OCR processing system for issues'
            })
        
        return alerts
    
    def get_document_quality_report(self, document_id: int) -> Dict[str, Any]:
        """Get detailed quality report for a specific document"""
        
        document = MedicalDocument.query.get(document_id)
        if not document:
            return {'error': 'Document not found'}
        
        if not document.ocr_processed:
            return {'error': 'Document not yet processed'}
        
        confidence_level = self._get_confidence_level(document.ocr_confidence or 0)
        
        # Text quality metrics
        text_metrics = self._analyze_text_quality(document.ocr_text or "")
        
        # PHI filtering report
        phi_report = self._get_phi_filtering_report(document)
        
        return {
            'document_info': {
                'id': document.id,
                'filename': document.filename,
                'document_type': document.document_type,
                'processed_at': document.ocr_processed_at.isoformat() if document.ocr_processed_at else None
            },
            'confidence': {
                'score': document.ocr_confidence,
                'level': confidence_level,
                'description': self._get_confidence_description(confidence_level)
            },
            'text_quality': text_metrics,
            'phi_filtering': phi_report,
            'recommendations': self._get_quality_recommendations(document, confidence_level, text_metrics)
        }
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level category"""
        if confidence >= self.confidence_thresholds['high']:
            return 'high'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _get_confidence_description(self, level: str) -> str:
        """Get human-readable confidence description"""
        descriptions = {
            'high': 'Excellent OCR quality - text is highly reliable',
            'medium': 'Good OCR quality - text is generally reliable with minor errors possible',
            'low': 'Poor OCR quality - text may contain significant errors and should be reviewed'
        }
        return descriptions.get(level, 'Unknown confidence level')
    
    def _analyze_text_quality(self, text: str) -> Dict[str, Any]:
        """Analyze the quality of extracted text"""
        if not text:
            return {
                'word_count': 0,
                'character_count': 0,
                'readability_score': 0,
                'suspicious_patterns': []
            }
        
        word_count = len(text.split())
        char_count = len(text)
        
        # Look for suspicious OCR patterns
        suspicious_patterns = []
        
        # Too many single characters (OCR fragmentation)
        single_chars = len([word for word in text.split() if len(word) == 1])
        if word_count > 0 and single_chars / word_count > 0.2:
            suspicious_patterns.append('High number of single character words (possible OCR fragmentation)')
        
        # Too many numeric sequences (possible misread text)
        import re
        numeric_sequences = len(re.findall(r'\b\d{3,}\b', text))
        if numeric_sequences > word_count * 0.1:
            suspicious_patterns.append('High number of numeric sequences (possible misread text)')
        
        # Unusual character patterns
        unusual_chars = len(re.findall(r'[^\w\s.,;:()[\]{}/<>@#$%^&*+-=|\\~`"\'?!]', text))
        if unusual_chars > char_count * 0.05:
            suspicious_patterns.append('Unusual characters detected (possible OCR artifacts)')
        
        # Calculate basic readability score (simplified)
        avg_word_length = char_count / word_count if word_count > 0 else 0
        readability_score = max(0, min(100, 100 - (abs(avg_word_length - 5) * 10)))
        
        return {
            'word_count': word_count,
            'character_count': char_count,
            'average_word_length': round(avg_word_length, 2),
            'readability_score': round(readability_score, 2),
            'suspicious_patterns': suspicious_patterns
        }
    
    def _get_phi_filtering_report(self, document: MedicalDocument) -> Dict[str, Any]:
        """Get PHI filtering report for document"""
        return {
            'phi_filtered': document.phi_filtered,
            'patterns_found': document.phi_patterns_list,
            'patterns_count': len(document.phi_patterns_list),
            'original_length': len(document.original_text) if document.original_text else 0,
            'filtered_length': len(document.ocr_text) if document.ocr_text else 0
        }
    
    def _get_quality_recommendations(self, document: MedicalDocument, confidence_level: str, text_metrics: Dict[str, Any]) -> List[str]:
        """Get recommendations for improving quality"""
        recommendations = []
        
        if confidence_level == 'low':
            recommendations.append('Consider manual review and correction of extracted text')
            recommendations.append('Check if original document quality can be improved before reprocessing')
        
        if text_metrics['suspicious_patterns']:
            recommendations.append('Review text for OCR artifacts and errors')
        
        if text_metrics['word_count'] < 10:
            recommendations.append('Very short text extracted - verify document contains readable content')
        
        if not document.phi_filtered:
            recommendations.append('Enable PHI filtering for HIPAA compliance')
        
        return recommendations
    
    def export_quality_report(self, format: str = 'json') -> Dict[str, Any]:
        """Export comprehensive quality report"""
        
        metrics = self.get_quality_metrics()
        
        # Add detailed document breakdown
        all_processed_docs = MedicalDocument.query.filter_by(ocr_processed=True).all()
        
        document_details = []
        for doc in all_processed_docs:
            document_details.append({
                'id': doc.id,
                'filename': doc.filename,
                'document_type': doc.document_type,
                'confidence': doc.ocr_confidence,
                'confidence_level': self._get_confidence_level(doc.ocr_confidence or 0),
                'processed_at': doc.ocr_processed_at.isoformat() if doc.ocr_processed_at else None,
                'phi_filtered': doc.phi_filtered,
                'text_length': len(doc.ocr_text) if doc.ocr_text else 0
            })
        
        report = {
            'report_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'report_type': 'OCR Quality Report',
                'format': format
            },
            'summary_metrics': metrics,
            'document_details': document_details
        }
        
        return report
