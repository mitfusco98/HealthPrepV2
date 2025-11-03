"""
Email Service for Transactional Emails
Handles password resets, welcome emails, trial reminders, and payment notifications
Uses Replit's Resend connector for secure API key management
"""
import os
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending transactional emails"""
    
    @staticmethod
    def _get_resend_credentials() -> Tuple[Optional[str], Optional[str]]:
        """
        Get Resend API credentials from Replit connector
        
        Returns:
            Tuple of (api_key, from_email) or (None, None) if not configured
        """
        try:
            hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
            x_replit_token = None
            
            repl_identity = os.environ.get('REPL_IDENTITY')
            web_repl_renewal = os.environ.get('WEB_REPL_RENEWAL')
            
            if repl_identity:
                x_replit_token = 'repl ' + repl_identity
            elif web_repl_renewal:
                x_replit_token = 'depl ' + web_repl_renewal
            
            if not hostname or not x_replit_token:
                logger.warning("Resend connector not configured (missing hostname or token)")
                return None, None
            
            response = requests.get(
                f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=resend',
                headers={
                    'Accept': 'application/json',
                    'X_REPLIT_TOKEN': x_replit_token
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Resend credentials: {response.status_code}")
                return None, None
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                logger.warning("Resend connector not set up")
                return None, None
            
            settings = items[0].get('settings', {})
            api_key = settings.get('api_key')
            from_email = settings.get('from_email', 'fuscodigitalsolutions@gmail.com')
            
            if not api_key:
                logger.error("Resend API key not found in connector settings")
                return None, None
            
            return api_key, from_email
            
        except Exception as e:
            logger.error(f"Error fetching Resend credentials: {str(e)}")
            return None, None
    
    @staticmethod
    def send_welcome_email(email: str, username: str, temp_password: str, org_name: str) -> bool:
        """
        Send welcome email with temporary password
        
        Args:
            email: Recipient email address
            username: User's username
            temp_password: Temporary password
            org_name: Organization name
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"Welcome to HealthPrep - {org_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Welcome to HealthPrep!</h2>
            <p>Your organization <strong>{org_name}</strong> has been registered with HealthPrep.</p>
            
            <h3>Your Login Credentials:</h3>
            <ul>
                <li><strong>Username:</strong> {username}</li>
                <li><strong>Temporary Password:</strong> {temp_password}</li>
            </ul>
            
            <p><strong>Important:</strong> You will be required to change your password and set up security questions on your first login.</p>
            
            <h3>Your 14-Day Free Trial:</h3>
            <p>Your trial period has started and you have full access to all HealthPrep features for 14 days.</p>
            <ul>
                <li>Unlimited patients and documents</li>
                <li>Full Epic FHIR integration</li>
                <li>Automated screening prep sheets</li>
            </ul>
            
            <h3>Next Steps:</h3>
            <ol>
                <li>Log in and change your password</li>
                <li>Set up your Epic FHIR connection</li>
                <li>Start processing patient screenings</li>
            </ol>
            
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def send_password_reset_email(email: str, username: str, reset_token: str, reset_url: str) -> bool:
        """
        Send password reset email with verification link
        
        Args:
            email: Recipient email address
            username: User's username
            reset_token: Password reset token (included for logging/backwards compatibility)
            reset_url: Complete reset URL with token already included
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = "HealthPrep - Password Reset Request"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Password Reset Request</h2>
            <p>Hello {username},</p>
            
            <p>We received a request to reset your password. Click the link below to reset your password:</p>
            
            <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a></p>
            
            <p>This link will expire in 1 hour.</p>
            
            <p>If you didn't request a password reset, you can safely ignore this email.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def send_trial_reminder_email(email: str, org_name: str, days_remaining: int) -> bool:
        """
        Send trial expiration reminder
        
        Args:
            email: Recipient email address
            org_name: Organization name
            days_remaining: Days remaining in trial
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"HealthPrep Trial Reminder - {days_remaining} Days Remaining"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Trial Period Reminder</h2>
            <p>Hello from HealthPrep,</p>
            
            <p>Your free trial for <strong>{org_name}</strong> will expire in <strong>{days_remaining} days</strong>.</p>
            
            <p>To continue using HealthPrep without interruption, your subscription will automatically activate at $100/month.</p>
            
            <h3>What happens next?</h3>
            <ul>
                <li>Your card on file will be charged $100/month starting after the trial</li>
                <li>You'll continue to have unlimited access to all features</li>
                <li>You can cancel anytime from your account settings</li>
            </ul>
            
            <p>Thank you for choosing HealthPrep!</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def send_payment_success_email(email: str, org_name: str, amount: float, invoice_url: Optional[str] = None) -> bool:
        """
        Send payment success receipt
        
        Args:
            email: Recipient email address
            org_name: Organization name
            amount: Payment amount in dollars
            invoice_url: URL to Stripe invoice (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"HealthPrep Payment Receipt - ${amount:.2f}"
        
        invoice_link = f'<p><a href="{invoice_url}">View Invoice</a></p>' if invoice_url else ''
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Payment Received</h2>
            <p>Thank you for your payment!</p>
            
            <h3>Payment Details:</h3>
            <ul>
                <li><strong>Organization:</strong> {org_name}</li>
                <li><strong>Amount:</strong> ${amount:.2f}</li>
                <li><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</li>
                <li><strong>Description:</strong> HealthPrep Monthly Subscription</li>
            </ul>
            
            {invoice_link}
            
            <p>Your subscription is active and you have full access to all HealthPrep features.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def send_payment_failed_email(email: str, org_name: str, amount: float) -> bool:
        """
        Send payment failure notification
        
        Args:
            email: Recipient email address
            org_name: Organization name
            amount: Failed payment amount
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = "HealthPrep - Payment Failed"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Payment Failed</h2>
            <p>We were unable to process your payment for <strong>{org_name}</strong>.</p>
            
            <h3>Payment Details:</h3>
            <ul>
                <li><strong>Amount:</strong> ${amount:.2f}</li>
                <li><strong>Description:</strong> HealthPrep Monthly Subscription</li>
            </ul>
            
            <h3>Action Required:</h3>
            <p>Please update your payment method to avoid service interruption.</p>
            <ol>
                <li>Log in to your HealthPrep account</li>
                <li>Go to Account Settings → Billing</li>
                <li>Update your payment method</li>
            </ol>
            
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    
    @staticmethod
    def send_organization_approved_email(email: str, username: str, org_name: str) -> bool:
        """
        Send organization approval notification
        
        Args:
            email: Recipient email address
            username: User's username
            org_name: Organization name
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"HealthPrep - Your Organization Has Been Approved!"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Welcome to HealthPrep!</h2>
            <p>Great news, {username}!</p>
            
            <p>Your organization <strong>{org_name}</strong> has been approved and is now active.</p>
            
            <h3>You can now:</h3>
            <ul>
                <li>Log in to your account</li>
                <li>Configure your Epic FHIR integration</li>
                <li>Add additional users to your organization</li>
                <li>Start processing patient screenings</li>
            </ul>
            
            <p>Your 14-day free trial is still active with full access to all features.</p>
            
            <h3>Next Steps:</h3>
            <ol>
                <li>Log in to HealthPrep</li>
                <li>Complete Epic OAuth setup in the admin panel</li>
                <li>Upload or sync your first patient data</li>
            </ol>
            
            <p>If you have any questions, please don't hesitate to contact our support team.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def send_organization_rejected_email(email: str, username: str, org_name: str, rejection_reason: str) -> bool:
        """
        Send organization rejection notification
        
        Args:
            email: Recipient email address
            username: User's username
            org_name: Organization name
            rejection_reason: Reason for rejection
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = f"HealthPrep - Organization Application Status"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Organization Application Update</h2>
            <p>Hello {username},</p>
            
            <p>Thank you for your interest in HealthPrep.</p>
            
            <p>Unfortunately, we are unable to approve your organization <strong>{org_name}</strong> at this time.</p>
            
            <h3>Reason:</h3>
            <p>{rejection_reason}</p>
            
            <p>If you believe this was an error or would like to discuss this decision, please contact our support team.</p>
            
            <p>Your payment method has not been charged.</p>
            
            <p>Best regards,<br>The HealthPrep Team</p>
        </body>
        </html>
        """
        
        return EmailService._send_email(email, subject, html_body)
    
    @staticmethod
    def _send_email(to_email: str, subject: str, html_body: str) -> bool:
        """
        Internal method to send email via Resend API
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Get credentials from Resend connector
        api_key, from_email = EmailService._get_resend_credentials()
        
        if not api_key:
            logger.warning(f"Email sending disabled (Resend not configured): {subject} to {to_email}")
            logger.debug(f"Email content:\n{html_body}")
            return False
        
        try:
            response = requests.post(
                'https://api.resend.com/emails',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'from': from_email,
                    'to': to_email,
                    'subject': subject,
                    'html': html_body
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}: {subject}")
                return True
            else:
                logger.error(f"Email send failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Email send error: {str(e)}")
            return False
