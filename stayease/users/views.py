from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from stayease.bookings.models import ACTIVE_BOOKING_STATUSES
from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.notifications.services import get_unread_count
from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.users.decorators import admin_required
from stayease.users.forms import ForgotPasswordRequestForm
from stayease.users.forms import UserChangePasswordForm
from stayease.users.forms import UserProfileForm
from stayease.users.mixins import AdminRequiredMixin
from stayease.users.mixins import OwnerRequiredMixin
from stayease.users.mixins import TenantRequiredMixin
from stayease.users.models import PasswordResetRequest
from stayease.users.models import ResetRequestStatus
from stayease.users.models import User
from stayease.users.models import UserRole

if TYPE_CHECKING:
    from django.db.models import QuerySet


class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Profile page allowing authenticated users to view and update their profile:
    First name, Last name, Email address, and Phone number.
    Cross-user editing via URL tampering (e.g. /users/2/ by user 1) is blocked with 403 Forbidden.
    """

    model = User
    form_class = UserProfileForm
    template_name = "users/user_detail.html"
    success_message = _("Your profile has been updated successfully.")

    def get_object(self, queryset: QuerySet | None = None) -> User:
        user = self.request.user
        assert isinstance(user, User)

        pk = self.kwargs.get("pk")
        if pk is not None and str(pk) != str(user.pk):
            raise PermissionDenied(_("You do not have permission to view or edit this profile."))

        return user

    def get_success_url(self) -> str:
        pk = self.kwargs.get("pk")
        if pk is not None:
            return reverse("users:detail", kwargs={"pk": pk})
        return reverse("users:profile")

    def form_valid(self, form: UserProfileForm):
        response = super().form_valid(form)
        user = self.object
        assert isinstance(user, User)

        # Synchronize email with allauth's EmailAddress table
        try:
            from allauth.account.models import EmailAddress

            EmailAddress.objects.filter(user=user).exclude(email__iexact=user.email).delete()
            email_record, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": True},
            )
            if not email_record.primary:
                email_record.set_as_primary()
        except Exception:
            pass

        return response


user_profile_view = UserProfileView.as_view()
user_detail_view = user_profile_view
user_update_view = user_profile_view
UserDetailView = UserProfileView
UserUpdateView = UserProfileView



class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        user = self.request.user
        assert isinstance(user, User)
        # Role-aware routing.
        if user.is_owner:
            return reverse("users:dashboard_owner")
        if user.is_admin_user:
            return reverse("users:dashboard_admin")
        # Tenant/default is directed to the tenant dashboard
        return reverse("users:dashboard_tenant")


user_redirect_view = UserRedirectView.as_view()


class OwnerDashboardView(OwnerRequiredMixin, TemplateView):
    template_name = "pages/dashboard_owner.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        assert isinstance(user, User)

        # 1. Properties, Rooms, and Beds owned by this owner
        owner_pgs = PG.objects.filter(owner=user, is_active=True)
        total_properties_count = owner_pgs.count()
        total_rooms_count = Room.objects.filter(
            pg__owner=user,
            pg__is_active=True,
            is_active=True,
        ).count()
        total_beds_count = Bed.objects.filter(
            room__pg__owner=user,
            room__pg__is_active=True,
            room__is_active=True,
            is_active=True,
        ).count()
        available_beds_count = (
            Bed.objects.filter(
                room__pg__owner=user,
                room__pg__is_active=True,
                room__is_active=True,
                is_active=True,
                is_available=True,
            )
            .exclude(bookings__status__in=ACTIVE_BOOKING_STATUSES)
            .count()
        )

        # 2. Booking requests for this owner's properties
        owner_bookings = Booking.objects.filter(bed__room__pg__owner=user)
        booking_stats = {
            "total": owner_bookings.count(),
            "pending": owner_bookings.filter(status=BookingStatus.PENDING).count(),
            "approved": owner_bookings.filter(
                status__in=[BookingStatus.APPROVED, BookingStatus.PAYMENT_PENDING],
            ).count(),
            "confirmed": owner_bookings.filter(status=BookingStatus.CONFIRMED).count(),
            "rejected": owner_bookings.filter(status=BookingStatus.REJECTED).count(),
        }
        latest_booking_request = (
            owner_bookings.select_related("tenant", "bed__room__pg")
            .order_by("-created_at")
            .first()
        )

        # 3. Owner notifications
        unread_notifications = get_unread_count(user)

        # 4. Detailed rooms for availability/occupancy overview
        owner_rooms = (
            Room.objects.filter(
                pg__owner=user,
                pg__is_active=True,
                is_active=True,
            )
            .select_related("pg")
            .prefetch_related("beds", "beds__bookings")
            .order_by("pg__name", "room_number")
        )

        context.update(
            {
                "total_properties_count": total_properties_count,
                "total_rooms_count": total_rooms_count,
                "total_beds_count": total_beds_count,
                "available_beds_count": available_beds_count,
                "booking_stats": booking_stats,
                "latest_booking_request": latest_booking_request,
                "unread_notification_count": unread_notifications,
                "owner_rooms": owner_rooms,
            },
        )
        return context


owner_dashboard_view = OwnerDashboardView.as_view()


class TenantDashboardView(TenantRequiredMixin, TemplateView):
    template_name = "pages/dashboard_tenant.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        assert isinstance(user, User)

        # 1. Available PGs & Beds
        total_active_pg_count = PG.objects.filter(is_active=True).count()
        available_bed_count = Bed.objects.filter(
            is_active=True,
            is_available=True,
            room__is_active=True,
            room__pg__is_active=True,
        ).exclude(
            bookings__status__in=ACTIVE_BOOKING_STATUSES,
        ).count()

        # 2. Bookings for current tenant
        user_bookings = Booking.objects.filter(tenant=user)
        booking_stats = {
            "total": user_bookings.count(),
            "pending": user_bookings.filter(status=BookingStatus.PENDING).count(),
            "approved": user_bookings.filter(
                status__in=[BookingStatus.APPROVED, BookingStatus.PAYMENT_PENDING],
            ).count(),
            "confirmed": user_bookings.filter(status=BookingStatus.CONFIRMED).count(),
            "rejected": user_bookings.filter(status=BookingStatus.REJECTED).count(),
        }
        latest_booking = (
            user_bookings.select_related("bed__room__pg")
            .order_by("-created_at")
            .first()
        )

        # 3. Notification stats
        unread_notifications = get_unread_count(user)

        context.update(
            {
                "total_active_pg_count": total_active_pg_count,
                "available_bed_count": available_bed_count,
                "booking_stats": booking_stats,
                "latest_booking": latest_booking,
                "unread_notification_count": unread_notifications,
            },
        )
        return context


tenant_dashboard_view = TenantDashboardView.as_view()


# ---------------------------------------------------------------------------
# Administrator-Mediated Password Reset Workflow Views
# ---------------------------------------------------------------------------


def generate_temporary_password(length: int = 14) -> str:
    """
    Generate a cryptographically secure random password containing letters,
    digits, and symbols to satisfy standard Django password validation.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*" for c in pwd)
        ):
            return pwd


