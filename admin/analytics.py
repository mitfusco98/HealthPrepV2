"""
Admin analytics and reporting
Provides insights into system usage, performance, and ROI metrics
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from models import Patient, Screening, Document, User, AdminLog, OCRProcessing, db
from sqlalchemy import func, and_, case

class AdminAnalytics:
    """Provides analytics and reporting for admin dashboard"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get key metrics for admin dashboard"""
        try:
            # Current date ranges
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)
            
            metrics = {
                "overview": self._get_overview_metrics(),
                "activity": self._get_activity_metrics(today_start, week_start, month_start),
                "screening_metrics": self._get_screening_metrics(),
                "document_metrics": self._get_document_metrics(),
                "roi_metrics": self._get_roi_metrics(),
                "quality_metrics": self._get_quality_metrics(),
                "generated_at": now.isoformat()
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error generating dashboard metrics: {str(e)}")
            return {"error": str(e)}
    
    def _get_overview_metrics(self) -> Dict[str, Any]:
        """Get basic system overview metrics"""
        try:
            total_patients = Patient.query.count()
            total_users = User.query.count()
            total_screenings = Screening.query.count()
            total_documents = Document.query.count()
            
            # Active screenings by status
            screening_status_counts = db.session.query(
                Screening.status,
                func.count(Screening.id)
            ).group_by(Screening.status).all()
            
            status_breakdown = {status: count for status, count in screening_status_counts}
            
            return {
                "total_patients": total_patients,
                "total_users": total_users,
                "total_screenings": total_screenings,
                "total_documents": total_documents,
                "screening_status_breakdown": status_breakdown
            }
            
        except Exception as e:
            self.logger.error(f"Error getting overview metrics: {str(e)}")
            return {}
    
    def _get_activity_metrics(self, today_start: datetime, week_start: datetime, month_start: datetime) -> Dict[str, Any]:
        """Get activity metrics for different time periods"""
        try:
            # Admin actions
            today_actions = AdminLog.query.filter(AdminLog.timestamp >= today_start).count()
            week_actions = AdminLog.query.filter(AdminLog.timestamp >= week_start).count()
            month_actions = AdminLog.query.filter(AdminLog.timestamp >= month_start).count()
            
            # Document processing
            today_processed = OCRProcessing.query.filter(OCRProcessing.processing_start >= today_start).count()
            week_processed = OCRProcessing.query.filter(OCRProcessing.processing_start >= week_start).count()
            month_processed = OCRProcessing.query.filter(OCRProcessing.processing_start >= month_start).count()
            
            # Screening updates
            today_screening_updates = Screening.query.filter(Screening.updated_at >= today_start).count()
            week_screening_updates = Screening.query.filter(Screening.updated_at >= week_start).count()
            month_screening_updates = Screening.query.filter(Screening.updated_at >= month_start).count()
            
            return {
                "admin_actions": {
                    "today": today_actions,
                    "week": week_actions,
                    "month": month_actions
                },
                "documents_processed": {
                    "today": today_processed,
                    "week": week_processed,
                    "month": month_processed
                },
                "screening_updates": {
                    "today": today_screening_updates,
                    "week": week_screening_updates,
                    "month": month_screening_updates
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting activity metrics: {str(e)}")
            return {}
    
    def _get_screening_metrics(self) -> Dict[str, Any]:
        """Get screening-related metrics"""
        try:
            # Screening compliance rates
            total_screenings = Screening.query.count()
            due_screenings = Screening.query.filter_by(status='due').count()
            due_soon_screenings = Screening.query.filter_by(status='due_soon').count()
            complete_screenings = Screening.query.filter_by(status='complete').count()
            
            compliance_rate = (complete_screenings / total_screenings * 100) if total_screenings > 0 else 0
            
            # Most common screening types
            screening_type_counts = db.session.query(
                func.count(Screening.id).label('count'),
                func.max(Screening.screening_type.has().name).label('screening_name')
            ).join(Screening.screening_type).group_by(
                Screening.screening_type_id
            ).order_by(func.count(Screening.id).desc()).limit(5).all()
            
            # Screening gaps (due + due_soon)
            gaps_by_type = db.session.query(
                func.count(Screening.id).label('gap_count'),
                func.max(Screening.screening_type.has().name).label('screening_name')
            ).join(Screening.screening_type).filter(
                Screening.status.in_(['due', 'due_soon'])
            ).group_by(
                Screening.screening_type_id
            ).order_by(func.count(Screening.id).desc()).limit(5).all()
            
            return {
                "total_screenings": total_screenings,
                "compliance_rate": round(compliance_rate, 2),
                "status_counts": {
                    "due": due_screenings,
                    "due_soon": due_soon_screenings,
                    "complete": complete_screenings
                },
                "most_common_screenings": [
                    {"name": name, "count": count} for count, name in screening_type_counts
                ],
                "top_screening_gaps": [
                    {"name": name, "gap_count": count} for count, name in gaps_by_type
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting screening metrics: {str(e)}")
            return {}
    
    def _get_document_metrics(self) -> Dict[str, Any]:
        """Get document processing metrics"""
        try:
            total_documents = Document.query.count()
            processed_documents = Document.query.filter_by(is_processed=True).count()
            processing_rate = (processed_documents / total_documents * 100) if total_documents > 0 else 0
            
            # Documents by type
            doc_type_counts = db.session.query(
                Document.document_type,
                func.count(Document.id)
            ).group_by(Document.document_type).all()
            
            # OCR confidence distribution
            confidence_ranges = [
                ("High (80-100%)", 80, 100),
                ("Medium (60-79%)", 60, 79),
                ("Low (40-59%)", 40, 59),
                ("Very Low (0-39%)", 0, 39)
            ]
            
            confidence_distribution = {}
            for label, min_conf, max_conf in confidence_ranges:
                count = Document.query.filter(
                    and_(
                        Document.ocr_confidence >= min_conf,
                        Document.ocr_confidence <= max_conf
                    )
                ).count()
                confidence_distribution[label] = count
            
            # Average OCR confidence
            avg_confidence = db.session.query(
                func.avg(Document.ocr_confidence)
            ).filter(Document.ocr_confidence.isnot(None)).scalar() or 0
            
            return {
                "total_documents": total_documents,
                "processed_documents": processed_documents,
                "processing_rate": round(processing_rate, 2),
                "document_types": {doc_type: count for doc_type, count in doc_type_counts},
                "confidence_distribution": confidence_distribution,
                "average_confidence": round(avg_confidence, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting document metrics: {str(e)}")
            return {}
    
    def _get_roi_metrics(self) -> Dict[str, Any]:
        """Calculate ROI and time-saving metrics"""
        try:
            # Estimate time saved based on automated processes
            total_patients = Patient.query.count()
            total_screenings = Screening.query.count()
            processed_documents = Document.query.filter_by(is_processed=True).count()
            
            # Time savings estimates (in minutes)
            time_per_manual_screening = 5  # minutes
            time_per_manual_document_review = 3  # minutes  
            time_per_prep_sheet = 15  # minutes
            
            estimated_time_saved = (
                (total_screenings * time_per_manual_screening) +
                (processed_documents * time_per_manual_document_review) +
                (total_patients * time_per_prep_sheet)
            )
            
            # Convert to hours
            hours_saved = estimated_time_saved / 60
            
            # Cost savings (assuming $30/hour for medical assistant time)
            hourly_rate = 30
            cost_savings = hours_saved * hourly_rate
            
            # Gaps closed (screenings moved from due to complete)
            gaps_closed = Screening.query.filter_by(status='complete').count()
            
            return {
                "estimated_minutes_saved": estimated_time_saved,
                "estimated_hours_saved": round(hours_saved, 2),
                "estimated_cost_savings": round(cost_savings, 2),
                "gaps_closed": gaps_closed,
                "automated_screenings": total_screenings,
                "processed_documents": processed_documents,
                "patients_with_prep_sheets": total_patients
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating ROI metrics: {str(e)}")
            return {}
    
    def _get_quality_metrics(self) -> Dict[str, Any]:
        """Get quality and performance metrics"""
        try:
            # OCR success rate
            total_ocr_attempts = OCRProcessing.query.count()
            successful_ocr = OCRProcessing.query.filter_by(success=True).count()
            ocr_success_rate = (successful_ocr / total_ocr_attempts * 100) if total_ocr_attempts > 0 else 0
            
            # Document classification accuracy (based on confidence scores)
            high_confidence_docs = Document.query.filter(Document.ocr_confidence >= 80).count()
            total_scored_docs = Document.query.filter(Document.ocr_confidence.isnot(None)).count()
            classification_accuracy = (high_confidence_docs / total_scored_docs * 100) if total_scored_docs > 0 else 0
            
            # System uptime proxy (based on processing activity)
            last_24h = datetime.utcnow() - timedelta(hours=24)
            recent_activity = OCRProcessing.query.filter(OCRProcessing.processing_start >= last_24h).count()
            system_health_score = min(100, (recent_activity / 10) * 100)  # Scale based on expected activity
            
            return {
                "ocr_success_rate": round(ocr_success_rate, 2),
                "classification_accuracy": round(classification_accuracy, 2),
                "system_health_score": round(system_health_score, 2),
                "total_ocr_attempts": total_ocr_attempts,
                "successful_ocr": successful_ocr,
                "high_confidence_documents": high_confidence_docs
            }
            
        except Exception as e:
            self.logger.error(f"Error getting quality metrics: {str(e)}")
            return {}
    
    def generate_performance_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            report = {
                "report_period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "executive_summary": {},
                "detailed_metrics": {},
                "trends": {},
                "recommendations": []
            }
            
            # Executive summary
            total_patients = Patient.query.count()
            screenings_updated = Screening.query.filter(Screening.updated_at >= cutoff_date).count()
            documents_processed = OCRProcessing.query.filter(
                OCRProcessing.processing_start >= cutoff_date
            ).count()
            
            report["executive_summary"] = {
                "total_patients_managed": total_patients,
                "screenings_updated_in_period": screenings_updated,
                "documents_processed_in_period": documents_processed,
                "estimated_time_saved_hours": round((screenings_updated * 5 + documents_processed * 3) / 60, 2)
            }
            
            # Detailed metrics
            report["detailed_metrics"] = {
                "screening_performance": self._get_screening_performance_metrics(cutoff_date),
                "document_processing": self._get_document_processing_metrics(cutoff_date),
                "user_activity": self._get_user_activity_metrics(cutoff_date),
                "system_performance": self._get_system_performance_metrics(cutoff_date)
            }
            
            # Generate recommendations
            report["recommendations"] = self._generate_recommendations(report["detailed_metrics"])
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {str(e)}")
            return {"error": str(e)}
    
    def _get_screening_performance_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get screening performance metrics for report"""
        try:
            # Compliance improvements
            recent_completions = Screening.query.filter(
                and_(
                    Screening.updated_at >= cutoff_date,
                    Screening.status == 'complete'
                )
            ).count()
            
            # Top performing screening types
            top_performers = db.session.query(
                func.count(Screening.id).label('completions'),
                func.max(Screening.screening_type.has().name).label('screening_name')
            ).join(Screening.screening_type).filter(
                and_(
                    Screening.updated_at >= cutoff_date,
                    Screening.status == 'complete'
                )
            ).group_by(Screening.screening_type_id).order_by(
                func.count(Screening.id).desc()
            ).limit(5).all()
            
            return {
                "recent_completions": recent_completions,
                "top_performing_screenings": [
                    {"name": name, "completions": count} for count, name in top_performers
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting screening performance metrics: {str(e)}")
            return {}
    
    def _get_document_processing_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get document processing metrics for report"""
        try:
            # Processing statistics
            total_processed = OCRProcessing.query.filter(
                OCRProcessing.processing_start >= cutoff_date
            ).count()
            
            successful_processed = OCRProcessing.query.filter(
                and_(
                    OCRProcessing.processing_start >= cutoff_date,
                    OCRProcessing.success == True
                )
            ).count()
            
            avg_confidence = db.session.query(
                func.avg(OCRProcessing.confidence_score)
            ).filter(
                and_(
                    OCRProcessing.processing_start >= cutoff_date,
                    OCRProcessing.success == True
                )
            ).scalar() or 0
            
            return {
                "total_processed": total_processed,
                "successful_processed": successful_processed,
                "success_rate": (successful_processed / total_processed * 100) if total_processed > 0 else 0,
                "average_confidence": round(avg_confidence, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting document processing metrics: {str(e)}")
            return {}
    
    def _get_user_activity_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get user activity metrics for report"""
        try:
            # Active users
            active_users = db.session.query(
                func.count(func.distinct(AdminLog.user_id))
            ).filter(AdminLog.timestamp >= cutoff_date).scalar()
            
            # Most active actions
            top_actions = db.session.query(
                AdminLog.action,
                func.count(AdminLog.id)
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(AdminLog.action).order_by(
                func.count(AdminLog.id).desc()
            ).limit(5).all()
            
            return {
                "active_users": active_users,
                "top_actions": [{"action": action, "count": count} for action, count in top_actions]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user activity metrics: {str(e)}")
            return {}
    
    def _get_system_performance_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get system performance metrics for report"""
        try:
            # Error rates
            total_operations = (
                AdminLog.query.filter(AdminLog.timestamp >= cutoff_date).count() +
                OCRProcessing.query.filter(OCRProcessing.processing_start >= cutoff_date).count()
            )
            
            failed_operations = OCRProcessing.query.filter(
                and_(
                    OCRProcessing.processing_start >= cutoff_date,
                    OCRProcessing.success == False
                )
            ).count()
            
            error_rate = (failed_operations / total_operations * 100) if total_operations > 0 else 0
            
            return {
                "total_operations": total_operations,
                "failed_operations": failed_operations,
                "error_rate": round(error_rate, 2),
                "uptime_estimate": round(100 - error_rate, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system performance metrics: {str(e)}")
            return {}
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics"""
        recommendations = []
        
        try:
            # Check document processing performance
            doc_metrics = metrics.get("document_processing", {})
            if doc_metrics.get("success_rate", 100) < 95:
                recommendations.append("Document processing success rate is below 95%. Review OCR configuration and document quality.")
            
            if doc_metrics.get("average_confidence", 100) < 75:
                recommendations.append("Average OCR confidence is below 75%. Consider improving document scanning quality.")
            
            # Check system performance
            sys_metrics = metrics.get("system_performance", {})
            if sys_metrics.get("error_rate", 0) > 5:
                recommendations.append("System error rate is above 5%. Review system logs and performance.")
            
            # Check screening performance
            screen_metrics = metrics.get("screening_performance", {})
            if screen_metrics.get("recent_completions", 0) == 0:
                recommendations.append("No recent screening completions detected. Review screening workflow and user adoption.")
            
            if not recommendations:
                recommendations.append("System is performing well within normal parameters.")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {str(e)}")
            return ["Unable to generate recommendations due to analysis error."]

# Global analytics instance
admin_analytics = AdminAnalytics()
