"""
ModelForms for PG, Room, and Bed management.

These forms are used by owner-facing CRUD views.
Validation enforces domain rules (capacity, uniqueness, positive values).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.properties.services import validate_bed_capacity

if TYPE_CHECKING:
    pass


class PGForm(forms.ModelForm):
    """Create / update a PG property."""

    class Meta:
        model = PG
        fields = [
            "name",
            "description",
            "address",
            "city",
            "rent_per_month",
            "amenities",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "rent_per_month": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "amenities": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "e.g. Wi-Fi, Laundry, Parking"}),
        }

    def clean_rent_per_month(self):
        value = self.cleaned_data.get("rent_per_month")
        if value is not None and value <= 0:
            raise ValidationError(_("Rent must be a positive amount."))
        return value


class RoomForm(forms.ModelForm):
    """Create / update a room within a PG."""

    class Meta:
        model = Room
        fields = [
            "room_number",
            "room_type",
            "capacity",
            "rent",
            "description",
        ]
        widgets = {
            "room_number": forms.TextInput(attrs={"class": "form-control"}),
            "room_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Single, Double, Dormitory"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "rent": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean_capacity(self):
        value = self.cleaned_data.get("capacity")
        if value is not None and value < 1:
            raise ValidationError(_("Capacity must be at least 1."))
        return value

    def clean_rent(self):
        value = self.cleaned_data.get("rent")
        if value is not None and value <= 0:
            raise ValidationError(_("Rent must be a positive amount."))
        return value


class BedForm(forms.ModelForm):
    """Create / update a bed within a room."""

    class Meta:
        model = Bed
        fields = [
            "label",
            "is_available",
        ]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": 'e.g. Bed A'}),
            "is_available": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, room=None, **kwargs):
        """
        Accept an optional *room* so that capacity validation
        can be performed on create.
        """
        self.room = room
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        # On create (no existing instance PK) enforce capacity limit.
        if self.room is not None and not self.instance.pk:
            validate_bed_capacity(self.room)
        return cleaned_data
