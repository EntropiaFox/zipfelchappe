import os  # NOQA
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")

from django.core.wsgi import get_wsgi_application  # NOQA
application = get_wsgi_application()
