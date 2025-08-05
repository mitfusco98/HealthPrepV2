"""
Admin log management and activity tracking
"""
from datetime import datetime
from flask import request
from app import db
from models import AdminLog, User
import json
import logging

class AdminLogger:
    """Handles admin activity logging for HIPAA compliance"""

    @staticmethod
    def log(user_id, action, details=None, ip_address=None, user_agent=None):
        """Log an admin action"""
        try:
            # Get request context if available
            if not ip_address and request:
                ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

            if not user_agent and request:
                user_agent = request.headers.get('User-Agent', '')

            # Create log entry
            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )

            db.session.add(log_entry)
            db.session.commit()

            # Also log to application logger
            logger = logging.getLogger(__name__)
            logger.info(f"Admin action: {action} by user {user_id} - {details}")

        except Exception as e:
            # Don't let logging errors break the application
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log admin action: {str(e)}")

    @staticmethod
    def log_data_access(user_id, data_type, record_id, action='view'):
        """Log access to sensitive data"""
        details = json.dumps({
            'data_type': data_type,
            'record_id': record_id,
            'action': action
        })

        AdminLogger.log(user_id, 'data_access', details)

    @staticmethod
    def log_system_change(user_id, change_type, old_value=None, new_value=None):
        """Log system configuration changes"""
        details = json.dumps({
            'change_type': change_type,
            'old_value': old_value,
            'new_value': new_value
        })

        AdminLogger.log(user_id, 'system_change', details)

    @staticmethod
    def log_security_event(user_id, event_type, severity='medium', details=None):
        """Log security-related events"""
        log_details = json.dumps({
            'event_type': event_type,
            'severity': severity,
            'details': details
        })

        AdminLogger.log(user_id, 'security_event', log_details)

    @staticmethod
    def get_user_activity(user_id, limit=50):
        """Get recent activity for a specific user"""
        return AdminLog.query.filter_by(user_id=user_id).order_by(
            AdminLog.timestamp.desc()
        ).limit(limit).all()

    @staticmethod
    def get_recent_activity(hours=24, limit=100):
        """Get recent activity across all users"""
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        return AdminLog.query.filter(
            AdminLog.timestamp >= cutoff_time
        ).order_by(AdminLog.timestamp.desc()).limit(limit).all()

    @staticmethod
    def get_activity_by_action(action, limit=50):
        """Get logs filtered by action type"""
        return AdminLog.query.filter_by(action=action).order_by(
            AdminLog.timestamp.desc()
        ).limit(limit).all()

    @staticmethod
    def get_activity_summary(days=7):
        """Get activity summary for dashboard"""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Count activities by type
        activities = db.session.query(
            AdminLog.action,
            db.func.count(AdminLog.id).label('count')
        ).filter(
            AdminLog.timestamp >= cutoff_date
        ).group_by(AdminLog.action).all()

        # Get unique users active in period
        active_users = db.session.query(
            db.func.count(db.distinct(AdminLog.user_id))
        ).filter(AdminLog.timestamp >= cutoff_date).scalar()

        # Get total activities
        total_activities = AdminLog.query.filter(
            AdminLog.timestamp >= cutoff_date
        ).count()

        return {
            'period_days': days,
            'total_activities': total_activities,
            'active_users': active_users,
            'activities_by_type': {activity.action: activity.count for activity in activities},
            'most_common_action': max(activities, key=lambda x: x.count).action if activities else None
        }

    @staticmethod
    def export_logs(start_date=None, end_date=None, user_id=None, action=None):
        """Export logs for compliance/auditing"""
        query = AdminLog.query

        if start_date:
            query = query.filter(AdminLog.timestamp >= start_date)

        if end_date:
            query = query.filter(AdminLog.timestamp <= end_date)

        if user_id:
            query = query.filter(AdminLog.user_id == user_id)

        if action:
            query = query.filter(AdminLog.action == action)

        logs = query.order_by(AdminLog.timestamp.desc()).all()

        # Convert to exportable format
        export_data = []
        for log in logs:
            export_data.append({
                'timestamp': log.timestamp.isoformat(),
                'user_id': log.user_id,
                'username': log.user.username if log.user else 'Unknown',
                'action': log.action,
                'details': log.details,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent
            })

        return export_data

    @staticmethod
    def cleanup_old_logs(days_to_keep=90):
        """Clean up old logs to manage database size"""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        deleted_count = AdminLog.query.filter(
            AdminLog.timestamp < cutoff_date
        ).delete()

        db.session.commit()

        # Log the cleanup action
        AdminLogger.log(
            user_id=None,
            action='log_cleanup',
            details=f"Cleaned up {deleted_count} log entries older than {days_to_keep} days"
        )

        return deleted_count

    @staticmethod
    def get_security_events(days=30):
        """Get security-related events"""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        security_logs = AdminLog.query.filter(
            AdminLog.action == 'security_event',
            AdminLog.timestamp >= cutoff_date
        ).order_by(AdminLog.timestamp.desc()).all()

        events = []
        for log in security_logs:
            try:
                details = json.loads(log.details) if log.details else {}
                events.append({
                    'timestamp': log.timestamp,
                    'user': log.user.username if log.user else 'System',
                    'event_type': details.get('event_type', 'Unknown'),
                    'severity': details.get('severity', 'medium'),
                    'details': details.get('details'),
                    'ip_address': log.ip_address
                })
            except json.JSONDecodeError:
                # Handle legacy log format
                events.append({
                    'timestamp': log.timestamp,
                    'user': log.user.username if log.user else 'System',
                    'event_type': 'Legacy Event',
                    'severity': 'low',
                    'details': log.details,
                    'ip_address': log.ip_address
                })

        return events

    @staticmethod
    def get_data_access_logs(days=30):
        """Get data access logs for compliance"""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        access_logs = AdminLog.query.filter(
            AdminLog.action == 'data_access',
            AdminLog.timestamp >= cutoff_date
        ).order_by(AdminLog.timestamp.desc()).all()

        access_events = []
        for log in access_logs:
            try:
                details = json.loads(log.details) if log.details else {}
                access_events.append({
                    'timestamp': log.timestamp,
                    'user': log.user.username if log.user else 'Unknown',
                    'data_type': details.get('data_type'),
                    'record_id': details.get('record_id'),
                    'action': details.get('action'),
                    'ip_address': log.ip_address
                })
            except json.JSONDecodeError:
                continue

        return access_events

class AuditTrail:
    """Specialized audit trail for medical data access"""

    @staticmethod
    def log_patient_access(user_id, patient_id, action='view'):
        """Log patient data access"""
        AdminLogger.log_data_access(user_id, 'patient', patient_id, action)

    @staticmethod
    def log_document_access(user_id, document_id, action='view'):
        """Log document access"""
        AdminLogger.log_data_access(user_id, 'document', document_id, action)

    @staticmethod
    def log_screening_modification(user_id, screening_id, modification_type):
        """Log screening modifications"""
        AdminLogger.log(user_id, 'screening_modified', f"Screening {screening_id}: {modification_type}")

    @staticmethod
    def log_prep_sheet_generation(user_id, patient_id):
        """Log prep sheet generation"""
        AdminLogger.log(user_id, 'prep_sheet_generated', f"Generated prep sheet for patient {patient_id}")

    @staticmethod
    def log_phi_filter_change(user_id, filter_type, enabled):
        """Log PHI filter configuration changes"""
        AdminLogger.log_system_change(
            user_id,
            f"phi_filter_{filter_type}",
            old_value=not enabled,
            new_value=enabled
        )