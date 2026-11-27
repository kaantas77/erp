from __future__ import annotations

from decimal import Decimal

import pytest

from inventory.models import Product, StockMove, Warehouse
from inventory.services import close_count, record_move, start_count
from partners.models import Partner


@pytest.fixture
def warehouse(db):
    return Warehouse.objects.create(code="DEP1", name="Merkez Depo")


@pytest.fixture
def product(db):
    return Product.objects.create(sku="URUN-1", name="Test Urunu", purchase_price=Decimal("10.00"))


@pytest.mark.django_db
def test_on_hand_hesabi_pozitif_ve_negatif_hareketler(warehouse, product):
    record_move(product=product, warehouse=warehouse, quantity=10)
    record_move(product=product, warehouse=warehouse, quantity=-3, kind=StockMove.Kind.OUT)

    assert product.on_hand(warehouse) == Decimal("7.000")


@pytest.mark.django_db
def test_negatif_stok_uyarisi_yok_ama_sayi_dogru(warehouse, product):
    record_move(product=product, warehouse=warehouse, quantity=-4)

    assert product.on_hand(warehouse) == Decimal("-4.000")


@pytest.mark.django_db
def test_sayim_acilirken_sistem_miktari_dondurulur(warehouse, product):
    record_move(product=product, warehouse=warehouse, quantity=8)

    session = start_count(warehouse=warehouse, products=Product.objects.all())
    line = session.lines.get(product=product)

    assert line.system_qty == Decimal("8.000")
    assert line.counted_qty is None


@pytest.mark.django_db
def test_sayim_kapatilinca_fark_hareketi_olusur(warehouse, product):
    record_move(product=product, warehouse=warehouse, quantity=8)
    session = start_count(warehouse=warehouse, products=Product.objects.all())
    line = session.lines.get(product=product)
    line.counted_qty = Decimal("5")
    line.save()

    moves = close_count(session)

    assert len(moves) == 1
    assert moves[0].quantity == Decimal("-3.000")
    assert moves[0].kind == StockMove.Kind.COUNT
    assert product.on_hand(warehouse) == Decimal("5.000")


@pytest.mark.django_db
def test_sayim_sayilmadan_kapatilamaz(warehouse, product):
    from inventory.services import CountError

    record_move(product=product, warehouse=warehouse, quantity=8)
    session = start_count(warehouse=warehouse, products=Product.objects.all())

    with pytest.raises(CountError, match="Sayilmayan"):
        close_count(session)


@pytest.mark.django_db
def test_fark_yoksa_hareket_yazilmaz(warehouse, product):
    record_move(product=product, warehouse=warehouse, quantity=8)
    session = start_count(warehouse=warehouse, products=Product.objects.all())
    line = session.lines.get(product=product)
    line.counted_qty = Decimal("8")
    line.save()

    assert close_count(session) == []
    assert StockMove.objects.filter(kind=StockMove.Kind.COUNT).count() == 0


@pytest.mark.django_db
def test_cari_bakiye_borc_eksi_alacak(db):
    from partners.services import add_entry, balance

    partner = Partner.objects.create(code="C1", name="Musteri A")
    add_entry(partner=partner, date="2026-01-01", description="Fatura", debit=Decimal("1000"))
    add_entry(partner=partner, date="2026-01-10", description="Tahsilat", credit=Decimal("400"))

    assert balance(partner) == Decimal("600.00")
