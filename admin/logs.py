"""
Admin log management functionality
"""
from models import AdminLog, User
from app import db
from datetime import datetime
import logging

def log_admin_action(user_id, action, details, ip_address=None):
    """Log an administrative action"""
    try:
        log_entry = AdminLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        logging.info(f"Admin action logged: {action} by user {user_id}")
        
    except Exception as e:
        logging.error(f"Error logging admin action: {e}")
        db.session.rollback()

def get_admin_logs(limit=100, user_id=None, action_type=None, date_from=None, date_to=None):
    """Get admin logs with optional filtering"""
    try:
        query = AdminLog.query
        
        # Apply filters
        if user_id:
            query = query.filter(AdminLog.user_id == user_id)
        
        if action_type:
            query = query.filter(AdminLog.action.contains(action_type))
        
        if date_from:
            query = query.filter(AdminLog.timestamp >= date_from)
        
        if date_to:
            query = query.filter(AdminLog.timestamp <= date_to)
        
        # Order by most recent first
        logs = query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
        
        return logs
        
    except Exception as e:
        logging.error(f"Error getting admin logs: {e}")
        return []

def get_log_statistics():
    """Get statistics about admin log activity"""
    try:
        from datetime import timedelta
        
        # Get total logs
        total_logs = AdminLog.query.count()
        
        # Get logs from last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_logs = AdminLog.query.filter(AdminLog.timestamp >= yesterday).count()
        
        # Get logs from last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_logs = AdminLog.query.filter(AdminLog.timestamp >= week_ago).count()
        
        # Get most active users
        from sqlalchemy import func
        active_users = db.session.query(
            AdminLog.user_id, 
            User.username,
            func.count(AdminLog.id).label('log_count')
        ).join(User).group_by(AdminLog.user_id, User.username)\
         .order_by(func.count(AdminLog.id).desc()).limit(5).all()
        
        # Get most common actions
        common_actions = db.session.query(
            AdminLog.action,
            func.count(AdminLog.id).label('action_count')
        ).group_by(AdminLog.action)\
         .order_by(func.count(AdminLog.id).desc()).limit(10).all()
        
        return {
            'total_logs': total_logs,
            'recent_logs': recent_logs,
            'weekly_logs': weekly_logs,
            'active_users': [
                {'user_id': user_id, 'username': username, 'count': count}
                for user_id, username, count in active_users
            ],
            'common_actions': [
                {'action': action, 'count': count}
                for action, count in common_actions
            ]
        }
        
    except Exception as e:
        logging.error(f"Error getting log statistics: {e}")
        return {}

def cleanup_old_logs(days_to_keep=90):
    """Clean up logs older than specified days"""
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        old_logs = AdminLog.query.filter(AdminLog.timestamp < cutoff_date)
        count = old_logs.count()
        old_logs.delete()
        
        db.session.commit()
        
        logging.info(f"Cleaned up {count} old admin logs")
        return count
        
    except Exception as e:
        logging.error(f"Error cleaning up old logs: {e}")
        db.session.rollback()
        return 0

def export_logs_to_json(date_from=None, date_to=None):
    """Export logs to JSON format for compliance"""
    try:
        query = AdminLog.query
        
        if date_from:
            query = query.filter(AdminLog.timestamp >= date_from)
        
        if date_to:
            query = query.filter(AdminLog.timestamp <= date_to)
        
        logs = query.order_by(AdminLog.timestamp.desc()).all()
        
        export_data = []
        for log in logs:
            export_data.append({
                'id': log.id,
                'user': log.user.username if log.user else 'System',
                'user_id': log.user_id,
                'action': log.action,
                'details': log.details,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat()
            })
        
        return export_data
        
    except Exception as e:
        logging.error(f"Error exporting logs: {e}")
        return []
