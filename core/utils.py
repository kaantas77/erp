from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

MONEY_STEP = Decimal("0.01")
QTY_STEP = Decimal("0.001")


def money(value: Decimal | int | str) -> Decimal:
    """Parayi iki basamaga yuvarlar (ROUND_HALF_UP)."""
    return Decimal(value).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def qty(value: Decimal | int | str) -> Decimal:
    """Miktari uc basamaga yuvarlar."""
    return Decimal(value).quantize(QTY_STEP, rounding=ROUND_HALF_UP)


def vat_split(net: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """Net tutardan (KDV, brut) dondurur."""
    net_value = money(net)
    vat_value = money(net_value * Decimal(rate) / Decimal(100))
    return vat_value, money(net_value + vat_value)


def next_number(model, prefix: str, field: str = "number", width: int = 4) -> str:
    """Ornek: SIP-2026-0001. Ayni yil icindeki en buyuk siradan devam eder."""
    stem = f"{prefix}-{timezone.localdate():%Y}-"
    values = model._default_manager.filter(**{f"{field}__startswith": stem}).values_list(
        field, flat=True
    )
    highest = 0
    for value in values:
        _, _, seq = str(value).rpartition("-")
        if seq.isdigit():
            highest = max(highest, int(seq))
    return f"{stem}{highest + 1:0{width}d}"
