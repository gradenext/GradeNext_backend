from django.utils import timezone
from quiz.models import StripeSubscription

def has_valid_paid_plan(user):
    try:
        sub = StripeSubscription.objects.get(user=user, status="active")
        return sub.end_date and sub.end_date > timezone.now()
    except StripeSubscription.DoesNotExist:
        return False
