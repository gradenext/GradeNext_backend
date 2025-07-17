# quiz/stripe_integration/urls.py

from django.urls import path
from .views import (
    CreateStripeCheckoutSession,
    stripe_success,
    stripe_cancel,
    CancelStripeSubscriptionAPIView,
    ChangeStripePlanAPIView
)
from .webhooks import stripe_webhook

urlpatterns = [
    path("create-checkout-session/", CreateStripeCheckoutSession.as_view(), name="stripe-checkout"),
    path("success/", stripe_success, name="stripe-success"),
    path("cancel/", stripe_cancel, name="stripe-cancel"),
    path("webhook/", stripe_webhook, name="stripe-webhook"), 
    path("cancel-subscription/", CancelStripeSubscriptionAPIView.as_view(), name="cancel-subscription"),
    path("change-plan/", ChangeStripePlanAPIView.as_view(), name="change-plan"),
]
