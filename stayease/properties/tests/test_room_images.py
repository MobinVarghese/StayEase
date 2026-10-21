"""
Tests for room image upload and management (max 3 per room).
"""

from __future__ import annotations

import io
from typing import Any, cast
from PIL import Image
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from stayease.discovery.services import get_rooms_with_availability
from stayease.properties.forms import RoomImageForm, RoomImageFormSet
from stayease.properties.models import PG, Room, RoomImage
from stayease.properties.tests.factories import PGFactory, RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def make_room(**kwargs: Any) -> Room:
    return RoomFactory(**kwargs)  # type: ignore[return-value]


def make_pg(**kwargs: Any) -> PG:
    return PGFactory(**kwargs)  # type: ignore[return-value]


def create_test_image(name="test.jpg", size=(100, 100), color="blue"):
    file_obj = io.BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(file_obj, "jpeg")
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/jpeg")


class TestRoomImageModel:
    """Tests for RoomImage model rules and constraints."""

    def test_create_room_image(self):
        room = make_room()
        img = RoomImage.objects.create(
            room=room,
            image=create_test_image(),
            caption="Master bedroom",
            order=1,
        )
        assert img.pk is not None
        assert img.room == room
        assert img.caption == "Master bedroom"
        assert img.order == 1
        assert "Master bedroom" in str(img) or "Image for" in str(img)

    def test_model_clean_enforces_max_3_images(self):
        room = make_room()
        for i in range(3):
            RoomImage.objects.create(
                room=room,
                image=create_test_image(f"test_{i}.jpg"),
                order=i,
            )

        assert room.images.count() == 3

        # Attempting to clean a 4th image raises ValidationError
        extra_img = RoomImage(
            room=room,
            image=create_test_image("extra.jpg"),
        )
        with pytest.raises(ValidationError, match="maximum of 3 photos"):
            extra_img.clean()

    def test_ordering_by_order_and_uploaded_at(self):
        room = make_room()
        img2 = RoomImage.objects.create(
            room=room,
            image=create_test_image("img2.jpg"),
            order=2,
            caption="Second",
        )
        img1 = RoomImage.objects.create(
            room=room,
            image=create_test_image("img1.jpg"),
            order=1,
            caption="First",
        )

        images = list(room.images.all())
        assert images[0] == img1
        assert images[1] == img2


class TestRoomImageForms:
    """Tests for RoomImageForm and RoomImageFormSet validation."""

    def test_valid_image_form(self):
        uploaded = create_test_image()
        form = RoomImageForm(
            data={"caption": "Balcony view", "order": 0},
            files={"image": uploaded},
        )
        assert form.is_valid(), form.errors

    def test_image_file_size_exceeding_limit(self):
        uploaded = create_test_image()
        uploaded.size = 6 * 1024 * 1024
        form = RoomImageForm(
            data={"caption": "Huge file", "order": 0},
            files={"image": uploaded},
        )
        assert not form.is_valid()
        assert "image" in form.errors
        assert any("5 MB" in str(err) for err in form.errors["image"])

    def test_formset_allows_up_to_3_images(self):
        room = make_room()
        data = {
            "images-TOTAL_FORMS": "3",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
            "images-0-caption": "Photo 1",
            "images-0-order": "0",
            "images-1-caption": "Photo 2",
            "images-1-order": "1",
        }
        files = MultiValueDict(
            {
                "images-0-image": [create_test_image("1.jpg")],
                "images-1-image": [create_test_image("2.jpg")],
            }
        )
        formset = RoomImageFormSet(data=data, files=files, instance=room)
        assert formset.is_valid(), formset.errors
        formset.save()
        assert room.images.count() == 2

    def test_formset_enforces_max_3_images(self):
        room = make_room()
        # Pre-populate 2 images
        for i in range(2):
            RoomImage.objects.create(
                room=room,
                image=create_test_image(f"existing_{i}.jpg"),
                order=i,
            )

        # Attempt to upload 2 more images (total 4)
        data = {
            "images-TOTAL_FORMS": "4",
            "images-INITIAL_FORMS": "2",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
            "images-0-id": str(room.images.all()[0].pk),
            "images-1-id": str(room.images.all()[1].pk),
            "images-2-caption": "Photo 3",
            "images-2-order": "2",
            "images-3-caption": "Photo 4",
            "images-3-order": "3",
        }
        files = MultiValueDict(
            {
                "images-2-image": [create_test_image("new1.jpg")],
                "images-3-image": [create_test_image("new2.jpg")],
            }
        )
        formset = RoomImageFormSet(data=data, files=files, instance=room)
        assert not formset.is_valid()
        assert any(
            "maximum of 3 photos" in str(err) for err in formset.non_form_errors()
        )


