from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import InvoiceForm, InvoiceLineFormSet
from .models import Invoice
from .services import InvoiceError, cancel_invoice, issue_invoice, mark_paid


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = "billing/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        queryset = Invoice.objects.select_related("partner")
        status = self.request.GET.get("status")
        if status in Invoice.Status.values:
            queryset = queryset.filter(status=status)
        kind = self.request.GET.get("kind")
        if kind in Invoice.Kind.values:
            queryset = queryset.filter(kind=kind)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Invoice.Status.choices
        context["kinds"] = Invoice.Kind.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_kind"] = self.request.GET.get("kind", "")
        return context


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = "billing/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lines"] = self.object.lines.select_related("product")
        return context


class InvoiceCreateView(LoginRequiredMixin, View):
    template_name = "billing/invoice_form.html"

    def get(self, request):
        initial = {}
        order_id = request.GET.get("order")
        if order_id and order_id.isdigit():
            initial["order"] = order_id
        return render(
            request,
            self.template_name,
            {"form": InvoiceForm(initial=initial), "formset": InvoiceLineFormSet()},
        )

    @transaction.atomic
    def post(self, request):
        form = InvoiceForm(request.POST)
        formset = InvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            invoice.save()
            formset.instance = invoice
            formset.save()
            messages.success(request, f"{invoice.number} faturasi olusturuldu.")
            return redirect("billing:invoice-detail", pk=invoice.pk)
        messages.error(request, "Fatura kaydedilemedi.")
        return render(request, self.template_name, {"form": form, "formset": formset})


class InvoiceUpdateView(LoginRequiredMixin, View):
    template_name = "billing/invoice_form.html"

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if not invoice.is_editable:
            messages.error(request, "Sadece taslak faturalar duzenlenebilir.")
            return redirect("billing:invoice-detail", pk=invoice.pk)
        return render(
            request,
            self.template_name,
            {
                "form": InvoiceForm(instance=invoice),
                "formset": InvoiceLineFormSet(instance=invoice),
                "invoice": invoice,
            },
        )

    @transaction.atomic
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if not invoice.is_editable:
            messages.error(request, "Sadece taslak faturalar duzenlenebilir.")
            return redirect("billing:invoice-detail", pk=invoice.pk)
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Fatura guncellendi.")
            return redirect("billing:invoice-detail", pk=invoice.pk)
        messages.error(request, "Fatura kaydedilemedi.")
        return render(
            request, self.template_name, {"form": form, "formset": formset, "invoice": invoice}
        )


class InvoiceActionView(LoginRequiredMixin, View):
    def post(self, request, pk, action):
        invoice = get_object_or_404(Invoice, pk=pk)
        handlers = {
            "issue": lambda: issue_invoice(invoice, user=request.user),
            "cancel": lambda: cancel_invoice(invoice, user=request.user),
            "pay": lambda: mark_paid(invoice),
        }
        messages_map = {
            "issue": "Fatura kesildi ve cariye islendi.",
            "cancel": "Fatura iptal edildi, ters kayit olustu.",
            "pay": "Fatura odendi olarak isaretlendi.",
        }
        if action not in handlers:
            messages.error(request, "Gecersiz islem.")
            return redirect("billing:invoice-detail", pk=invoice.pk)
        try:
            handlers[action]()
        except InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, messages_map[action])
        return redirect("billing:invoice-detail", pk=invoice.pk)
