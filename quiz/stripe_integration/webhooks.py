# quiz/stripe_integration/webhooks.py

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from quiz.models import CustomUser, StripeSubscription
import logging
import time
from datetime import datetime
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

@csrf_exempt
def stripe_webhook(request):
    # print("⚡ Stripe Webhook Triggered")
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        print("⚠️ Webhook signature verification failed:", e)
        return HttpResponse(status=400)

    event_type = event['type']
    data_object = event['data']['object']

    # ✅ New Checkout Session Completed (initial purchase)
    if event_type == 'checkout.session.completed':
        session = data_object
        customer_email = session.get('customer_email')
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        metadata = session.get("metadata", {})

        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        discount = stripe_sub.get("discount")
        coupon_id = discount["coupon"]["id"] if discount else None

        plan = metadata.get("plan", "unknown")
        duration = int(metadata.get("duration", 1))
        platform_fee_applied = metadata.get("platform_fee_applied", "true") == "true"

        try:
            user = CustomUser.objects.get(email=customer_email)

            StripeSubscription.objects.create(
                user=user,
                user_email=user.email,
                user_name=user.student_name,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                plan=plan,
                duration=duration,
                platform_fee_applied=platform_fee_applied,
                coupon_applied=coupon_id,
                start_date=timezone.now(),
                end_date=timezone.now() + timezone.timedelta(days=30 * duration),
                status='active'
            )

            user.plan = plan
            user.is_verified = True
            user.save()
            print(f"✅ New subscription created for {user.email}")

        except CustomUser.DoesNotExist:
            StripeSubscription.objects.create(
                user=None,
                user_email=customer_email,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                plan=plan,
                duration=duration,
                platform_fee_applied=platform_fee_applied
            )
            print(f"⚠️ Subscription created for unknown user {customer_email}")

    # ✅ Subscription auto-renewed successfully


    elif event['type'] == 'invoice.paid':
        logger.info("🔁 Handling invoice.paid event")
        invoice = event['data']['object']

        try:
            # Get subscription ID
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                for line in invoice.get("lines", {}).get("data", []):
                    parent = line.get("parent")
                    if parent and isinstance(parent, dict):
                        sub_item = parent.get("subscription_item_details")
                        if sub_item and sub_item.get("subscription"):
                            subscription_id = sub_item["subscription"]
                            break
                        sub_details = parent.get("subscription_details")
                        if sub_details and sub_details.get("subscription"):
                            subscription_id = sub_details["subscription"]
                            break

            if not subscription_id:
                logger.warning("❌ Could not extract subscription_id from invoice lines")
                return HttpResponse(status=200)

            logger.info(f"✅ Processing invoice.paid for subscription ID: {subscription_id}")

            # 🔁 Retry DB fetch for 3 seconds
            stripe_subscription = None
            for i in range(5):
                try:
                    stripe_subscription = StripeSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    break
                except StripeSubscription.DoesNotExist:
                    time.sleep(1)

            if not stripe_subscription:
                logger.error(f"❌ StripeSubscription not found for {subscription_id} after retrying")
                return HttpResponse(status=200)

            # Update billing period dates
            period = invoice["lines"]["data"][0]["period"]
            stripe_subscription.start_date = make_aware(datetime.fromtimestamp(period["start"]))
            stripe_subscription.end_date = make_aware(datetime.fromtimestamp(period["end"]))
            stripe_subscription.save()

            logger.info(f"✅ Subscription dates updated for {stripe_subscription.user_email}")
            return HttpResponse(status=200)

        except Exception as e:
            logger.exception(f"❌ Exception during invoice.paid: {e}")
            return HttpResponse(status=500)

    # 🛑 User cancelled subscription manually
    elif event_type == 'customer.subscription.deleted':
        subscription = data_object
        subscription_id = subscription.get("id")

        try:
            sub = StripeSubscription.objects.get(stripe_subscription_id=subscription_id)
            sub.status = 'cancelled'
            sub.save()
            print(f"🛑 Subscription manually cancelled for {sub.user_email}")
        except StripeSubscription.DoesNotExist:
            print(f"⚠️ Subscription cancellation: No subscription found for ID {subscription_id}")
            
    elif event_type == 'invoice.payment_failed':
        logger.info("❌ Handling invoice.payment_failed event")
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')  # Primary check

        # Fallback from invoice lines
        if not subscription_id:
            lines = invoice.get("lines", {}).get("data", [])
            if lines:
                parent = lines[0].get("parent")
                if isinstance(parent, dict):
                    sub_details = parent.get("subscription_item_details")
                    if isinstance(sub_details, dict):
                        subscription_id = sub_details.get("subscription")

        if not subscription_id:
            logger.warning("❌ Could not find subscription_id in invoice.payment_failed")
            return HttpResponse(status=200)

        try:
            stripe_subscription = StripeSubscription.objects.get(stripe_subscription_id=subscription_id)
            stripe_subscription.status = 'expired'
            stripe_subscription.save()
            print(f"❌ Subscription marked as expired for {stripe_subscription.user_email}")
        except StripeSubscription.DoesNotExist:
            print(f"⚠️ No matching subscription found to expire: {subscription_id}")

    return HttpResponse(status=200)
