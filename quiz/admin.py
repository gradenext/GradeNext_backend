from django.contrib import admin

# Register your models here.
# quiz/admin.py - Add coupon admin
from .models import Coupon

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'plan_type', 'is_valid', 'times_used')
    readonly_fields = ('times_used',)
    search_fields = ('code',)