from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse

EXEMPT_PATHS = [
    reverse('register'),
    reverse('login'),
    reverse('user-profile'),
]

class PlanVerificationMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path in EXEMPT_PATHS:
            return None
            
        if request.user.is_authenticated:
            plan = request.user.plan
            path = request.path
            
            # Basic plan restrictions
            if plan == 'basic' and any(p in path for p in ['/revision-questions/', '/topic-questions/']):
                return JsonResponse({
                    'error': 'Upgrade to Pro or Enterprise plan to access this feature'
                }, status=403)
                
            # Pro plan restrictions
            if plan == 'pro' and '/topic-questions/' in path:
                return JsonResponse({
                    'error': 'Enterprise plan required for topic-wise questions'
                }, status=403)
        
        return None