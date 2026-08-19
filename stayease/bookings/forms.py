"""
Booking forms.

Kept minimal — the heavy lifting (validation, concurrency checks) is
handled by ``services.py``.  The form captures the tenant's intent;
the service validates and executes it.
"""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class BookingRequestForm(forms.Form):
    """
    A simple confirmation form for a tenant booking a specific bed.

    The bed is identified by the URL (``bed_pk``), not by a form field
    that could be tampered with.  This form exists mainly to provide
    CSRF protection and a clean POST submission.
    """

    confirm = forms.BooleanField(
        required=True,
        widget=forms.HiddenInput,
        initial=True,
        label=_("Confirm booking request"),
    )
