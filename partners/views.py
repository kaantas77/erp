from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import LedgerEntryForm, PartnerForm, PaymentForm
from .models import Partner
from .services import record_payment, statement

BALANCE = Coalesce(
    Sum(F("entries__debit") - F("entries__credit")),
    Value(0),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = "partners/partner_list.html"
    context_object_name = "partners"
    paginate_by = 50

    def get_queryset(self):
        queryset = Partner.objects.annotate(balance=BALANCE)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(name__icontains=search) | Q(tax_no__icontains=search)
            )
        kind = self.request.GET.get("kind")
        if kind in Partner.Kind.values:
            queryset = queryset.filter(kind__in=[kind, Partner.Kind.BOTH])
        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("q", "")
        context["selected_kind"] = self.request.GET.get("kind", "")
        context["kinds"] = Partner.Kind.choices
        return context


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "partners/partner_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Cari kaydedildi.")
        return super().form_valid(form)


class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = "partners/partner_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Cari guncellendi.")
        return super().form_valid(form)


class PartnerDetailView(LoginRequiredMixin, DetailView):
    model = Partner
    template_name = "partners/partner_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rows"] = statement(self.object)
        context["balance"] = self.object.balance()
        context["payment_form"] = kwargs.get("payment_form") or PaymentForm(
            initial={"date": timezone.localdate()}
        )
        context["entry_form"] = kwargs.get("entry_form") or LedgerEntryForm(
            initial={"date": timezone.localdate()}
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action", "payment")
        if action == "entry":
            form = LedgerEntryForm(request.POST)
            if form.is_valid():
                entry = form.save(commit=False)
                entry.partner = self.object
                entry.source = entry.Source.MANUAL
                entry.created_by = request.user
                entry.save()
                messages.success(request, "Cari hareket eklendi.")
                return redirect("partners:partner-detail", pk=self.object.pk)
            messages.error(request, "Hareket kaydedilemedi.")
            return self.render_to_response(self.get_context_data(entry_form=form))

        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                record_payment(
                    partner=self.object,
                    amount=form.cleaned_data["amount"],
                    date=form.cleaned_data["date"],
                    description=form.cleaned_data.get("description", ""),
                    user=request.user,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Tahsilat/odeme kaydedildi.")
                return redirect("partners:partner-detail", pk=self.object.pk)
        else:
            messages.error(request, "Odeme kaydedilemedi.")
        return self.render_to_response(self.get_context_data(payment_form=form))


class PartnerLedgerPdfPlaceholderView(LoginRequiredMixin, DetailView):
    """Ekstre yazdirma icin ayni sablonu kullanir (print CSS)."""

    model = Partner
    template_name = "partners/partner_detail.html"

    def get(self, request, *args, **kwargs):
        partner = get_object_or_404(Partner, pk=kwargs["pk"])
        return redirect("partners:partner-detail", pk=partner.pk)
