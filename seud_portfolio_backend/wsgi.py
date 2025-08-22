"""
WSGI config for seud_portfolio_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

_existing = os.environ.get("DJANGO_SETTINGS_MODULE")
if _existing:
	os.environ["DJANGO_SETTINGS_MODULE"] = _existing.strip()
else:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seud_portfolio_backend.settings")

application = get_wsgi_application()
