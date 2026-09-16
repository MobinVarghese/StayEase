from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
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
from stayease.users.forms import UserProfileForm
from stayease.users.mixins import OwnerRequiredMixin
from stayease.users.mixins import TenantRequiredMixin
from stayease.users.models import User

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
            return reverse("admin:index")
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

