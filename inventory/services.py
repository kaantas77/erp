"""Stok ve sayim is kurallari."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.utils import qty

from .models import CountLine, CountSession, Product, StockMove, Warehouse, on_hand


class CountError(Exception):
    """Sayim akisinda is kurali ihlali."""


def record_move(
    *,
    product: Product,
    warehouse: Warehouse,
    quantity: Decimal,
    kind: str = StockMove.Kind.IN,
    unit_cost: Decimal | None = None,
    reference: str = "",
    note: str = "",
    user=None,
) -> StockMove:
    return StockMove.objects.create(
        product=product,
        warehouse=warehouse,
        quantity=qty(quantity),
        unit_cost=unit_cost if unit_cost is not None else product.purchase_price,
        kind=kind,
        reference=reference,
        note=note,
        created_by=user,
    )


def start_count(
    *,
    warehouse: Warehouse,
    products=None,
    user=None,
    note: str = "",
) -> CountSession:
    """Depodaki urunler icin sayim acar; sistem miktarlarini o an dondurur."""
    queryset = products if products is not None else Product.objects.filter(is_active=True)
    with transaction.atomic():
        session = CountSession.objects.create(warehouse=warehouse, created_by=user, note=note)
        lines = [
            CountLine(session=session, product=product, system_qty=on_hand(product, warehouse))
            for product in queryset
        ]
        CountLine.objects.bulk_create(lines)
    return session


def save_counts(session: CountSession, data: dict[int, Decimal | None]) -> None:
    """sayim satirlarini {line_id: sayilan} sozlugu ile gunceller."""
    if not session.is_open:
        raise CountError("Kapatilmis sayim duzenlenemez.")
    lines = {line.pk: line for line in session.lines.all()}
    unknown = set(data) - set(lines)
    if unknown:
        raise CountError(f"Sayimda olmayan satir: {sorted(unknown)}")
    with transaction.atomic():
        for line_id, counted in data.items():
            line = lines[line_id]
            line.counted_qty = None if counted is None else qty(counted)
            line.save(update_fields=["counted_qty", "updated_at"])


def close_count(session: CountSession, user=None) -> list[StockMove]:
    """Farklari stok hareketine cevirip sayimi kapatir."""
    with transaction.atomic():
        session = CountSession.objects.select_for_update().get(pk=session.pk)
        if not session.is_open:
            raise CountError("Sadece acik sayimlar kapatilabilir.")
        lines = list(session.lines.select_related("product"))
        if not lines:
            raise CountError("Satirsiz sayim kapatilamaz.")
        missing = [line.product.sku for line in lines if line.counted_qty is None]
        if missing:
            raise CountError("Sayilmayan urunler var: " + ", ".join(missing[:5]))

        moves = []
        for line in lines:
            delta = qty(line.counted_qty - line.system_qty)
            if delta == 0:
                continue
            moves.append(
                StockMove.objects.create(
                    product=line.product,
                    warehouse=session.warehouse,
                    quantity=delta,
                    unit_cost=line.product.purchase_price,
                    kind=StockMove.Kind.COUNT,
                    reference=session.number,
                    note=f"Sayim farki: {line.system_qty} -> {line.counted_qty}",
                    created_by=user or session.created_by,
                )
            )
        session.status = CountSession.Status.CLOSED
        session.closed_at = timezone.now()
        session.save(update_fields=["status", "closed_at", "updated_at"])
    return moves