class ForgotPasswordRequestView(FormView):
    """
    Public view allowing users who cannot remember their password to submit
    a reset request for administrative review.
    """

    template_name = "accounts/forgot_password.html"
    form_class = ForgotPasswordRequestForm

    def get_success_url(self) -> str:
        return reverse("users:forgot_password_done")

    def form_valid(self, form: ForgotPasswordRequestForm):
        user = form.matched_user
        if not user:
            user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()

        assert user is not None

        PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            reason=form.cleaned_data.get("reason", "") or "",
            status=ResetRequestStatus.PENDING,
        )
        messages.success(
            self.request,
            _(
                "Your password reset request has been submitted for administrative review. "
                "An administrator will review your request."
            ),
        )
        return super().form_valid(form)


forgot_password_request_view = ForgotPasswordRequestView.as_view()
forgot_password = forgot_password_request_view


class ForgotPasswordSuccessView(TemplateView):
    """
    Confirmation screen shown after submitting a password reset request.
    """

    template_name = "accounts/forgot_password_done.html"


forgot_password_success_view = ForgotPasswordSuccessView.as_view()
forgot_password_done = forgot_password_success_view


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """
    Administrator dashboard showing platform summary metrics,
    per-PG booking activity report with optional date filtering,
    and the Password Reset Requests management table with approve/reject actions.
    """

    template_name = "pages/dashboard_admin.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 1. Summary Cards Metrics
        total_pgs = PG.objects.count()
        total_rooms = Room.objects.count()
        total_users = User.objects.count()
        total_bookings = Booking.objects.count()
        confirmed_bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED).count()
        active_bookings = Booking.objects.filter(status__in=ACTIVE_BOOKING_STATUSES).count()
        pending_bookings = Booking.objects.filter(status=BookingStatus.PENDING).count()
        rejected_bookings = Booking.objects.filter(status=BookingStatus.REJECTED).count()

        # 2. PG Booking Report with Optional Date Filter
        period = self.request.GET.get("period", "all")
        now = timezone.now()
        booking_filter = Q()
        report_booking_qs = Booking.objects.all()

        if period == "month":
            start_of_period = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            booking_filter = Q(rooms__beds__bookings__created_at__gte=start_of_period)
            report_booking_qs = report_booking_qs.filter(created_at__gte=start_of_period)
        elif period == "year":
            start_of_period = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            booking_filter = Q(rooms__beds__bookings__created_at__gte=start_of_period)
            report_booking_qs = report_booking_qs.filter(created_at__gte=start_of_period)
        else:
            period = "all"

        # Aggregated totals for the selected period
        period_total_bookings = report_booking_qs.count()
        period_confirmed_bookings = report_booking_qs.filter(status=BookingStatus.CONFIRMED).count()
        period_pending_bookings = report_booking_qs.filter(status=BookingStatus.PENDING).count()
        period_rejected_bookings = report_booking_qs.filter(status=BookingStatus.REJECTED).count()

        # Query all PGs with booking activity counts (ordered by total_bookings DESC, name ASC)
        pg_booking_report = (
            PG.objects.select_related("owner")
            .annotate(
                room_count=Count("rooms", distinct=True),
                total_bookings=Count(
                    "rooms__beds__bookings",
                    filter=booking_filter & Q(rooms__beds__bookings__isnull=False),
                    distinct=True,
                ),
                confirmed_bookings=Count(
                    "rooms__beds__bookings",
                    filter=booking_filter & Q(rooms__beds__bookings__status=BookingStatus.CONFIRMED),
                    distinct=True,
                ),
                pending_bookings=Count(
                    "rooms__beds__bookings",
                    filter=booking_filter & Q(rooms__beds__bookings__status=BookingStatus.PENDING),
                    distinct=True,
                ),
                rejected_bookings=Count(
                    "rooms__beds__bookings",
                    filter=booking_filter & Q(rooms__beds__bookings__status=BookingStatus.REJECTED),
                    distinct=True,
                ),
            )
            .order_by("-total_bookings", "name")
        )

        # 3. Password Reset Requests
        requests_qs = (
            PasswordResetRequest.objects.select_related("user", "processed_by")
            .order_by("-created_at")
        )

        context.update(
            {
                # Summary Cards
                "total_pgs_count": total_pgs,
                "total_rooms_count": total_rooms,
                "total_users_count": total_users,
                "total_bookings_count": total_bookings,
                "confirmed_bookings_count": confirmed_bookings,
                "active_bookings_count": active_bookings,
                "pending_bookings_count": pending_bookings,
                "rejected_bookings_count": rejected_bookings,
                # PG Booking Report
                "pg_booking_report": pg_booking_report,
                "selected_period": period,
                "period_total_bookings": period_total_bookings,
                "period_confirmed_bookings": period_confirmed_bookings,
                "period_pending_bookings": period_pending_bookings,
                "period_rejected_bookings": period_rejected_bookings,
                # Password Reset Requests
                "reset_requests": requests_qs,
                "pending_requests_count": requests_qs.filter(
                    status=ResetRequestStatus.PENDING,
                ).count(),
                "approved_requests_count": requests_qs.filter(
                    status=ResetRequestStatus.APPROVED,
                ).count(),
                "rejected_requests_count": requests_qs.filter(
                    status=ResetRequestStatus.REJECTED,
                ).count(),
            },
        )
        return context


