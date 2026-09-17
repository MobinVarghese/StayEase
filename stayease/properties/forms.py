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
from stayease.properties.models import RoomImage
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
            "amenities",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "amenities": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "e.g. Wi-Fi, Laundry, Parking"}),
        }


class RoomForm(forms.ModelForm):
    """Create / update a room within a PG."""

    class Meta:
        model = Room
        fields = [
            "room_number",
            "room_type",
            "capacity",
            "description",
        ]
        widgets = {
            "room_number": forms.TextInput(attrs={"class": "form-control"}),
            "room_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Single, Double, Dormitory"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean_capacity(self):
        value = self.cleaned_data.get("capacity")
        if value is not None and value < 1:
            raise ValidationError(_("Capacity must be at least 1."))
        return value

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data

        room_type = cleaned_data.get("room_type")
        capacity = cleaned_data.get("capacity")

        if room_type and capacity is not None:
            rt = room_type.strip().lower()
            if rt == "single" and capacity != 1:
                self.add_error("capacity", _("A single room can only have 1 bed (capacity must be 1)."))
            elif rt == "double" and capacity != 2:
                self.add_error("capacity", _("A double room can only have 2 beds (capacity must be 2)."))

        if self.instance and self.instance.pk and room_type:
            rt = room_type.strip().lower()
            active_beds = self.instance.beds.filter(is_active=True).count()
            if rt == "single" and active_beds > 1:
                self.add_error(
                    "room_type",
                    _(
                        "Cannot set room type to Single because this room already has %(count)d active beds. A single room can only have 1 bed.",
                    )
                    % {"count": active_beds},
                )
            elif rt == "double" and active_beds > 2:
                self.add_error(
                    "room_type",
                    _(
                        "Cannot set room type to Double because this room already has %(count)d active beds. A double room can only have 2 beds.",
                    )
                    % {"count": active_beds},
                )

        return cleaned_data


class BedForm(forms.ModelForm):
    """Create / update a bed within a room."""

    class Meta:
        model = Bed
        fields = [
            "label",
            "rent_per_month",
            "is_available",
        ]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": 'e.g. Bed A, Bed 1'}),
            "rent_per_month": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01", "placeholder": "e.g. 7500.00"}),
            "is_available": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, room=None, **kwargs):
        """
        Accept an optional *room* so that capacity validation
        can be performed on create.
        """
        self.room = room
        super().__init__(*args, **kwargs)

    def clean_rent_per_month(self):
        value = self.cleaned_data.get("rent_per_month")
        if value is None or value <= 0:
            raise ValidationError(_("Rent must be a positive amount."))
        return value

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data

        room = self.room
        if room is None and self.instance and hasattr(self.instance, "room_id") and self.instance.room_id:
            room = self.instance.room

        is_active = cleaned_data.get("is_active", True)
        if room is not None and is_active:
            try:
                validate_bed_capacity(room, exclude_bed_pk=self.instance.pk)
            except ValidationError as exc:
                self.add_error(None, exc)

        return cleaned_data


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class RoomImageForm(forms.ModelForm):
    """Form for a single room image."""

    class Meta:
        model = RoomImage
        fields = ["image", "caption", "order"]
        widgets = {
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": _("e.g. Balcony view, Bed area")}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0", "style": "width: 90px;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].required = False
        self.fields["order"].initial = 0
        if self.instance and self.instance.pk:
            self.fields["image"].required = False
        else:
            self.fields["image"].required = False

    def has_changed(self) -> bool:
        # If this is a new form slot and no image was uploaded, treat as unchanged (empty slot)
        if not self.instance.pk and not self.files.get(self.add_prefix("image")):
            return False
        return super().has_changed()

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "size") and image.size > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError(_("Image file size cannot exceed 5 MB."))
        return image

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data is not None and cleaned_data.get("order") is None:
            cleaned_data["order"] = 0
        return cleaned_data


class BaseRoomImageFormSet(forms.BaseInlineFormSet):
    """
    Inline formset enforcing a maximum of 3 images per room across existing and new items.
    """

    default_error_messages = {
        "too_many_forms": _("You can upload a maximum of 3 photos per room."),
    }

    def clean(self):
        super().clean()
        total_images = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if self.can_delete and form.cleaned_data.get(forms.formsets.DELETION_FIELD_NAME, False):
                continue
            if form.instance.pk or form.cleaned_data.get("image"):
                total_images += 1

        if total_images > 3:
            raise ValidationError(_("You can upload a maximum of 3 photos per room."))


RoomImageFormSet = forms.inlineformset_factory(
    Room,
    RoomImage,
    form=RoomImageForm,
    formset=BaseRoomImageFormSet,
    fields=["image", "caption", "order"],
    extra=3,
    max_num=3,
    validate_max=True,
    can_delete=True,
)

