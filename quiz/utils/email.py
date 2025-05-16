from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

import traceback

def send_otp_email(email, otp, purpose="registration"):
    subject = f"GradeNext - OTP for {purpose.capitalize()}"
    message = f"Your OTP for {purpose} is: {otp}\nThis OTP is valid for 15 minutes."

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"[EMAIL ERROR] Failed to send OTP to {email}: {str(e)}")
        logger.error(traceback.format_exc())  # Full stack trace for logs
        raise  # Let the view handle it
