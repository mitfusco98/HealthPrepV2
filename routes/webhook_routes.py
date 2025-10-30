"""
Webhook Routes
Handles incoming webhooks from external services (Stripe, etc.)
"""

from flask import Blueprint, request, jsonify
import logging
import os
import stripe

from services.stripe_service import StripeService
from services.email_service import EmailService
from models import Organization

logger = logging.getLogger(__name__)

# Create blueprint
webhook_bp = Blueprint('webhooks', __name__)

# Stripe webhook secret for signature verification
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')


@webhook_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhook events
    Verifies signature and processes subscription events
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Verify webhook signature
        if STRIPE_WEBHOOK_SECRET:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, STRIPE_WEBHOOK_SECRET
                )
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Stripe webhook signature verification failed: {str(e)}")
                return jsonify({'error': 'Invalid signature'}), 400
        else:
            # Development mode: accept without verification
            event = stripe.Event.construct_from(
                request.get_json(), stripe.api_key
            )
            logger.warning("Stripe webhook signature verification skipped (no secret configured)")
        
        event_type = event['type']
        logger.info(f"Received Stripe webhook event: {event_type}")
        
        # Handle the event
        success = StripeService.handle_webhook_event(event)
        
        if success:
            # Send email notifications for specific events
            _send_webhook_notifications(event)
            return jsonify({'received': True}), 200
        else:
            logger.error(f"Failed to handle webhook event: {event_type}")
            return jsonify({'error': 'Event handling failed'}), 500
            
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _send_webhook_notifications(event: dict):
    """Send email notifications based on webhook events"""
    event_type = event['type']
    data = event['data']['object']
    
    try:
        # Get organization for the event
        org = None
        
        if event_type == 'checkout.session.completed':
            org_id = data.get('metadata', {}).get('org_id')
            if org_id:
                org = Organization.query.get(org_id)
        
        elif event_type in ['customer.subscription.created', 'customer.subscription.updated', 
                           'customer.subscription.deleted']:
            subscription_id = data['id']
            org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        
        elif event_type in ['invoice.payment_succeeded', 'invoice.payment_failed']:
            subscription_id = data.get('subscription')
            if subscription_id:
                org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        
        if not org or not org.billing_email:
            logger.debug(f"No organization or billing email found for event {event_type}")
            return
        
        # Send appropriate notification
        if event_type == 'checkout.session.completed':
            EmailService.send_welcome_email(
                to_email=org.billing_email,
                org_name=org.name,
                trial_days=14
            )
            logger.info(f"Sent welcome email to {org.billing_email}")
        
        elif event_type == 'customer.subscription.updated':
            status = data['status']
            if status == 'active' and org.subscription_status == 'trialing':
                # Trial ended, subscription activated
                EmailService.send_custom_email(
                    to_email=org.billing_email,
                    subject='Your HealthPrep Trial Has Ended - Subscription Active',
                    template_name='subscription_activated',
                    context={
                        'org_name': org.name,
                        'monthly_amount': '$100.00'
                    }
                )
                logger.info(f"Sent subscription activated email to {org.billing_email}")
        
        elif event_type == 'invoice.payment_succeeded':
            # Payment successful notification
            EmailService.send_custom_email(
                to_email=org.billing_email,
                subject='Payment Successful - HealthPrep Subscription',
                template_name='payment_success',
                context={
                    'org_name': org.name,
                    'amount': f"${data.get('amount_paid', 0) / 100:.2f}",
                    'invoice_date': data.get('created', '')
                }
            )
            logger.info(f"Sent payment success email to {org.billing_email}")
        
        elif event_type == 'invoice.payment_failed':
            # Payment failed notification
            EmailService.send_custom_email(
                to_email=org.billing_email,
                subject='Payment Failed - Action Required',
                template_name='payment_failed',
                context={
                    'org_name': org.name,
                    'amount': f"${data.get('amount_due', 0) / 100:.2f}",
                    'next_retry': data.get('next_payment_attempt', '')
                }
            )
            logger.warning(f"Sent payment failed email to {org.billing_email}")
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled notification
            EmailService.send_custom_email(
                to_email=org.billing_email,
                subject='Your HealthPrep Subscription Has Been Cancelled',
                template_name='subscription_cancelled',
                context={
                    'org_name': org.name,
                    'cancelled_date': data.get('canceled_at', '')
                }
            )
            logger.info(f"Sent subscription cancelled email to {org.billing_email}")
            
    except Exception as e:
        logger.error(f"Failed to send webhook notification: {str(e)}")
        # Don't fail the webhook processing if email fails
        pass
