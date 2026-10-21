from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="ra4kjN5VB6EpoGNov8ZGeOGJ9gl3I4LTUx47l4MohM6Ta8GBCEF0pw14AWvsI6Zi",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# Use SMTP backend when credentials are configured; fall back to console.
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
_email_host_user = env("EMAIL_HOST_USER", default="")
_email_host_password = env("EMAIL_HOST_PASSWORD", default="")

if _email_host_user and _email_host_password:
    EMAIL_BACKEND = env(
        "DJANGO_EMAIL_BACKEND",
        default="django.core.mail.backends.smtp.EmailBackend",
    )
    EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_HOST_USER = _email_host_user
    EMAIL_HOST_PASSWORD = _email_host_password
else:
    import logging as _logging

    _logging.getLogger(__name__).info(
        "EMAIL_HOST_USER/EMAIL_HOST_PASSWORD not configured — "
        "using console email backend. Emails will be printed to stdout."
    )
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# WhiteNoise
# ------------------------------------------------------------------------------
# http://whitenoise.evans.io/en/latest/django.html#using-whitenoise-in-development
INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]


# django-debug-toolbar (disabled as requested)
# ------------------------------------------------------------------------------
# To re-enable the debug toolbar, uncomment the lines below:
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]


# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# Your stuff...
# ------------------------------------------------------------------------------
