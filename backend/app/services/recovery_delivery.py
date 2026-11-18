"""Password-recovery delivery adapters.

Development mode deliberately does not contact external providers. Production
can use SMTP for email and Twilio's HTTPS API for SMS by supplying credentials
through environment variables.
"""

from email.message import EmailMessage
import smtplib
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import base64

from ..config import get_settings


def send_reset_email(recipient: str, reset_link: str) -> None:
    settings = get_settings()
    if settings.email_provider == "development":
        return
    if not all((settings.smtp_host, settings.smtp_username, settings.smtp_password)):
        raise RuntimeError("SMTP password-recovery delivery is not configured")
    message = EmailMessage()
    message["Subject"] = "Reset your AquaSense AI password"
    message["From"] = settings.email_from
    message["To"] = recipient
    message.set_content(f"Use this link to reset your AquaSense AI password. It expires in 30 minutes and can be used once:\n\n{reset_link}\n\nIf you did not request this, ignore this email.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_reset_sms(recipient: str, otp: str) -> None:
    settings = get_settings()
    if settings.sms_provider == "development":
        return
    if not all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number)):
        raise RuntimeError("Twilio password-recovery delivery is not configured")
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    credentials = base64.b64encode(f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()).decode()
    body = urlencode({"From": settings.twilio_from_number, "To": recipient, "Body": f"Your AquaSense AI password reset OTP is {otp}. It expires in 30 minutes."}).encode()
    request = Request(endpoint, data=body, headers={"Authorization": f"Basic {credentials}"}, method="POST")
    with urlopen(request, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"SMS provider returned HTTP {response.status}")
