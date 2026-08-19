"""
URL configuration for the bookings app.

All URLs are namespaced under ``bookings:``.
Tenant and owner views are separated by URL prefix and enforced
by authorization mixins/decorators defined in ``stayease.users``.
"""

from django.urls import path

from stayease.bookings import views

app_name = "bookings"

urlpatterns = [
    # ------------------------------------------------------------------
    # Tenant URLs
    # ------------------------------------------------------------------
    # Tenant booking history
    path(
        "",
        views.TenantBookingListView.as_view(),
        name="booking_list",
    ),
    # Create a booking for a specific bed
    path(
        "create/<int:bed_pk>/",
        views.BookingCreateView.as_view(),
        name="booking_create",
    ),
    # Booking detail (accessible to tenant and owner)
    path(
        "<int:pk>/",
        views.BookingDetailView.as_view(),
        name="booking_detail",
    ),
    # ------------------------------------------------------------------
    # Owner URLs
    # ------------------------------------------------------------------
    # Owner booking management dashboard
    path(
        "owner/",
        views.OwnerBookingListView.as_view(),
        name="owner_booking_list",
    ),
    # Owner approves a PENDING booking (POST only)
    path(
        "<int:pk>/approve/",
        views.BookingApproveView.as_view(),
        name="booking_approve",
    ),
    # Owner rejects a PENDING booking (POST only)
    path(
        "<int:pk>/reject/",
        views.BookingRejectView.as_view(),
        name="booking_reject",
    ),
]
