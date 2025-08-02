"""
Admin log management system for HIPAA compliance and audit trails.
Provides comprehensive logging, filtering, and export capabilities.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import request
from sqlalchemy import and_, or_, func
from app import db
from models import AdminLog, User

logger = logging.getLogger(__name__)

class AdminLogManager:
    """Manages admin activity logging and audit trails"""
    
    def __init__(self):
        self.log_retention_days = 2555  # 7 years for HIPAA compliance
        self.max_export_records = 10000
    
    def log_activity(self, action: str, details: str = None, user_id: int = None, 
                    ip_address: str = None, user_agent: str = None) -> bool:
        """
        Log administrative activity
        
        Args:
            action: Type of action performed
            details: Detailed description of the action
            user_id: ID of user performing action
            ip_address: IP address of request
            user_agent: User agent string
            
        Returns:
            Boolean indicating success
        """
        try:
            # Get request context if available
            if not ip_address and request:
                ip_address = request.remote_addr
            if not user_agent and request:
                user_agent = request.headers.get('User-Agent', '')
            
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                details=details or '',
                ip_address=ip_address,
                user_agent=user_agent[:512] if user_agent else None,  # Truncate long user agents
                timestamp=datetime.utcnow()
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            logger.info(f"Admin activity logged: {action} by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging admin activity: {str(e)}")
            db.session.rollback()
            return False
    
    def get_logs(self, filters: Dict = None, page: int = 1, per_page: int = 50) -> Dict:
        """
        Get admin logs with filtering and pagination
        
        Args:
            filters: Dictionary of filter criteria
            page: Page number for pagination
            per_page: Records per page
            
        Returns:
            Dictionary with logs and pagination info
        """
        try:
            query = AdminLog.query.join(User, AdminLog.user_id == User.id, isouter=True)
            
            # Apply filters
            if filters:
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('action'):
                    query = query.filter(AdminLog.action.ilike(f"%{filters['action']}%"))
                
                if filters.get('date_from'):
                    try:
                        date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                        query = query.filter(AdminLog.timestamp >= date_from)
                    except ValueError:
                        pass
                
                if filters.get('date_to'):
                    try:
                        date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d')
                        # Add 1 day to include the entire day
                        date_to = date_to + timedelta(days=1)
                        query = query.filter(AdminLog.timestamp < date_to)
                    except ValueError:
                        pass
                
                if filters.get('ip_address'):
                    query = query.filter(AdminLog.ip_address.ilike(f"%{filters['ip_address']}%"))
                
                if filters.get('search'):
                    search_term = f"%{filters['search']}%"
                    query = query.filter(
                        or_(
                            AdminLog.action.ilike(search_term),
                            AdminLog.details.ilike(search_term)
                        )
                    )
            
            # Order by timestamp (most recent first)
            query = query.order_by(AdminLog.timestamp.desc())
            
            # Paginate
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            
            return {
                'logs': pagination.items,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'per_page': per_page,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next,
                'prev_num': pagination.prev_num,
                'next_num': pagination.next_num
            }
            
        except Exception as e:
            logger.error(f"Error getting admin logs: {str(e)}")
            return {
                'logs': [],
                'total': 0,
                'pages': 0,
                'current_page': page,
                'per_page': per_page,
                'has_prev': False,
                'has_next': False,
                'prev_num': None,
                'next_num': None
            }
    
    def get_log_statistics(self, days: int = 30) -> Dict:
        """
        Get admin log statistics for the dashboard
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total logs in period
            total_logs = AdminLog.query.filter(AdminLog.timestamp >= cutoff_date).count()
            
            # Unique users active
            unique_users = db.session.query(AdminLog.user_id).filter(
                AdminLog.timestamp >= cutoff_date,
                AdminLog.user_id.isnot(None)
            ).distinct().count()
            
            # Top actions
            top_actions = db.session.query(
                AdminLog.action,
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(AdminLog.action).order_by(
                func.count(AdminLog.id).desc()
            ).limit(10).all()
            
            # Daily activity (last 7 days)
            daily_activity = []
            for i in range(7):
                day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                
                day_count = AdminLog.query.filter(
                    and_(
                        AdminLog.timestamp >= day_start,
                        AdminLog.timestamp < day_end
                    )
                ).count()
                
                daily_activity.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': day_count
                })
            
            daily_activity.reverse()  # Oldest first
            
            # Recent critical actions
            critical_actions = ['user_created', 'user_deleted', 'phi_config_changed', 
                              'screening_type_deleted', 'preset_import']
            
            recent_critical = AdminLog.query.filter(
                and_(
                    AdminLog.timestamp >= cutoff_date,
                    AdminLog.action.in_(critical_actions)
                )
            ).order_by(AdminLog.timestamp.desc()).limit(5).all()
            
            return {
                'total_logs': total_logs,
                'unique_users': unique_users,
                'top_actions': [{'action': action, 'count': count} for action, count in top_actions],
                'daily_activity': daily_activity,
                'recent_critical': recent_critical
            }
            
        except Exception as e:
            logger.error(f"Error getting log statistics: {str(e)}")
            return {
                'total_logs': 0,
                'unique_users': 0,
                'top_actions': [],
                'daily_activity': [],
                'recent_critical': []
            }
    
    def export_logs(self, filters: Dict = None, format: str = 'json', limit: int = None) -> Dict:
        """
        Export admin logs in specified format
        
        Args:
            filters: Filter criteria
            format: Export format ('json', 'csv')
            limit: Maximum number of records to export
            
        Returns:
            Dictionary with export data
        """
        try:
            if limit is None:
                limit = self.max_export_records
            
            query = AdminLog.query.join(User, AdminLog.user_id == User.id, isouter=True)
            
            # Apply same filters as get_logs
            if filters:
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('action'):
                    query = query.filter(AdminLog.action.ilike(f"%{filters['action']}%"))
                
                if filters.get('date_from'):
                    try:
                        date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                        query = query.filter(AdminLog.timestamp >= date_from)
                    except ValueError:
                        pass
                
                if filters.get('date_to'):
                    try:
                        date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d')
                        date_to = date_to + timedelta(days=1)
                        query = query.filter(AdminLog.timestamp < date_to)
                    except ValueError:
                        pass
            
            logs = query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
            
            if format == 'json':
                export_data = [
                    {
                        'id': log.id,
                        'timestamp': log.timestamp.isoformat(),
                        'user_id': log.user_id,
                        'username': log.user.username if log.user else 'System',
                        'action': log.action,
                        'details': log.details,
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent
                    }
                    for log in logs
                ]
            elif format == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(['Timestamp', 'User', 'Action', 'Details', 'IP Address'])
                
                # Write data
                for log in logs:
                    writer.writerow([
                        log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        log.user.username if log.user else 'System',
                        log.action,
                        log.details or '',
                        log.ip_address or ''
                    ])
                
                export_data = output.getvalue()
                output.close()
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            return {
                'success': True,
                'data': export_data,
                'format': format,
                'record_count': len(logs),
                'export_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting logs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_logs(self) -> Dict:
        """
        Clean up logs older than retention period
        
        Returns:
            Dictionary with cleanup results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.log_retention_days)
            
            # Count logs to be deleted
            old_logs_count = AdminLog.query.filter(AdminLog.timestamp < cutoff_date).count()
            
            if old_logs_count == 0:
                return {
                    'success': True,
                    'deleted_count': 0,
                    'message': 'No old logs to clean up'
                }
            
            # Delete old logs
            AdminLog.query.filter(AdminLog.timestamp < cutoff_date).delete()
            db.session.commit()
            
            logger.info(f"Cleaned up {old_logs_count} old admin logs")
            
            return {
                'success': True,
                'deleted_count': old_logs_count,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_activity_summary(self, user_id: int, days: int = 30) -> Dict:
        """
        Get activity summary for a specific user
        
        Args:
            user_id: User ID to analyze
            days: Number of days to analyze
            
        Returns:
            Dictionary with user activity summary
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Get user's logs
            logs = AdminLog.query.filter(
                and_(
                    AdminLog.user_id == user_id,
                    AdminLog.timestamp >= cutoff_date
                )
            ).order_by(AdminLog.timestamp.desc()).all()
            
            # Calculate statistics
            total_actions = len(logs)
            unique_actions = len(set(log.action for log in logs))
            
            # Action breakdown
            action_counts = {}
            for log in logs:
                action_counts[log.action] = action_counts.get(log.action, 0) + 1
            
            # Most active days
            daily_counts = {}
            for log in logs:
                day = log.timestamp.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            
            most_active_day = max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None
            
            return {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'period_days': days,
                'total_actions': total_actions,
                'unique_actions': unique_actions,
                'action_breakdown': action_counts,
                'most_active_day': {
                    'date': most_active_day[0].isoformat(),
                    'actions': most_active_day[1]
                } if most_active_day else None,
                'recent_logs': logs[:10]  # Last 10 actions
            }
            
        except Exception as e:
            logger.error(f"Error getting user activity summary: {str(e)}")
            return {'error': str(e)}

# Global log manager instance
log_manager = AdminLogManager()

def log_admin_activity(action: str, details: str = None, user_id: int = None):
    """Convenience function to log admin activity"""
    return log_manager.log_activity(action, details, user_id)
