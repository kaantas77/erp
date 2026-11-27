from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from .forms import (
    CategoryForm,
    CountLineFormSet,
    CountStartForm,
    ProductForm,
    StockMoveForm,
    WarehouseForm,
)
from .models import Category, CountSession, Product, StockMove, Warehouse
from .services import CountError, close_count, start_count

TOTAL_QTY = Coalesce(
    Sum("moves__quantity"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=3)
)


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "inventory/product_list.html"
    context_object_name = "products"
    paginate_by = 50

    def get_queryset(self):
        queryset = Product.objects.select_related("category").annotate(total_qty=TOTAL_QTY)
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(sku__icontains=search) | Q(name__icontains=search))
        category = self.request.GET.get("category")
        if category and category.isdigit():
            queryset = queryset.filter(category_id=int(category))
        return queryset.order_by("sku")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["search"] = self.request.GET.get("q", "")
        context["selected_category"] = self.request.GET.get("category", "")
        return context


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")

    def form_valid(self, form):
        messages.success(self.request, "Urun eklendi.")
        return super().form_valid(form)


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")

    def form_valid(self, form):
        messages.success(self.request, "Urun guncellendi.")
        return super().form_valid(form)


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:product-list")


class WarehouseListView(LoginRequiredMixin, ListView):
    model = Warehouse
    template_name = "inventory/warehouse_list.html"
    context_object_name = "warehouses"


class WarehouseCreateView(LoginRequiredMixin, CreateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = "inventory/warehouse_form.html"
    success_url = reverse_lazy("inventory:warehouse-list")


class StockOverviewView(LoginRequiredMixin, ListView):
    template_name = "inventory/stock_overview.html"
    context_object_name = "products"
    paginate_by = 100

    def get_queryset(self):
        queryset = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .annotate(total_qty=TOTAL_QTY)
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(sku__icontains=search) | Q(name__icontains=search))
        if self.request.GET.get("low") == "1":
            queryset = queryset.filter(total_qty__lte=F("reorder_level"))
        return queryset.order_by("sku")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warehouses"] = Warehouse.objects.filter(is_active=True)
        context["search"] = self.request.GET.get("q", "")
        context["low_only"] = self.request.GET.get("low") == "1"
        return context


class StockMoveListView(LoginRequiredMixin, ListView):
    model = StockMove
    template_name = "inventory/move_list.html"
    context_object_name = "moves"
    paginate_by = 100

    def get_queryset(self):
        queryset = StockMove.objects.select_related("product", "warehouse", "created_by")
        warehouse = self.request.GET.get("warehouse")
        if warehouse and warehouse.isdigit():
            queryset = queryset.filter(warehouse_id=int(warehouse))
        kind = self.request.GET.get("kind")
        if kind in StockMove.Kind.values:
            queryset = queryset.filter(kind=kind)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warehouses"] = Warehouse.objects.all()
        context["kinds"] = StockMove.Kind.choices
        context["selected_warehouse"] = self.request.GET.get("warehouse", "")
        context["selected_kind"] = self.request.GET.get("kind", "")
        return context


class StockMoveCreateView(LoginRequiredMixin, CreateView):
    model = StockMove
    form_class = StockMoveForm
    template_name = "inventory/move_form.html"
    success_url = reverse_lazy("inventory:move-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Stok hareketi kaydedildi.")
        return super().form_valid(form)


class CountListView(LoginRequiredMixin, ListView):
    model = CountSession
    template_name = "inventory/count_list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return CountSession.objects.select_related("warehouse", "created_by")


class CountStartView(LoginRequiredMixin, FormView):
    template_name = "inventory/count_start.html"
    form_class = CountStartForm

    def form_valid(self, form):
        session = start_count(
            warehouse=form.cleaned_data["warehouse"],
            user=self.request.user,
            note=form.cleaned_data.get("note", ""),
        )
        messages.success(self.request, f"{session.number} sayimi acildi.")
        return redirect("inventory:count-detail", pk=session.pk)


class CountDetailView(LoginRequiredMixin, DetailView):
    model = CountSession
    template_name = "inventory/count_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lines"] = self.object.lines.select_related("product")
        context["formset"] = kwargs.get("formset") or CountLineFormSet(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_open:
            messages.error(request, "Kapatilmis sayim duzenlenemez.")
            return redirect("inventory:count-detail", pk=self.object.pk)
        formset = CountLineFormSet(request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Sayim miktarlari kaydedildi.")
            return redirect("inventory:count-detail", pk=self.object.pk)
        messages.error(request, "Sayim kaydedilemedi, alanlari kontrol edin.")
        return render(
            request,
            self.template_name,
            self.get_context_data(object=self.object, formset=formset),
        )


class CountCloseView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        session = get_object_or_404(CountSession, pk=pk)
        try:
            moves = close_count(session, user=request.user)
        except CountError as exc:
            messages.error(request, str(exc))
        else:
            if moves:
                messages.success(
                    request, f"Sayim kapatildi, {len(moves)} duzeltme hareketi olustu."
                )
            else:
                messages.info(request, "Sayim kapatildi, fark bulunmadi.")
        return redirect("inventory:count-detail", pk=session.pk)
