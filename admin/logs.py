from datetime import datetime, timedelta
from flask import request
from models import AdminLog, User
from app import db
import logging

class AdminLogManager:
    """Manager class for admin logging functionality"""
    
    def __init__(self):
        pass
    
    def log_action(self, user_id, action, details=None, target_type=None, target_id=None):
        """Log administrative actions for audit trail"""
        try:
            # Get IP address and user agent from request context
            ip_address = request.remote_addr if request else 'system'
            user_agent = request.headers.get('User-Agent') if request else 'system'
            
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                description=str(details) if details else action,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            logging.info(f"Admin action logged: {action} by user {user_id}")
            
        except Exception as e:
            logging.error(f"Failed to log admin action: {str(e)}")
            db.session.rollback()
    
    def get_recent_logs(self, limit=10):
        """Get recent admin logs"""
        try:
            return AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logging.error(f"Error retrieving recent logs: {str(e)}")
            return []
    
    def get_filtered_logs(self, filters, page=1, per_page=50):
        """Get filtered admin logs with pagination"""
        try:
            query = AdminLog.query
            
            # Apply filters
            if filters.get('action'):
                query = query.filter(AdminLog.action.ilike(f'%{filters["action"]}%'))
            
            if filters.get('user_id'):
                query = query.filter(AdminLog.user_id == filters['user_id'])
            
            if filters.get('start_date'):
                query = query.filter(AdminLog.timestamp >= filters['start_date'])
            
            if filters.get('end_date'):
                end_date = filters['end_date'] + timedelta(days=1)
                query = query.filter(AdminLog.timestamp < end_date)
            
            # Order by most recent first
            query = query.order_by(AdminLog.timestamp.desc())
            
            # Paginate
            logs = query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            return {
                'logs': logs.items,
                'pagination': logs
            }
            
        except Exception as e:
            logging.error(f"Error retrieving filtered logs: {str(e)}")
            return {'logs': [], 'pagination': None}
    
    def get_event_types(self):
        """Get list of unique event types for filtering"""
        try:
            actions = db.session.query(AdminLog.action).distinct().all()
            return [action[0] for action in actions]
        except Exception as e:
            logging.error(f"Error getting event types: {str(e)}")
            return []
    
    def export_logs(self, days=30, format_type='json'):
        """Export admin logs"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs = AdminLog.query.filter(AdminLog.timestamp >= cutoff_date).all()
            
            export_data = []
            for log in logs:
                export_data.append({
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'action': log.action,
                    'description': log.description,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent
                })
            
            return {
                'success': True,
                'data': export_data,
                'count': len(export_data)
            }
            
        except Exception as e:
            logging.error(f"Error exporting logs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def log_admin_action(action, description=None, user_id=None, ip_address=None):
    """Log administrative actions for audit trail"""
    try:
        # Get current user if not provided
        if not user_id:
            from flask_login import current_user
            if current_user.is_authenticated:
                user_id = current_user.id
        
        # Get IP address if not provided
        if not ip_address:
            ip_address = request.remote_addr if request else 'system'
        
        # Get user agent
        user_agent = request.headers.get('User-Agent') if request else 'system'
        
        log_entry = AdminLog(
            user_id=user_id,
            action=action,
            description=description or action,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        logging.info(f"Admin action logged: {action} by user {user_id}")
        
    except Exception as e:
        logging.error(f"Failed to log admin action: {str(e)}")
        db.session.rollback()

def get_admin_logs(page=1, per_page=50, filter_action=None, filter_user=None, date_from=None, date_to=None):
    """Get filtered admin logs with pagination"""
    try:
        query = AdminLog.query
        
        # Apply filters
        if filter_action:
            query = query.filter(AdminLog.action.ilike(f'%{filter_action}%'))
        
        if filter_user:
            query = query.join(User).filter(User.username.ilike(f'%{filter_user}%'))
        
        if date_from:
            query = query.filter(AdminLog.timestamp >= date_from)
        
        if date_to:
            # Add 1 day to include entire day
            end_date = date_to + timedelta(days=1)
            query = query.filter(AdminLog.timestamp < end_date)
        
        # Order by most recent first
        query = query.order_by(AdminLog.timestamp.desc())
        
        # Paginate
        logs = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return logs
        
    except Exception as e:
        logging.error(f"Error retrieving admin logs: {str(e)}")
        return None

def get_log_statistics():
    """Get statistics about admin log activity"""
    try:
        # Total logs
        total_logs = AdminLog.query.count()
        
        # Logs in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = AdminLog.query.filter(AdminLog.timestamp >= week_ago).count()
        
        # Most active users (last 30 days)
        month_ago = datetime.utcnow() - timedelta(days=30)
        active_users = db.session.query(
            User.username,
            db.func.count(AdminLog.id).label('action_count')
        ).join(AdminLog).filter(
            AdminLog.timestamp >= month_ago
        ).group_by(User.id, User.username).order_by(
            db.func.count(AdminLog.id).desc()
        ).limit(5).all()
        
        # Most common actions
        common_actions = db.session.query(
            AdminLog.action,
            db.func.count(AdminLog.id).label('count')
        ).filter(
            AdminLog.timestamp >= month_ago
        ).group_by(AdminLog.action).order_by(
            db.func.count(AdminLog.id).desc()
        ).limit(10).all()
        
        return {
            'total_logs': total_logs,
            'recent_logs': recent_logs,
            'active_users': [{'username': user[0], 'count': user[1]} for user in active_users],
            'common_actions': [{'action': action[0], 'count': action[1]} for action in common_actions]
        }
        
    except Exception as e:
        logging.error(f"Error getting log statistics: {str(e)}")
        return {
            'total_logs': 0,
            'recent_logs': 0,
            'active_users': [],
            'common_actions': []
        }

def export_logs_to_json(date_from=None, date_to=None):
    """Export admin logs to JSON format for compliance"""
    try:
        query = AdminLog.query.join(User, AdminLog.user_id == User.id, isouter=True)
        
        if date_from:
            query = query.filter(AdminLog.timestamp >= date_from)
        if date_to:
            end_date = date_to + timedelta(days=1)
            query = query.filter(AdminLog.timestamp < end_date)
        
        logs = query.order_by(AdminLog.timestamp.desc()).all()
        
        export_data = []
        for log in logs:
            export_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.username if log.user else 'System',
                'action': log.action,
                'description': log.description,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent
            })
        
        return export_data
        
    except Exception as e:
        logging.error(f"Error exporting logs: {str(e)}")
        return []

def cleanup_old_logs(days_to_keep=365):
    """Clean up logs older than specified days"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = AdminLog.query.filter(
            AdminLog.timestamp < cutoff_date
        ).delete()
        
        db.session.commit()
        
        log_admin_action(
            'LOG_CLEANUP',
            f'Deleted {deleted_count} log entries older than {days_to_keep} days'
        )
        
        return deleted_count
        
    except Exception as e:
        logging.error(f"Error cleaning up logs: {str(e)}")
        db.session.rollback()
        return 0
