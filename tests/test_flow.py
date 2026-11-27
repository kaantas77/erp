from __future__ import annotations

from decimal import Decimal

import pytest

from billing.models import Invoice, InvoiceLine
from billing.services import cancel_invoice, issue_invoice
from inventory.models import Product, Warehouse
from inventory.services import record_move
from partners.models import Partner
from partners.services import balance
from sales.models import Order, OrderLine
from sales.services import (
    OrderError,
    available_qty,
    cancel_order,
    confirm_order,
    mark_shipped,
)


@pytest.fixture
def setup_data(db):
    warehouse = Warehouse.objects.create(code="DEP1", name="Merkez")
    product = Product.objects.create(
        sku="URUN-1", name="Urun", purchase_price=Decimal("10"), sale_price=Decimal("15")
    )
    customer = Partner.objects.create(code="M1", name="Musteri", kind=Partner.Kind.CUSTOMER)
    record_move(product=product, warehouse=warehouse, quantity=20)
    return {"warehouse": warehouse, "product": product, "customer": customer}


def _order(setup_data, quantity="5"):
    order = Order.objects.create(partner=setup_data["customer"], warehouse=setup_data["warehouse"])
    OrderLine.objects.create(
        order=order,
        product=setup_data["product"],
        quantity=Decimal(quantity),
        unit_price=Decimal("15.00"),
        vat_rate=Decimal("20"),
    )
    return order


@pytest.mark.django_db
def test_onay_stok_dusurmez_sadece_rezerve_eder(setup_data):
    order = _order(setup_data)
    confirm_order(order)

    order.refresh_from_db()
    assert order.status == Order.Status.CONFIRMED
    # fiziksel stok hala 20
    assert setup_data["product"].on_hand(setup_data["warehouse"]) == Decimal("20.000")
    # ama satilabilir 15
    assert available_qty(setup_data["product"], setup_data["warehouse"]) == Decimal("15.000")


@pytest.mark.django_db
def test_iki_siparis_stoktan_fazla_rezerve_edemez(setup_data):
    _order(setup_data, "15")
    first = Order.objects.first()
    confirm_order(first)

    second = _order(setup_data, "10")
    with pytest.raises(OrderError, match="satilabilir stok yetersiz"):
        confirm_order(second)


@pytest.mark.django_db
def test_sevk_edince_fiziksel_stok_duser(setup_data):
    order = _order(setup_data)
    confirm_order(order)
    mark_shipped(order)

    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED
    assert setup_data["product"].on_hand(setup_data["warehouse"]) == Decimal("15.000")


@pytest.mark.django_db
def test_iptal_rezervasyonu_serbest_birakir(setup_data):
    order = _order(setup_data)
    confirm_order(order)
    cancel_order(order)

    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert available_qty(setup_data["product"], setup_data["warehouse"]) == Decimal("20.000")
    assert setup_data["product"].on_hand(setup_data["warehouse"]) == Decimal("20.000")


@pytest.mark.django_db
def test_sevk_edilmis_siparis_iptal_edilemez(setup_data):
    order = _order(setup_data)
    confirm_order(order)
    mark_shipped(order)

    with pytest.raises(OrderError, match="Sevk edilmis"):
        cancel_order(order)


@pytest.mark.django_db
def test_fatura_kesilince_cari_borclanir_ve_iptal_ters_kayit_yazar(setup_data):
    invoice = Invoice.objects.create(
        partner=setup_data["customer"], kind=Invoice.Kind.SALES, date="2026-02-01"
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        product=setup_data["product"],
        quantity=Decimal("2"),
        unit_price=Decimal("100"),
        vat_rate=Decimal("20"),
    )

    issue_invoice(invoice)
    invoice.refresh_from_db()

    assert invoice.status == Invoice.Status.ISSUED
    assert invoice.net_total == Decimal("200.00")
    assert invoice.vat_total == Decimal("40.00")
    assert invoice.grand_total == Decimal("240.00")
    assert balance(setup_data["customer"]) == Decimal("240.00")

    cancel_invoice(invoice)
    assert balance(setup_data["customer"]) == Decimal("0.00")


@pytest.mark.django_db
def test_alis_faturasi_cariye_alacak_yazar(setup_data):
    supplier = Partner.objects.create(code="T1", name="Tedarikci", kind=Partner.Kind.SUPPLIER)
    invoice = Invoice.objects.create(
        partner=supplier, kind=Invoice.Kind.PURCHASE, date="2026-02-01"
    )
    InvoiceLine.objects.create(
        invoice=invoice, description="Hizmet", quantity=Decimal("1"), unit_price=Decimal("500")
    )
    issue_invoice(invoice)

    # bize borclu degiliz: bakiye negatif (biz tedarikciye borcluyuz)
    assert balance(supplier) == Decimal("-600.00")


@pytest.mark.django_db
def test_satirli_iskonto_ve_kdv_hesabi(setup_data):
    invoice = Invoice.objects.create(partner=setup_data["customer"], date="2026-02-01")
    line = InvoiceLine.objects.create(
        invoice=invoice,
        quantity=Decimal("3"),
        unit_price=Decimal("100"),
        discount_pct=Decimal("10"),
        vat_rate=Decimal("20"),
    )

    assert line.net_amount == Decimal("270.00")
    assert line.vat_amount == Decimal("54.00")
    assert line.gross_amount == Decimal("324.00")
