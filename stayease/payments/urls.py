"""
URL configuration for the payments app.

All URLs are namespaced under ``payments:``.
"""

from django.urls import path

from stayease.payments import views

app_name = "payments"

urlpatterns = [
    # Initiate payment for a booking (tenant only)
    path(
        "initiate/<int:booking_pk>/",
        views.PaymentInitiateView.as_view(),
        name="payment_initiate",
    ),
    # Process the dummy payment (tenant only)
    path(
        "process/<int:pk>/",
        views.PaymentProcessView.as_view(),
        name="payment_process",
    ),
    # Payment receipt / detail (tenant only)
    path(
        "<int:pk>/",
        views.PaymentDetailView.as_view(),
        name="payment_detail",
    ),
]
