"""
Admin logging functionality
Handles comprehensive event tracking and audit trails
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

from models import AdminLog, User
from app import db

logger = logging.getLogger(__name__)

class AdminLogger:
    """Handles admin activity logging and audit trails"""
    
    def log_action(self, user_id: Optional[int], action: str, resource_type: str,
                   resource_id: Optional[int] = None, details: Dict[str, Any] = None,
                   ip_address: str = None, user_agent: str = None) -> bool:
        """
        Log an administrative action
        
        Args:
            user_id: ID of user performing action (None for system actions)
            action: Type of action performed
            resource_type: Type of resource affected
            resource_id: ID of specific resource
            details: Additional details about the action
            ip_address: User's IP address
            user_agent: User's browser/client info
        """
        try:
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            logger.debug(f"Logged action: {action} by user {user_id} on {resource_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging admin action: {str(e)}")
            db.session.rollback()
            return False
    
    def get_logs(self, limit: int = 100, offset: int = 0,
                 user_id: Optional[int] = None, action: Optional[str] = None,
                 resource_type: Optional[str] = None,
                 date_from: Optional[datetime] = None,
                 date_to: Optional[datetime] = None) -> List[AdminLog]:
        """
        Retrieve admin logs with filtering
        """
        try:
            query = AdminLog.query
            
            # Apply filters
            if user_id:
                query = query.filter(AdminLog.user_id == user_id)
            
            if action:
                query = query.filter(AdminLog.action.ilike(f'%{action}%'))
            
            if resource_type:
                query = query.filter(AdminLog.resource_type == resource_type)
            
            if date_from:
                query = query.filter(AdminLog.timestamp >= date_from)
            
            if date_to:
                query = query.filter(AdminLog.timestamp <= date_to)
            
            # Order by most recent first
            logs = query.order_by(AdminLog.timestamp.desc())\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
            
            return logs
            
        except Exception as e:
            logger.error(f"Error retrieving admin logs: {str(e)}")
            return []
    
    def get_log_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get statistics about admin logs over a time period
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total logs
            total_logs = AdminLog.query.filter(AdminLog.timestamp >= cutoff_date).count()
            
            # Logs by action type
            action_counts = db.session.query(
                AdminLog.action,
                db.func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(AdminLog.action).all()
            
            # Logs by user
            user_counts = db.session.query(
                User.username,
                db.func.count(AdminLog.id).label('count')
            ).join(AdminLog).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(User.username).all()
            
            # Daily activity
            daily_counts = db.session.query(
                db.func.date(AdminLog.timestamp).label('date'),
                db.func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(db.func.date(AdminLog.timestamp)).all()
            
            return {
                'total_logs': total_logs,
                'period_days': days,
                'action_counts': {action: count for action, count in action_counts},
                'user_counts': {username: count for username, count in user_counts},
                'daily_activity': {
                    str(date): count for date, count in daily_counts
                },
                'avg_daily_activity': total_logs / days if days > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating log statistics: {str(e)}")
            return {}
    
    def get_user_activity(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent activity for a specific user
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            logs = AdminLog.query.filter(
                AdminLog.user_id == user_id,
                AdminLog.timestamp >= cutoff_date
            ).order_by(AdminLog.timestamp.desc()).all()
            
            activity = []
            for log in logs:
                activity.append({
                    'id': log.id,
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'timestamp': log.timestamp,
                    'details': log.details,
                    'ip_address': log.ip_address
                })
            
            return activity
            
        except Exception as e:
            logger.error(f"Error getting user activity: {str(e)}")
            return []
    
    def export_logs(self, user_id: Optional[int] = None, action: Optional[str] = None,
                   resource_type: Optional[str] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Export logs to JSON format for compliance/auditing
        """
        try:
            # Convert date strings to datetime objects
            from_date = None
            to_date = None
            
            if date_from:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
            
            if date_to:
                to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            
            # Get filtered logs
            logs = self.get_logs(
                limit=10000,  # Large limit for export
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                date_from=from_date,
                date_to=to_date
            )
            
            # Format for export
            exported_logs = []
            for log in logs:
                exported_logs.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'username': log.user.username if log.user else 'System',
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'details': log.details,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent
                })
            
            export_data = {
                'export_metadata': {
                    'exported_at': datetime.utcnow().isoformat(),
                    'exported_by': user_id,
                    'total_logs': len(exported_logs),
                    'filters': {
                        'user_id': user_id,
                        'action': action,
                        'resource_type': resource_type,
                        'date_from': date_from,
                        'date_to': date_to
                    }
                },
                'logs': exported_logs
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting logs: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_logs(self, days_to_keep: int = 365) -> int:
        """
        Clean up old log entries (for compliance with data retention policies)
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Count logs to be deleted
            logs_to_delete = AdminLog.query.filter(AdminLog.timestamp < cutoff_date).count()
            
            # Delete old logs
            AdminLog.query.filter(AdminLog.timestamp < cutoff_date).delete()
            db.session.commit()
            
            logger.info(f"Cleaned up {logs_to_delete} log entries older than {days_to_keep} days")
            
            # Log the cleanup action
            self.log_action(
                user_id=None,  # System action
                action='log_cleanup',
                resource_type='admin_log',
                details={
                    'logs_deleted': logs_to_delete,
                    'cutoff_date': cutoff_date.isoformat(),
                    'retention_days': days_to_keep
                }
            )
            
            return logs_to_delete
            
        except Exception as e:
            logger.error(f"Error cleaning up logs: {str(e)}")
            db.session.rollback()
            return 0
    
    def get_security_events(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get security-related events for monitoring
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            security_actions = [
                'login_failed',
                'user_login',
                'user_logout',
                'password_changed',
                'admin_access_denied',
                'unauthorized_access',
                'user_admin_toggled',
                'phi_settings_updated'
            ]
            
            logs = AdminLog.query.filter(
                AdminLog.timestamp >= cutoff_date,
                AdminLog.action.in_(security_actions)
            ).order_by(AdminLog.timestamp.desc()).all()
            
            events = []
            for log in logs:
                events.append({
                    'id': log.id,
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'user': log.user.username if log.user else 'System',
                    'ip_address': log.ip_address,
                    'details': log.details,
                    'severity': self._get_event_severity(log.action)
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting security events: {str(e)}")
            return []
    
    def _get_event_severity(self, action: str) -> str:
        """
        Determine severity level for security events
        """
        high_severity = ['login_failed', 'unauthorized_access', 'admin_access_denied']
        medium_severity = ['user_admin_toggled', 'phi_settings_updated', 'password_changed']
        
        if action in high_severity:
            return 'high'
        elif action in medium_severity:
            return 'medium'
        else:
            return 'low'
    
    def get_audit_trail(self, resource_type: str, resource_id: int) -> List[Dict[str, Any]]:
        """
        Get complete audit trail for a specific resource
        """
        try:
            logs = AdminLog.query.filter(
                AdminLog.resource_type == resource_type,
                AdminLog.resource_id == resource_id
            ).order_by(AdminLog.timestamp.asc()).all()
            
            audit_trail = []
            for log in logs:
                audit_trail.append({
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'user': log.user.username if log.user else 'System',
                    'details': log.details,
                    'ip_address': log.ip_address
                })
            
            return audit_trail
            
        except Exception as e:
            logger.error(f"Error getting audit trail: {str(e)}")
            return []
