"""
URL configuration for the properties app.

All URLs are owner-facing and require authentication + OWNER role.
The namespace is ``properties``.
"""

from django.urls import path

from stayease.properties import views

app_name = "properties"

urlpatterns = [
    # ------------------------------------------------------------------
    # PG
    # ------------------------------------------------------------------
    path("", views.PGListView.as_view(), name="pg_list"),
    path("create/", views.PGCreateView.as_view(), name="pg_create"),
    path("<int:pg_pk>/", views.PGDetailView.as_view(), name="pg_detail"),
    path("<int:pg_pk>/edit/", views.PGUpdateView.as_view(), name="pg_edit"),
    path("<int:pg_pk>/delete/", views.PGDeleteView.as_view(), name="pg_delete"),
    # ------------------------------------------------------------------
    # Room
    # ------------------------------------------------------------------
    path(
        "<int:pg_pk>/rooms/create/",
        views.RoomCreateView.as_view(),
        name="room_create",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/",
        views.RoomDetailView.as_view(),
        name="room_detail",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/edit/",
        views.RoomUpdateView.as_view(),
        name="room_edit",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/delete/",
        views.RoomDeleteView.as_view(),
        name="room_delete",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/images/",
        views.RoomImageManageView.as_view(),
        name="room_images",
    ),
    # ------------------------------------------------------------------
    # Bed
    # ------------------------------------------------------------------
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/beds/create/",
        views.BedCreateView.as_view(),
        name="bed_create",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/beds/<int:bed_pk>/edit/",
        views.BedUpdateView.as_view(),
        name="bed_edit",
    ),
    path(
        "<int:pg_pk>/rooms/<int:room_pk>/beds/<int:bed_pk>/delete/",
        views.BedDeleteView.as_view(),
        name="bed_delete",
    ),
]
