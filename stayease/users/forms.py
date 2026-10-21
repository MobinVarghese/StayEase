from allauth.account.forms import LoginForm as AllauthLoginForm
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


def validate_and_clean_phone_number(phone_raw: str) -> str:
    """
    Validates and cleans phone numbers:
    - Strips whitespace and hyphens
    - Allows optional +91 or leading 0 prefix, normalizing to 10 digits
    - Ensures exactly 10 digits and strictly numeric
    - Mandatory / required field
    """
    phone = (phone_raw or "").strip()
    if not phone:
        raise forms.ValidationError(_("Phone number is required."))

    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:].strip()
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:].strip()
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:].strip()

    if not cleaned.isdigit():
        raise forms.ValidationError(_("Phone number must contain only numbers."))

    if len(cleaned) > 10:
        raise forms.ValidationError(_("Phone number cannot be more than 10 digits."))

    if len(cleaned) < 10:
        raise forms.ValidationError(_("Phone number must be at least 10 digits."))

    return cleaned


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """

    first_name = forms.CharField(
        max_length=150,
        label=_("First Name"),
        widget=forms.TextInput(attrs={"placeholder": _("First name")}),
    )
    last_name = forms.CharField(
        max_length=150,
        label=_("Last Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Last name")}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label=_("Phone Number"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("10-digit mobile number"),
                "maxlength": "10",
                "pattern": r"[0-9]{10}",
                "inputmode": "numeric",
            }
        ),
        help_text=_("10-digit contact phone number."),
        error_messages={
            "required": _("Phone number is required."),
        },
    )
    role = forms.ChoiceField(
        choices=SIGNUP_ROLE_CHOICES,
        initial=UserRole.TENANT,
        widget=forms.RadioSelect,
        label=_("I am a"),
    )

    def clean_phone_number(self):
        return validate_and_clean_phone_number(self.cleaned_data.get("phone_number", ""))

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone_number = self.cleaned_data["phone_number"]
        user.role = self.cleaned_data["role"]
        user.save(update_fields=["first_name", "last_name", "phone_number", "role"])
        return user


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """

    first_name = forms.CharField(
        max_length=150,
        label=_("First Name"),
        widget=forms.TextInput(attrs={"placeholder": _("First name")}),
    )
    last_name = forms.CharField(
        max_length=150,
        label=_("Last Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Last name")}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label=_("Phone Number"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("10-digit mobile number"),
                "maxlength": "10",
                "pattern": r"[0-9]{10}",
                "inputmode": "numeric",
            }
        ),
        help_text=_("10-digit contact phone number."),
        error_messages={
            "required": _("Phone number is required."),
        },
    )
    role = forms.ChoiceField(
        choices=SIGNUP_ROLE_CHOICES,
        initial=UserRole.TENANT,
        widget=forms.RadioSelect,
        label=_("I am a"),
    )

    def clean_phone_number(self):
        return validate_and_clean_phone_number(self.cleaned_data.get("phone_number", ""))

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone_number = self.cleaned_data["phone_number"]
        user.role = self.cleaned_data["role"]
        user.save(update_fields=["first_name", "last_name", "phone_number", "role"])
        return user


class UserProfileForm(forms.ModelForm):
    """
    Form for authenticated users to view and update their profile details:
    First name, Last name, Email address, and Phone number.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        label=_("First name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("First name")}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label=_("Last name"),
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Last name")}),
    )
    email = forms.EmailField(
        required=True,
        label=_("Email address"),
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": _("name@example.com")}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label=_("Phone number"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("10-digit mobile number"),
                "maxlength": "10",
                "pattern": r"[0-9]{10}",
                "inputmode": "numeric",
            },
        ),
        help_text=_("10-digit contact phone number."),
        error_messages={
            "required": _("Phone number is required."),
        },
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number"]

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError(_("Email address is required."))
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("This email address is already in use."))
        return email

    def clean_phone_number(self):
        return validate_and_clean_phone_number(self.cleaned_data.get("phone_number", ""))


class ForgotPasswordRequestForm(forms.Form):
    """
    Form for users to request an administrator-mediated password reset.
    """

    email = forms.EmailField(
        label=_("Email address"),
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": _("name@example.com"),
                "autocomplete": "email",
            },
        ),
    )
    reason = forms.CharField(
        label=_("Reason (optional)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": _("Optional: describe why you need an administrator password reset"),
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matched_user: User | None = None

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError(_("Please enter your registered email address."))

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise forms.ValidationError(
                _("No account found with this email address. Please check and try again."),
            )

        if not user.is_active:
            raise forms.ValidationError(
                _("This account is currently inactive. Please contact support."),
            )

        from .models import PasswordResetRequest
        from .models import ResetRequestStatus

        if PasswordResetRequest.objects.filter(
            user=user,
            status=ResetRequestStatus.PENDING,
        ).exists():
            raise forms.ValidationError(
                _(
                    "A password reset request is already pending review for this account. "
                    "Please wait for an administrator to process it."
                ),
            )

        self.matched_user = user
        return email


class UserChangePasswordForm(admin_forms.PasswordChangeForm):
    """
    Change-password form for authenticated users with styled Bootstrap 5 widgets.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class UserLoginForm(AllauthLoginForm):
    """
    Custom login form allowing users to sign in using either their email
    or username (such as 'admin').
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"] = forms.CharField(
            label=_("Email or Username"),
            widget=forms.TextInput(
                attrs={
                    "placeholder": _("Enter your email or username"),
                    "autocomplete": "username",
                }
            ),
        )

    def user_credentials(self) -> dict:
        credentials = super().user_credentials()
        login_val = credentials.get("email") or credentials.get("username")
        if login_val and login_val.strip().lower() == "admin":
            admin_user = User.objects.filter(
                email__in=["admin", "admin@stayease.com", "admin@admin.com"],
            ).first()
            if admin_user:
                credentials["email"] = admin_user.email
        return credentials



