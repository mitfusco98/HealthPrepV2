"""
Security Alert Service for HIPAA-Compliant Breach Notifications
Sends email alerts for security events via Resend integration
Implements HITRUST CSF Domain 11 - Incident Management requirements
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from services.email_service import EmailService
from models import AdminLog, User, Organization, db

logger = logging.getLogger(__name__)


class SecurityAlertService:
    """Service for sending security alerts and managing breach notifications"""
    
    ALERT_THRESHOLDS = {
        'failed_logins_per_ip': 10,
        'failed_logins_window_minutes': 5,
        'phi_filter_failure_threshold': 1,
    }
    
    ALERT_EVENT_TYPES = [
        'account_lockout',
        'brute_force_detected', 
        'phi_filter_failed',
        'document_processing_failed',
        'suspicious_access_pattern'
    ]
    
    @staticmethod
    def send_account_lockout_alert(user: User, ip_address: str, failed_attempts: int) -> bool:
        """
        Send alert when an account is locked out due to failed login attempts
        
        Args:
            user: The locked user
            ip_address: IP address of the lockout trigger
            failed_attempts: Number of failed attempts
            
        Returns:
            True if alert sent successfully
        """
        org = Organization.query.get(user.org_id)
        org_name = org.name if org else 'Unknown Organization'
        
        admin_emails = SecurityAlertService._get_org_admin_emails(user.org_id)
        
        subject = f"[SECURITY ALERT] Account Lockout - {user.username}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="background-color: #dc3545; color: white; padding: 15px; margin-bottom: 20px;">
                <h2 style="margin: 0;">Security Alert: Account Lockout</h2>
            </div>
            
            <h3>Incident Details:</h3>
            <ul>
                <li><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                <li><strong>User:</strong> {user.username}</li>
                <li><strong>Organization:</strong> {org_name}</li>
                <li><strong>IP Address:</strong> {ip_address}</li>
                <li><strong>Failed Attempts:</strong> {failed_attempts}</li>
            </ul>
            
            <h3>Recommended Actions:</h3>
            <ol>
                <li>Verify if this was a legitimate user forgetting their password</li>
                <li>Check for suspicious login patterns from this IP address</li>
                <li>If unauthorized access is suspected, review audit logs</li>
                <li>Consider blocking the IP address if attack pattern detected</li>
            </ol>
            
            <p style="color: #666; font-size: 12px;">
                This is an automated security alert from HealthPrep. 
                The account will automatically unlock after 15 minutes.
            </p>
        </body>
        </html>
        """
        
        success = True
        for email in admin_emails:
            if not EmailService._send_email(email, subject, html_body):
                success = False
                logger.warning(f"Failed to send lockout alert to {email}")
        
        SecurityAlertService._log_alert_sent('account_lockout', user.org_id, {
            'user_id': user.id,
            'username': user.username,
            'ip_address': ip_address,
            'failed_attempts': failed_attempts,
            'recipients': admin_emails
        })
        
        return success
    
    @staticmethod
    def send_brute_force_alert(ip_address: str, org_id: int, attempt_count: int, usernames_targeted: List[str]) -> bool:
        """
        Send alert when brute force attack is detected from an IP
        
        Args:
            ip_address: Source IP of the attack
            org_id: Organization ID being targeted
            attempt_count: Number of failed attempts
            usernames_targeted: List of usernames that were targeted
            
        Returns:
            True if alert sent successfully
        """
        org = Organization.query.get(org_id)
        org_name = org.name if org else 'Unknown Organization'
        
        admin_emails = SecurityAlertService._get_org_admin_emails(org_id)
        
        usernames_display = ', '.join(usernames_targeted[:5])
        if len(usernames_targeted) > 5:
            usernames_display += f' and {len(usernames_targeted) - 5} more'
        
        subject = f"[CRITICAL SECURITY ALERT] Brute Force Attack Detected"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="background-color: #721c24; color: white; padding: 15px; margin-bottom: 20px;">
                <h2 style="margin: 0;">CRITICAL: Brute Force Attack Detected</h2>
            </div>
            
            <h3>Attack Details:</h3>
            <ul>
                <li><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                <li><strong>Source IP:</strong> {ip_address}</li>
                <li><strong>Organization:</strong> {org_name}</li>
                <li><strong>Failed Attempts:</strong> {attempt_count} in the last 5 minutes</li>
                <li><strong>Accounts Targeted:</strong> {usernames_display}</li>
            </ul>
            
            <h3>Immediate Actions Required:</h3>
            <ol>
                <li><strong>Review the source IP</strong> - Determine if this is a known bad actor</li>
                <li><strong>Check for successful logins</strong> - Verify no accounts were compromised</li>
                <li><strong>Consider IP blocking</strong> - Add to firewall blocklist if appropriate</li>
                <li><strong>Notify affected users</strong> - Alert users whose accounts were targeted</li>
            </ol>
            
            <p style="background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107;">
                <strong>Note:</strong> This attack pattern may indicate a targeted attempt to access your healthcare data.
                If you suspect a breach, follow your incident response procedures.
            </p>
            
            <p style="color: #666; font-size: 12px;">
                This is an automated security alert from HealthPrep's breach detection system.
            </p>
        </body>
        </html>
        """
        
        success = True
        for email in admin_emails:
            if not EmailService._send_email(email, subject, html_body):
                success = False
                logger.warning(f"Failed to send brute force alert to {email}")
        
        SecurityAlertService._log_alert_sent('brute_force_detected', org_id, {
            'ip_address': ip_address,
            'attempt_count': attempt_count,
            'usernames_targeted': usernames_targeted,
            'recipients': admin_emails
        })
        
        # Create formal incident for brute force attack
        IncidentLogger.log_incident_detected(
            org_id=org_id,
            severity='P3',
            category='authentication_attack',
            description=f'Brute force attack detected from IP {ip_address}',
            details={
                'ip_address': ip_address,
                'attempt_count': attempt_count,
                'usernames_targeted': usernames_targeted,
                'org_name': org_name
            },
            ip_address=ip_address
        )
        
        return success
    
    @staticmethod
    def send_phi_filter_failure_alert(org_id: int, document_id: int, document_type: str, error_message: str) -> bool:
        """
        Send alert when PHI filter fails to process a document
        
        Args:
            org_id: Organization ID
            document_id: ID of the document that failed
            document_type: Type of document (manual/fhir)
            error_message: Error description
            
        Returns:
            True if alert sent successfully
        """
        org = Organization.query.get(org_id)
        org_name = org.name if org else 'Unknown Organization'
        
        admin_emails = SecurityAlertService._get_org_admin_emails(org_id)
        
        subject = f"[SECURITY ALERT] PHI Filter Processing Failure"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="background-color: #856404; color: white; padding: 15px; margin-bottom: 20px;">
                <h2 style="margin: 0;">Alert: PHI Filter Processing Failure</h2>
            </div>
            
            <h3>Incident Details:</h3>
            <ul>
                <li><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                <li><strong>Organization:</strong> {org_name}</li>
                <li><strong>Document ID:</strong> {document_id}</li>
                <li><strong>Document Type:</strong> {document_type}</li>
                <li><strong>Error:</strong> {error_message}</li>
            </ul>
            
            <h3>Impact Assessment:</h3>
            <p>The PHI filter was unable to process this document. This may mean:</p>
            <ul>
                <li>Protected Health Information may not have been properly redacted</li>
                <li>The document may contain unfiltered patient identifiers</li>
                <li>Manual review of the document may be required</li>
            </ul>
            
            <h3>Recommended Actions:</h3>
            <ol>
                <li>Review the document in the admin panel</li>
                <li>Manually verify PHI has been redacted</li>
                <li>Re-process the document if necessary</li>
                <li>Document the incident for HIPAA compliance</li>
            </ol>
            
            <p style="color: #666; font-size: 12px;">
                This is an automated security alert from HealthPrep's PHI protection system.
            </p>
        </body>
        </html>
        """
        
        success = True
        for email in admin_emails:
            if not EmailService._send_email(email, subject, html_body):
                success = False
                logger.warning(f"Failed to send PHI filter alert to {email}")
        
        SecurityAlertService._log_alert_sent('phi_filter_failed', org_id, {
            'document_id': document_id,
            'document_type': document_type,
            'error_message': error_message,
            'recipients': admin_emails
        })
        
        return success
    
    @staticmethod
    def check_and_alert_brute_force(ip_address: str, org_id: int) -> bool:
        """
        Check for brute force patterns and send alert if threshold exceeded
        
        Args:
            ip_address: IP address to check
            org_id: Organization ID
            
        Returns:
            True if brute force detected and alert sent
        """
        from sqlalchemy import func
        
        window_start = datetime.utcnow() - timedelta(
            minutes=SecurityAlertService.ALERT_THRESHOLDS['failed_logins_window_minutes']
        )
        
        recent_failures = db.session.query(AdminLog).filter(
            AdminLog.event_type == 'login_failed',
            AdminLog.ip_address == ip_address,
            AdminLog.timestamp >= window_start
        ).all()
        
        if len(recent_failures) >= SecurityAlertService.ALERT_THRESHOLDS['failed_logins_per_ip']:
            usernames = list(set([
                log.data.get('username', 'unknown') 
                for log in recent_failures 
                if log.data
            ]))
            
            SecurityAlertService.send_brute_force_alert(
                ip_address=ip_address,
                org_id=org_id,
                attempt_count=len(recent_failures),
                usernames_targeted=usernames
            )
            return True
        
        return False
    
    @staticmethod
    def get_unacknowledged_alerts(org_id: int, limit: int = 10) -> List[Dict]:
        """
        Get recent security alerts that haven't been acknowledged
        
        Args:
            org_id: Organization ID
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
        """
        from sqlalchemy import or_, text, func
        
        # Use coalesce to handle null data and missing key - if not explicitly 'true', show as unacknowledged
        acknowledged_expr = func.coalesce(
            AdminLog.data.op('->>')(text("'acknowledged'")),
            ''
        )
        
        alerts = db.session.query(AdminLog).filter(
            AdminLog.org_id == org_id,
            AdminLog.event_type.in_(SecurityAlertService.ALERT_EVENT_TYPES),
            acknowledged_expr != 'true'
        ).order_by(AdminLog.timestamp.desc()).limit(limit).all()
        
        return [{
            'id': alert.id,
            'event_type': alert.event_type,
            'timestamp': alert.timestamp,
            'data': alert.data,
            'ip_address': alert.ip_address
        } for alert in alerts]
    
    @staticmethod
    def acknowledge_alert(alert_id: int, user_id: int) -> bool:
        """
        Mark a security alert as acknowledged
        
        Args:
            alert_id: ID of the alert to acknowledge
            user_id: ID of the user acknowledging
            
        Returns:
            True if acknowledged successfully
        """
        alert = AdminLog.query.get(alert_id)
        if alert:
            if alert.data is None:
                alert.data = {}
            alert.data['acknowledged'] = 'true'
            alert.data['acknowledged_by'] = user_id
            alert.data['acknowledged_at'] = datetime.utcnow().isoformat()
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def _get_org_admin_emails(org_id: int) -> List[str]:
        """Get email addresses of all admins in an organization"""
        admins = User.query.filter(
            User.org_id == org_id,
            User.role.in_(['admin', 'root_admin']),
            User.email.isnot(None)
        ).all()
        
        return [admin.email for admin in admins if admin.email]
    
    @staticmethod
    def _log_alert_sent(event_type: str, org_id: int, data: Dict) -> None:
        """Log that a security alert was sent"""
        from models import log_admin_event
        
        log_admin_event(
            event_type=f'security_alert_{event_type}',
            user_id=None,
            org_id=org_id,
            ip=None,
            data={
                'alert_type': event_type,
                'alert_data': data,
                'sent_at': datetime.utcnow().isoformat(),
                'acknowledged': 'false'
            },
            resource_type='security_alert'
        )


