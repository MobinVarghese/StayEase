from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DiscoveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stayease.discovery"
    verbose_name = _("Discovery")
