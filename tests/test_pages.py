from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_status_and_content(client: Client):
    url = reverse("home")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    # Verify StayEase branding and core front-page components are present
    assert b"StayEase" in response.content
    assert b"Find Your Perfect" in response.content
    assert b"hero-search-box" in response.content
    assert b"hero-pg.jpg" in response.content
    assert b"Bengaluru" in response.content
    assert b"How StayEase Works" in response.content


@pytest.mark.django_db
def test_about_page_status_and_content(client: Client):
    url = reverse("about")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    assert b"About StayEase" in response.content
    assert b"Making Co-Living Simple" in response.content


@pytest.mark.django_db
def test_sign_in_page_rendering(client: Client):
    url = reverse("account_login")
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    assert b"Welcome Back" in response.content
    assert b"auth-card" in response.content
    assert b"Sign In" in response.content
    assert b"Sign up for StayEase" in response.content

