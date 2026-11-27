"""Rapor sorgulari. View'lar buradan beslenir, boylece test edilebilir kalir."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from billing.models import Invoice
from inventory.models import Product, StockMove, Warehouse
from partners.models import Partner
from sales.models import Order

QTY_FIELD = DecimalField(max_digits=14, decimal_places=3)
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def stock_balances(*, search: str = "", low_only: bool = False, warehouse=None):
    queryset = Product.objects.filter(is_active=True).select_related("category")
    if warehouse is not None:
        queryset = queryset.annotate(
            total_qty=Coalesce(
                Sum("moves__quantity", filter=Q(moves__warehouse=warehouse)),
                Value(0),
                output_field=QTY_FIELD,
            )
        )
    else:
        queryset = queryset.annotate(
            total_qty=Coalesce(Sum("moves__quantity"), Value(0), output_field=QTY_FIELD)
        )
    if search:
        queryset = queryset.filter(Q(sku__icontains=search) | Q(name__icontains=search))
    if low_only:
        queryset = queryset.filter(total_qty__lte=F("reorder_level"))
    return queryset.order_by("sku")


def stock_value_by_warehouse() -> list[dict]:
    rows = []
    for warehouse in Warehouse.objects.filter(is_active=True):
        moves = StockMove.objects.filter(warehouse=warehouse)
        qty = moves.aggregate(total=Coalesce(Sum("quantity"), Value(0), output_field=QTY_FIELD))[
            "total"
        ]
        value = moves.aggregate(
            total=Coalesce(Sum(F("quantity") * F("unit_cost")), Value(0), output_field=MONEY_FIELD)
        )["total"]
        rows.append({"warehouse": warehouse, "quantity": qty, "value": value})
    return rows


def partner_balances(*, only_debtors: bool = False, kind: str = "") -> list[dict]:
    balance = Coalesce(
        Sum(F("entries__debit") - F("entries__credit")), Value(0), output_field=MONEY_FIELD
    )
    queryset = Partner.objects.filter(is_active=True).annotate(balance=balance)
    if kind:
        queryset = queryset.filter(kind__in=[kind, Partner.Kind.BOTH])
    rows = [
        {"partner": partner, "balance": partner.balance} for partner in queryset.order_by("name")
    ]
    if only_debtors:
        rows = [row for row in rows if row["balance"] > 0]
    return rows


def sales_summary(*, start: date | None = None, end: date | None = None) -> dict:
    invoices = Invoice.objects.filter(kind=Invoice.Kind.SALES, status__in=["issued", "paid"])
    if start:
        invoices = invoices.filter(date__gte=start)
    if end:
        invoices = invoices.filter(date__lte=end)
    total = Decimal("0")
    count = 0
    for invoice in invoices.prefetch_related("lines"):
        total += invoice.grand_total
        count += 1
    return {"invoice_count": count, "total": total}


def dashboard_numbers() -> dict:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    open_orders = Order.objects.filter(
        status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED]
    ).count()
    draft_invoices = Invoice.objects.filter(status=Invoice.Status.DRAFT).count()
    unpaid_invoices = Invoice.objects.filter(
        kind=Invoice.Kind.SALES, status=Invoice.Status.ISSUED
    ).count()
    low_stock = stock_balances(low_only=True).count()
    month_sales = sales_summary(start=month_start, end=today)["total"]
    receivables = sum((row["balance"] for row in partner_balances(only_debtors=True)), Decimal("0"))
    return {
        "open_orders": open_orders,
        "draft_invoices": draft_invoices,
        "unpaid_invoices": unpaid_invoices,
        "low_stock": low_stock,
        "month_sales": month_sales,
        "receivables": receivables,
    }


def recent_moves(limit: int = 10):
    return StockMove.objects.select_related("product", "warehouse")[:limit]


def to_csv(headers: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()
