from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from inventory.models import Product, Warehouse


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="test", password="gecici12345")


@pytest.mark.django_db
def test_giris_yapmadan_dashboard_login_yonlendirir(client):
    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 302
    assert "/hesap/login/" in response["Location"]


@pytest.mark.django_db
def test_giris_yapinca_dashboard_acilir(client, user):
    client.force_login(user)
    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 200
    assert "Dashboard" in response.content.decode()


@pytest.mark.django_db
def test_urun_listesi_acilir(client, user):
    client.force_login(user)
    Product.objects.create(sku="P1", name="Urun")

    response = client.get(reverse("inventory:product-list"))

    assert response.status_code == 200
    assert "P1" in response.content.decode()


@pytest.mark.django_db
def test_saglik_ucnoktasi_calisir(client):
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_sayim_baslat_ve_detay_acilir(client, user):
    client.force_login(user)
    warehouse = Warehouse.objects.create(code="D1", name="Depo")
    Product.objects.create(sku="P1", name="Urun")

    response = client.post(
        reverse("inventory:count-start"), {"warehouse": warehouse.pk, "note": ""}
    )

    assert response.status_code == 302
    detail = client.get(response["Location"])
    assert detail.status_code == 200
    assert "P1" in detail.content.decode()
