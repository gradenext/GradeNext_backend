# quiz/stripe_integration/views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .helpers import create_checkout_session
from django.http import HttpResponse
import stripe
from quiz.models import StripeSubscription
from .prices import STRIPE_PRICE_IDS

class CreateStripeCheckoutSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        plan = request.data.get("plan")
        duration = request.data.get("duration")
        include_platform_fee = request.data.get("platform_fee_applied", True)
        coupon_code = request.data.get("coupon_code")
        
        print("user data assigning in checkout api :", user)
        print("duration from request.data:", request.data)
        print("plan from request.data:", plan)
        print("request.user:",request.user)

        try:
            session = create_checkout_session(user, plan, duration, include_platform_fee, request,coupon_code=coupon_code)
            return Response({
                "sessionId": session.id,
                "checkout_url": session.url
            })
        except stripe.error.InvalidRequestError as e:
            return Response({"error": "Invalid coupon code."}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Success & Cancel Redirect Views
def stripe_success(request):
    return HttpResponse("✅ Payment successful! Subscription activated.")

def stripe_cancel(request):
    return HttpResponse("❌ Payment cancelled. Please try again.")


class CancelStripeSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            subscription = StripeSubscription.objects.get(user=user, status="active")

            try:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,  
                    cancel_at_period_end=True
                )
            except stripe.error.StripeError as e:
                return Response({"error": f"Stripe error: {str(e)}"}, status=400)

            # subscription.status = "cancelled"
            subscription.cancel_at_period_end = True
            subscription.save()

            return Response({
                "message": "Subscription will be cancelled at the end of the current billing period."
            }, status=status.HTTP_200_OK)

        except StripeSubscription.DoesNotExist:
            return Response({"error": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        
        
# quiz/stripe_integration/views.py

class ChangeStripePlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_plan = request.data.get("plan")        
        duration = str(request.data.get("duration"))  

        if not new_plan or not duration:
            return Response({"error": "Plan and duration are required."}, status=400)

        try:
            # Get active subscription
            subscription = StripeSubscription.objects.get(user=user, status="active")
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

            # Get new price ID
            new_price_id = STRIPE_PRICE_IDS[new_plan][duration]
            
            print(f"Changing subscription to {new_plan} for {duration} month(s)")

            # Modify subscription with new plan
            updated = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    "id": stripe_sub['items']['data'][0].id,
                    "price": new_price_id,
                }],
                billing_cycle_anchor="now",  # 👈 force immediate cycle change
                proration_behavior="create_prorations",
                cancel_at_period_end=False,
                metadata={
                    "plan": new_plan,
                    "duration": duration,
                    "changed_by_user_id": str(user.id)
                }
            )


            # ❌ No local DB update here – let webhook handle it
            return Response({
                "message": f"Subscription change requested for {new_plan} ({duration} month(s))",
                "stripe_subscription_status": updated["status"],
                "proration_behavior": "create_prorations",
            })

        except StripeSubscription.DoesNotExist:
            return Response({"error": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)

        except KeyError:
            return Response({"error": "Invalid plan or duration."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

