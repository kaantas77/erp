from __future__ import annotations

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView, View

from billing.models import Invoice
from inventory.models import Warehouse
from partners.models import Partner
from sales.models import Order

from . import queries


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = queries.dashboard_numbers()
        context["recent_moves"] = queries.recent_moves(limit=12)
        context["warehouse_values"] = queries.stock_value_by_warehouse()
        context["debtors"] = queries.partner_balances(only_debtors=True)[:10]
        return context


class StockReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/stock_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get("q", "").strip()
        low_only = self.request.GET.get("low") == "1"
        warehouse_id = self.request.GET.get("warehouse", "")
        warehouse = None
        if warehouse_id.isdigit():
            warehouse = Warehouse.objects.filter(pk=int(warehouse_id)).first()
        context["products"] = queries.stock_balances(
            search=search, low_only=low_only, warehouse=warehouse
        )
        context["warehouses"] = Warehouse.objects.filter(is_active=True)
        context["search"] = search
        context["low_only"] = low_only
        context["selected_warehouse"] = warehouse_id
        context["warehouse"] = warehouse
        return context


class PartnerBalanceReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/partner_balances.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kind = self.request.GET.get("kind", "")
        only_debtors = self.request.GET.get("debtors") == "1"
        rows = queries.partner_balances(only_debtors=only_debtors, kind=kind)
        context["rows"] = rows
        context["total"] = sum((row["balance"] for row in rows), 0)
        context["kinds"] = Partner.Kind.choices
        context["selected_kind"] = kind
        context["only_debtors"] = only_debtors
        return context


class SalesReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/sales_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start = _parse_date(self.request.GET.get("start"))
        end = _parse_date(self.request.GET.get("end"))
        invoices = Invoice.objects.filter(
            kind=Invoice.Kind.SALES, status__in=["issued", "paid"]
        ).select_related("partner")
        if start:
            invoices = invoices.filter(date__gte=start)
        if end:
            invoices = invoices.filter(date__lte=end)
        rows = []
        total = 0
        for invoice in invoices.prefetch_related("lines"):
            amount = invoice.grand_total
            total += amount
            rows.append({"invoice": invoice, "amount": amount})
        context["rows"] = rows
        context["total"] = total
        context["start"] = self.request.GET.get("start", "")
        context["end"] = self.request.GET.get("end", "")
        context["summary"] = queries.sales_summary(start=start, end=end)
        return context


class StockCsvExportView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get("q", "").strip()
        low_only = request.GET.get("low") == "1"
        products = queries.stock_balances(search=search, low_only=low_only)
        rows = [
            [p.sku, p.name, p.unit, str(p.total_qty), str(p.reorder_level), str(p.sale_price)]
            for p in products
        ]
        content = queries.to_csv(
            ["Stok kodu", "Urun", "Birim", "Miktar", "Kritik stok", "Satis fiyati"], rows
        )
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="stok-{timezone.localdate():%Y%m%d}.csv"'
        )
        return response


class PartnerCsvExportView(LoginRequiredMixin, View):
    def get(self, request):
        rows_data = queries.partner_balances()
        rows = [
            [
                row["partner"].code,
                row["partner"].name,
                row["partner"].get_kind_display(),
                str(row["balance"]),
            ]
            for row in rows_data
        ]
        content = queries.to_csv(["Cari kodu", "Unvan", "Tur", "Bakiye"], rows)
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="cari-{timezone.localdate():%Y%m%d}.csv"'
        )
        return response


class CountVarianceReportView(LoginRequiredMixin, View):
    """Son sayimlarin fark ozeti."""

    def get(self, request):
        from inventory.models import CountSession

        sessions = CountSession.objects.filter(status=CountSession.Status.CLOSED).select_related(
            "warehouse"
        )[:50]
        rows = [
            {
                "session": session,
                "variance": session.total_variance,
                "variance_count": session.variance_count,
            }
            for session in sessions
        ]
        return render(request, "reports/count_variance.html", {"rows": rows})


class OpenOrdersReportView(LoginRequiredMixin, TemplateView):
    template_name = "reports/open_orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = Order.objects.filter(
            status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED]
        ).select_related("partner", "warehouse")
        context["orders"] = orders
        return context
