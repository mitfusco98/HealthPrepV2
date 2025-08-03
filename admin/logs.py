"""
Admin log management
Handles system logging, audit trails, and administrative activity tracking
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc
from app import db
from models import AdminLog, User
import logging
import json

class AdminLogManager:
    """Manages administrative logging and audit trails"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def log_action(self, action, description=None, user_id=None, ip_address=None, user_agent=None):
        """Log an administrative action"""
        try:
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            self.logger.info(f"Admin action logged: {action} by user {user_id}")
            return log_entry.id
            
        except Exception as e:
            self.logger.error(f"Error logging admin action: {str(e)}")
            db.session.rollback()
            return None
    
    def get_logs(self, filters=None, page=1, per_page=50):
        """Get administrative logs with optional filtering"""
        try:
            query = AdminLog.query
            
            # Apply filters
            if filters:
                if filters.get('action'):
                    query = query.filter(AdminLog.action.contains(filters['action']))
                
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('user_name'):
                    query = query.join(User).filter(User.username.contains(filters['user_name']))
                
                if filters.get('start_date'):
                    start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d')
                    query = query.filter(AdminLog.created_at >= start_date)
                
                if filters.get('end_date'):
                    end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d') + timedelta(days=1)
                    query = query.filter(AdminLog.created_at < end_date)
                
                if filters.get('ip_address'):
                    query = query.filter(AdminLog.ip_address == filters['ip_address'])
            
            # Order by most recent first
            query = query.order_by(AdminLog.created_at.desc())
            
            # Paginate
            logs = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return logs
            
        except Exception as e:
            self.logger.error(f"Error getting admin logs: {str(e)}")
            return None
    
    def get_log_statistics(self, days=30):
        """Get statistics about admin log activity"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total logs in period
            total_logs = AdminLog.query.filter(AdminLog.created_at >= cutoff_date).count()
            
            # Logs by action type
            from sqlalchemy import func
            action_stats = db.session.query(
                AdminLog.action,
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.created_at >= cutoff_date
            ).group_by(AdminLog.action).order_by(desc('count')).all()
            
            # Logs by user
            user_stats = db.session.query(
                User.username,
                func.count(AdminLog.id).label('count')
            ).join(AdminLog).filter(
                AdminLog.created_at >= cutoff_date
            ).group_by(User.username).order_by(desc('count')).all()
            
            # Daily activity
            daily_stats = db.session.query(
                func.date(AdminLog.created_at).label('date'),
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.created_at >= cutoff_date
            ).group_by(func.date(AdminLog.created_at)).order_by('date').all()
            
            return {
                'total_logs': total_logs,
                'period_days': days,
                'action_breakdown': [{'action': action, 'count': count} for action, count in action_stats],
                'user_activity': [{'username': username, 'count': count} for username, count in user_stats],
                'daily_activity': [{'date': str(date), 'count': count} for date, count in daily_stats]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting log statistics: {str(e)}")
            return {}
    
    def export_logs(self, filters=None, format='json'):
        """Export logs to various formats"""
        try:
            query = AdminLog.query
            
            # Apply same filters as get_logs
            if filters:
                if filters.get('action'):
                    query = query.filter(AdminLog.action.contains(filters['action']))
                
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('start_date'):
                    start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d')
                    query = query.filter(AdminLog.created_at >= start_date)
                
                if filters.get('end_date'):
                    end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d') + timedelta(days=1)
                    query = query.filter(AdminLog.created_at < end_date)
            
            logs = query.order_by(AdminLog.created_at.desc()).all()
            
            if format == 'json':
                return self._export_logs_json(logs)
            elif format == 'csv':
                return self._export_logs_csv(logs)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
        except Exception as e:
            self.logger.error(f"Error exporting logs: {str(e)}")
            raise
    
    def _export_logs_json(self, logs):
        """Export logs as JSON"""
        export_data = {
            'exported_at': datetime.utcnow().isoformat(),
            'total_logs': len(logs),
            'logs': []
        }
        
        for log in logs:
            log_data = {
                'id': log.id,
                'action': log.action,
                'description': log.description,
                'user_id': log.user_id,
                'username': log.user.username if log.user else None,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.created_at.isoformat()
            }
            export_data['logs'].append(log_data)
        
        return json.dumps(export_data, indent=2)
    
    def _export_logs_csv(self, logs):
        """Export logs as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Action', 'Description', 'User ID', 'Username',
            'IP Address', 'User Agent', 'Created At'
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.id,
                log.action,
                log.description,
                log.user_id,
                log.user.username if log.user else '',
                log.ip_address,
                log.user_agent,
                log.created_at.isoformat()
            ])
        
        return output.getvalue()
    
    def cleanup_old_logs(self, days_to_keep=90):
        """Clean up old log entries"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            old_logs = AdminLog.query.filter(AdminLog.created_at < cutoff_date)
            count = old_logs.count()
            
            old_logs.delete()
            db.session.commit()
            
            self.logger.info(f"Cleaned up {count} old log entries older than {days_to_keep} days")
            
            # Log the cleanup action
            self.log_action(
                'log_cleanup',
                f'Cleaned up {count} log entries older than {days_to_keep} days'
            )
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {str(e)}")
            db.session.rollback()
            return 0
    
    def get_security_events(self, days=7):
        """Get security-related log events"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            security_actions = [
                'user_login',
                'user_logout',
                'login_failed',
                'password_change',
                'user_created',
                'user_deactivated',
                'permission_change',
                'admin_access',
                'phi_filtering',
                'document_access',
                'data_export'
            ]
            
            security_logs = AdminLog.query.filter(
                and_(
                    AdminLog.created_at >= cutoff_date,
                    AdminLog.action.in_(security_actions)
                )
            ).order_by(AdminLog.created_at.desc()).all()
            
            return security_logs
            
        except Exception as e:
            self.logger.error(f"Error getting security events: {str(e)}")
            return []
    
    def detect_suspicious_activity(self, hours=24):
        """Detect potentially suspicious activity patterns"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours)
            
            suspicious_patterns = []
            
            # Multiple failed login attempts
            from sqlalchemy import func
            failed_logins = db.session.query(
                AdminLog.ip_address,
                func.count(AdminLog.id).label('attempts')
            ).filter(
                and_(
                    AdminLog.action == 'login_failed',
                    AdminLog.created_at >= cutoff_date
                )
            ).group_by(AdminLog.ip_address).having(func.count(AdminLog.id) >= 5).all()
            
            for ip, attempts in failed_logins:
                suspicious_patterns.append({
                    'type': 'multiple_failed_logins',
                    'details': f'{attempts} failed login attempts from IP {ip}',
                    'severity': 'high' if attempts >= 10 else 'medium'
                })
            
            # Unusual activity hours (outside 6 AM - 10 PM)
            unusual_hours = AdminLog.query.filter(
                and_(
                    AdminLog.created_at >= cutoff_date,
                    or_(
                        func.extract('hour', AdminLog.created_at) < 6,
                        func.extract('hour', AdminLog.created_at) > 22
                    )
                )
            ).count()
            
            if unusual_hours > 10:
                suspicious_patterns.append({
                    'type': 'unusual_activity_hours',
                    'details': f'{unusual_hours} actions performed outside normal hours',
                    'severity': 'low'
                })
            
            # High volume of PHI access
            phi_access = AdminLog.query.filter(
                and_(
                    AdminLog.action.in_(['document_access', 'patient_viewed', 'prep_sheet_generated']),
                    AdminLog.created_at >= cutoff_date
                )
            ).count()
            
            if phi_access > 100:
                suspicious_patterns.append({
                    'type': 'high_phi_access',
                    'details': f'{phi_access} PHI access events in {hours} hours',
                    'severity': 'medium'
                })
            
            return suspicious_patterns
            
        except Exception as e:
            self.logger.error(f"Error detecting suspicious activity: {str(e)}")
            return []
    
    def get_user_activity_summary(self, user_id, days=30):
        """Get activity summary for a specific user"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            user_logs = AdminLog.query.filter(
                and_(
                    AdminLog.user_id == user_id,
                    AdminLog.created_at >= cutoff_date
                )
            ).order_by(AdminLog.created_at.desc()).all()
            
            # Categorize actions
            action_categories = {
                'authentication': ['user_login', 'user_logout', 'password_change'],
                'patient_management': ['patient_created', 'patient_updated', 'patient_viewed'],
                'document_management': ['document_uploaded', 'document_processed', 'document_viewed'],
                'screening_management': ['screening_created', 'screening_updated', 'screenings_refreshed'],
                'administrative': ['admin_access', 'settings_changed', 'preset_import'],
                'other': []
            }
            
            categorized_actions = {category: [] for category in action_categories.keys()}
            
            for log in user_logs:
                categorized = False
                for category, actions in action_categories.items():
                    if log.action in actions:
                        categorized_actions[category].append(log)
                        categorized = True
                        break
                
                if not categorized:
                    categorized_actions['other'].append(log)
            
            summary = {
                'user_id': user_id,
                'period_days': days,
                'total_actions': len(user_logs),
                'categories': {
                    category: len(logs) for category, logs in categorized_actions.items()
                },
                'most_recent_activity': user_logs[0].created_at if user_logs else None,
                'daily_average': len(user_logs) / days if days > 0 else 0
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting user activity summary: {str(e)}")
            return {}
    
    def archive_logs(self, archive_before_date):
        """Archive old logs to separate storage"""
        try:
            # In a production system, this would move logs to long-term storage
            # For now, we'll just mark them as archived
            
            logs_to_archive = AdminLog.query.filter(
                AdminLog.created_at < archive_before_date
            )
            
            count = logs_to_archive.count()
            
            # In a real implementation, you would:
            # 1. Export logs to external storage (S3, etc.)
            # 2. Verify the export
            # 3. Delete from active database
            
            self.logger.info(f"Would archive {count} logs before {archive_before_date}")
            
            # Log the archival
            self.log_action(
                'logs_archived',
                f'Archived {count} logs before {archive_before_date}'
            )
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error archiving logs: {str(e)}")
            return 0
