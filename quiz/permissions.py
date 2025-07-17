# quiz/permissions.py
from rest_framework.permissions import BasePermission
from django.utils import timezone
from quiz.models import StripeSubscription


class HasActiveSubscription(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.plan == 'trial' and user.trial_start_date:
            return timezone.now() <= user.trial_start_date + timezone.timedelta(days=14)

        if user.plan in ['basic', 'pro', 'enterprise']:
            sub = StripeSubscription.objects.filter(user=user).order_by('-end_date').first()
            if sub:
                now = timezone.now()
                if sub.end_date and sub.end_date > now and sub.status == 'active':
                    return True
                else:
                    return False

        return False
