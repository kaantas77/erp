from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

from core.utils import money

from .models import LedgerEntry, Partner


def add_entry(
    *,
    partner: Partner,
    date,
    description: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    source: str = LedgerEntry.Source.MANUAL,
    source_ref: str = "",
    user=None,
) -> LedgerEntry:
    debit = money(debit)
    credit = money(credit)
    if debit and credit:
        raise ValueError("Bir harekette hem borc hem alacak olamaz.")
    if not debit and not credit:
        raise ValueError("Borc veya alacak girilmeli.")
    return LedgerEntry.objects.create(
        partner=partner,
        date=date,
        description=description,
        debit=debit,
        credit=credit,
        source=source,
        source_ref=source_ref,
        created_by=user,
    )


def balance(partner: Partner) -> Decimal:
    total = partner.entries.aggregate(total=Sum(F("debit") - F("credit")))["total"]
    return money(total or Decimal("0"))


def statement(partner: Partner) -> list[dict]:
    """Cari ekstre: her hareketin uzerine kumulatif bakiye ekler."""
    running = Decimal("0")
    rows = []
    for entry in partner.entries.order_by("date", "id"):
        running += entry.debit - entry.credit
        rows.append({"entry": entry, "running_balance": money(running)})
    return rows


@transaction.atomic
def record_payment(
    *, partner: Partner, amount: Decimal, date, description: str = "", user=None
) -> LedgerEntry:
    """Musteriden tahsilat: alacak. Tedarikciye odeme: borc."""
    amount = money(amount)
    if amount <= 0:
        raise ValueError("Tutar sifirdan buyuk olmali.")
    is_collection = partner.is_customer and not partner.is_supplier
    payload = {
        "partner": partner,
        "date": date,
        "description": description or ("Tahsilat" if is_collection else "Odeme"),
        "source": LedgerEntry.Source.PAYMENT,
        "user": user,
    }
    if is_collection:
        payload["credit"] = amount
    else:
        payload["debit"] = amount
    return add_entry(**payload)
