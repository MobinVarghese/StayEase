"""
Owner-facing CRUD views for PG, Room, and Bed management.

Every view enforces:
  1. Authentication (via LoginRequiredMixin inherited through OwnerRequiredMixin)
  2. Role check (only OWNER role)
  3. Ownership verification (owner can only manage their own properties)

The ownership chain is:  Owner → PG → Room → Bed
Nested resources always verify the full chain back to the authenticated owner.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from stayease.properties.forms import BedForm
from stayease.properties.forms import PGForm
from stayease.properties.forms import RoomForm
from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.properties.services import can_hard_delete_bed
from stayease.properties.services import can_hard_delete_pg
from stayease.properties.services import can_hard_delete_room
from stayease.users.mixins import OwnerRequiredMixin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_owner_pg(request, pg_pk):
    """Return PG owned by the current user or raise 403."""
    pg = get_object_or_404(PG, pk=pg_pk)
    if pg.owner_id != request.user.pk:
        raise PermissionDenied(_("You do not have permission to manage this property."))
    return pg


def _get_owner_room(request, pg_pk, room_pk):
    """Return (pg, room) after verifying the full ownership chain."""
    pg = _get_owner_pg(request, pg_pk)
    room = get_object_or_404(Room, pk=room_pk, pg=pg)
    return pg, room


def _get_owner_bed(request, pg_pk, room_pk, bed_pk):
    """Return (pg, room, bed) after verifying the full ownership chain."""
    pg, room = _get_owner_room(request, pg_pk, room_pk)
    bed = get_object_or_404(Bed, pk=bed_pk, room=room)
    return pg, room, bed


# ===========================================================================
# PG Views
# ===========================================================================


class PGListView(OwnerRequiredMixin, ListView):
    """List all PGs owned by the authenticated owner."""

    model = PG
    template_name = "properties/pg_list.html"
    context_object_name = "pgs"
    paginate_by = 12

    def get_queryset(self):
        return PG.objects.filter(owner=self.request.user).order_by("-created_at")


class PGCreateView(OwnerRequiredMixin, CreateView):
    """Create a new PG property."""

    model = PG
    form_class = PGForm
    template_name = "properties/pg_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, _("PG created successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:pg_detail", kwargs={"pg_pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Create New PG")
        ctx["submit_label"] = _("Create PG")
        return ctx


class PGDetailView(OwnerRequiredMixin, DetailView):
    """Show PG details with its rooms and beds hierarchy."""

    model = PG
    template_name = "properties/pg_detail.html"
    context_object_name = "pg"
    pk_url_kwarg = "pg_pk"

    def get_object(self, queryset=None):
        pg = super().get_object(queryset)
        if pg.owner_id != self.request.user.pk:
            raise PermissionDenied(_("You do not have permission to view this property."))
        return pg

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rooms"] = (
            self.object.rooms
            .filter(is_active=True)
            .prefetch_related("beds")
            .order_by("room_number")
        )
        ctx["can_hard_delete"] = can_hard_delete_pg(self.object)
        return ctx


class PGUpdateView(OwnerRequiredMixin, UpdateView):
    """Edit an existing PG property."""

    model = PG
    form_class = PGForm
    template_name = "properties/pg_form.html"
    pk_url_kwarg = "pg_pk"

    def get_object(self, queryset=None):
        pg = super().get_object(queryset)
        if pg.owner_id != self.request.user.pk:
            raise PermissionDenied(_("You do not have permission to edit this property."))
        return pg

    def form_valid(self, form):
        messages.success(self.request, _("PG updated successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:pg_detail", kwargs={"pg_pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Edit PG")
        ctx["submit_label"] = _("Save Changes")
        ctx["pg"] = self.object
        return ctx


class PGDeleteView(OwnerRequiredMixin, DeleteView):
    """
    Deactivate or hard-delete a PG.

    Business rule: If bookings exist for any bed in this PG, the PG
    is deactivated (is_active=False). Otherwise it is permanently deleted.
    """

    model = PG
    template_name = "properties/pg_confirm_delete.html"
    context_object_name = "pg"
    pk_url_kwarg = "pg_pk"

    def get_object(self, queryset=None):
        pg = super().get_object(queryset)
        if pg.owner_id != self.request.user.pk:
            raise PermissionDenied(_("You do not have permission to delete this property."))
        return pg

    def form_valid(self, request, *args, **kwargs):
        pg = self.get_object()
        if can_hard_delete_pg(pg):
            pg.delete()
            messages.success(request, _("PG \"%(name)s\" has been permanently deleted.") % {"name": pg.name})
        else:
            pg.is_active = False
            pg.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                _("PG \"%(name)s\" has been deactivated (booking history preserved).") % {"name": pg.name},
            )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("properties:pg_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_hard_delete"] = can_hard_delete_pg(self.object)
        return ctx


# ===========================================================================
# Room Views
# ===========================================================================


class RoomCreateView(OwnerRequiredMixin, CreateView):
    """Add a room to a PG."""

    model = Room
    form_class = RoomForm
    template_name = "properties/room_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.pg = _get_owner_pg(request, self.kwargs["pg_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.pg = self.pg
        messages.success(self.request, _("Room added successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:room_detail", kwargs={
            "pg_pk": self.pg.pk,
            "room_pk": self.object.pk,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["page_title"] = _("Add Room")
        ctx["submit_label"] = _("Add Room")
        return ctx


class RoomDetailView(OwnerRequiredMixin, DetailView):
    """Show room details with its beds."""

    model = Room
    template_name = "properties/room_detail.html"
    context_object_name = "room"
    pk_url_kwarg = "room_pk"

    def dispatch(self, request, *args, **kwargs):
        self.pg = _get_owner_pg(request, self.kwargs["pg_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Room.objects.filter(pg=self.pg)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["beds"] = self.object.beds.order_by("label")
        ctx["can_hard_delete"] = can_hard_delete_room(self.object)
        ctx["active_bed_count"] = self.object.beds.filter(is_active=True).count()
        return ctx


class RoomUpdateView(OwnerRequiredMixin, UpdateView):
    """Edit a room."""

    model = Room
    form_class = RoomForm
    template_name = "properties/room_form.html"
    pk_url_kwarg = "room_pk"

    def dispatch(self, request, *args, **kwargs):
        self.pg = _get_owner_pg(request, self.kwargs["pg_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Room.objects.filter(pg=self.pg)

    def form_valid(self, form):
        messages.success(self.request, _("Room updated successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:room_detail", kwargs={
            "pg_pk": self.pg.pk,
            "room_pk": self.object.pk,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["page_title"] = _("Edit Room")
        ctx["submit_label"] = _("Save Changes")
        return ctx


class RoomDeleteView(OwnerRequiredMixin, DeleteView):
    """Deactivate or hard-delete a room."""

    model = Room
    template_name = "properties/room_confirm_delete.html"
    context_object_name = "room"
    pk_url_kwarg = "room_pk"

    def dispatch(self, request, *args, **kwargs):
        self.pg = _get_owner_pg(request, self.kwargs["pg_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Room.objects.filter(pg=self.pg)

    def form_valid(self, request, *args, **kwargs):
        room = self.get_object()
        if can_hard_delete_room(room):
            room.delete()
            messages.success(request, _("Room \"%(num)s\" has been permanently deleted.") % {"num": room.room_number})
        else:
            room.is_active = False
            room.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                _("Room \"%(num)s\" has been deactivated (booking history preserved).") % {"num": room.room_number},
            )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("properties:pg_detail", kwargs={"pg_pk": self.pg.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["can_hard_delete"] = can_hard_delete_room(self.object)
        return ctx


# ===========================================================================
# Bed Views
# ===========================================================================


class BedCreateView(OwnerRequiredMixin, CreateView):
    """Add a bed to a room (subject to capacity check)."""

    model = Bed
    form_class = BedForm
    template_name = "properties/bed_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.pg, self.room = _get_owner_room(
            request, self.kwargs["pg_pk"], self.kwargs["room_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["room"] = self.room
        return kwargs

    def form_valid(self, form):
        form.instance.room = self.room
        messages.success(self.request, _("Bed added successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:room_detail", kwargs={
            "pg_pk": self.pg.pk,
            "room_pk": self.room.pk,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["room"] = self.room
        ctx["page_title"] = _("Add Bed")
        ctx["submit_label"] = _("Add Bed")
        return ctx


class BedUpdateView(OwnerRequiredMixin, UpdateView):
    """Edit a bed (label / availability)."""

    model = Bed
    form_class = BedForm
    template_name = "properties/bed_form.html"
    pk_url_kwarg = "bed_pk"

    def dispatch(self, request, *args, **kwargs):
        self.pg, self.room, _ = _get_owner_bed(
            request, self.kwargs["pg_pk"], self.kwargs["room_pk"], self.kwargs["bed_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Bed.objects.filter(room=self.room)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["room"] = self.room
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Bed updated successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("properties:room_detail", kwargs={
            "pg_pk": self.pg.pk,
            "room_pk": self.room.pk,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["room"] = self.room
        ctx["page_title"] = _("Edit Bed")
        ctx["submit_label"] = _("Save Changes")
        return ctx


class BedDeleteView(OwnerRequiredMixin, DeleteView):
    """Deactivate or hard-delete a bed."""

    model = Bed
    template_name = "properties/bed_confirm_delete.html"
    context_object_name = "bed"
    pk_url_kwarg = "bed_pk"

    def dispatch(self, request, *args, **kwargs):
        self.pg, self.room, _ = _get_owner_bed(
            request, self.kwargs["pg_pk"], self.kwargs["room_pk"], self.kwargs["bed_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Bed.objects.filter(room=self.room)

    def form_valid(self, request, *args, **kwargs):
        bed = self.get_object()
        if can_hard_delete_bed(bed):
            bed.delete()
            messages.success(request, _("Bed \"%(label)s\" has been permanently deleted.") % {"label": bed.label})
        else:
            bed.is_active = False
            bed.save(update_fields=["is_active", "updated_at"])
            messages.success(
                request,
                _("Bed \"%(label)s\" has been deactivated (booking history preserved).") % {"label": bed.label},
            )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("properties:room_detail", kwargs={
            "pg_pk": self.pg.pk,
            "room_pk": self.room.pk,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pg"] = self.pg
        ctx["room"] = self.room
        ctx["can_hard_delete"] = can_hard_delete_bed(self.object)
        return ctx
