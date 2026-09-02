"""
Booking views.

All views enforce server-side authorization using Member 1's mixins.
Business logic is delegated to ``services.py`` — views handle HTTP
concerns only (request parsing, template rendering, messages, redirects).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

from stayease.notifications.services import (
    notify_booking_approved,
    notify_booking_rejected,
    notify_booking_requested,
)
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView

from stayease.bookings.forms import BookingRequestForm
from stayease.bookings.models import ACTIVE_BOOKING_STATUSES
from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.services import approve_booking
from stayease.bookings.services import create_booking_request
from stayease.bookings.services import reject_booking
from stayease.properties.models import Bed
from stayease.users.mixins import OwnerRequiredMixin
from stayease.users.mixins import TenantRequiredMixin


# ======================================================================
# Tenant views
# ======================================================================


class BookingCreateView(TenantRequiredMixin, TemplateView):
    """
    Display a bed's details and let the tenant confirm a booking request.

    GET  → show bed info + confirmation form.
    POST → create the booking via ``services.create_booking_request()``.
    """

    template_name = "bookings/booking_form.html"

    def _get_bed(self):
        return get_object_or_404(
            Bed.objects.select_related("room__pg"),
            pk=self.kwargs["bed_pk"],
            is_active=True,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bed = self._get_bed()
        ctx["bed"] = bed
        ctx["room"] = bed.room
        ctx["pg"] = bed.room.pg
        ctx["form"] = BookingRequestForm()
        # Check if bed already has an active booking (display hint)
        ctx["has_active_booking"] = Booking.objects.filter(
            bed=bed, status__in=ACTIVE_BOOKING_STATUSES
        ).exists()
        return ctx

    def post(self, request, *args, **kwargs):
        bed = self._get_bed()
        form = BookingRequestForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Invalid form submission."))
            return redirect("bookings:booking_create", bed_pk=bed.pk)

        try:
            booking = create_booking_request(tenant=request.user, bed=bed)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("bookings:booking_create", bed_pk=bed.pk)

        # Member 5 integration: notify the PG owner
        notify_booking_requested(booking)

        messages.success(
            request,
            _("Your booking request has been submitted successfully!"),
        )
        return redirect("bookings:booking_detail", pk=booking.pk)


class TenantBookingListView(TenantRequiredMixin, ListView):
    """List the authenticated tenant's own bookings (history)."""

    model = Booking
    template_name = "bookings/booking_list.html"
    context_object_name = "bookings"
    paginate_by = 20

    def get_queryset(self):
        return (
            Booking.objects.filter(tenant=self.request.user)
            .select_related("bed__room__pg")
            .order_by("-created_at")
        )


class BookingDetailView(LoginRequiredMixin, DetailView):
    """
    Booking detail — accessible to:
     • The tenant who owns the booking.
     • The owner of the PG associated with the bed.
    """

    model = Booking
    template_name = "bookings/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.select_related(
            "tenant", "bed__room__pg__owner"
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        is_tenant = obj.tenant_id == user.pk
        is_pg_owner = obj.bed.room.pg.owner_id == user.pk
        is_admin = getattr(user, "is_admin_user", False)
        if not (is_tenant or is_pg_owner or is_admin):
            raise PermissionDenied(
                _("You do not have permission to view this booking.")
            )
        return obj


# ======================================================================
# Owner views
# ======================================================================


class OwnerBookingListView(OwnerRequiredMixin, ListView):
    """List bookings for all PGs owned by the authenticated owner."""

    model = Booking
    template_name = "bookings/booking_owner_list.html"
    context_object_name = "bookings"
    paginate_by = 20

    def get_queryset(self):
        return (
            Booking.objects.filter(
                bed__room__pg__owner=self.request.user,
            )
            .select_related("tenant", "bed__room__pg")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx["pending_count"] = qs.filter(status=BookingStatus.PENDING).count()
        return ctx


class BookingApproveView(OwnerRequiredMixin, View):
    """POST-only: Owner approves a PENDING booking."""

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking.objects.select_related("bed__room__pg"),
            pk=pk,
        )
        try:
            approve_booking(booking=booking, owner=request.user)
        except PermissionDenied:
            messages.error(
                request,
                _("You do not have permission to manage this booking."),
            )
            return redirect("bookings:owner_booking_list")
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("bookings:booking_detail", pk=pk)

        # Member 5 integration: notify the tenant
        notify_booking_approved(booking)

        messages.success(request, _("Booking has been approved."))
        return redirect("bookings:booking_detail", pk=pk)


class BookingRejectView(OwnerRequiredMixin, View):
    """POST-only: Owner rejects a PENDING booking."""

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking.objects.select_related("bed__room__pg"),
            pk=pk,
        )
        try:
            reject_booking(booking=booking, owner=request.user)
        except PermissionDenied:
            messages.error(
                request,
                _("You do not have permission to manage this booking."),
            )
            return redirect("bookings:owner_booking_list")
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("bookings:booking_detail", pk=pk)

        # Member 5 integration: notify the tenant
        notify_booking_rejected(booking)

        messages.success(request, _("Booking has been rejected."))
        return redirect("bookings:booking_detail", pk=pk)
