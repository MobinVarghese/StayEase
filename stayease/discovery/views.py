"""
Discovery views — tenant-facing PG browsing and search.

These views require the user to be logged in with the TENANT role.

Business logic ownership: Member 3
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from stayease.discovery.forms import PGSearchForm
from stayease.discovery.services import (
    get_distinct_cities,
    get_rooms_with_availability,
    search_pgs,
)
from stayease.properties.models import PG
from stayease.users.mixins import TenantRequiredMixin


class PGDiscoveryListView(TenantRequiredMixin, ListView):
    """
    Tenant-only PG listing page with search, filtering, and pagination.

    Requires TENANT role login. Query parameters are passed to ``search_pgs()``
    which builds a filtered, annotated queryset at the database level.
    """

    model = PG
    template_name = "discovery/pg_list.html"
    context_object_name = "pgs"
    paginate_by = 12

    def get_queryset(self):
        return search_pgs(self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cities = get_distinct_cities()
        ctx["search_form"] = PGSearchForm(
            data=self.request.GET or None,
            cities=cities,
        )
        # Preserve current filter state for pagination links.
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        ctx["current_filters"] = query_params.urlencode()
        return ctx


class PGDiscoveryDetailView(TenantRequiredMixin, DetailView):
    """
    PG detail page showing rooms, beds, and availability.

    Requires TENANT role login. Only active PGs are visible. Rooms and beds are loaded with
    availability annotations.  Each bookable bed renders a link to
    ``bookings:booking_create`` (owned by Member 4).
    """

    model = PG
    template_name = "discovery/pg_detail.html"
    context_object_name = "pg"
    pk_url_kwarg = "pg_pk"

    def get_queryset(self):
        return PG.objects.filter(is_active=True).prefetch_related(
            "rooms__beds__bookings",
        )

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pg_pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rooms_data"] = get_rooms_with_availability(self.object)
        return ctx
