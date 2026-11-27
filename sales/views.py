from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import OrderForm, OrderLineFormSet
from .models import Order
from .services import OrderError, cancel_order, confirm_order, mark_shipped


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "sales/order_list.html"
    context_object_name = "orders"
    paginate_by = 50

    def get_queryset(self):
        queryset = Order.objects.select_related("partner", "warehouse")
        status = self.request.GET.get("status")
        if status in Order.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        return context


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "sales/order_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lines"] = self.object.lines.select_related("product")
        return context


class OrderCreateView(LoginRequiredMixin, View):
    template_name = "sales/order_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"form": OrderForm(), "formset": OrderLineFormSet()},
        )

    @transaction.atomic
    def post(self, request):
        form = OrderForm(request.POST)
        formset = OrderLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            formset.instance = order
            formset.save()
            messages.success(request, f"{order.number} siparisi olusturuldu.")
            return redirect("sales:order-detail", pk=order.pk)
        messages.error(request, "Siparis kaydedilemedi, alanlari kontrol edin.")
        return render(request, self.template_name, {"form": form, "formset": formset})


class OrderUpdateView(LoginRequiredMixin, View):
    template_name = "sales/order_form.html"

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if not order.is_editable:
            messages.error(request, "Sadece taslak siparisler duzenlenebilir.")
            return redirect("sales:order-detail", pk=order.pk)
        return render(
            request,
            self.template_name,
            {
                "form": OrderForm(instance=order),
                "formset": OrderLineFormSet(instance=order),
                "order": order,
            },
        )

    @transaction.atomic
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if not order.is_editable:
            messages.error(request, "Sadece taslak siparisler duzenlenebilir.")
            return redirect("sales:order-detail", pk=order.pk)
        form = OrderForm(request.POST, instance=order)
        formset = OrderLineFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Siparis guncellendi.")
            return redirect("sales:order-detail", pk=order.pk)
        messages.error(request, "Siparis kaydedilemedi.")
        return render(
            request, self.template_name, {"form": form, "formset": formset, "order": order}
        )


class OrderActionView(LoginRequiredMixin, View):
    """onayla / sevk / iptal islemleri."""

    def post(self, request, pk, action):
        order = get_object_or_404(Order, pk=pk)
        handlers = {
            "confirm": lambda: confirm_order(order, user=request.user),
            "ship": lambda: mark_shipped(order, user=request.user),
            "cancel": lambda: cancel_order(order, user=request.user),
        }
        messages_map = {
            "confirm": "Siparis onaylandi, stok rezerve edildi.",
            "ship": "Siparis sevk edildi, stok dustu.",
            "cancel": "Siparis iptal edildi.",
        }
        if action not in handlers:
            messages.error(request, "Gecersiz islem.")
            return redirect("sales:order-detail", pk=order.pk)
        try:
            handlers[action]()
        except OrderError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, messages_map[action])
        return redirect("sales:order-detail", pk=order.pk)
