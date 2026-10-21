"""Module for all Form Tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.utils.translation import gettext_lazy as _

from stayease.users.forms import UserAdminCreationForm
from stayease.users.forms import UserProfileForm

if TYPE_CHECKING:
    from stayease.users.models import User

pytestmark = pytest.mark.django_db


class TestUserAdminCreationForm:
    """
    Test class for all tests related to the UserAdminCreationForm
    """

    def test_username_validation_error_msg(self, user: User):
        """
        Tests UserAdminCreation Form's unique validator functions correctly by testing:
            1) A new user with an existing username cannot be added.
            2) Only 1 error is raised by the UserCreation Form
            3) The desired error message is raised
        """

        # The user already exists,
        # hence cannot be created.
        form = UserAdminCreationForm(
            {
                "email": user.email,
                "password1": user.password,
                "password2": user.password,
            },
        )

        assert not form.is_valid()
        assert len(form.errors) == 1
        assert "email" in form.errors
        assert form.errors["email"][0] == _("This email has already been taken.")


class TestUserSignupFormPhoneValidation:
    """Tests for phone number validation in signup form."""

    def test_phone_number_more_than_10_digits_rejected(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "1234567890123",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "phone_number" in form.errors
        assert form.errors["phone_number"][0] == _("Phone number cannot be more than 10 digits.")

    def test_phone_number_less_than_10_digits_rejected(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "12345",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "phone_number" in form.errors
        assert form.errors["phone_number"][0] == _("Phone number must be at least 10 digits.")

    def test_phone_number_non_numeric_rejected(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "98765abcde",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "phone_number" in form.errors
        assert form.errors["phone_number"][0] == _("Phone number must contain only numbers.")

    def test_phone_number_10_digits_valid(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "9876543210",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["phone_number"] == "9876543210"

    def test_phone_number_with_country_code_normalized(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "+91 9876543210",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["phone_number"] == "9876543210"

    def test_phone_number_empty_is_rejected(self):
        from stayease.users.forms import UserSignupForm

        form = UserSignupForm(
            data={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone_number": "",
                "role": "TENANT",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "phone_number" in form.errors
        assert form.errors["phone_number"][0] == _("Phone number is required.")


class TestUserProfileForm:
    def test_valid_profile_form(self, user: User):
        form = UserProfileForm(
            instance=user,
            data={
                "first_name": "UpdatedFirst",
                "last_name": "UpdatedLast",
                "email": user.email,
                "phone_number": "+91 9123456780",
            },
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["phone_number"] == "9123456780"
        updated_user = form.save()
        assert updated_user.first_name == "UpdatedFirst"
        assert updated_user.last_name == "UpdatedLast"
        assert updated_user.phone_number == "9123456780"

    def test_duplicate_email_rejected(self, user: User):
        from stayease.users.tests.factories import UserFactory

        UserFactory.create(email="other@example.com")
        form = UserProfileForm(
            instance=user,
            data={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": "other@example.com",
                "phone_number": "9123456780",
            },
        )
        assert not form.is_valid()
        assert "email" in form.errors

    def test_invalid_phone_rejected(self, user: User):
        form = UserProfileForm(
            instance=user,
            data={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_number": "not-a-number",
            },
        )
        assert not form.is_valid()
        assert "phone_number" in form.errors



