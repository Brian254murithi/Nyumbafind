"""WSGI config for NyumbaFind."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nyumbafind.settings")

application = get_wsgi_application()
