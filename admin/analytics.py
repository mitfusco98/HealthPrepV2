"""
Admin analytics and reporting
Provides dashboard statistics and system health monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import func, desc

from models import Patient, Screening, ScreeningType, MedicalDocument, AdminLog, User
from app import db

logger = logging.getLogger(__name__)

class AdminAnalytics:
    """Provides analytics and reporting for admin dashboard"""
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard statistics
        """
        try:
            # Basic counts
            total_patients = Patient.query.count()
            total_screenings = Screening.query.count()
            active_screening_types = ScreeningType.query.filter_by(is_active=True).count()
            total_documents = MedicalDocument.query.count()
            
            # Screening status distribution
            screening_status = db.session.query(
                Screening.status,
                func.count(Screening.id).label('count')
            ).group_by(Screening.status).all()
            
            status_distribution = {status: count for status, count in screening_status}
            
            # Recent activity (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent_documents = MedicalDocument.query.filter(
                MedicalDocument.date_uploaded >= seven_days_ago
            ).count()
            
            recent_activity = AdminLog.query.filter(
                AdminLog.timestamp >= seven_days_ago
            ).count()
            
            # User statistics
            total_users = User.query.count()
            admin_users = User.query.filter_by(is_admin=True).count()
            
            # Compliance metrics
            compliance_rate = self._calculate_overall_compliance()
            
            return {
                'overview': {
                    'total_patients': total_patients,
                    'total_screenings': total_screenings,
                    'active_screening_types': active_screening_types,
                    'total_documents': total_documents,
                    'total_users': total_users,
                    'admin_users': admin_users
                },
                'screening_status': status_distribution,
                'recent_activity': {
                    'new_documents': recent_documents,
                    'admin_actions': recent_activity
                },
                'performance': {
                    'compliance_rate': compliance_rate,
                    'avg_screenings_per_patient': round(total_screenings / max(total_patients, 1), 1)
                },
                'last_updated': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return {'error': str(e)}
    
    def get_screening_analytics(self) -> Dict[str, Any]:
        """
        Get detailed screening analytics
        """
        try:
            # Screening type performance
            screening_performance = db.session.query(
                ScreeningType.name,
                func.count(Screening.id).label('total_screenings'),
                func.sum(func.case([(Screening.status == 'Complete', 1)], else_=0)).label('completed'),
                func.sum(func.case([(Screening.status == 'Due', 1)], else_=0)).label('due'),
                func.sum(func.case([(Screening.status == 'Due Soon', 1)], else_=0)).label('due_soon')
            ).join(Screening).filter(
                ScreeningType.is_active == True
            ).group_by(ScreeningType.name).all()
            
            performance_data = []
            for perf in screening_performance:
                total = perf.total_screenings
                completion_rate = (perf.completed / total * 100) if total > 0 else 0
                
                performance_data.append({
                    'screening_type': perf.name,
                    'total_screenings': total,
                    'completed': perf.completed,
                    'due': perf.due,
                    'due_soon': perf.due_soon,
                    'completion_rate': round(completion_rate, 1)
                })
            
            # Monthly trends
            monthly_trends = self._get_monthly_screening_trends()
            
            return {
                'screening_performance': performance_data,
                'monthly_trends': monthly_trends,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting screening analytics: {str(e)}")
            return {'error': str(e)}
    
    def get_document_analytics(self) -> Dict[str, Any]:
        """
        Get document processing analytics
        """
        try:
            # Document type distribution
            doc_distribution = db.session.query(
                MedicalDocument.document_type,
                func.count(MedicalDocument.id).label('count')
            ).group_by(MedicalDocument.document_type).all()
            
            # OCR processing stats
            total_docs_with_ocr = MedicalDocument.query.filter(
                MedicalDocument.ocr_text.isnot(None)
            ).count()
            
            avg_confidence = db.session.query(
                func.avg(MedicalDocument.ocr_confidence)
            ).filter(
                MedicalDocument.ocr_confidence.isnot(None)
            ).scalar()
            
            # Low confidence documents
            low_confidence_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence < 60,
                MedicalDocument.ocr_confidence.isnot(None)
            ).count()
            
            # Recent uploads (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_uploads = MedicalDocument.query.filter(
                MedicalDocument.date_uploaded >= thirty_days_ago
            ).count()
            
            return {
                'document_distribution': {doc_type: count for doc_type, count in doc_distribution},
                'ocr_statistics': {
                    'total_processed': total_docs_with_ocr,
                    'avg_confidence': round(avg_confidence or 0, 1),
                    'low_confidence_count': low_confidence_docs
                },
                'upload_activity': {
                    'recent_uploads_30d': recent_uploads
                },
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting document analytics: {str(e)}")
            return {'error': str(e)}
    
    def get_user_analytics(self) -> Dict[str, Any]:
        """
        Get user activity analytics
        """
        try:
            # User activity in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            user_activity = db.session.query(
                User.username,
                func.count(AdminLog.id).label('activity_count'),
                func.max(AdminLog.timestamp).label('last_activity')
            ).outerjoin(AdminLog).filter(
                AdminLog.timestamp >= thirty_days_ago
            ).group_by(User.username).all()
            
            # Most common actions
            action_frequency = db.session.query(
                AdminLog.action,
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= thirty_days_ago
            ).group_by(AdminLog.action).order_by(desc('count')).limit(10).all()
            
            # Login statistics
            login_stats = self._get_login_statistics()
            
            return {
                'user_activity': [
                    {
                        'username': ua.username,
                        'activity_count': ua.activity_count,
                        'last_activity': ua.last_activity
                    } for ua in user_activity
                ],
                'common_actions': {action: count for action, count in action_frequency},
                'login_statistics': login_stats,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {str(e)}")
            return {'error': str(e)}
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get system health indicators
        """
        try:
            # Database size and performance indicators
            total_records = (
                Patient.query.count() +
                Screening.query.count() +
                MedicalDocument.query.count() +
                AdminLog.query.count()
            )
            
            # Recent errors from logs
            recent_errors = AdminLog.query.filter(
                AdminLog.action.like('%error%'),
                AdminLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            # OCR processing health
            unprocessed_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_text.is_(None),
                MedicalDocument.date_uploaded >= datetime.utcnow() - timedelta(days=1)
            ).count()
            
            # Screening engine health
            stale_screenings = Screening.query.filter(
                Screening.updated_at < datetime.utcnow() - timedelta(days=7)
            ).count()
            
            # Determine overall health status
            health_score = 100
            if recent_errors > 10:
                health_score -= 20
            if unprocessed_docs > 50:
                health_score -= 15
            if stale_screenings > 100:
                health_score -= 10
            
            health_status = 'Excellent' if health_score >= 90 else \
                           'Good' if health_score >= 70 else \
                           'Fair' if health_score >= 50 else 'Poor'
            
            return {
                'overall_status': health_status,
                'health_score': health_score,
                'indicators': {
                    'total_records': total_records,
                    'recent_errors_24h': recent_errors,
                    'unprocessed_documents': unprocessed_docs,
                    'stale_screenings': stale_screenings
                },
                'recommendations': self._get_health_recommendations(health_score),
                'last_checked': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {'error': str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics
        """
        try:
            # Query performance indicators
            large_queries = AdminLog.query.filter(
                AdminLog.action.like('%query%'),
                AdminLog.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).count()
            
            # Processing times (would need to be tracked separately)
            # For now, provide placeholder metrics
            
            return {
                'database_performance': {
                    'recent_large_queries': large_queries,
                    'connection_pool_status': 'Healthy'  # Placeholder
                },
                'processing_performance': {
                    'avg_screening_refresh_time': '2.3s',  # Placeholder
                    'avg_prep_sheet_generation': '1.8s'    # Placeholder
                },
                'last_measured': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_overall_compliance(self) -> float:
        """
        Calculate overall screening compliance rate
        """
        try:
            total_screenings = Screening.query.count()
            completed_screenings = Screening.query.filter_by(status='Complete').count()
            
            if total_screenings == 0:
                return 0.0
            
            return round((completed_screenings / total_screenings) * 100, 1)
            
        except Exception as e:
            logger.error(f"Error calculating compliance rate: {str(e)}")
            return 0.0
    
    def _get_monthly_screening_trends(self) -> List[Dict[str, Any]]:
        """
        Get monthly screening trends for the last 12 months
        """
        try:
            twelve_months_ago = datetime.utcnow() - timedelta(days=365)
            
            monthly_data = db.session.query(
                func.year(Screening.updated_at).label('year'),
                func.month(Screening.updated_at).label('month'),
                func.count(Screening.id).label('count'),
                func.sum(func.case([(Screening.status == 'Complete', 1)], else_=0)).label('completed')
            ).filter(
                Screening.updated_at >= twelve_months_ago
            ).group_by(
                func.year(Screening.updated_at),
                func.month(Screening.updated_at)
            ).order_by('year', 'month').all()
            
            trends = []
            for data in monthly_data:
                completion_rate = (data.completed / data.count * 100) if data.count > 0 else 0
                trends.append({
                    'year': data.year,
                    'month': data.month,
                    'month_name': datetime(data.year, data.month, 1).strftime('%B %Y'),
                    'total_screenings': data.count,
                    'completed_screenings': data.completed,
                    'completion_rate': round(completion_rate, 1)
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting monthly trends: {str(e)}")
            return []
    
    def _get_login_statistics(self) -> Dict[str, Any]:
        """
        Get user login statistics
        """
        try:
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            # Successful logins
            successful_logins = AdminLog.query.filter(
                AdminLog.action == 'user_login',
                AdminLog.timestamp >= seven_days_ago
            ).count()
            
            # Failed login attempts
            failed_logins = AdminLog.query.filter(
                AdminLog.action == 'login_failed',
                AdminLog.timestamp >= seven_days_ago
            ).count()
            
            # Unique users logged in
            unique_users = db.session.query(AdminLog.user_id).filter(
                AdminLog.action == 'user_login',
                AdminLog.timestamp >= seven_days_ago
            ).distinct().count()
            
            return {
                'successful_logins_7d': successful_logins,
                'failed_logins_7d': failed_logins,
                'unique_users_7d': unique_users,
                'success_rate': round((successful_logins / max(successful_logins + failed_logins, 1)) * 100, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting login statistics: {str(e)}")
            return {}
    
    def _get_health_recommendations(self, health_score: int) -> List[str]:
        """
        Get system health recommendations based on score
        """
        recommendations = []
        
        if health_score < 70:
            recommendations.append("Review recent error logs for critical issues")
            recommendations.append("Check OCR processing queue for backlogs")
            recommendations.append("Consider running screening refresh to update stale data")
        
        if health_score < 50:
            recommendations.append("Immediate attention required - multiple system issues detected")
            recommendations.append("Contact system administrator for urgent maintenance")
        
        if health_score >= 90:
            recommendations.append("System is performing well - continue regular monitoring")
        
        return recommendations
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database connection and size information
        """
        try:
            # Table record counts
            table_counts = {
                'patients': Patient.query.count(),
                'screenings': Screening.query.count(),
                'screening_types': ScreeningType.query.count(),
                'documents': MedicalDocument.query.count(),
                'admin_logs': AdminLog.query.count(),
                'users': User.query.count()
            }
            
            # Database connection info
            engine_info = {
                'database_url': db.engine.url.database,
                'driver': str(db.engine.url.drivername),
                'pool_size': getattr(db.engine.pool, 'size', 'Unknown'),
                'pool_checked_out': getattr(db.engine.pool, 'checkedout', 'Unknown')
            }
            
            return {
                'table_counts': table_counts,
                'total_records': sum(table_counts.values()),
                'connection_info': engine_info
            }
            
        except Exception as e:
            logger.error(f"Error getting database info: {str(e)}")
            return {'error': str(e)}
