"""
Tests for the Custom Admin Dashboard and PG Booking Activity Report.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestAdminDashboardAccess:
    """Test authorization rules for the Admin Dashboard."""

    def test_admin_can_access_dashboard(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        # Canonical users namespace route
        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 200
        assert "pages/dashboard_admin.html" in [t.name for t in response.templates]

        # Alias route /admin-dashboard/
        alias_response = client.get(reverse("admin_dashboard"))
        assert alias_response.status_code == 200

    def test_tenant_cannot_access_dashboard(self, client):
        tenant = UserFactory(role=UserRole.TENANT)
        client.force_login(tenant)

        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 403

        alias_response = client.get(reverse("admin_dashboard"))
        assert alias_response.status_code == 403

    def test_owner_cannot_access_dashboard(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        client.force_login(owner)

        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 403

        alias_response = client.get(reverse("admin_dashboard"))
        assert alias_response.status_code == 403

    def test_unauthenticated_user_redirected_to_login(self, client):
        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

        alias_response = client.get(reverse("admin_dashboard"))
        assert alias_response.status_code == 302
        assert "/accounts/login/" in alias_response.url


class TestAdminDashboardSummaryMetrics:
    """Test summary metric cards displayed on the Admin Dashboard."""

    def test_summary_metrics_values(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        # Setup properties, rooms, beds, and bookings
        pg1 = PGFactory()
        pg2 = PGFactory()
        room1 = RoomFactory(pg=pg1, room_type="Single", capacity=1)
        room2 = RoomFactory(pg=pg2, room_type="Single", capacity=1)
        bed1 = BedFactory(room=room1)
        bed2 = BedFactory(room=room2)

        tenant1 = UserFactory(role=UserRole.TENANT)
        tenant2 = UserFactory(role=UserRole.TENANT)

        # 1 confirmed, 1 pending, 1 rejected
        BookingFactory(bed=bed1, tenant=tenant1, status=BookingStatus.CONFIRMED)
        BookingFactory(bed=bed2, tenant=tenant2, status=BookingStatus.PENDING)
        # Rejected is terminal, so bed1 can also have a rejected booking
        BookingFactory(bed=bed1, tenant=tenant2, status=BookingStatus.REJECTED)

        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 200

        ctx = response.context
        assert ctx["total_pgs_count"] >= 2
        assert ctx["total_rooms_count"] >= 2
        assert ctx["total_bookings_count"] >= 3
        assert ctx["confirmed_bookings_count"] >= 1
        assert ctx["pending_bookings_count"] >= 1
        assert ctx["rejected_bookings_count"] >= 1


class TestPGBookingReport:
    """Test per-PG booking activity aggregation report."""

    def test_pg_booking_counts_and_zero_booking_display(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        # PG Alpha: 2 confirmed, 1 pending, 1 rejected
        pg_alpha = PGFactory(name="Alpha PG")
        room_a1 = RoomFactory(pg=pg_alpha, room_type="Single", capacity=1)
        room_a2 = RoomFactory(pg=pg_alpha, room_type="Single", capacity=1)
        room_a3 = RoomFactory(pg=pg_alpha, room_type="Single", capacity=1)
        bed_a1 = BedFactory(room=room_a1)
        bed_a2 = BedFactory(room=room_a2)
        bed_a3 = BedFactory(room=room_a3)
        BookingFactory(bed=bed_a1, status=BookingStatus.CONFIRMED)
        BookingFactory(bed=bed_a2, status=BookingStatus.CONFIRMED)
        BookingFactory(bed=bed_a3, status=BookingStatus.PENDING)
        BookingFactory(bed=bed_a1, status=BookingStatus.REJECTED)

        # PG Beta: 1 confirmed
        pg_beta = PGFactory(name="Beta PG")
        room_b = RoomFactory(pg=pg_beta, room_type="Single", capacity=1)
        bed_b = BedFactory(room=room_b)
        BookingFactory(bed=bed_b, status=BookingStatus.CONFIRMED)

        # PG Gamma: 0 bookings
        pg_gamma = PGFactory(name="Gamma PG")
        room_c = RoomFactory(pg=pg_gamma, room_type="Single", capacity=1)
        BedFactory(room=room_c)

        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 200

        report_map = {pg.id: pg for pg in response.context["pg_booking_report"]}

        # Alpha PG
        assert report_map[pg_alpha.id].total_bookings == 4
        assert report_map[pg_alpha.id].confirmed_bookings == 2
        assert report_map[pg_alpha.id].pending_bookings == 1
        assert report_map[pg_alpha.id].rejected_bookings == 1

        # Beta PG
        assert report_map[pg_beta.id].total_bookings == 1
        assert report_map[pg_beta.id].confirmed_bookings == 1
        assert report_map[pg_beta.id].pending_bookings == 0
        assert report_map[pg_beta.id].rejected_bookings == 0

        # Gamma PG (zero bookings)
        assert report_map[pg_gamma.id].total_bookings == 0
        assert report_map[pg_gamma.id].confirmed_bookings == 0
        assert report_map[pg_gamma.id].pending_bookings == 0
        assert report_map[pg_gamma.id].rejected_bookings == 0

    def test_pg_booking_report_ordering(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        pg_low = PGFactory(name="Low Activity PG")
        pg_high = PGFactory(name="High Activity PG")
        pg_mid = PGFactory(name="Mid Activity PG")

        # 1 booking on low
        r_low = RoomFactory(pg=pg_low, room_type="Single", capacity=1)
        b_low = BedFactory(room=r_low)
        BookingFactory(bed=b_low, status=BookingStatus.CONFIRMED)

        # 5 bookings on high (using 5 rooms/beds)
        for _ in range(5):
            r = RoomFactory(pg=pg_high, room_type="Single", capacity=1)
            b = BedFactory(room=r)
            BookingFactory(bed=b, status=BookingStatus.CONFIRMED)

        # 3 bookings on mid (using 3 rooms/beds)
        for _ in range(3):
            r = RoomFactory(pg=pg_mid, room_type="Single", capacity=1)
            b = BedFactory(room=r)
            BookingFactory(bed=b, status=BookingStatus.CONFIRMED)

        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == 200

        report = list(response.context["pg_booking_report"])
        idx_high = next(i for i, pg in enumerate(report) if pg.id == pg_high.id)
        idx_mid = next(i for i, pg in enumerate(report) if pg.id == pg_mid.id)
        idx_low = next(i for i, pg in enumerate(report) if pg.id == pg_low.id)

        assert idx_high < idx_mid < idx_low

    def test_dynamic_booking_creation_updates_report(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        pg = PGFactory(name="Dynamic PG")
        room = RoomFactory(pg=pg, room_type="Single", capacity=1)
        bed = BedFactory(room=room)

        # Initial check: 0 bookings
        response1 = client.get(reverse("users:dashboard_admin"))
        report_map1 = {p.id: p for p in response1.context["pg_booking_report"]}
        assert report_map1[pg.id].total_bookings == 0

        # Create new booking
        BookingFactory(bed=bed, status=BookingStatus.CONFIRMED)

        # Second check: 1 booking
        response2 = client.get(reverse("users:dashboard_admin"))
        report_map2 = {p.id: p for p in response2.context["pg_booking_report"]}
        assert report_map2[pg.id].total_bookings == 1
        assert report_map2[pg.id].confirmed_bookings == 1

    def test_status_change_updates_counts(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        pg = PGFactory()
        room = RoomFactory(pg=pg, room_type="Single", capacity=1)
        bed = BedFactory(room=room)
        booking = BookingFactory(bed=bed, status=BookingStatus.PENDING)

        # Initial: 1 pending, 0 confirmed
        res1 = client.get(reverse("users:dashboard_admin"))
        report1 = {p.id: p for p in res1.context["pg_booking_report"]}
        assert report1[pg.id].pending_bookings == 1
        assert report1[pg.id].confirmed_bookings == 0

        # Change to confirmed
        booking.status = BookingStatus.CONFIRMED
        booking.save()

        res2 = client.get(reverse("users:dashboard_admin"))
        report2 = {p.id: p for p in res2.context["pg_booking_report"]}
        assert report2[pg.id].pending_bookings == 0
        assert report2[pg.id].confirmed_bookings == 1

    def test_date_filters(self, client):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        pg = PGFactory(name="Time Filter PG")
        room1 = RoomFactory(pg=pg, room_type="Single", capacity=1)
        room2 = RoomFactory(pg=pg, room_type="Single", capacity=1)
        bed1 = BedFactory(room=room1)
        bed2 = BedFactory(room=room2)

        now = timezone.now()
        # Booking 1: created right now (this month, this year)
        b1 = BookingFactory(bed=bed1, status=BookingStatus.CONFIRMED)

        # Booking 2: created 400 days ago (last year)
        b2 = BookingFactory(bed=bed2, status=BookingStatus.CONFIRMED)
        past_date = now - timedelta(days=400)
        Booking.objects.filter(id=b2.id).update(created_at=past_date)

        # All time
        res_all = client.get(reverse("users:dashboard_admin") + "?period=all")
        report_all = {p.id: p for p in res_all.context["pg_booking_report"]}
        assert report_all[pg.id].total_bookings == 2

        # This year (should exclude b2 from 400 days ago)
        res_year = client.get(reverse("users:dashboard_admin") + "?period=year")
        report_year = {p.id: p for p in res_year.context["pg_booking_report"]}
        assert report_year[pg.id].total_bookings == 1

        # This month (should only include b1)
        res_month = client.get(reverse("users:dashboard_admin") + "?period=month")
        report_month = {p.id: p for p in res_month.context["pg_booking_report"]}
        assert report_month[pg.id].total_bookings == 1

    def test_query_efficiency_no_n_plus_one(self, client, django_assert_num_queries):
        admin = UserFactory(role=UserRole.ADMIN)
        client.force_login(admin)

        # Baseline with 1 PG
        pg1 = PGFactory()
        room1 = RoomFactory(pg=pg1, room_type="Single", capacity=1)
        bed1 = BedFactory(room=room1)
        BookingFactory(bed=bed1, status=BookingStatus.CONFIRMED)

        # Record query count for 1 PG (23 queries for session, auth, metrics, notification, and reports)
        with django_assert_num_queries(23):
            response = client.get(reverse("users:dashboard_admin"))
            assert response.status_code == 200

        # Add 5 more PGs
        for i in range(5):
            pg = PGFactory(name=f"PG Efficiency {i}")
            room = RoomFactory(pg=pg, room_type="Single", capacity=1)
            bed = BedFactory(room=room)
            BookingFactory(bed=bed, status=BookingStatus.CONFIRMED)

        # Query count must remain exactly 23: strictly no N+1 query problem!
        with django_assert_num_queries(23):
            response2 = client.get(reverse("users:dashboard_admin"))
            assert response2.status_code == 200
            assert len(response2.context["pg_booking_report"]) >= 6

