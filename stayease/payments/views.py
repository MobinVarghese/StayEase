"""
Payment views.

All views enforce server-side authorization.
Business logic is delegated to ``services.py``.

No real payment credentials are collected.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import TemplateView
from django.views import View

from stayease.bookings.models import Booking
from stayease.payments.models import Payment
from stayease.payments.services import initiate_payment
from stayease.payments.services import process_dummy_payment
from stayease.users.mixins import TenantRequiredMixin


class PaymentInitiateView(TenantRequiredMixin, TemplateView):
    """
    Display booking summary and allow the tenant to initiate payment.

    GET  → show booking info + "Proceed to Pay" button.
    POST → create the payment via ``services.initiate_payment()``.
    """

    template_name = "payments/payment_initiate.html"

    def _get_booking(self):
        return get_object_or_404(
            Booking.objects.select_related(
                "tenant", "bed__room__pg",
            ),
            pk=self.kwargs["booking_pk"],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        booking = self._get_booking()
        # Only the tenant can see the payment page
        if booking.tenant != self.request.user:
            raise PermissionDenied(
                _("You do not have permission to pay for this booking.")
            )
        ctx["booking"] = booking
        ctx["amount"] = booking.bed.rent_per_month
        return ctx

    def post(self, request, *args, **kwargs):
        booking = self._get_booking()
        try:
            payment = initiate_payment(booking=booking, user=request.user)
        except PermissionDenied:
            messages.error(
                request,
                _("You do not have permission to pay for this booking."),
            )
            return redirect("bookings:booking_detail", pk=booking.pk)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("bookings:booking_detail", pk=booking.pk)

        return redirect("payments:payment_process", pk=payment.pk)


class PaymentProcessView(TenantRequiredMixin, TemplateView):
    """
    Dummy payment processing page.

    GET  → show payment details with "Simulate Success" / "Simulate Failure" buttons.
    POST → process the dummy payment.
    """

    template_name = "payments/payment_process.html"

    def _get_payment(self):
        return get_object_or_404(
            Payment.objects.select_related(
                "booking__tenant", "booking__bed__room__pg",
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        payment = self._get_payment()
        if payment.booking.tenant != self.request.user:
            raise PermissionDenied(
                _("You do not have permission to process this payment.")
            )
        ctx["payment"] = payment
        ctx["booking"] = payment.booking
        return ctx

    def post(self, request, *args, **kwargs):
        payment = self._get_payment()
        simulate_success = request.POST.get("action") == "success"

        try:
            process_dummy_payment(
                payment=payment,
                user=request.user,
                simulate_success=simulate_success,
            )
        except PermissionDenied:
            messages.error(
                request,
                _("You do not have permission to process this payment."),
            )
            return redirect("bookings:booking_list")
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("payments:payment_detail", pk=payment.pk)

        if simulate_success:
            messages.success(
                request,
                _("Payment successful! Your booking is now confirmed."),
            )
        else:
            messages.warning(
                request,
                _("Payment failed. Please try again or contact support."),
            )

        return redirect("payments:payment_detail", pk=payment.pk)


class PaymentDetailView(TenantRequiredMixin, DetailView):
    """
    Payment receipt / detail view.

    Only the booking's tenant can see their own payment.
    """

    model = Payment
    template_name = "payments/payment_detail.html"
    context_object_name = "payment"

    def get_queryset(self):
        return Payment.objects.select_related(
            "booking__tenant", "booking__bed__room__pg",
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.booking.tenant != self.request.user:
            raise PermissionDenied(
                _("You do not have permission to view this payment.")
            )
        return obj