class IncidentLogger:
    """
    Incident Response logging for HIPAA/HITRUST compliance.
    
    Logs incident lifecycle events to AdminLog for visibility in:
    - /admin/logs (organization admins)
    - /root-admin/system/logs (root admins)
    
    See docs/INCIDENT_RESPONSE_PLAN.md for full incident response procedures.
    """
    
    SEVERITY_LEVELS = ['P1', 'P2', 'P3', 'P4']
    
    INCIDENT_CATEGORIES = [
        'authentication_attack',
        'account_compromise', 
        'phi_exposure',
        'unauthorized_access',
        'system_compromise',
        'data_exfiltration',
        'ransomware',
        'insider_threat',
        'third_party_breach'
    ]
    
    @staticmethod
    def log_incident_detected(
        org_id: int,
        severity: str,
        category: str,
        description: str,
        details: Optional[Dict] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> Optional[int]:
        """
        Log detection of a new security incident.
        
        Args:
            org_id: Organization affected
            severity: P1 (Critical), P2 (High), P3 (Medium), P4 (Low)
            category: Incident category from INCIDENT_CATEGORIES
            description: Human-readable incident description
            details: Additional structured data
            user_id: User who detected/reported (if applicable)
            ip_address: Source IP (if applicable)
            
        Returns:
            AdminLog ID for incident tracking
        """
        from models import log_admin_event
        
        incident_data = {
            'severity': severity,
            'category': category,
            'description': description,
            'detected_at': datetime.utcnow().isoformat(),
            'status': 'detected',
            **(details or {})
        }
        
        log_entry = log_admin_event(
            event_type='incident_detected',
            user_id=user_id,
            org_id=org_id,
            ip=ip_address,
            data=incident_data,
            resource_type='security_incident',
            action_details=f"[{severity}] {category}: {description}"
        )
        
        logger.warning(f"INCIDENT DETECTED: [{severity}] {category} in org {org_id}: {description}")
        
        return log_entry.id if log_entry else None
    
    @staticmethod
    def log_incident_escalated(
        org_id: int,
        incident_id: int,
        new_severity: str,
        reason: str,
        escalated_to: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log escalation of an incident to higher severity.
        
        Args:
            org_id: Organization affected
            incident_id: Original incident AdminLog ID
            new_severity: New severity level (P1-P4)
            reason: Reason for escalation
            escalated_to: Role/person escalated to
            user_id: User performing escalation
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='incident_escalated',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'new_severity': new_severity,
                'reason': reason,
                'escalated_to': escalated_to,
                'escalated_at': datetime.utcnow().isoformat()
            },
            resource_type='security_incident',
            resource_id=incident_id,
            action_details=f"Incident escalated to {new_severity}: {reason}"
        )
        
        logger.warning(f"INCIDENT ESCALATED: {incident_id} to {new_severity} - {reason}")
    
    @staticmethod
    def log_incident_contained(
        org_id: int,
        incident_id: int,
        actions_taken: List[str],
        user_id: Optional[int] = None
    ) -> None:
        """
        Log containment of an incident.
        
        Args:
            org_id: Organization affected
            incident_id: Incident AdminLog ID
            actions_taken: List of containment actions performed
            user_id: User performing containment
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='incident_contained',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'actions_taken': actions_taken,
                'contained_at': datetime.utcnow().isoformat()
            },
            resource_type='security_incident',
            resource_id=incident_id,
            action_details=f"Incident contained: {', '.join(actions_taken)}"
        )
        
        logger.info(f"INCIDENT CONTAINED: {incident_id} - Actions: {actions_taken}")
    
    @staticmethod
    def log_incident_resolved(
        org_id: int,
        incident_id: int,
        resolution_summary: str,
        root_cause: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log resolution of an incident.
        
        Args:
            org_id: Organization affected
            incident_id: Incident AdminLog ID
            resolution_summary: Summary of resolution
            root_cause: Root cause if determined
            user_id: User performing resolution
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='incident_resolved',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'resolution_summary': resolution_summary,
                'root_cause': root_cause,
                'resolved_at': datetime.utcnow().isoformat()
            },
            resource_type='security_incident',
            resource_id=incident_id,
            action_details=f"Incident resolved: {resolution_summary}"
        )
        
        logger.info(f"INCIDENT RESOLVED: {incident_id} - {resolution_summary}")
    
    @staticmethod
    def log_incident_closed(
        org_id: int,
        incident_id: int,
        lessons_learned: Optional[List[str]] = None,
        action_items: Optional[List[Dict]] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log closure of an incident after post-incident activities.
        
        Args:
            org_id: Organization affected
            incident_id: Incident AdminLog ID
            lessons_learned: List of lessons from incident
            action_items: List of follow-up action items
            user_id: User closing incident
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='incident_closed',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'lessons_learned': lessons_learned or [],
                'action_items': action_items or [],
                'closed_at': datetime.utcnow().isoformat()
            },
            resource_type='security_incident',
            resource_id=incident_id,
            action_details=f"Incident closed with {len(lessons_learned or [])} lessons learned"
        )
        
        logger.info(f"INCIDENT CLOSED: {incident_id}")
    
    @staticmethod
    def log_breach_investigation_started(
        org_id: int,
        incident_id: int,
        phi_types_potentially_involved: List[str],
        estimated_individuals_affected: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log start of formal HIPAA breach investigation.
        
        Args:
            org_id: Organization affected
            incident_id: Related incident AdminLog ID
            phi_types_potentially_involved: Types of PHI (names, DOB, SSN, etc.)
            estimated_individuals_affected: Initial estimate of affected count
            user_id: User initiating investigation
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='breach_investigation_started',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'phi_types': phi_types_potentially_involved,
                'estimated_affected': estimated_individuals_affected,
                'investigation_started_at': datetime.utcnow().isoformat()
            },
            resource_type='breach_investigation',
            resource_id=incident_id,
            action_details=f"Breach investigation started - PHI types: {', '.join(phi_types_potentially_involved)}"
        )
        
        logger.warning(f"BREACH INVESTIGATION STARTED: Incident {incident_id}, PHI: {phi_types_potentially_involved}")
    
    @staticmethod
    def log_breach_confirmed(
        org_id: int,
        incident_id: int,
        phi_types_confirmed: List[str],
        individuals_affected: int,
        breach_discovery_date: datetime,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log confirmation of a HIPAA breach.
        
        HIPAA 60-day notification clock starts from discovery_date.
        
        Args:
            org_id: Organization affected
            incident_id: Related incident AdminLog ID
            phi_types_confirmed: Confirmed types of PHI exposed
            individuals_affected: Count of affected individuals
            breach_discovery_date: Date breach was discovered (starts 60-day clock)
            user_id: User confirming breach
        """
        from models import log_admin_event
        
        notification_deadline = breach_discovery_date + timedelta(days=60)
        
        log_admin_event(
            event_type='breach_confirmed',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'phi_types_confirmed': phi_types_confirmed,
                'individuals_affected': individuals_affected,
                'discovery_date': breach_discovery_date.isoformat(),
                'notification_deadline': notification_deadline.isoformat(),
                'confirmed_at': datetime.utcnow().isoformat()
            },
            resource_type='breach_investigation',
            resource_id=incident_id,
            action_details=f"BREACH CONFIRMED: {individuals_affected} individuals, deadline {notification_deadline.strftime('%Y-%m-%d')}"
        )
        
        logger.critical(f"BREACH CONFIRMED: Incident {incident_id}, {individuals_affected} affected, deadline {notification_deadline}")
    
    @staticmethod
    def log_breach_notification(
        org_id: int,
        notification_type: str,
        recipient_count: int,
        phi_types: List[str],
        incident_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> None:
        """
        Log dispatch of HIPAA breach notification.
        
        Args:
            org_id: Organization sending notification
            notification_type: 'individual', 'media', or 'hhs'
            recipient_count: Number of recipients
            phi_types: Types of PHI involved
            incident_id: Related incident AdminLog ID
            user_id: User sending notification
        """
        from models import log_admin_event
        
        log_admin_event(
            event_type='breach_notification_sent',
            user_id=user_id,
            org_id=org_id,
            ip=None,
            data={
                'incident_id': incident_id,
                'notification_type': notification_type,
                'recipient_count': recipient_count,
                'phi_types': phi_types,
                'sent_at': datetime.utcnow().isoformat()
            },
            resource_type='breach_notification',
            resource_id=incident_id,
            action_details=f"Breach notification ({notification_type}) sent to {recipient_count} recipients"
        )
        
        logger.info(f"BREACH NOTIFICATION SENT: {notification_type} to {recipient_count} recipients")
