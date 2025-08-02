"""
Admin log management and activity tracking
Handles comprehensive logging of administrative actions
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import request
from models import AdminLog, User, db
from sqlalchemy import func, and_, or_

class AdminLogger:
    """Handles administrative activity logging"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def log_action(self, user_id: int, action: str, entity_type: str = None, 
                   entity_id: int = None, details: Dict[str, Any] = None) -> bool:
        """Log an administrative action"""
        try:
            # Get request information if available
            ip_address = None
            user_agent = None
            
            if request:
                ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
                user_agent = request.environ.get('HTTP_USER_AGENT', '')[:500]  # Limit length
            
            admin_log = AdminLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(admin_log)
            db.session.commit()
            
            self.logger.info(f"Logged admin action: {action} by user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging admin action: {str(e)}")
            db.session.rollback()
            return False
    
    def get_logs(self, limit: int = 100, offset: int = 0, 
                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Retrieve admin logs with optional filtering"""
        try:
            query = db.session.query(AdminLog, User.username).outerjoin(
                User, AdminLog.user_id == User.id
            )
            
            # Apply filters
            if filters:
                if filters.get('user_id'):
                    query = query.filter(AdminLog.user_id == filters['user_id'])
                
                if filters.get('action'):
                    query = query.filter(AdminLog.action.ilike(f"%{filters['action']}%"))
                
                if filters.get('entity_type'):
                    query = query.filter(AdminLog.entity_type == filters['entity_type'])
                
                if filters.get('start_date'):
                    query = query.filter(AdminLog.timestamp >= filters['start_date'])
                
                if filters.get('end_date'):
                    query = query.filter(AdminLog.timestamp <= filters['end_date'])
                
                if filters.get('ip_address'):
                    query = query.filter(AdminLog.ip_address == filters['ip_address'])
            
            # Get total count for pagination
            total_count = query.count()
            
            # Apply pagination and ordering
            logs = query.order_by(AdminLog.timestamp.desc()).offset(offset).limit(limit).all()
            
            # Format results
            log_list = []
            for admin_log, username in logs:
                log_entry = {
                    "id": admin_log.id,
                    "user_id": admin_log.user_id,
                    "username": username or "Unknown User",
                    "action": admin_log.action,
                    "entity_type": admin_log.entity_type,
                    "entity_id": admin_log.entity_id,
                    "timestamp": admin_log.timestamp,
                    "formatted_timestamp": admin_log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "ip_address": admin_log.ip_address,
                    "user_agent": admin_log.user_agent,
                    "details": json.loads(admin_log.details) if admin_log.details else None
                }
                log_list.append(log_entry)
            
            return {
                "logs": log_list,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
            
        except Exception as e:
            self.logger.error(f"Error retrieving admin logs: {str(e)}")
            return {"error": str(e)}
    
    def get_log_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get log statistics for the specified time period"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total actions in period
            total_actions = AdminLog.query.filter(
                AdminLog.timestamp >= cutoff_date
            ).count()
            
            # Actions by type
            action_counts = db.session.query(
                AdminLog.action,
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(AdminLog.action).order_by(func.count(AdminLog.id).desc()).all()
            
            # Actions by user
            user_counts = db.session.query(
                User.username,
                func.count(AdminLog.id).label('count')
            ).outerjoin(
                AdminLog, User.id == AdminLog.user_id
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(User.username).order_by(func.count(AdminLog.id).desc()).all()
            
            # Actions by entity type
            entity_counts = db.session.query(
                AdminLog.entity_type,
                func.count(AdminLog.id).label('count')
            ).filter(
                and_(
                    AdminLog.timestamp >= cutoff_date,
                    AdminLog.entity_type.isnot(None)
                )
            ).group_by(AdminLog.entity_type).order_by(func.count(AdminLog.id).desc()).all()
            
            # Daily activity
            daily_activity = db.session.query(
                func.date(AdminLog.timestamp).label('date'),
                func.count(AdminLog.id).label('count')
            ).filter(
                AdminLog.timestamp >= cutoff_date
            ).group_by(func.date(AdminLog.timestamp)).order_by(func.date(AdminLog.timestamp)).all()
            
            return {
                "period_days": days,
                "total_actions": total_actions,
                "action_breakdown": [{"action": action, "count": count} for action, count in action_counts],
                "user_activity": [{"username": username or "Unknown", "count": count} for username, count in user_counts],
                "entity_breakdown": [{"entity_type": entity_type, "count": count} for entity_type, count in entity_counts],
                "daily_activity": [{"date": date.isoformat(), "count": count} for date, count in daily_activity],
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting log statistics: {str(e)}")
            return {"error": str(e)}
    
    def export_logs(self, filters: Dict[str, Any] = None, format: str = 'json') -> Dict[str, Any]:
        """Export logs in specified format"""
        try:
            # Get all matching logs (no pagination)
            result = self.get_logs(limit=10000, offset=0, filters=filters)
            
            if "error" in result:
                return result
            
            logs = result["logs"]
            
            if format.lower() == 'csv':
                return self._export_logs_csv(logs)
            else:
                return {
                    "format": "json",
                    "data": logs,
                    "total_exported": len(logs),
                    "exported_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error exporting logs: {str(e)}")
            return {"error": str(e)}
    
    def _export_logs_csv(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export logs in CSV format"""
        try:
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'Username', 'Action', 'Entity Type', 'Entity ID',
                'Timestamp', 'IP Address', 'Details'
            ])
            
            # Write data
            for log in logs:
                writer.writerow([
                    log['id'],
                    log['username'],
                    log['action'],
                    log['entity_type'] or '',
                    log['entity_id'] or '',
                    log['formatted_timestamp'],
                    log['ip_address'] or '',
                    json.dumps(log['details']) if log['details'] else ''
                ])
            
            csv_data = output.getvalue()
            output.close()
            
            return {
                "format": "csv",
                "data": csv_data,
                "total_exported": len(logs),
                "exported_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting logs to CSV: {str(e)}")
            return {"error": str(e)}
    
    def cleanup_old_logs(self, days_to_keep: int = 365) -> Dict[str, Any]:
        """Clean up old log entries"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Count logs to be deleted
            old_logs_count = AdminLog.query.filter(
                AdminLog.timestamp < cutoff_date
            ).count()
            
            if old_logs_count == 0:
                return {
                    "deleted_count": 0,
                    "message": "No old logs to cleanup"
                }
            
            # Delete old logs
            deleted_count = AdminLog.query.filter(
                AdminLog.timestamp < cutoff_date
            ).delete()
            
            db.session.commit()
            
            self.logger.info(f"Cleaned up {deleted_count} old admin logs")
            
            return {
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "days_kept": days_to_keep
            }
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}
    
    def get_user_activity_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get activity summary for a specific user"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            user = User.query.get(user_id)
            if not user:
                return {"error": "User not found"}
            
            # Get user's actions in period
            user_logs = AdminLog.query.filter(
                and_(
                    AdminLog.user_id == user_id,
                    AdminLog.timestamp >= cutoff_date
                )
            ).order_by(AdminLog.timestamp.desc()).all()
            
            # Summarize by action type
            action_summary = {}
            for log in user_logs:
                action = log.action
                if action not in action_summary:
                    action_summary[action] = {
                        "count": 0,
                        "first_occurrence": log.timestamp,
                        "last_occurrence": log.timestamp
                    }
                
                action_summary[action]["count"] += 1
                
                if log.timestamp > action_summary[action]["last_occurrence"]:
                    action_summary[action]["last_occurrence"] = log.timestamp
                
                if log.timestamp < action_summary[action]["first_occurrence"]:
                    action_summary[action]["first_occurrence"] = log.timestamp
            
            return {
                "user_id": user_id,
                "username": user.username,
                "period_days": days,
                "total_actions": len(user_logs),
                "action_summary": action_summary,
                "recent_actions": [
                    {
                        "action": log.action,
                        "entity_type": log.entity_type,
                        "entity_id": log.entity_id,
                        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "ip_address": log.ip_address
                    } for log in user_logs[:10]  # Last 10 actions
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user activity summary: {str(e)}")
            return {"error": str(e)}

# Global admin logger instance
admin_logger = AdminLogger()
