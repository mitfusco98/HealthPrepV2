"""
Admin log management and utilities
Handles comprehensive logging of admin actions and system events
"""
import logging
from datetime import datetime, timedelta
from flask import request
from app import db
from models import AdminLog, User

logger = logging.getLogger(__name__)

class AdminLogger:
    """Simple wrapper class for admin logging functionality"""
    
    def log_action(self, user_id, action, resource_type=None, resource_id=None, details=None, ip_address=None):
        """Log an admin action - wrapper for log_admin_action function"""
        return log_admin_action(user_id, action, resource_type, resource_id, details, ip_address)

def log_admin_action(user_id, action, resource_type=None, resource_id=None, details=None, ip_address=None):
    """Log an admin action to the database"""
    try:
        if ip_address is None:
            ip_address = request.remote_addr if request else None
        
        admin_log = AdminLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(admin_log)
        db.session.commit()
        
        logger.info(f"Admin action logged: {action} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        db.session.rollback()

class AdminLogManager:
    """Manages admin logs and provides analytics"""
    
    def __init__(self):
        pass
    
    def get_recent_logs(self, limit=50, user_id=None, action=None, days=30):
        """Get recent admin logs with optional filtering"""
        query = AdminLog.query
        
        # Date filtering
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(AdminLog.timestamp >= cutoff_date)
        
        # User filtering
        if user_id:
            query = query.filter(AdminLog.user_id == user_id)
        
        # Action filtering
        if action:
            query = query.filter(AdminLog.action == action)
        
        return query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
    
    def get_log_statistics(self, days=30):
        """Get statistics about admin activity"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total actions
        total_actions = AdminLog.query.filter(
            AdminLog.timestamp >= cutoff_date
        ).count()
        
        # Actions by type
        action_counts = db.session.query(
            AdminLog.action,
            db.func.count(AdminLog.id).label('count')
        ).filter(
            AdminLog.timestamp >= cutoff_date
        ).group_by(AdminLog.action).all()
        
        # Actions by user
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
            'total_actions': total_actions,
            'actions_by_type': [
                {'action': row.action, 'count': row.count}
                for row in action_counts
            ],
            'actions_by_user': [
                {'username': row.username, 'count': row.count}
                for row in user_counts
            ],
            'daily_activity': [
                {'date': row.date.isoformat(), 'count': row.count}
                for row in daily_counts
            ]
        }
    
    def export_logs(self, start_date=None, end_date=None, format='json'):
        """Export logs in various formats"""
        query = AdminLog.query.join(User)
        
        if start_date:
            query = query.filter(AdminLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AdminLog.timestamp <= end_date)
        
        logs = query.order_by(AdminLog.timestamp.desc()).all()
        
        if format == 'json':
            import json
            export_data = []
            
            for log in logs:
                export_data.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user': log.user.username if log.user else 'Unknown',
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'details': log.details,
                    'ip_address': log.ip_address
                })
            
            return json.dumps(export_data, indent=2)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'ID', 'Timestamp', 'User', 'Action', 'Resource Type',
                'Resource ID', 'Details', 'IP Address'
            ])
            
            # Data rows
            for log in logs:
                writer.writerow([
                    log.id,
                    log.timestamp.isoformat(),
                    log.user.username if log.user else 'Unknown',
                    log.action,
                    log.resource_type or '',
                    log.resource_id or '',
                    str(log.details) if log.details else '',
                    log.ip_address or ''
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def cleanup_old_logs(self, days_to_keep=365):
        """Clean up old log entries"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = AdminLog.query.filter(
            AdminLog.timestamp < cutoff_date
        ).delete()
        
        db.session.commit()
        
        logger.info(f"Cleaned up {deleted_count} old admin log entries")
        return deleted_count
    
    def get_user_activity_summary(self, user_id, days=30):
        """Get activity summary for a specific user"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        user = User.query.get(user_id)
        if not user:
            return None
        
        logs = AdminLog.query.filter(
            AdminLog.user_id == user_id,
            AdminLog.timestamp >= cutoff_date
        ).order_by(AdminLog.timestamp.desc()).all()
        
        # Action summary
        action_summary = {}
        for log in logs:
            action = log.action
            if action not in action_summary:
                action_summary[action] = 0
            action_summary[action] += 1
        
        # Resource summary
        resource_summary = {}
        for log in logs:
            resource_type = log.resource_type or 'system'
            if resource_type not in resource_summary:
                resource_summary[resource_type] = 0
            resource_summary[resource_type] += 1
        
        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            },
            'period_days': days,
            'total_actions': len(logs),
            'action_summary': action_summary,
            'resource_summary': resource_summary,
            'recent_actions': [
                {
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id
                }
                for log in logs[:10]  # Last 10 actions
            ]
        }
    
    def get_security_events(self, days=30):
        """Get security-related log events"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        security_actions = [
            'login', 'logout', 'password_change', 'user_create',
            'user_delete', 'role_change', 'settings_change',
            'phi_settings_change', 'failed_login'
        ]
        
        security_logs = AdminLog.query.filter(
            AdminLog.timestamp >= cutoff_date,
            AdminLog.action.in_(security_actions)
        ).order_by(AdminLog.timestamp.desc()).all()
        
        return [
            {
                'timestamp': log.timestamp,
                'user': log.user.username if log.user else 'System',
                'action': log.action,
                'ip_address': log.ip_address,
                'details': log.details
            }
            for log in security_logs
        ]
    
    def generate_compliance_report(self, start_date, end_date):
        """Generate a compliance report for audit purposes"""
        logs = AdminLog.query.filter(
            AdminLog.timestamp >= start_date,
            AdminLog.timestamp <= end_date
        ).order_by(AdminLog.timestamp.asc()).all()
        
        report = {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'total_events': len(logs),
            'phi_access_events': [],
            'user_management_events': [],
            'system_configuration_events': [],
            'data_modification_events': []
        }
        
        for log in logs:
            event_data = {
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.username if log.user else 'System',
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'ip_address': log.ip_address
            }
            
            # Categorize events
            if 'phi' in log.action.lower() or log.resource_type in ['document', 'patient']:
                report['phi_access_events'].append(event_data)
            elif log.action in ['user_create', 'user_delete', 'role_change']:
                report['user_management_events'].append(event_data)
            elif 'settings' in log.action.lower():
                report['system_configuration_events'].append(event_data)
            elif log.action in ['create', 'update', 'delete']:
                report['data_modification_events'].append(event_data)
        
        return report
