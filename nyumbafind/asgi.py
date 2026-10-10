"""ASGI config for NyumbaFind."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nyumbafind.settings")

application = get_asgi_application()