admin_dashboard_view = AdminDashboardView.as_view()


@require_POST
@admin_required
def approve_password_reset(request, request_id: int):
    """
    POST /admin/reset/<request_id>/approve/
    Approves a pending password reset request, generates a secure temporary
    password, sets it on the user using user.set_password(), and saves it in
    new_password for admin communication out-of-band.
    """
    reset_request = get_object_or_404(PasswordResetRequest, id=request_id)

    # State machine guard: only pending requests can be approved
    if reset_request.status != ResetRequestStatus.PENDING:
        messages.error(
            request,
            _("This request cannot be approved because it is not pending review."),
        )
        return redirect(reverse("users:dashboard_admin"))

    temp_password = generate_temporary_password()
    user = reset_request.user
    user.set_password(temp_password)
    user.save(update_fields=["password"])

    reset_request.status = ResetRequestStatus.APPROVED
    reset_request.processed_by = request.user
    reset_request.processed_at = timezone.now()
    reset_request.new_password = temp_password
    admin_notes = request.POST.get("admin_notes", "").strip()
    if admin_notes:
        reset_request.admin_notes = admin_notes
    reset_request.save()

    messages.success(
        request,
        _(
            f"Password reset request for {user.email} was APPROVED. "
            f"Temporary password: {temp_password}"
        ),
    )
    return redirect(reverse("users:dashboard_admin"))


