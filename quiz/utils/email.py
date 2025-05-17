# utils/email.py
from django.core.mail import EmailMessage
import logging

logger = logging.getLogger(__name__)

def send_otp_email(to_email, otp, purpose='registration'):
    subject = f"Your GradeNext OTP for {purpose}"
    body = f"Your verification code is {otp}. It expires in 10 minutes."
    email = EmailMessage(subject, body, to=[to_email])
    try:
        email.send(fail_silently=False)
        logger.info(f"Sent OTP {otp} to {to_email} for {purpose}")
    except Exception as e:
        logger.error(f"Error sending OTP email to {to_email}: {e}", exc_info=True)
        raise
