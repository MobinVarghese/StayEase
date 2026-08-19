"""
Discovery forms.

Search/filter form for PG listing — used in the discovery list view.
"""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class PGSearchForm(forms.Form):
    """
    Form for PG search and filtering on the discovery listing page.

    All fields are optional — an empty form returns all active PGs.
    """

    q = forms.CharField(
        required=False,
        label=_("Search"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Search by name, description, city, or amenities…"),
                "class": "form-control",
                "id": "id_search_q",
            },
        ),
    )
    city = forms.CharField(
        required=False,
        label=_("City"),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "id_filter_city",
            },
        ),
    )
    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        label=_("Min Price (₹/month)"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("Min"),
                "class": "form-control",
                "id": "id_filter_min_price",
            },
        ),
    )
    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        label=_("Max Price (₹/month)"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("Max"),
                "class": "form-control",
                "id": "id_filter_max_price",
            },
        ),
    )
    available_only = forms.BooleanField(
        required=False,
        label=_("Available beds only"),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "id": "id_filter_available_only",
            },
        ),
    )

    def __init__(self, *args, cities: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate city choices from the database.
        city_choices = [("", _("All Cities"))]
        if cities:
            city_choices += [(c, c) for c in cities]
        self.fields["city"].widget.choices = city_choices
