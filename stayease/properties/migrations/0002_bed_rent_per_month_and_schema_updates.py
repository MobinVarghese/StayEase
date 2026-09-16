# Generated manually for StayEase bed-level pricing hierarchy
from decimal import Decimal

from django.db import migrations, models


def backfill_bed_rents_and_populate_beds(apps, schema_editor):
    Bed = apps.get_model("properties", "Bed")
    Room = apps.get_model("properties", "Room")

    # 1. Backfill existing beds with room rent or PG rent
    for bed in Bed.objects.select_related("room", "room__pg").all():
        if bed.rent_per_month == Decimal("0.00") or bed.rent_per_month is None:
            if bed.room and bed.room.rent:
                bed.rent_per_month = bed.room.rent
            elif bed.room and bed.room.pg and bed.room.pg.rent_per_month:
                bed.rent_per_month = bed.room.pg.rent_per_month
            else:
                bed.rent_per_month = Decimal("5000.00")
            bed.save(update_fields=["rent_per_month"])

    # 2. For rooms that currently have zero beds, automatically provision default beds
    # based on the room's stated capacity, using room/PG rent.
    for room in Room.objects.select_related("pg").all():
        if room.beds.count() == 0 and room.capacity > 0:
            default_rent = room.rent or (room.pg.rent_per_month if room.pg else None) or Decimal("5000.00")
            for i in range(1, room.capacity + 1):
                Bed.objects.create(
                    room=room,
                    label=f"Bed {i}",
                    rent_per_month=default_rent,
                    is_available=True,
                    is_active=True,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bed",
            name="rent_per_month",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Monthly rent for this bed.",
                max_digits=10,
                verbose_name="rent per month",
            ),
        ),
        migrations.AlterField(
            model_name="pg",
            name="rent_per_month",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Base / representative monthly rent for this PG (legacy).",
                max_digits=10,
                null=True,
                verbose_name="rent per month",
            ),
        ),
        migrations.AlterField(
            model_name="room",
            name="rent",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Legacy / reference monthly rent for this room.",
                max_digits=10,
                null=True,
                verbose_name="rent",
            ),
        ),
        migrations.RunPython(
            backfill_bed_rents_and_populate_beds,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
