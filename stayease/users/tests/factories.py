from typing import Any

from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory

from stayease.users.models import User
from stayease.users.models import UserRole


class UserFactory(DjangoModelFactory[User]):
    email = Faker("email")
    name = Faker("name")
    role = UserRole.TENANT

    @post_generation
    def password(self: Any, create: bool, extracted: str | None, **kwargs):  # noqa: FBT001
        raw_password = (
            extracted
            if extracted
            else Faker(
                "password",
                length=42,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})
        )
        self.set_password(raw_password)
        if create:
            self.save()

    class Meta:
        model = User
        django_get_or_create = ["email"]
        skip_postgeneration_save = True

