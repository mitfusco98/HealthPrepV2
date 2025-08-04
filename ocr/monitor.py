"""
OCR monitoring dashboard with quality assessment and processing statistics.
Provides real-time monitoring of OCR performance and document processing.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from app import db
from models import MedicalDocument, AdminLog

class OCRMonitor:
    """Monitors OCR processing performance and quality metrics."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_processing_dashboard_data(self, days: int = 7) -> Dict[str, any]:
        """Get comprehensive OCR processing data for dashboard display."""
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get documents processed in the time period
            processed_docs = db.session.query(MedicalDocument).filter(
                MedicalDocument.created_at >= start_date,
                MedicalDocument.content.isnot(None)  # Has been OCR processed
            ).all()
            
            # Calculate basic statistics
            total_documents = len(processed_docs)
            total_with_ocr = len([d for d in processed_docs if d.content])
            total_with_phi_filter = len([d for d in processed_docs if d.has_phi_filtered])
            
            # Confidence distribution
            confidence_stats = self._calculate_confidence_distribution(processed_docs)
            
            # Processing trends by day
            daily_trends = self._calculate_daily_processing_trends(processed_docs, days)
            
            # Quality assessment summary
            quality_summary = self._assess_overall_quality(processed_docs)
            
            # Document type breakdown
            type_breakdown = self._calculate_type_breakdown(processed_docs)
            
            # Performance metrics
            performance_metrics = self._calculate_performance_metrics(processed_docs)
            
            return {
                'summary': {
                    'total_documents': total_documents,
                    'ocr_processed': total_with_ocr,
                    'phi_filtered': total_with_phi_filter,
                    'processing_rate': (total_with_ocr / max(total_documents, 1)) * 100,
                    'phi_filter_rate': (total_with_phi_filter / max(total_with_ocr, 1)) * 100,
                    'period_days': days
                },
                'confidence_distribution': confidence_stats,
                'daily_trends': daily_trends,
                'quality_summary': quality_summary,
                'document_types': type_breakdown,
                'performance_metrics': performance_metrics,
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating OCR dashboard data: {e}")
            return self._get_empty_dashboard_data()
    
    def _calculate_confidence_distribution(self, documents: List[MedicalDocument]) -> Dict[str, any]:
        """Calculate confidence score distribution and statistics."""
        
        confidence_scores = [d.confidence_score for d in documents if d.confidence_score is not None]
        
        if not confidence_scores:
            return {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
                'very_low_confidence': 0,
                'average_confidence': 0.0,
                'median_confidence': 0.0,
                'total_scored': 0
            }
        
        # Convert to percentage scale (stored as 0-1, display as 0-100)
        confidence_percentages = [score * 100 for score in confidence_scores]
        
        # Categorize confidence levels
        high_confidence = len([s for s in confidence_percentages if s >= 80])
        medium_confidence = len([s for s in confidence_percentages if 60 <= s < 80])
        low_confidence = len([s for s in confidence_percentages if 40 <= s < 60])
        very_low_confidence = len([s for s in confidence_percentages if s < 40])
        
        # Calculate statistics
        avg_confidence = sum(confidence_percentages) / len(confidence_percentages)
        sorted_scores = sorted(confidence_percentages)
        median_confidence = sorted_scores[len(sorted_scores) // 2]
        
        return {
            'high_confidence': high_confidence,
            'medium_confidence': medium_confidence,
            'low_confidence': low_confidence,
            'very_low_confidence': very_low_confidence,
            'average_confidence': round(avg_confidence, 1),
            'median_confidence': round(median_confidence, 1),
            'total_scored': len(confidence_scores),
            'distribution_percentages': {
                'high': round((high_confidence / len(confidence_scores)) * 100, 1),
                'medium': round((medium_confidence / len(confidence_scores)) * 100, 1),
                'low': round((low_confidence / len(confidence_scores)) * 100, 1),
                'very_low': round((very_low_confidence / len(confidence_scores)) * 100, 1)
            }
        }
    
    def _calculate_daily_processing_trends(self, documents: List[MedicalDocument], days: int) -> List[Dict]:
        """Calculate daily processing trends over the specified period."""
        
        # Group documents by date
        daily_counts = defaultdict(lambda: {
            'total': 0,
            'ocr_processed': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'avg_confidence': 0.0
        })
        
        for doc in documents:
            doc_date = doc.created_at.date()
            daily_counts[doc_date]['total'] += 1
            
            if doc.content:
                daily_counts[doc_date]['ocr_processed'] += 1
                
                if doc.confidence_score is not None:
                    confidence_pct = doc.confidence_score * 100
                    
                    if confidence_pct >= 80:
                        daily_counts[doc_date]['high_confidence'] += 1
                    elif confidence_pct >= 60:
                        daily_counts[doc_date]['medium_confidence'] += 1
                    else:
                        daily_counts[doc_date]['low_confidence'] += 1
        
        # Calculate average confidence per day
        for date_key, counts in daily_counts.items():
            date_docs = [d for d in documents if d.created_at.date() == date_key and d.confidence_score]
            if date_docs:
                avg_conf = sum(d.confidence_score * 100 for d in date_docs) / len(date_docs)
                counts['avg_confidence'] = round(avg_conf, 1)
        
        # Convert to list format for easy chart rendering
        end_date = datetime.utcnow().date()
        trends = []
        
        for i in range(days):
            date = end_date - timedelta(days=i)
            counts = daily_counts.get(date, daily_counts[None])  # Get default if no data
            
            trends.append({
                'date': date.isoformat(),
                'date_display': date.strftime('%m/%d'),
                **counts
            })
        
        return list(reversed(trends))  # Chronological order
    
    def _assess_overall_quality(self, documents: List[MedicalDocument]) -> Dict[str, any]:
        """Assess overall OCR quality and identify potential issues."""
        
        total_docs = len(documents)
        ocr_docs = [d for d in documents if d.content]
        confident_docs = [d for d in ocr_docs if d.confidence_score and d.confidence_score >= 0.6]
        
        # Quality indicators
        quality_indicators = {
            'processing_success_rate': (len(ocr_docs) / max(total_docs, 1)) * 100,
            'high_confidence_rate': (len(confident_docs) / max(len(ocr_docs), 1)) * 100,
            'phi_filtering_coverage': (len([d for d in ocr_docs if d.has_phi_filtered]) / max(len(ocr_docs), 1)) * 100
        }
        
        # Identify potential issues
        issues = []
        recommendations = []
        
        if quality_indicators['processing_success_rate'] < 90:
            issues.append("Low OCR processing success rate")
            recommendations.append("Check document quality and supported formats")
        
        if quality_indicators['high_confidence_rate'] < 70:
            issues.append("High number of low-confidence extractions")
            recommendations.append("Consider document preprocessing or format optimization")
        
        if len(ocr_docs) > 0:
            avg_text_length = sum(len(d.content or '') for d in ocr_docs) / len(ocr_docs)
            if avg_text_length < 100:
                issues.append("Average extracted text length is very short")
                recommendations.append("Verify document content and OCR configuration")
        
        # Overall quality assessment
        overall_score = (
            quality_indicators['processing_success_rate'] * 0.4 +
            quality_indicators['high_confidence_rate'] * 0.6
        )
        
        if overall_score >= 85:
            overall_quality = "Excellent"
        elif overall_score >= 75:
            overall_quality = "Good"
        elif overall_score >= 60:
            overall_quality = "Fair"
        else:
            overall_quality = "Poor"
        
        return {
            'overall_quality': overall_quality,
            'overall_score': round(overall_score, 1),
            'quality_indicators': {k: round(v, 1) for k, v in quality_indicators.items()},
            'issues': issues,
            'recommendations': recommendations,
            'documents_analyzed': total_docs
        }
    
    def _calculate_type_breakdown(self, documents: List[MedicalDocument]) -> Dict[str, any]:
        """Calculate processing statistics by document type."""
        
        type_stats = defaultdict(lambda: {
            'total': 0,
            'ocr_processed': 0,
            'avg_confidence': 0.0,
            'avg_text_length': 0
        })
        
        for doc in documents:
            doc_type = doc.document_type or 'unknown'
            type_stats[doc_type]['total'] += 1
            
            if doc.content:
                type_stats[doc_type]['ocr_processed'] += 1
        
        # Calculate averages for each type
        for doc_type, stats in type_stats.items():
            type_docs = [d for d in documents if (d.document_type or 'unknown') == doc_type]
            
            # Average confidence
            confident_docs = [d for d in type_docs if d.confidence_score is not None]
            if confident_docs:
                avg_conf = sum(d.confidence_score * 100 for d in confident_docs) / len(confident_docs)
                stats['avg_confidence'] = round(avg_conf, 1)
            
            # Average text length
            text_docs = [d for d in type_docs if d.content]
            if text_docs:
                avg_length = sum(len(d.content) for d in text_docs) / len(text_docs)
                stats['avg_text_length'] = round(avg_length, 0)
        
        return dict(type_stats)
    
    def _calculate_performance_metrics(self, documents: List[MedicalDocument]) -> Dict[str, any]:
        """Calculate performance metrics for OCR processing."""
        
        if not documents:
            return {
                'documents_per_day': 0,
                'processing_efficiency': 0,
                'error_rate': 0,
                'avg_processing_time': None
            }
        
        # Calculate processing rate
        period_days = (max(d.created_at for d in documents) - min(d.created_at for d in documents)).days + 1
        docs_per_day = len(documents) / max(period_days, 1)
        
        # Processing efficiency (successful OCR / total docs)
        successful_ocr = len([d for d in documents if d.content])
        efficiency = (successful_ocr / len(documents)) * 100
        
        # Error rate (docs without content / total docs)
        error_rate = ((len(documents) - successful_ocr) / len(documents)) * 100
        
        return {
            'documents_per_day': round(docs_per_day, 1),
            'processing_efficiency': round(efficiency, 1),
            'error_rate': round(error_rate, 1),
            'total_period_days': period_days,
            'total_documents_analyzed': len(documents)
        }
    
    def get_low_confidence_documents(self, threshold: float = 0.6, limit: int = 50) -> List[Dict]:
        """Get documents with low confidence scores for review."""
        
        try:
            low_confidence_docs = db.session.query(MedicalDocument).filter(
                MedicalDocument.confidence_score < threshold,
                MedicalDocument.confidence_score.isnot(None)
            ).order_by(MedicalDocument.confidence_score.asc()).limit(limit).all()
            
            return [{
                'id': doc.id,
                'filename': doc.filename,
                'document_type': doc.document_type,
                'document_date': doc.document_date.isoformat() if doc.document_date else None,
                'confidence_score': round(doc.confidence_score * 100, 1) if doc.confidence_score else 0,
                'content_length': len(doc.content) if doc.content else 0,
                'patient_id': doc.patient_id,
                'created_at': doc.created_at.isoformat()
            } for doc in low_confidence_docs]
            
        except Exception as e:
            self.logger.error(f"Error retrieving low confidence documents: {e}")
            return []
    
    def get_recent_processing_activity(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """Get recent OCR processing activity."""
        
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            recent_docs = db.session.query(MedicalDocument).filter(
                MedicalDocument.created_at >= start_time,
                MedicalDocument.content.isnot(None)
            ).order_by(MedicalDocument.created_at.desc()).limit(limit).all()
            
            return [{
                'id': doc.id,
                'filename': doc.filename,
                'document_type': doc.document_type,
                'confidence_score': round(doc.confidence_score * 100, 1) if doc.confidence_score else 0,
                'quality_assessment': self._get_quality_label(doc.confidence_score),
                'phi_filtered': doc.has_phi_filtered,
                'content_length': len(doc.content) if doc.content else 0,
                'processed_at': doc.created_at.isoformat()
            } for doc in recent_docs]
            
        except Exception as e:
            self.logger.error(f"Error retrieving recent processing activity: {e}")
            return []
    
    def _get_quality_label(self, confidence_score: Optional[float]) -> str:
        """Get quality label for confidence score."""
        
        if confidence_score is None:
            return "Unknown"
        
        confidence_pct = confidence_score * 100
        
        if confidence_pct >= 80:
            return "High"
        elif confidence_pct >= 60:
            return "Medium"
        elif confidence_pct >= 40:
            return "Low"
        else:
            return "Very Low"
    
    def _get_empty_dashboard_data(self) -> Dict[str, any]:
        """Return empty dashboard data structure for error cases."""
        
        return {
            'summary': {
                'total_documents': 0,
                'ocr_processed': 0,
                'phi_filtered': 0,
                'processing_rate': 0,
                'phi_filter_rate': 0,
                'period_days': 0
            },
            'confidence_distribution': {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
                'very_low_confidence': 0,
                'average_confidence': 0.0,
                'median_confidence': 0.0,
                'total_scored': 0
            },
            'daily_trends': [],
            'quality_summary': {
                'overall_quality': "No Data",
                'overall_score': 0,
                'quality_indicators': {},
                'issues': ["No documents processed"],
                'recommendations': [],
                'documents_analyzed': 0
            },
            'document_types': {},
            'performance_metrics': {
                'documents_per_day': 0,
                'processing_efficiency': 0,
                'error_rate': 0,
                'avg_processing_time': None
            },
            'last_updated': datetime.utcnow().isoformat()
        }
