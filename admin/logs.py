"""
Admin logging system for comprehensive system monitoring and audit trails.
Handles admin action logging, user activity tracking, and log management.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import request
import json

from app import db
from models import AdminLog, User

def log_admin_action(user_id: int, action: str, details: str = None, 
                    ip_address: str = None) -> AdminLog:
    """Log an admin action with details and context."""
    
    try:
        # Get IP address from request if not provided
        if ip_address is None and request:
            ip_address = request.remote_addr
        
        # Create log entry
        log_entry = AdminLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to system logger
        logger = logging.getLogger(__name__)
        logger.info(f"Admin action logged: User {user_id} - {action} - {details}")
        
        return log_entry
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log admin action: {e}")
        # Don't raise exception to avoid breaking the main operation
        return None

def log_user_login(user_id: int, success: bool = True, details: str = None):
    """Log user login attempt."""
    
    action = "USER_LOGIN_SUCCESS" if success else "USER_LOGIN_FAILED"
    log_admin_action(user_id, action, details)

def log_user_logout(user_id: int):
    """Log user logout."""
    
    log_admin_action(user_id, "USER_LOGOUT", "User logged out")

def log_screening_type_action(user_id: int, action_type: str, screening_type_name: str,
                             screening_type_id: int = None):
    """Log screening type related actions."""
    
    action_map = {
        'create': 'CREATE_SCREENING_TYPE',
        'update': 'UPDATE_SCREENING_TYPE',
        'delete': 'DELETE_SCREENING_TYPE',
        'activate': 'ACTIVATE_SCREENING_TYPE',
        'deactivate': 'DEACTIVATE_SCREENING_TYPE'
    }
    
    action = action_map.get(action_type, f'SCREENING_TYPE_{action_type.upper()}')
    details = f"Screening type: {screening_type_name}"
    
    if screening_type_id:
        details += f" (ID: {screening_type_id})"
    
    log_admin_action(user_id, action, details)

def log_patient_action(user_id: int, action_type: str, patient_mrn: str, 
                      patient_name: str = None):
    """Log patient-related actions."""
    
    action_map = {
        'create': 'CREATE_PATIENT',
        'update': 'UPDATE_PATIENT',
        'delete': 'DELETE_PATIENT',
        'view': 'VIEW_PATIENT',
        'prep_sheet': 'GENERATE_PREP_SHEET'
    }
    
    action = action_map.get(action_type, f'PATIENT_{action_type.upper()}')
    details = f"Patient MRN: {patient_mrn}"
    
    if patient_name:
        details += f" ({patient_name})"
    
    log_admin_action(user_id, action, details)

def log_document_action(user_id: int, action_type: str, document_id: int,
                       document_filename: str = None):
    """Log document-related actions."""
    
    action_map = {
        'upload': 'UPLOAD_DOCUMENT',
        'delete': 'DELETE_DOCUMENT',
        'view': 'VIEW_DOCUMENT',
        'ocr_process': 'OCR_PROCESS_DOCUMENT',
        'phi_filter': 'PHI_FILTER_DOCUMENT'
    }
    
    action = action_map.get(action_type, f'DOCUMENT_{action_type.upper()}')
    details = f"Document ID: {document_id}"
    
    if document_filename:
        details += f" ({document_filename})"
    
    log_admin_action(user_id, action, details)

def log_system_action(user_id: int, action_type: str, details: str = None):
    """Log system-level actions."""
    
    action_map = {
        'refresh_screenings': 'REFRESH_ALL_SCREENINGS',
        'backup_database': 'BACKUP_DATABASE',
        'update_settings': 'UPDATE_SYSTEM_SETTINGS',
        'phi_settings': 'UPDATE_PHI_SETTINGS',
        'checklist_settings': 'UPDATE_CHECKLIST_SETTINGS'
    }
    
    action = action_map.get(action_type, f'SYSTEM_{action_type.upper()}')
    log_admin_action(user_id, action, details)

def log_security_event(user_id: int, event_type: str, details: str = None):
    """Log security-related events."""
    
    event_map = {
        'failed_login': 'SECURITY_FAILED_LOGIN',
        'password_change': 'SECURITY_PASSWORD_CHANGE',
        'permission_denied': 'SECURITY_PERMISSION_DENIED',
        'suspicious_activity': 'SECURITY_SUSPICIOUS_ACTIVITY'
    }
    
    action = event_map.get(event_type, f'SECURITY_{event_type.upper()}')
    log_admin_action(user_id, action, details)

class AdminLogManager:
    """Manages admin log retrieval, filtering, and analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_logs(self, filters: Dict[str, Any] = None, page: int = 1, 
                per_page: int = 50) -> Dict[str, Any]:
        """Get admin logs with filtering and pagination."""
        
        try:
            # Build base query
            query = AdminLog.query
            
            # Apply filters
            if filters:
                if 'action' in filters and filters['action']:
                    query = query.filter(AdminLog.action.ilike(f"%{filters['action']}%"))
                
                if 'user_id' in filters and filters['user_id']:
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if 'user_name' in filters and filters['user_name']:
                    query = query.join(User).filter(User.username.ilike(f"%{filters['user_name']}%"))
                
                if 'date_from' in filters and filters['date_from']:
                    try:
                        date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                        query = query.filter(AdminLog.created_at >= date_from)
                    except ValueError:
                        pass
                
                if 'date_to' in filters and filters['date_to']:
                    try:
                        date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d') + timedelta(days=1)
                        query = query.filter(AdminLog.created_at < date_to)
                    except ValueError:
                        pass
            
            # Order by most recent first
            query = query.order_by(AdminLog.created_at.desc())
            
            # Paginate
            paginated_logs = query.paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Format logs for display
            formatted_logs = []
            for log in paginated_logs.items:
                formatted_logs.append({
                    'id': log.id,
                    'user_id': log.user_id,
                    'username': log.user.username if log.user else 'Unknown',
                    'action': log.action,
                    'details': log.details,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'created_at_iso': log.created_at.isoformat(),
                    'action_category': self._categorize_action(log.action)
                })
            
            return {
                'logs': formatted_logs,
                'pagination': {
                    'page': paginated_logs.page,
                    'pages': paginated_logs.pages,
                    'per_page': paginated_logs.per_page,
                    'total': paginated_logs.total,
                    'has_next': paginated_logs.has_next,
                    'has_prev': paginated_logs.has_prev,
                    'next_num': paginated_logs.next_num,
                    'prev_num': paginated_logs.prev_num
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error retrieving admin logs: {e}")
            return {
                'logs': [],
                'pagination': {
                    'page': 1, 'pages': 0, 'per_page': per_page, 'total': 0,
                    'has_next': False, 'has_prev': False
                }
            }
    
    def get_log_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get admin log statistics for the specified time period."""
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get logs in the time period
            logs = AdminLog.query.filter(
                AdminLog.created_at >= start_date
            ).all()
            
            # Calculate statistics
            total_actions = len(logs)
            unique_users = len(set(log.user_id for log in logs if log.user_id))
            
            # Action breakdown
            action_counts = {}
            category_counts = {}
            
            for log in logs:
                # Count by specific action
                action_counts[log.action] = action_counts.get(log.action, 0) + 1
                
                # Count by category
                category = self._categorize_action(log.action)
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Daily activity
            daily_activity = {}
            for log in logs:
                day_key = log.created_at.date().isoformat()
                daily_activity[day_key] = daily_activity.get(day_key, 0) + 1
            
            # Most active users
            user_activity = {}
            for log in logs:
                if log.user_id:
                    user_activity[log.user_id] = user_activity.get(log.user_id, 0) + 1
            
            # Get user details for top users
            top_users = []
            for user_id, count in sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]:
                user = User.query.get(user_id)
                if user:
                    top_users.append({
                        'user_id': user_id,
                        'username': user.username,
                        'action_count': count
                    })
            
            return {
                'summary': {
                    'total_actions': total_actions,
                    'unique_users': unique_users,
                    'period_days': days,
                    'actions_per_day': round(total_actions / max(days, 1), 1)
                },
                'action_breakdown': dict(sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
                'category_breakdown': category_counts,
                'daily_activity': daily_activity,
                'top_users': top_users,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating log statistics: {e}")
            return {
                'summary': {'total_actions': 0, 'unique_users': 0, 'period_days': days},
                'action_breakdown': {},
                'category_breakdown': {},
                'daily_activity': {},
                'top_users': []
            }
    
    def _categorize_action(self, action: str) -> str:
        """Categorize admin actions for better organization."""
        
        action_upper = action.upper()
        
        if any(keyword in action_upper for keyword in ['LOGIN', 'LOGOUT', 'PASSWORD', 'PERMISSION']):
            return 'Authentication & Security'
        elif any(keyword in action_upper for keyword in ['SCREENING', 'REFRESH']):
            return 'Screening Management'
        elif any(keyword in action_upper for keyword in ['PATIENT', 'PREP_SHEET']):
            return 'Patient Management'
        elif any(keyword in action_upper for keyword in ['DOCUMENT', 'OCR', 'PHI']):
            return 'Document Processing'
        elif any(keyword in action_upper for keyword in ['SETTINGS', 'CONFIG', 'SYSTEM']):
            return 'System Configuration'
        else:
            return 'Other'
    
    def export_logs(self, filters: Dict[str, Any] = None, format_type: str = 'json') -> Dict[str, Any]:
        """Export admin logs in specified format."""
        
        try:
            # Get all matching logs (no pagination for export)
            query = AdminLog.query
            
            # Apply same filters as get_logs method
            if filters:
                if 'action' in filters and filters['action']:
                    query = query.filter(AdminLog.action.ilike(f"%{filters['action']}%"))
                
                if 'user_id' in filters and filters['user_id']:
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if 'date_from' in filters and filters['date_from']:
                    try:
                        date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                        query = query.filter(AdminLog.created_at >= date_from)
                    except ValueError:
                        pass
                
                if 'date_to' in filters and filters['date_to']:
                    try:
                        date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d') + timedelta(days=1)
                        query = query.filter(AdminLog.created_at < date_to)
                    except ValueError:
                        pass
            
            logs = query.order_by(AdminLog.created_at.desc()).all()
            
            # Format for export
            exported_logs = []
            for log in logs:
                exported_logs.append({
                    'timestamp': log.created_at.isoformat(),
                    'user_id': log.user_id,
                    'username': log.user.username if log.user else 'Unknown',
                    'action': log.action,
                    'details': log.details,
                    'ip_address': log.ip_address,
                    'category': self._categorize_action(log.action)
                })
            
            export_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'total_records': len(exported_logs),
                'filters_applied': filters or {},
                'logs': exported_logs
            }
            
            if format_type == 'json':
                return {
                    'success': True,
                    'data': export_data,
                    'filename': f"admin_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                    'content_type': 'application/json'
                }
            else:
                return {
                    'success': False,
                    'error': f"Unsupported export format: {format_type}"
                }
                
        except Exception as e:
            self.logger.error(f"Error exporting admin logs: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_logs(self, days_to_keep: int = 365) -> Dict[str, Any]:
        """Clean up old admin logs beyond retention period."""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Count logs to be deleted
            logs_to_delete = AdminLog.query.filter(AdminLog.created_at < cutoff_date).count()
            
            # Delete old logs
            deleted_count = AdminLog.query.filter(AdminLog.created_at < cutoff_date).delete()
            db.session.commit()
            
            self.logger.info(f"Cleaned up {deleted_count} admin logs older than {days_to_keep} days")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'days_retained': days_to_keep
            }
            
        except Exception as e:
            self.logger.error(f"Error cleaning up admin logs: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0
            }

# Initialize global log manager instance
log_manager = AdminLogManager()
