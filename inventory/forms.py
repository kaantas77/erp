from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Category, CountLine, CountSession, Product, StockMove, Warehouse


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "unit",
            "purchase_price",
            "sale_price",
            "vat_rate",
            "reorder_level",
            "is_active",
        ]
        widgets = {
            "sku": forms.TextInput(attrs={"placeholder": "ORN-001"}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["code", "name", "is_active"]


class CountStartForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        label="Depo", queryset=Warehouse.objects.filter(is_active=True)
    )
    note = forms.CharField(label="Not", required=False, max_length=200)


class StockMoveForm(forms.ModelForm):
    class Meta:
        model = StockMove
        fields = ["product", "warehouse", "quantity", "kind", "unit_cost", "reference", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True)


CountLineFormSet = inlineformset_factory(
    CountSession,
    CountLine,
    fields=["counted_qty"],
    extra=0,
    can_delete=False,
    widgets={"counted_qty": forms.NumberInput(attrs={"step": "0.001", "class": "form-control"})},
)
