# from django.contrib import admin

# # Register your models here.
# # quiz/admin.py - Add coupon admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .models import Coupon, StripeSubscription

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'plan_type', 'is_valid', 'times_used')
    readonly_fields = ('times_used',)
    search_fields = ('code',)



@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'student_name', 'grade', 'is_staff', 'is_superuser', 'is_verified')
    search_fields = ('email', 'student_name', 'parent_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('student_name', 'parent_name', 'gender', 'grade', 'courses', 'country', 'state', 'zip_code')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Plan Info', {'fields': ('plan', 'applied_coupon')}),
        ('Verification', {'fields': ('is_verified',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'student_name', 'parent_name', 'gender', 'grade', 'is_staff', 'is_superuser')}
        ),
    )


@admin.register(StripeSubscription)
class StripeSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'user_name', 'plan', 'duration', 'stripe_subscription_id', 'created_at')
    search_fields = ('user_email', 'stripe_subscription_id', 'stripe_customer_id')
    list_filter = ('plan', 'duration', 'platform_fee_applied')
    readonly_fields = ('created_at',)