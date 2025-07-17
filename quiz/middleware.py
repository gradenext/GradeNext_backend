from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from quiz.utils.plan_check import has_valid_paid_plan
from quiz.models import StripeSubscription

EXEMPT_PATHS = [
    reverse('register'),
    reverse('login'),
    reverse('user-profile'),
    reverse('verify-otp'), 
    # Add any views you want open access to
]


class PlanVerificationMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        # print("🔥 PlanVerificationMiddleware running for path:", request.path)
        if (
            request.path.startswith("/admin/") or
            request.path in EXEMPT_PATHS
        ):
            return None


        if request.user.is_authenticated:
            user = request.user
            plan = user.plan
            path = request.path

            # 🧪 Trial Plan Expiry Check
            # print("🔍 Checking plan for user:", user.email, "Plan:", plan)
            # if plan == 'trial' and user.trial_start_date:
            #     if timezone.now() > user.trial_start_date + timedelta(days=14):
            #         return JsonResponse({
            #             'error': 'Trial expired. Please upgrade to continue.'
            #         }, status=403)

            # # 🧾 Paid Plan Expiry Check
            # if plan in ['basic', 'pro', 'enterprise']:
            #     try:
            #         sub = StripeSubscription.objects.get(user=user, status='active')
            #         # ✅ Expire the subscription if needed
            #         if sub.end_date and sub.end_date < timezone.now():
            #             print("⚠️ Subscription expired for user:", user.email)
            #             sub.status = 'expired'
            #             sub.save()
            #             return JsonResponse({
            #                 'error': 'Your subscription has expired. Please renew to continue.'
            #             }, status=403)
            #     except StripeSubscription.DoesNotExist:
            #         pass

            # 🔒 Plan-Based Feature Restrictions
            if plan == 'basic' and any(p in path for p in ['/revision-questions/', '/topic-questions/']):
                return JsonResponse({
                    'error': 'Upgrade to Pro or Enterprise plan to access this feature'
                }, status=403)

            if plan == 'pro' and '/topic-questions/' in path:
                return JsonResponse({
                    'error': 'Enterprise plan required for topic-wise questions'
                }, status=403)

        return None
