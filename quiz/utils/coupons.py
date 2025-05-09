# quiz/utils/coupons.py - New file
from django.utils import timezone
from ..models import Coupon
def validate_coupon(code):
    try:
        coupon = Coupon.objects.get(code=code)
        if coupon.is_valid():
            return coupon
        return None
    except Coupon.DoesNotExist:
        return None