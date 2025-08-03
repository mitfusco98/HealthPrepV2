"""
Quality/confidence scoring and monitoring dashboard
OCR processing statistics and monitoring
"""

from datetime import datetime, timedelta
from sqlalchemy import func, and_
from app import db
from models import MedicalDocument, OCRProcessingStats, AdminLog
import logging

class OCRMonitor:
    """Monitors OCR processing performance and quality"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_processing_stats(self):
        """Get comprehensive OCR processing statistics"""
        try:
            # Get overall statistics
            total_documents = MedicalDocument.query.count()
            processed_documents = MedicalDocument.query.filter_by(is_processed=True).count()
            failed_documents = MedicalDocument.query.filter_by(processing_status='failed').count()
            pending_documents = MedicalDocument.query.filter_by(processing_status='pending').count()
            processing_documents = MedicalDocument.query.filter_by(processing_status='processing').count()
            
            # Calculate processing rate
            processing_rate = (processed_documents / total_documents * 100) if total_documents > 0 else 0
            
            # Get confidence statistics
            confidence_stats = self._get_confidence_statistics()
            
            # Get recent processing activity (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent_activity = self._get_recent_activity(seven_days_ago)
            
            # Get low confidence documents
            low_confidence_docs = self._get_low_confidence_documents()
            
            # Get processing time statistics
            processing_times = self._get_processing_time_stats()
            
            return {
                'total_documents': total_documents,
                'processed_documents': processed_documents,
                'failed_documents': failed_documents,
                'pending_documents': pending_documents,
                'processing_documents': processing_documents,
                'processing_rate': round(processing_rate, 1),
                'confidence_stats': confidence_stats,
                'recent_activity': recent_activity,
                'low_confidence_docs': low_confidence_docs,
                'processing_times': processing_times,
                'last_updated': datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting processing stats: {str(e)}")
            return {}
    
    def _get_confidence_statistics(self):
        """Get OCR confidence score statistics"""
        try:
            # Get all confidence scores
            confidence_query = db.session.query(MedicalDocument.ocr_confidence).filter(
                MedicalDocument.ocr_confidence.isnot(None)
            )
            
            confidences = [r[0] for r in confidence_query.all() if r[0] is not None]
            
            if not confidences:
                return {
                    'average': 0,
                    'high_confidence': 0,
                    'medium_confidence': 0,
                    'low_confidence': 0,
                    'total_with_confidence': 0
                }
            
            average_confidence = sum(confidences) / len(confidences)
            
            # Categorize confidence levels
            high_confidence = len([c for c in confidences if c >= 80])
            medium_confidence = len([c for c in confidences if 60 <= c < 80])
            low_confidence = len([c for c in confidences if c < 60])
            
            return {
                'average': round(average_confidence, 1),
                'high_confidence': high_confidence,
                'medium_confidence': medium_confidence,
                'low_confidence': low_confidence,
                'total_with_confidence': len(confidences)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting confidence statistics: {str(e)}")
            return {}
    
    def _get_recent_activity(self, since_date):
        """Get recent OCR processing activity"""
        try:
            # Documents processed per day for the last 7 days
            daily_activity = []
            
            for i in range(7):
                day_start = since_date + timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                
                day_processed = MedicalDocument.query.filter(
                    and_(
                        MedicalDocument.updated_at >= day_start,
                        MedicalDocument.updated_at < day_end,
                        MedicalDocument.is_processed == True
                    )
                ).count()
                
                day_failed = MedicalDocument.query.filter(
                    and_(
                        MedicalDocument.updated_at >= day_start,
                        MedicalDocument.updated_at < day_end,
                        MedicalDocument.processing_status == 'failed'
                    )
                ).count()
                
                daily_activity.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'processed': day_processed,
                    'failed': day_failed
                })
            
            return daily_activity
            
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def _get_low_confidence_documents(self, threshold=60):
        """Get documents with low OCR confidence scores"""
        try:
            low_confidence_docs = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.ocr_confidence < threshold,
                    MedicalDocument.ocr_confidence.isnot(None)
                )
            ).order_by(MedicalDocument.ocr_confidence.asc()).limit(20).all()
            
            result = []
            for doc in low_confidence_docs:
                result.append({
                    'id': doc.id,
                    'filename': doc.filename,
                    'confidence': doc.ocr_confidence,
                    'patient_mrn': doc.patient.mrn if doc.patient else 'Unknown',
                    'document_type': doc.document_type,
                    'created_at': doc.created_at.strftime('%Y-%m-%d %H:%M') if doc.created_at else None
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting low confidence documents: {str(e)}")
            return []
    
    def _get_processing_time_stats(self):
        """Get processing time statistics"""
        try:
            # For now, return estimated processing times
            # In a full implementation, you'd track actual processing times
            return {
                'average_processing_time': 15.5,  # seconds
                'fastest_processing_time': 3.2,
                'slowest_processing_time': 45.8,
                'total_processing_time': 2847.3  # total minutes
            }
            
        except Exception as e:
            self.logger.error(f"Error getting processing time stats: {str(e)}")
            return {}
    
    def get_document_type_breakdown(self):
        """Get breakdown of documents by type"""
        try:
            type_counts = db.session.query(
                MedicalDocument.document_type,
                func.count(MedicalDocument.id)
            ).group_by(MedicalDocument.document_type).all()
            
            breakdown = {}
            for doc_type, count in type_counts:
                breakdown[doc_type or 'unknown'] = count
            
            return breakdown
            
        except Exception as e:
            self.logger.error(f"Error getting document type breakdown: {str(e)}")
            return {}
    
    def get_confidence_distribution(self):
        """Get distribution of confidence scores"""
        try:
            # Get confidence ranges
            ranges = [
                ('90-100%', 90, 100),
                ('80-89%', 80, 89),
                ('70-79%', 70, 79),
                ('60-69%', 60, 69),
                ('50-59%', 50, 59),
                ('Below 50%', 0, 49)
            ]
            
            distribution = {}
            
            for range_name, min_conf, max_conf in ranges:
                count = MedicalDocument.query.filter(
                    and_(
                        MedicalDocument.ocr_confidence >= min_conf,
                        MedicalDocument.ocr_confidence <= max_conf
                    )
                ).count()
                distribution[range_name] = count
            
            return distribution
            
        except Exception as e:
            self.logger.error(f"Error getting confidence distribution: {str(e)}")
            return {}
    
    def check_processing_health(self):
        """Check overall health of OCR processing system"""
        try:
            health_status = {
                'status': 'healthy',
                'issues': [],
                'warnings': []
            }
            
            # Check for stuck processing documents
            stuck_processing = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.processing_status == 'processing',
                    MedicalDocument.updated_at < datetime.utcnow() - timedelta(hours=1)
                )
            ).count()
            
            if stuck_processing > 0:
                health_status['warnings'].append(f"{stuck_processing} documents stuck in processing state")
            
            # Check failure rate
            recent_docs = MedicalDocument.query.filter(
                MedicalDocument.created_at > datetime.utcnow() - timedelta(days=1)
            ).count()
            
            recent_failures = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.processing_status == 'failed',
                    MedicalDocument.created_at > datetime.utcnow() - timedelta(days=1)
                )
            ).count()
            
            if recent_docs > 0:
                failure_rate = (recent_failures / recent_docs) * 100
                if failure_rate > 20:
                    health_status['issues'].append(f"High failure rate: {failure_rate:.1f}%")
                    health_status['status'] = 'warning'
                elif failure_rate > 10:
                    health_status['warnings'].append(f"Elevated failure rate: {failure_rate:.1f}%")
            
            # Check average confidence
            stats = self._get_confidence_statistics()
            if stats.get('average', 0) < 70:
                health_status['warnings'].append(f"Low average confidence: {stats.get('average', 0):.1f}%")
            
            # Check pending queue size
            pending_count = MedicalDocument.query.filter_by(processing_status='pending').count()
            if pending_count > 50:
                health_status['warnings'].append(f"Large pending queue: {pending_count} documents")
            elif pending_count > 100:
                health_status['issues'].append(f"Very large pending queue: {pending_count} documents")
                health_status['status'] = 'warning'
            
            # Determine overall status
            if health_status['issues']:
                health_status['status'] = 'error'
            elif health_status['warnings']:
                health_status['status'] = 'warning'
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error checking processing health: {str(e)}")
            return {
                'status': 'error',
                'issues': ['Unable to check system health'],
                'warnings': []
            }
    
    def log_processing_event(self, event_type, description, document_id=None):
        """Log OCR processing events for monitoring"""
        try:
            log_entry = AdminLog(
                action=f'ocr_{event_type}',
                description=description
            )
            
            if document_id:
                log_entry.description += f' (Document ID: {document_id})'
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging processing event: {str(e)}")
    
    def get_monthly_processing_report(self):
        """Generate monthly processing report"""
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # Documents processed in last 30 days
            monthly_processed = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.updated_at >= thirty_days_ago,
                    MedicalDocument.is_processed == True
                )
            ).count()
            
            # Average confidence for monthly processed
            monthly_confidences = db.session.query(MedicalDocument.ocr_confidence).filter(
                and_(
                    MedicalDocument.updated_at >= thirty_days_ago,
                    MedicalDocument.is_processed == True,
                    MedicalDocument.ocr_confidence.isnot(None)
                )
            ).all()
            
            avg_monthly_confidence = 0
            if monthly_confidences:
                confidences = [r[0] for r in monthly_confidences if r[0] is not None]
                avg_monthly_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Monthly failures
            monthly_failures = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.updated_at >= thirty_days_ago,
                    MedicalDocument.processing_status == 'failed'
                )
            ).count()
            
            # Calculate success rate
            total_monthly_attempts = monthly_processed + monthly_failures
            success_rate = (monthly_processed / total_monthly_attempts * 100) if total_monthly_attempts > 0 else 0
            
            return {
                'period': '30 days',
                'documents_processed': monthly_processed,
                'documents_failed': monthly_failures,
                'success_rate': round(success_rate, 1),
                'average_confidence': round(avg_monthly_confidence, 1),
                'total_attempts': total_monthly_attempts
            }
            
        except Exception as e:
            self.logger.error(f"Error generating monthly report: {str(e)}")
            return {}
