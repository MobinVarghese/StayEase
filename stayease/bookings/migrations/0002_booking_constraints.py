# Migration: Add database-level constraints to prevent duplicate/concurrent bookings.
#
# This migration adds:
# 1. A partial unique constraint ensuring at most one "active" booking
#    (PENDING, APPROVED, PAYMENT_PENDING, or CONFIRMED) exists per bed.
# 2. An index on (tenant, status) for efficient tenant-history queries.
# 3. An index on (bed, status) for efficient availability checks.
#
# These constraints are the PRIMARY defence against concurrent double-bookings.
# Application-level checks in services.py are a secondary safeguard.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        # ------------------------------------------------------------------
        # Partial unique constraint: only one active booking per bed.
        # "Active" = status IN (PENDING, APPROVED, PAYMENT_PENDING, CONFIRMED)
        # REJECTED bookings do NOT block new bookings for the same bed.
        #
        # PostgreSQL supports partial unique indexes via condition=Q(...).
        # ------------------------------------------------------------------
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                fields=["bed"],
                name="unique_active_booking_per_bed",
                condition=models.Q(
                    status__in=[
                        "PENDING",
                        "APPROVED",
                        "PAYMENT_PENDING",
                        "CONFIRMED",
                    ]
                ),
            ),
        ),
        # ------------------------------------------------------------------
        # Index: tenant + status  (tenant booking history / dashboard)
        # ------------------------------------------------------------------
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["tenant", "status"],
                name="idx_booking_tenant_status",
            ),
        ),
        # ------------------------------------------------------------------
        # Index: bed + status  (availability lookups)
        # ------------------------------------------------------------------
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["bed", "status"],
                name="idx_booking_bed_status",
            ),
        ),
    ]
