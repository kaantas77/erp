from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from inventory.models import StockMove, on_hand
from inventory.services import record_move

from .models import Order, OrderReservation


class OrderError(Exception):
    """Siparis akisinda is kurali ihlali."""


def reserved_qty(product, warehouse) -> Decimal:
    """Baska siparislerce rezerve edilmis miktar."""
    total = OrderReservation.objects.filter(
        warehouse=warehouse,
        order_line__product=product,
        order_line__order__status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED],
    ).aggregate(total=Sum("quantity"))["total"]
    return total or Decimal("0")


def available_qty(product, warehouse) -> Decimal:
    """Satilabilir miktar = fiziksel stok - rezervasyon."""
    return on_hand(product, warehouse) - reserved_qty(product, warehouse)


@transaction.atomic
def confirm_order(order: Order, user=None) -> None:
    """Siparisi onaylar ve miktari rezerve eder. Fiziksel stok DUSMEZ.

    Fiziksel cikis mark_shipped() icinde yazilir; boylece sevk edilmemis
    mal rafta kalir ve depo sayimi dogru cikar.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.DRAFT:
        raise OrderError("Sadece taslak siparisler onaylanabilir.")
    lines = list(order.lines.select_related("product"))
    if not lines:
        raise OrderError("Sipariste urun yok.")

    for line in lines:
        if line.quantity <= 0:
            raise OrderError(f"{line.product.sku} icin miktar sifirdan buyuk olmali.")
        free = available_qty(line.product, order.warehouse)
        if free < line.quantity:
            raise OrderError(
                f"{line.product.sku} icin satilabilir stok yetersiz "
                f"(rezervesiz mevcut {free}, istenen {line.quantity})."
            )

    for line in lines:
        OrderReservation.objects.create(
            order_line=line, warehouse=order.warehouse, quantity=line.quantity
        )

    order.status = Order.Status.CONFIRMED
    order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def mark_shipped(order: Order, user=None) -> None:
    """Sevkiyati kaydeder: fiziksel stok cikisi BURADA yazilir, rezervasyon kapanir."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.CONFIRMED:
        raise OrderError("Sadece onayli siparisler sevk edilebilir.")

    lines = list(order.lines.select_related("product"))
    for line in lines:
        free = on_hand(line.product, order.warehouse)
        if free < line.quantity:
            raise OrderError(
                f"{line.product.sku} icin fiziksel stok yetersiz "
                f"(mevcut {free}, sevk edilecek {line.quantity})."
            )

    for line in lines:
        record_move(
            product=line.product,
            warehouse=order.warehouse,
            quantity=-line.quantity,
            kind=StockMove.Kind.OUT,
            unit_cost=line.product.purchase_price,
            reference=order.number,
            note=f"Siparis sevki ({order.partner.name})",
            user=user,
        )

    OrderReservation.objects.filter(order_line__order=order).delete()
    order.status = Order.Status.SHIPPED
    order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def cancel_order(order: Order, user=None) -> None:
    """Onayli sipariste rezervasyonu serbest birakir; sevk edilmis olanda stogu geri alir."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.CANCELLED:
        raise OrderError("Siparis zaten iptal.")
    if order.status == Order.Status.SHIPPED:
        raise OrderError("Sevk edilmis siparis iptal edilemez; iade faturasi kesin.")

    if order.status == Order.Status.CONFIRMED:
        # Onayda fiziksel stok dusmedigi icin iptalde stok hareketi YAZILMAZ;
        # hanya rezervasyon serbest birakilir.
        OrderReservation.objects.filter(order_line__order=order).delete()

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
