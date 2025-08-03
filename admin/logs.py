"""
Admin logging functionality.
Handles comprehensive logging of admin actions and system events.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from flask import request
from flask_login import current_user

from app import db
from models import AdminLog, User

def log_admin_action(user_id: Optional[int], action: str, details: Optional[str] = None, 
                    ip_address: Optional[str] = None) -> bool:
    """Log an admin action to the database"""
    try:
        # Get IP address if not provided
        if ip_address is None and request:
            ip_address = request.remote_addr
        
        # Create log entry
        log_entry = AdminLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to application logger
        logger = logging.getLogger(__name__)
        user_info = f"User {user_id}" if user_id else "System"
        logger.info(f"Admin Action: {user_info} - {action} - {details} - IP: {ip_address}")
        
        return True
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log admin action: {str(e)}")
        db.session.rollback()
        return False

def log_user_action(action: str, details: Optional[str] = None) -> bool:
    """Log action for current user"""
    user_id = current_user.id if current_user.is_authenticated else None
    return log_admin_action(user_id, action, details)

def log_system_event(event: str, details: Optional[str] = None) -> bool:
    """Log system event (no user associated)"""
    return log_admin_action(None, f"SYSTEM: {event}", details)

def log_security_event(event: str, details: Optional[str] = None, 
                      ip_address: Optional[str] = None) -> bool:
    """Log security-related event"""
    user_id = current_user.id if current_user.is_authenticated else None
    return log_admin_action(user_id, f"SECURITY: {event}", details, ip_address)

def log_phi_access(action: str, patient_id: Optional[int] = None, 
                   document_id: Optional[int] = None) -> bool:
    """Log PHI access for HIPAA compliance"""
    details = []
    if patient_id:
        details.append(f"Patient ID: {patient_id}")
    if document_id:
        details.append(f"Document ID: {document_id}")
    
    detail_str = " | ".join(details) if details else None
    return log_user_action(f"PHI ACCESS: {action}", detail_str)

def log_data_modification(action: str, table: str, record_id: int, 
                         changes: Optional[Dict] = None) -> bool:
    """Log data modification events"""
    details = f"Table: {table}, Record ID: {record_id}"
    if changes:
        details += f" | Changes: {changes}"
    
    return log_user_action(f"DATA MODIFICATION: {action}", details)

class AdminLogManager:
    """Manager class for admin logging operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_logs(self, page: int = 1, per_page: int = 50, 
                filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get paginated admin logs with optional filtering"""
        try:
            query = AdminLog.query
            
            if filters:
                # Apply filters
                if filters.get('action'):
                    query = query.filter(AdminLog.action.contains(filters['action']))
                
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('start_date'):
                    query = query.filter(AdminLog.timestamp >= filters['start_date'])
                
                if filters.get('end_date'):
                    query = query.filter(AdminLog.timestamp <= filters['end_date'])
                
                if filters.get('ip_address'):
                    query = query.filter(AdminLog.ip_address == filters['ip_address'])
            
            # Get paginated results
            logs = query.order_by(AdminLog.timestamp.desc())\
                       .paginate(page=page, per_page=per_page, error_out=False)
            
            # Format results
            log_data = []
            for log in logs.items:
                user_name = log.user.username if log.user else 'System'
                log_data.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'user_name': user_name,
                    'action': log.action,
                    'details': log.details,
                    'ip_address': log.ip_address
                })
            
            return {
                'logs': log_data,
                'pagination': {
                    'page': logs.page,
                    'pages': logs.pages,
                    'per_page': logs.per_page,
                    'total': logs.total,
                    'has_next': logs.has_next,
                    'has_prev': logs.has_prev
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting admin logs: {str(e)}")
            return {'logs': [], 'pagination': {}}
    
    def get_recent_logs(self, limit: int = 10) -> List[Any]:
        """Get recent admin logs for dashboard display"""
        try:
            logs = AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
            return logs
        except Exception as e:
            self.logger.error(f"Error getting recent logs: {str(e)}")
            return []
    
    def get_filtered_logs(self, filters: Optional[Dict[str, Any]] = None, 
                         page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Get filtered logs - alias for get_logs method"""
        return self.get_logs(page=page, per_page=per_page, filters=filters)
    
    def get_event_types(self) -> List[str]:
        """Get unique event types for filter dropdown"""
        try:
            actions = db.session.query(AdminLog.action).distinct().all()
            return [action[0] for action in actions if action[0]]
        except Exception as e:
            self.logger.error(f"Error getting event types: {str(e)}")
            return []
    
    def export_logs(self, days: int = 30, format_type: str = 'json') -> Dict[str, Any]:
        """Export logs for a specified number of days"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            end_date = datetime.utcnow()
            
            export_data = self.export_logs(start_date=start_date, end_date=end_date, format=format_type)
            
            return {
                'success': True,
                'data': export_data,
                'format': format_type
            }
        except Exception as e:
            self.logger.error(f"Error exporting logs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_action(self, user_id: Optional[int], action: str, 
                   target_type: Optional[str] = None, target_id: Optional[int] = None,
                   details: Optional[Dict] = None) -> bool:
        """Log an action - wrapper for log_admin_action function"""
        detail_str = None
        if details:
            detail_str = str(details)
        if target_type and target_id:
            if detail_str:
                detail_str += f" | Target: {target_type} ID {target_id}"
            else:
                detail_str = f"Target: {target_type} ID {target_id}"
        
        return log_admin_action(user_id, action, detail_str)
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get statistics about admin logs"""
        try:
            total_logs = AdminLog.query.count()
            
            # Logs by action type
            action_stats = db.session.query(
                AdminLog.action,
                db.func.count(AdminLog.id).label('count')
            ).group_by(AdminLog.action).all()
            
            # Recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(hours=24)
            recent_logs = AdminLog.query.filter(AdminLog.timestamp >= yesterday).count()
            
            # Most active users
            user_stats = db.session.query(
                User.username,
                db.func.count(AdminLog.id).label('count')
            ).join(AdminLog, User.id == AdminLog.user_id)\
             .group_by(User.username)\
             .order_by(db.func.count(AdminLog.id).desc())\
             .limit(10).all()
            
            # Security events
            security_logs = AdminLog.query.filter(
                AdminLog.action.like('SECURITY:%')
            ).count()
            
            # PHI access logs
            phi_logs = AdminLog.query.filter(
                AdminLog.action.like('PHI ACCESS:%')
            ).count()
            
            return {
                'total_logs': total_logs,
                'recent_activity': recent_logs,
                'security_events': security_logs,
                'phi_access_events': phi_logs,
                'action_breakdown': {
                    action: count for action, count in action_stats
                },
                'most_active_users': [
                    {'username': username, 'action_count': count}
                    for username, count in user_stats
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting log statistics: {str(e)}")
            return {}
    
    def export_logs(self, start_date: Optional[datetime] = None, 
                   end_date: Optional[datetime] = None,
                   format: str = 'json') -> Dict[str, Any]:
        """Export logs for compliance or analysis"""
        try:
            query = AdminLog.query
            
            if start_date:
                query = query.filter(AdminLog.timestamp >= start_date)
            
            if end_date:
                query = query.filter(AdminLog.timestamp <= end_date)
            
            logs = query.order_by(AdminLog.timestamp.desc()).all()
            
            export_data = []
            for log in logs:
                export_data.append({
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'user_name': log.user.username if log.user else 'System',
                    'action': log.action,
                    'details': log.details,
                    'ip_address': log.ip_address
                })
            
            return {
                'export_generated': datetime.utcnow().isoformat(),
                'total_records': len(export_data),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                },
                'logs': export_data
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting logs: {str(e)}")
            return {}
    
    def cleanup_old_logs(self, days_to_keep: int = 365) -> int:
        """Clean up logs older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            old_logs = AdminLog.query.filter(AdminLog.timestamp < cutoff_date)
            count = old_logs.count()
            
            old_logs.delete()
            db.session.commit()
            
            self.logger.info(f"Cleaned up {count} old admin logs")
            log_system_event("Log Cleanup", f"Removed {count} logs older than {days_to_keep} days")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {str(e)}")
            db.session.rollback()
            return 0
    
    def get_security_report(self) -> Dict[str, Any]:
        """Generate security-focused log report"""
        try:
            # Get security events from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            security_logs = AdminLog.query.filter(
                AdminLog.action.like('SECURITY:%'),
                AdminLog.timestamp >= thirty_days_ago
            ).all()
            
            phi_logs = AdminLog.query.filter(
                AdminLog.action.like('PHI ACCESS:%'),
                AdminLog.timestamp >= thirty_days_ago
            ).all()
            
            # Failed login attempts
            failed_logins = AdminLog.query.filter(
                AdminLog.action.like('%login%'),
                AdminLog.action.like('%failed%'),
                AdminLog.timestamp >= thirty_days_ago
            ).all()
            
            # Unusual IP addresses
            ip_stats = db.session.query(
                AdminLog.ip_address,
                db.func.count(AdminLog.id).label('count')
            ).filter(AdminLog.timestamp >= thirty_days_ago)\
             .group_by(AdminLog.ip_address)\
             .order_by(db.func.count(AdminLog.id).desc()).all()
            
            return {
                'report_period': '30 days',
                'security_events': len(security_logs),
                'phi_access_events': len(phi_logs),
                'failed_login_attempts': len(failed_logins),
                'unique_ip_addresses': len(ip_stats),
                'top_ip_addresses': [
                    {'ip': ip, 'requests': count} 
                    for ip, count in ip_stats[:10]
                ],
                'security_event_details': [
                    {
                        'timestamp': log.timestamp.isoformat(),
                        'action': log.action,
                        'user': log.user.username if log.user else 'Unknown',
                        'ip': log.ip_address,
                        'details': log.details
                    }
                    for log in security_logs[-20:]  # Last 20 events
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error generating security report: {str(e)}")
            return {}