class TestRoomImageViews:
    """Tests for owner-facing RoomImageManageView and RoomDetailView."""

    def test_owner_can_access_room_images_page(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        room = make_room(pg=pg)
        client.force_login(owner)

        url = reverse(
            "properties:room_images", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert "formset" in response.context
        assert "Manage Room Photos" in response.content.decode()

    def test_other_owner_cannot_access_room_images(self, client):
        owner1 = UserFactory(role=UserRole.OWNER)
        owner2 = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner1)
        room = make_room(pg=pg)
        client.force_login(owner2)

        url = reverse(
            "properties:room_images", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_tenant_cannot_access_room_images(self, client):
        tenant = UserFactory(role=UserRole.TENANT)
        pg = make_pg()
        room = make_room(pg=pg)
        client.force_login(tenant)

        url = reverse(
            "properties:room_images", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        response = client.get(url)
        assert response.status_code == 403

    def test_owner_can_upload_images_via_post(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        room = make_room(pg=pg)
        client.force_login(owner)

        url = reverse(
            "properties:room_images", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        data = {
            "images-TOTAL_FORMS": "3",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
            "images-0-caption": "Room View A",
            "images-0-order": "0",
            "images-0-image": create_test_image("room1.jpg"),
        }
        response = client.post(url, data=data)
        assert response.status_code == 302
        assert response.url == reverse(
            "properties:room_detail", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        assert room.images.count() == 1
        first_image = room.images.first()
        assert first_image is not None
        assert first_image.caption == "Room View A"

    def test_owner_can_delete_image_via_formset(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        room = make_room(pg=pg)
        img = RoomImage.objects.create(
            room=room,
            image=create_test_image("delete_me.jpg"),
            caption="To be deleted",
        )
        client.force_login(owner)

        url = reverse(
            "properties:room_images", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        data = {
            "images-TOTAL_FORMS": "1",
            "images-INITIAL_FORMS": "1",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
            "images-0-id": str(img.pk),
            "images-0-DELETE": "on",
        }
        response = client.post(url, data=data)
        assert response.status_code == 302
        assert room.images.count() == 0

    def test_room_detail_view_includes_images_in_context(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        room = make_room(pg=pg)
        RoomImage.objects.create(
            room=room,
            image=create_test_image("detail_test.jpg"),
            caption="Detail view test",
        )
        client.force_login(owner)

        url = reverse(
            "properties:room_detail", kwargs={"pg_pk": pg.pk, "room_pk": room.pk}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context["images"]) == 1
        assert "Room Photos" in response.content.decode()
        assert "Detail view test" in response.content.decode()


class TestDiscoveryRoomImagesIntegration:
    """Tests that uploaded room images are properly visible to tenants."""

    def test_discovery_services_includes_images(self):
        pg = make_pg()
        room = make_room(pg=pg, is_active=True)
        RoomImage.objects.create(
            room=room,
            image=create_test_image("tenant_visible.jpg"),
            caption="Cozy Bed Area",
        )

        rooms_data = get_rooms_with_availability(pg)
        assert len(rooms_data) == 1
        assert "images" in rooms_data[0]
        assert len(rooms_data[0]["images"]) == 1
        assert rooms_data[0]["images"][0].caption == "Cozy Bed Area"

    def test_tenant_pg_detail_shows_room_photos(self, client):
        tenant = UserFactory(role=UserRole.TENANT)
        pg = make_pg(is_active=True)
        room = make_room(pg=pg, is_active=True)
        RoomImage.objects.create(
            room=room,
            image=create_test_image("tenant_view.jpg"),
            caption="Spacious Double Room",
        )
        client.force_login(tenant)

        url = reverse("discovery:pg_detail", kwargs={"pg_pk": pg.pk})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Room Photos" in content
        assert "Spacious Double Room" in content


class TestRoomCreateWithImages:
    """Tests for uploading room images directly while creating the room."""

    def test_owner_can_upload_images_while_creating_room(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        client.force_login(owner)

        url = reverse("properties:room_create", kwargs={"pg_pk": pg.pk})

        data = {
            "room_number": "201",
            "room_type": "Double",
            "capacity": 2,
            "description": "Lovely room with balcony",
            # Formset management fields (prefix is 'images')
            "images-TOTAL_FORMS": "3",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
            # Image 1
            "images-0-image": create_test_image("img1.jpg"),
            "images-0-caption": "Balcony view",
            "images-0-order": "1",
            # Image 2
            "images-1-image": create_test_image("img2.jpg"),
            "images-1-caption": "Study desk",
            "images-1-order": "2",
            # Image 3 (empty)
            "images-2-caption": "",
            "images-2-order": "0",
        }

        response = client.post(url, data)
        assert response.status_code == 302

        room = Room.objects.get(pg=pg, room_number="201")
        assert room.images.count() == 2
        captions = list(room.images.values_list("caption", flat=True))
        assert "Balcony view" in captions
        assert "Study desk" in captions

    def test_owner_can_create_room_without_images(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        client.force_login(owner)

        url = reverse("properties:room_create", kwargs={"pg_pk": pg.pk})
        data = {
            "room_number": "202",
            "room_type": "Single",
            "capacity": 1,
            "description": "Simple single room",
            "images-TOTAL_FORMS": "3",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "3",
        }

        response = client.post(url, data)
        assert response.status_code == 302
        room = Room.objects.get(pg=pg, room_number="202")
        assert room.images.count() == 0

    def test_owner_creating_room_gets_formset_in_context(self, client):
        owner = UserFactory(role=UserRole.OWNER)
        pg = make_pg(owner=owner)
        client.force_login(owner)

        url = reverse("properties:room_create", kwargs={"pg_pk": pg.pk})
        response = client.get(url)
        assert response.status_code == 200
        assert "image_formset" in response.context
        assert "Room Photos (Optional)" in response.content.decode()