@require_POST
@admin_required
def reject_password_reset(request, request_id: int):
    """
    POST /admin/reset/<request_id>/reject/
    Rejects a pending password reset request without modifying the user's password.
    """
    reset_request = get_object_or_404(PasswordResetRequest, id=request_id)

    # State machine guard: only pending requests can be rejected
    if reset_request.status != ResetRequestStatus.PENDING:
        messages.error(
            request,
            _("This request cannot be rejected because it is not pending review."),
        )
        return redirect(reverse("users:dashboard_admin"))

    reset_request.status = ResetRequestStatus.REJECTED
    reset_request.processed_by = request.user
    reset_request.processed_at = timezone.now()
    admin_notes = request.POST.get("admin_notes", "").strip()
    if admin_notes:
        reset_request.admin_notes = admin_notes
    reset_request.save()

    messages.info(
        request,
        _(f"Password reset request for {reset_request.user.email} was REJECTED."),
    )
    return redirect(reverse("users:dashboard_admin"))


class UserChangePasswordView(LoginRequiredMixin, FormView):
    """
    Authenticated change-password view matching /profile/change-password/.
    Allows logged-in users (including those using a temporary password)
    to update their password securely.
    """

    template_name = "users/change_password.html"
    form_class = UserChangePasswordForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: UserChangePasswordForm):
        user = form.save()
        # Maintain session so the user is not logged out after password change
        update_session_auth_hash(self.request, user)
        messages.success(
            self.request,
            _("Your password has been changed successfully."),
        )
        return redirect(reverse("users:profile"))


change_password = UserChangePasswordView.as_view()
user_change_password_view = change_password


