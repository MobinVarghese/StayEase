from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _

from .models import User
from .models import UserRole

# Choices exposed at signup — ADMIN is never self-assigned.
SIGNUP_ROLE_CHOICES = [
    (UserRole.TENANT, _("Tenant — I'm looking for accommodation")),
    (UserRole.OWNER, _("Owner — I manage PG properties")),
]


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """

    role = forms.ChoiceField(
        choices=SIGNUP_ROLE_CHOICES,
        initial=UserRole.TENANT,
        widget=forms.RadioSelect,
        label=_("I am a"),
    )

    def save(self, request):
        user = super().save(request)
        user.role = self.cleaned_data["role"]
        user.save(update_fields=["role"])
        return user


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """

    role = forms.ChoiceField(
        choices=SIGNUP_ROLE_CHOICES,
        initial=UserRole.TENANT,
        widget=forms.RadioSelect,
        label=_("I am a"),
    )

    def save(self, request):
        user = super().save(request)
        user.role = self.cleaned_data["role"]
        user.save(update_fields=["role"])
        return user

