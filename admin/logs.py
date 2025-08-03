"""
Admin logging functionality
"""

import json
import logging
from datetime import datetime
from flask import request
from flask_login import current_user

logger = logging.getLogger(__name__)

class AdminLogger:
    """Handles admin action logging"""

    def __init__(self):
        pass

    def log_action(self, user_id=None, action=None, resource_type=None, 
                   resource_id=None, details=None, ip_address=None, user_agent=None):
        """Log an admin action"""
        try:
            from models import AdminLog
            from app import db

            # Use current user if not specified
            if user_id is None and current_user.is_authenticated:
                user_id = current_user.id

            # Get request info if not provided
            if ip_address is None and request:
                ip_address = request.remote_addr

            if user_agent is None and request:
                user_agent = request.user_agent.string

            # Convert details to JSON if it's a dict
            if isinstance(details, dict):
                details = json.dumps(details)

            log_entry = AdminLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )

            db.session.add(log_entry)
            db.session.commit()

        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
            # Don't raise exception to avoid breaking the main flow
            pass

    def get_recent_logs(self, limit=50):
        """Get recent admin logs"""
        try:
            from models import AdminLog
            return AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to retrieve admin logs: {e}")
            return []

# Initialize a global instance for convenience
admin_logger = AdminLogger()

def log_admin_action(user_id=None, action=None, resource_type=None, 
                    resource_id=None, details=None, ip_address=None, user_agent=None):
    """Convenience function for logging admin actions"""
    admin_logger.log_action(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )