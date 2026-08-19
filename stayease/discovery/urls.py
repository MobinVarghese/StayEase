"""
URL configuration for the discovery app.

All URLs are tenant-facing (public).  The namespace is ``discovery``.
"""

from django.urls import path

from stayease.discovery import views

app_name = "discovery"

urlpatterns = [
    path("", views.PGDiscoveryListView.as_view(), name="pg_list"),
    path("<int:pg_pk>/", views.PGDiscoveryDetailView.as_view(), name="pg_detail"),
]
