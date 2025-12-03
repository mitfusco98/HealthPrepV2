"""
Stripe Service for Subscription Management
Handles subscription creation, updates, and webhook processing
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import stripe

from models import Organization, db

logger = logging.getLogger(__name__)

# Initialize Stripe with API key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


class StripeService:
    """Service for managing Stripe subscriptions"""
    
    # Subscription product configuration
    SUBSCRIPTION_PRICE = 10000  # $100.00 in cents
    TRIAL_DAYS = 14
    PRODUCT_NAME = "HealthPrep Subscription"
    
    @staticmethod
    def create_customer(organization: Organization, email: str) -> Optional[str]:
        """
        Create Stripe customer for organization
        
        Args:
            organization: Organization model instance
            email: Billing email address
            
        Returns:
            Stripe customer ID or None if error
        """
        try:
            # Check for existing customers with this email
            existing_customers = stripe.Customer.list(email=email, limit=10)
            
            # Look for customer with valid org_id in metadata
            for customer in existing_customers.data:
                customer_org_id = customer.metadata.get('org_id')
                if customer_org_id:
                    # Check if this organization still exists in our database
                    from models import Organization as OrgModel
                    org_exists = OrgModel.query.filter_by(id=int(customer_org_id)).first()
                    if org_exists and org_exists.id == organization.id:
                        # Reuse existing customer for this org
                        logger.info(f"Reusing existing Stripe customer {customer.id} for organization {organization.id}")
                        return customer.id
                    elif not org_exists:
                        # Orphaned customer - archive it
                        logger.warning(f"Archiving orphaned Stripe customer {customer.id} (org_id {customer_org_id} no longer exists)")
                        try:
                            stripe.Customer.modify(customer.id, metadata={'archived': 'true', 'archived_at': datetime.utcnow().isoformat()})
                        except:
                            pass
            
            # No reusable customer found - create new one
            customer = stripe.Customer.create(
                email=email,
                name=organization.name,
                metadata={
                    'org_id': organization.id,
                    'org_name': organization.name,
                    'site': organization.site or '',
                    'specialty': organization.specialty or ''
                }
            )
            
            logger.info(f"Created Stripe customer {customer.id} for organization {organization.id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            return None
    
    @staticmethod
    def create_subscription(customer_id: str, price_id: str = None, trial_days: int = None) -> Optional[Dict]:
        """
        Create subscription with trial period
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID (if None, uses test mode)
            trial_days: Number of trial days (default: 14)
            
        Returns:
            Subscription object dict or None if error
        """
        try:
            if trial_days is None:
                trial_days = StripeService.TRIAL_DAYS
            
            # Use trial_period_days only (cannot use both trial_period_days and trial_end)
            subscription_params = {
                'customer': customer_id,
                'trial_period_days': trial_days,
                'payment_behavior': 'default_incomplete',
                'payment_settings': {
                    'save_default_payment_method': 'on_subscription'
                }
            }
            
            # Add price if provided (production), otherwise create ad-hoc price (development)
            if price_id:
                subscription_params['items'] = [{'price': price_id}]
            else:
                # Development mode: create ad-hoc price
                subscription_params['items'] = [{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': StripeService.PRODUCT_NAME,
                        },
                        'recurring': {
                            'interval': 'month',
                        },
                        'unit_amount': StripeService.SUBSCRIPTION_PRICE,
                    },
                }]
            
            subscription = stripe.Subscription.create(**subscription_params)
            
            logger.info(f"Created subscription {subscription.id} for customer {customer_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation failed: {str(e)}")
            return None
    
    @staticmethod
    def start_trial_subscription(organization: Organization, trial_days: int = None) -> bool:
        """
        Start a trial subscription for an approved organization
        
        Args:
            organization: Organization model instance with stripe_customer_id
            trial_days: Number of trial days (default: 14)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not organization.stripe_customer_id:
                logger.error(f"Cannot start trial for org {organization.id} - no Stripe customer ID")
                return False
            
            # Create subscription with trial using configured price ID
            price_id = os.environ.get('STRIPE_PRICE_ID')
            subscription = StripeService.create_subscription(
                customer_id=organization.stripe_customer_id,
                price_id=price_id,
                trial_days=trial_days or StripeService.TRIAL_DAYS
            )
            
            if not subscription:
                return False
            
            # Update organization with subscription info
            organization.stripe_subscription_id = subscription.id
            organization.subscription_status = subscription.status
            organization.trial_start_date = datetime.utcnow()
            organization.trial_expires = datetime.utcfromtimestamp(subscription.trial_end) if subscription.get('trial_end') else datetime.utcnow() + timedelta(days=StripeService.TRIAL_DAYS)
            
            db.session.commit()
            
            logger.info(f"Started trial subscription {subscription.id} for organization {organization.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start trial subscription for org {organization.id}: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def create_checkout_session(
        organization: Organization,
        success_url: str,
        cancel_url: str,
        price_id: str = None
    ) -> Optional[str]:
        """
        Create Stripe Checkout session for payment method setup (no subscription yet)
        
        Args:
            organization: Organization model instance
            success_url: URL to redirect after successful payment method setup
            cancel_url: URL to redirect if setup cancelled
            price_id: Stripe price ID (optional, unused in setup mode)
            
        Returns:
            Checkout session URL or None if error
        """
        try:
            # Create or get customer
            if not organization.stripe_customer_id:
                customer_id = StripeService.create_customer(
                    organization,
                    organization.billing_email or organization.contact_email
                )
                if not customer_id:
                    return None
                organization.stripe_customer_id = customer_id
                db.session.commit()
            else:
                customer_id = organization.stripe_customer_id
            
            # Create checkout session in SETUP mode (collect payment method only)
            checkout_params = {
                'customer': customer_id,
                'mode': 'setup',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'payment_method_types': ['card'],
                'metadata': {
                    'org_id': organization.id,
                    'org_name': organization.name
                }
            }
            
            session = stripe.checkout.Session.create(**checkout_params)
            
            logger.info(f"Created setup checkout session {session.id} for organization {organization.id}")
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe setup checkout session creation failed: {str(e)}")
            return None
    
    @staticmethod
    def create_billing_portal_session(customer_id: str, return_url: str) -> Optional[str]:
        """
        Create Stripe Customer Portal session for billing management
        
        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after managing billing
            
        Returns:
            Portal session URL or None if error
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            logger.info(f"Created billing portal session for customer {customer_id}")
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe billing portal session creation failed: {str(e)}")
            return None
    
    @staticmethod
    def cancel_subscription(subscription_id: str) -> bool:
        """
        Cancel subscription at period end
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Cancelled subscription {subscription_id} at period end")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription cancellation failed: {str(e)}")
            return False
    
    @staticmethod
    def update_payment_method(customer_id: str, payment_method_id: str) -> bool:
        """
        Update customer's default payment method
        
        Args:
            customer_id: Stripe customer ID
            payment_method_id: New payment method ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            logger.info(f"Updated payment method for customer {customer_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment method update failed: {str(e)}")
            return False
    
    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[Dict]:
        """
        Get subscription details
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            Subscription dict or None if error
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription: {str(e)}")
            return None
    
    @staticmethod
    def handle_webhook_event(event: Dict) -> bool:
        """
        Handle Stripe webhook events
        
        Args:
            event: Stripe event dict
            
        Returns:
            True if handled successfully, False otherwise
        """
        event_type = event['type']
        data = event['data']['object']
        
        try:
            if event_type == 'checkout.session.completed':
                return StripeService._handle_checkout_completed(data)
            
            elif event_type == 'customer.subscription.created':
                return StripeService._handle_subscription_created(data)
            
            elif event_type == 'customer.subscription.updated':
                return StripeService._handle_subscription_updated(data)
            
            elif event_type == 'customer.subscription.deleted':
                return StripeService._handle_subscription_deleted(data)
            
            elif event_type == 'customer.subscription.paused':
                return StripeService._handle_subscription_paused(data)
            
            elif event_type == 'customer.subscription.resumed':
                return StripeService._handle_subscription_resumed(data)
            
            elif event_type == 'invoice.payment_succeeded':
                return StripeService._handle_payment_succeeded(data)
            
            elif event_type == 'invoice.payment_failed':
                return StripeService._handle_payment_failed(data)
            
            elif event_type == 'customer.subscription.trial_will_end':
                return StripeService._handle_trial_will_end(data)
            
            elif event_type == 'customer.updated':
                return StripeService._handle_customer_updated(data)
            
            elif event_type == 'setup_intent.succeeded':
                return StripeService._handle_setup_intent_succeeded(data)
            
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"Webhook event handling failed: {str(e)}")
            return False
    
    @staticmethod
    def _handle_checkout_completed(session: Dict) -> bool:
        """Handle successful checkout session completion (setup mode)"""
        from services.email_service import EmailService
        from models import User
        from flask import url_for
        
        org_id = session['metadata'].get('org_id')
        if not org_id:
            logger.warning("Checkout session missing org_id metadata")
            return False
        
        org = Organization.query.get(org_id)
        if not org:
            logger.error(f"Organization {org_id} not found for checkout session")
            return False
        
        # Extract customer ID from the session
        customer_id = session.get('customer')
        if customer_id and not org.stripe_customer_id:
            org.stripe_customer_id = customer_id
            logger.info(f"Saved Stripe customer ID {customer_id} for organization {org_id}")
        
        # In setup mode, we get a setup_intent instead of subscription
        setup_intent_id = session.get('setup_intent')
        if setup_intent_id:
            try:
                # Retrieve the setup intent to get the payment method
                setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
                payment_method_id = setup_intent.get('payment_method')
                
                if payment_method_id:
                    # Set the default payment method for the customer
                    stripe.Customer.modify(
                        customer_id,
                        invoice_settings={'default_payment_method': payment_method_id}
                    )
                    logger.info(f"Set default payment method {payment_method_id} for customer {customer_id}")
                    
                    # Mark that organization has payment info but no active subscription yet
                    org.subscription_status = 'payment_method_added'
                    logger.info(f"Organization {org_id} payment method saved, awaiting approval")
                    
            except stripe.error.StripeError as e:
                logger.error(f"Failed to process setup intent: {str(e)}")
                return False
        
        # Send welcome email to admin user (for API-based signups without session)
        admin_user = User.query.filter_by(org_id=org.id, role='admin').first()
        if admin_user and admin_user.password_reset_token:
            try:
                password_setup_url = url_for('password_reset.reset_password', 
                                            token=admin_user.password_reset_token, 
                                            _external=True)
                
                EmailService.send_admin_welcome_email(
                    email=admin_user.email,
                    username=admin_user.username,
                    org_name=org.name,
                    password_setup_url=password_setup_url
                )
                logger.info(f"Welcome email sent via webhook to {admin_user.email} for organization {org_id}")
            except Exception as email_error:
                logger.error(f"Failed to send welcome email via webhook: {str(email_error)}")
        
        db.session.commit()
        logger.info(f"Checkout setup completed for organization {org_id}")
        return True
    
    @staticmethod
    def _handle_subscription_created(subscription: Dict) -> bool:
        """Handle subscription creation"""
        customer_id = subscription['customer']
        
        # Find organization by customer ID
        org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        if not org:
            logger.warning(f"No organization found for customer {customer_id}")
            return False
        
        org.stripe_subscription_id = subscription['id']
        org.subscription_status = subscription['status']
        
        db.session.commit()
        logger.info(f"Subscription created for organization {org.id}")
        return True
    
    @staticmethod
    def _handle_subscription_updated(subscription: Dict) -> bool:
        """Handle subscription updates"""
        subscription_id = subscription['id']
        
        # Find organization by subscription ID
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            logger.warning(f"No organization found for subscription {subscription_id}")
            return False
        
        org.subscription_status = subscription['status']
        
        # Handle trial ending
        if subscription['status'] == 'active' and org.setup_status == 'trial':
            org.setup_status = 'live'
        
        db.session.commit()
        logger.info(f"Subscription updated for organization {org.id}: status={subscription['status']}")
        return True
    
    @staticmethod
    def _handle_subscription_deleted(subscription: Dict) -> bool:
        """Handle subscription cancellation"""
        subscription_id = subscription['id']
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            return False
        
        org.subscription_status = 'canceled'
        org.setup_status = 'suspended'
        
        db.session.commit()
        logger.info(f"Subscription deleted for organization {org.id}")
        return True
    
    @staticmethod
    def _handle_payment_succeeded(invoice: Dict) -> bool:
        """Handle successful payment"""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return True
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            return False
        
        org.subscription_status = 'active'
        if org.setup_status in ['trial', 'suspended']:
            org.setup_status = 'live'
        
        db.session.commit()
        logger.info(f"Payment succeeded for organization {org.id}")
        return True
    
    @staticmethod
    def _handle_payment_failed(invoice: Dict) -> bool:
        """Handle failed payment"""
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return True
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            return False
        
        org.subscription_status = 'past_due'
        
        db.session.commit()
        logger.warning(f"Payment failed for organization {org.id}")
        return True
    
    @staticmethod
    def _handle_trial_will_end(subscription: Dict) -> bool:
        """
        Handle trial ending soon notification (sent 3 days before trial ends)
        This allows sending reminder emails to organizations
        """
        from services.email_service import EmailService
        
        subscription_id = subscription['id']
        customer_id = subscription.get('customer')
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        
        if not org:
            logger.warning(f"No organization found for trial ending subscription {subscription_id}")
            return False
        
        trial_end = subscription.get('trial_end')
        if trial_end:
            from datetime import datetime
            trial_end_date = datetime.utcfromtimestamp(trial_end)
            days_remaining = (trial_end_date - datetime.utcnow()).days
            
            logger.info(f"Trial ending soon for organization {org.id}: {days_remaining} days remaining")
            
            if org.billing_email:
                try:
                    EmailService.send_trial_reminder_email(
                        email=org.billing_email,
                        org_name=org.name,
                        days_remaining=days_remaining
                    )
                    logger.info(f"Sent trial ending reminder to {org.billing_email}")
                except Exception as e:
                    logger.error(f"Failed to send trial ending email: {str(e)}")
        
        return True
    
    @staticmethod
    def _handle_subscription_paused(subscription: Dict) -> bool:
        """
        Handle subscription paused event
        This can occur when billing is paused via Stripe dashboard or billing portal
        """
        subscription_id = subscription['id']
        customer_id = subscription.get('customer')
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        
        if not org:
            logger.warning(f"No organization found for paused subscription {subscription_id}")
            return False
        
        org.subscription_status = 'paused'
        db.session.commit()
        
        logger.info(f"Subscription paused for organization {org.id}")
        return True
    
    @staticmethod
    def _handle_subscription_resumed(subscription: Dict) -> bool:
        """
        Handle subscription resumed event
        Restores access after a paused subscription is resumed
        """
        subscription_id = subscription['id']
        customer_id = subscription.get('customer')
        
        org = Organization.query.filter_by(stripe_subscription_id=subscription_id).first()
        if not org:
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        
        if not org:
            logger.warning(f"No organization found for resumed subscription {subscription_id}")
            return False
        
        # Update to the actual subscription status from Stripe
        org.subscription_status = subscription.get('status', 'active')
        if org.setup_status == 'suspended':
            org.setup_status = 'live'
        
        db.session.commit()
        
        logger.info(f"Subscription resumed for organization {org.id}: status={org.subscription_status}")
        return True
    
    @staticmethod
    def _handle_customer_updated(customer: Dict) -> bool:
        """
        Handle customer updated event
        This fires when customer details or payment methods change via billing portal
        """
        customer_id = customer['id']
        
        org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        if not org:
            logger.debug(f"No organization found for customer {customer_id}")
            return True  # Not an error, just no matching org
        
        # Check if default payment method was updated
        default_payment_method = customer.get('invoice_settings', {}).get('default_payment_method')
        if default_payment_method:
            # Customer now has a valid payment method
            logger.info(f"Customer {customer_id} payment method updated for organization {org.id}")
            
            # If org was waiting for payment, update status
            if org.subscription_status == 'payment_method_added' or not org.stripe_subscription_id:
                # Payment method added/updated - check if we need to create subscription
                logger.info(f"Organization {org.id} has payment method, subscription_status={org.subscription_status}")
        
        # Update email if changed
        if customer.get('email') and customer['email'] != org.billing_email:
            org.billing_email = customer['email']
            logger.info(f"Updated billing email for organization {org.id}")
        
        db.session.commit()
        return True
    
    @staticmethod
    def _handle_setup_intent_succeeded(setup_intent: Dict) -> bool:
        """
        Handle successful setup intent
        This fires when payment method is added via billing portal or setup mode checkout
        """
        customer_id = setup_intent.get('customer')
        payment_method_id = setup_intent.get('payment_method')
        
        if not customer_id:
            logger.debug("Setup intent has no customer ID")
            return True
        
        org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        if not org:
            logger.debug(f"No organization found for customer {customer_id}")
            return True
        
        if payment_method_id:
            logger.info(f"Setup intent succeeded for organization {org.id}: payment_method={payment_method_id}")
            
            # Ensure payment method is set as default for future invoices
            try:
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={'default_payment_method': payment_method_id}
                )
                logger.info(f"Set default payment method for customer {customer_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Failed to set default payment method: {str(e)}")
            
            # Update org status if waiting for payment
            if org.subscription_status in ['incomplete', 'past_due']:
                # Payment method added - may resolve payment issues on next invoice
                logger.info(f"Organization {org.id} added payment method while in {org.subscription_status} state")
            elif not org.stripe_subscription_id and org.subscription_status != 'manual_billing':
                # No subscription yet - mark as payment method added
                org.subscription_status = 'payment_method_added'
                logger.info(f"Organization {org.id} payment method added, awaiting subscription")
        
        db.session.commit()
        return True
    
    @staticmethod
    def sync_subscription_from_stripe(org: Organization) -> bool:
        """
        Sync organization's subscription status from Stripe
        Useful for reconciliation or when webhooks may have been missed
        
        Args:
            org: Organization to sync
            
        Returns:
            True if synced successfully, False otherwise
        """
        try:
            if not org.stripe_customer_id:
                logger.warning(f"Cannot sync org {org.id} - no Stripe customer ID")
                return False
            
            # Get customer from Stripe
            customer = stripe.Customer.retrieve(org.stripe_customer_id, expand=['subscriptions'])
            
            # Check for active subscriptions
            subscriptions = customer.get('subscriptions', {}).get('data', [])
            
            if subscriptions:
                # Use the first active subscription
                sub = subscriptions[0]
                org.stripe_subscription_id = sub['id']
                org.subscription_status = sub['status']
                
                # Update trial info if present
                if sub.get('trial_end'):
                    org.trial_expires = datetime.utcfromtimestamp(sub['trial_end'])
                
                logger.info(f"Synced subscription for org {org.id}: status={sub['status']}")
            else:
                # No subscriptions - check if payment method exists
                default_pm = customer.get('invoice_settings', {}).get('default_payment_method')
                if default_pm:
                    org.subscription_status = 'payment_method_added'
                    logger.info(f"Org {org.id} has payment method but no subscription")
                else:
                    logger.info(f"Org {org.id} has no subscription or payment method")
            
            db.session.commit()
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to sync subscription for org {org.id}: {str(e)}")
            return False
    
    @staticmethod
    def activate_subscription_after_trial(org: Organization) -> bool:
        """
        Activate subscription for an organization whose trial has expired.
        This handles the case where trial was set manually but no Stripe subscription exists.
        
        Creates a new subscription that charges immediately (no trial period).
        
        Args:
            org: Organization with expired trial and valid payment method
            
        Returns:
            True if subscription activated successfully, False otherwise
        """
        try:
            if not org.stripe_customer_id:
                logger.error(f"Cannot activate subscription for org {org.id} - no Stripe customer ID")
                return False
            
            # Check if there's already a subscription
            if org.stripe_subscription_id:
                # Sync from Stripe to get current status
                return StripeService.sync_subscription_from_stripe(org)
            
            # Verify customer has a payment method
            customer = stripe.Customer.retrieve(org.stripe_customer_id)
            default_pm = customer.get('invoice_settings', {}).get('default_payment_method')
            
            if not default_pm:
                logger.warning(f"Cannot activate subscription for org {org.id} - no payment method")
                org.subscription_status = 'incomplete'
                db.session.commit()
                return False
            
            # Create subscription without trial (charge immediately)
            price_id = os.environ.get('STRIPE_PRICE_ID')
            
            subscription_params = {
                'customer': org.stripe_customer_id,
                'payment_behavior': 'error_if_incomplete',
                'expand': ['latest_invoice.payment_intent']
            }
            
            # Use configured price ID if available, otherwise use ad-hoc pricing
            if price_id:
                subscription_params['items'] = [{'price': price_id}]
            else:
                subscription_params['items'] = [{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': StripeService.PRODUCT_NAME,
                        },
                        'recurring': {
                            'interval': 'month',
                        },
                        'unit_amount': StripeService.SUBSCRIPTION_PRICE,
                    },
                }]
            
            subscription = stripe.Subscription.create(**subscription_params)
            
            # Update organization
            org.stripe_subscription_id = subscription.id
            org.subscription_status = subscription.status
            
            if subscription.status == 'active':
                org.setup_status = 'live'
                logger.info(f"Subscription activated successfully for org {org.id}")
            else:
                logger.warning(f"Subscription created but status is {subscription.status} for org {org.id}")
            
            db.session.commit()
            return subscription.status == 'active'
            
        except stripe.error.CardError as e:
            logger.error(f"Card declined for org {org.id}: {str(e)}")
            org.subscription_status = 'past_due'
            db.session.commit()
            return False
        except stripe.error.StripeError as e:
            logger.error(f"Failed to activate subscription for org {org.id}: {str(e)}")
            return False
    
    @staticmethod
    def ensure_subscription_exists(org: Organization) -> bool:
        """
        Ensure an organization has an active Stripe subscription.
        If trial has expired and org has payment method but no subscription,
        this will create one.
        
        Args:
            org: Organization to check/activate
            
        Returns:
            True if org has active subscription, False otherwise
        """
        if not org.stripe_customer_id:
            return False
        
        # Check current billing state
        billing = org.billing_state
        
        if billing['state'] == 'active':
            return True
        
        if billing['state'] == 'trialing':
            return True
        
        if billing['state'] == 'trial_expired':
            # Trial expired - try to activate subscription
            return StripeService.activate_subscription_after_trial(org)
        
        if billing['state'] == 'payment_method_added':
            # Has payment but no subscription - org needs approval first
            return False
        
        # Sync from Stripe as fallback
        return StripeService.sync_subscription_from_stripe(org)
