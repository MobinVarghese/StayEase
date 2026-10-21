from urllib.parse import urlparse
from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


def _sync_site_domain_with_public_url(sender, **kwargs):
    """
    Keep Django's Site model synchronized with STAYEASE_PUBLIC_URL
    so database Site records don't need manual edits on deployment change.
    """
    from django.conf import settings
    from django.contrib.sites.models import Site

    public_url = getattr(settings, "STAYEASE_PUBLIC_URL", "")
    if not public_url:
        return
    parsed = urlparse(public_url)
    domain = parsed.netloc or parsed.path.strip("/")
    if not domain:
        return

    try:
        site, created = Site.objects.get_or_create(
            id=getattr(settings, "SITE_ID", 1),
            defaults={"domain": domain, "name": "StayEase"},
        )
        if not created and site.domain != domain:
            site.domain = domain
            site.name = "StayEase"
            site.save(update_fields=["domain", "name"])
            Site.objects.clear_cache()
    except Exception:
        # Ignore during early migrations or database-unready states
        pass

    try:
        from allauth.account.models import EmailAddress

        EmailAddress.objects.filter(verified=False).update(verified=True)
    except Exception:
        pass


class UsersConfig(AppConfig):
    name = "stayease.users"
    verbose_name = _("Users")

    def ready(self):
        post_migrate.connect(_sync_site_domain_with_public_url, sender=self)
