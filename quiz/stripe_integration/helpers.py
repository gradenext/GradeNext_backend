import stripe
from django.conf import settings
from .prices import STRIPE_PRICE_IDS

stripe.api_key = settings.STRIPE_SECRET_KEY

PROMOTION_CODES = {
    "FIRST50": "promo_1RkeEwGb17a8LOzTD1PDWyEt"
}


def create_checkout_session(user, plan, duration, include_platform_fee=True, request=None, coupon_code=None):
    try:
        price_id = STRIPE_PRICE_IDS[plan][str(duration)]
    except KeyError:
        raise ValueError("Invalid plan or duration")

    line_items = [{"price": price_id, "quantity": 1}]
    if include_platform_fee:
        line_items.append({"price": STRIPE_PRICE_IDS["platform_fee"], "quantity": 1})

    session_data = {
        "payment_method_types": ["card"],
        "customer_email": user.email,
        "line_items": line_items,
        "mode": "subscription",
        "metadata": {
            "plan": plan,
            "duration": duration,
            "platform_fee_applied": str(include_platform_fee)
        },
        "success_url": f"https://app.gradenext.com/pricing-success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"https://app.gradenext.com/pricing-cancel?session_id={{CHECKOUT_SESSION_ID}}",

    }

    # ✅ Use promotion_code (not coupon) if provided
    if coupon_code:
        promo_id = PROMOTION_CODES.get(coupon_code.upper())
        if not promo_id:
            raise ValueError("Invalid coupon code.")
        session_data["discounts"] = [{"promotion_code": promo_id}]


    session = stripe.checkout.Session.create(**session_data)
    return session

