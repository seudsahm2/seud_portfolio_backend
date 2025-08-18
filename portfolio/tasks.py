from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime
try:
    from supabase import create_client
except Exception:  # pragma: no cover
    create_client = None


@shared_task
def send_contact_email(name: str, email: str, message: str) -> str:
    subject = f"Portfolio contact from {name}"
    body = f"From: {name} <{email}>\n\n{message}"
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL])
    return f"sent:{datetime.utcnow().isoformat()}"


@shared_task
def refresh_knowledge() -> str:
    # placeholder for later AI ingestion; succeeds to prove scheduling works
    return f"refreshed:{datetime.utcnow().isoformat()}"
