from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import PasswordResetRequest
from .models import User

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number", "role")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "first_name", "last_name", "phone_number", "role", "is_superuser"]
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    ordering = ["id"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "email",
        "status",
        "created_at",
        "processed_by",
        "processed_at",
        "new_password",
    ]
    list_filter = ["status", "created_at", "processed_at"]
    search_fields = ["user__email", "email", "user__first_name", "user__last_name", "reason"]
    readonly_fields = ["created_at", "processed_at", "processed_by", "new_password"]
    ordering = ["-created_at"]
    actions = ["approve_selected_requests", "reject_selected_requests"]

    @admin.action(description=_("Approve selected reset requests (generate temp password)"))
    def approve_selected_requests(self, request, queryset):
        from django.utils import timezone
        from .models import ResetRequestStatus
        from .views import generate_temporary_password

        approved_count = 0
        for req in queryset:
            if req.status != ResetRequestStatus.PENDING:
                self.message_user(
                    request,
                    _(f"Request #{req.id} for {req.user.email} is not pending ({req.status}) — skipped."),
                    level="warning",
                )
                continue

            temp_pass = generate_temporary_password()
            req.user.set_password(temp_pass)
            req.user.save(update_fields=["password"])

            req.status = ResetRequestStatus.APPROVED
            req.processed_by = request.user
            req.processed_at = timezone.now()
            req.new_password = temp_pass
            req.save()

            approved_count += 1
            self.message_user(
                request,
                _(f"Approved reset for {req.user.email}. Temporary password: {temp_pass}"),
                level="success",
            )

        if approved_count:
            self.message_user(
                request,
                _(f"Successfully approved {approved_count} password reset request(s)."),
                level="info",
            )

    @admin.action(description=_("Reject selected reset requests"))
    def reject_selected_requests(self, request, queryset):
        from django.utils import timezone
        from .models import ResetRequestStatus

        rejected_count = 0
        for req in queryset:
            if req.status != ResetRequestStatus.PENDING:
                self.message_user(
                    request,
                    _(f"Request #{req.id} for {req.user.email} is not pending ({req.status}) — skipped."),
                    level="warning",
                )
                continue

            req.status = ResetRequestStatus.REJECTED
            req.processed_by = request.user
            req.processed_at = timezone.now()
            req.save()
            rejected_count += 1

        self.message_user(
            request,
            _(f"Rejected {rejected_count} password reset request(s)."),
            level="info",
        )

