from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from stayease.users.mixins import OwnerRequiredMixin
from stayease.users.mixins import TenantRequiredMixin
from stayease.users.models import User

if TYPE_CHECKING:
    from django.db.models import QuerySet


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        user = self.request.user
        assert isinstance(user, User)
        return user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        user = self.request.user
        assert isinstance(user, User)
        return user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        user = self.request.user
        assert isinstance(user, User)
        # Role-aware routing.
        if user.is_owner:
            return reverse("users:dashboard_owner")
        if user.is_admin_user and user.is_staff:
            return reverse("admin:index")
        # Tenant/default is directed to the tenant dashboard
        return reverse("users:dashboard_tenant")


user_redirect_view = UserRedirectView.as_view()


class OwnerDashboardView(OwnerRequiredMixin, TemplateView):
    template_name = "pages/dashboard_owner.html"


owner_dashboard_view = OwnerDashboardView.as_view()


class TenantDashboardView(TenantRequiredMixin, TemplateView):
    template_name = "pages/dashboard_tenant.html"


tenant_dashboard_view = TenantDashboardView.as_view()

